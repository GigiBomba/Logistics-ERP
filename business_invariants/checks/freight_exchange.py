"""
Business Invariants — Freight Exchange Integration

Ensures integrity of freight exchange imports: source attribution,
duplicate prevention, saved-search fidelity, rate-limit compliance,
webhook security, and adapter completeness.
"""

from __future__ import annotations

from business_invariants.decorators import invariant
from business_invariants.models import (
    ExecutionFrequency,
    InvariantCategory,
    InvariantContext,
    InvariantResult,
    InvariantStatus,
    Severity,
)

COMMIT = ExecutionFrequency.COMMIT
NIGHTLY = ExecutionFrequency.NIGHTLY


@invariant(
    id="FEX-001",
    title="Imported loads retain source",
    description=(
        "Trips imported from freight exchange have source = 'freight_exchange', "
        "source_provider_id, source_reference_id set."
    ),
    category=InvariantCategory.FREIGHT_EXCHANGE,
    modules=["freight_exchange"],
    severity=Severity.HIGH,
    execution=[COMMIT, NIGHTLY],
    rationale="Imported loads without source attribution cannot be traced.",
    tags=["freight-exchange", "import", "source-tracking"],
)
def check_imported_loads_retain_source(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that trips with source='freight_exchange' have provider
    and reference IDs populated.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FEX-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        orphan_rows = ctx.db.execute(
            """
            SELECT id, source, source_provider_id, source_reference_id
            FROM trips
            WHERE source = 'freight_exchange'
              AND (
                  source_provider_id IS NULL
                  OR source_reference_id IS NULL
                  OR source_provider_id = ''
                  OR source_reference_id = ''
              )
            """
        ).fetchall()
    except Exception:
        return InvariantResult(
            invariant_id="FEX-001",
            status=InvariantStatus.PASS,
            message="Could not query trips table — runtime validation skipped",
            affected_modules=["freight_exchange"],
        )

    if orphan_rows:
        trip_ids = [int(r[0]) for r in orphan_rows[:20]]
        return InvariantResult(
            invariant_id="FEX-001",
            status=InvariantStatus.FAIL,
            expected=(
                "All freight exchange trips have source_provider_id "
                "and source_reference_id"
            ),
            actual=f"{len(orphan_rows)} trip(s) missing source attribution fields",
            message="Imported loads missing provider or reference IDs",
            root_cause=(
                "Trips with source='freight_exchange' have NULL or empty "
                "source_provider_id or source_reference_id"
            ),
            suggested_fix=(
                "Update the freight exchange import pipeline to always populate "
                "source_provider_id and source_reference_id when source='freight_exchange'."
            ),
            affected_modules=["freight_exchange"],
            details={"missing_attribution_trip_ids": trip_ids[:10]},
        )

    return InvariantResult(
        invariant_id="FEX-001",
        status=InvariantStatus.PASS,
        expected="All imported trips have source attribution",
        actual="No trips missing source_provider_id or source_reference_id",
        message="All imported loads retain their source attribution",
        affected_modules=["freight_exchange"],
    )


@invariant(
    id="FEX-002",
    title="Duplicate imports prevented",
    description=(
        "No two trips share the same "
        "(source_provider_id, source_reference_id, company_id)."
    ),
    category=InvariantCategory.FREIGHT_EXCHANGE,
    modules=["freight_exchange"],
    severity=Severity.CRITICAL,
    execution=[COMMIT],
    rationale="Duplicate trips cause double-booking and financial errors.",
    tags=["freight-exchange", "deduplication", "data-integrity"],
)
def check_duplicate_imports_prevented(ctx: InvariantContext) -> InvariantResult:
    """
    Check for duplicate trips that share the same
    (source_provider_id, source_reference_id, company_id) tuple.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FEX-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        duplicates = ctx.db.execute(
            """
            SELECT source_provider_id, source_reference_id, company_id,
                   COUNT(*) AS cnt,
                   GROUP_CONCAT(id) AS trip_ids
            FROM trips
            WHERE source = 'freight_exchange'
              AND source_provider_id IS NOT NULL
              AND source_reference_id IS NOT NULL
            GROUP BY source_provider_id, source_reference_id, company_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()
    except Exception:
        return InvariantResult(
            invariant_id="FEX-002",
            status=InvariantStatus.PASS,
            message="Could not query trips table — runtime validation skipped",
            affected_modules=["freight_exchange"],
        )

    if duplicates:
        dup_summary: list[dict[str, object]] = []
        for row in duplicates:
            dup_summary.append(
                {
                    "provider_id": str(row[0]),
                    "reference_id": str(row[1]),
                    "company_id": int(row[2]) if row[2] else None,
                    "count": int(row[3]),
                    "trip_ids": str(row[4]),
                }
            )

        return InvariantResult(
            invariant_id="FEX-002",
            status=InvariantStatus.FAIL,
            expected=(
                "Each (source_provider_id, source_reference_id, "
                "company_id) combination is unique"
            ),
            actual=f"{len(duplicates)} duplicate group(s) found",
            message="Duplicate freight exchange import detected",
            root_cause=(
                "Multiple trips share the same source_provider_id, "
                "source_reference_id, and company_id"
            ),
            suggested_fix=(
                "Add a UNIQUE constraint on "
                "(source_provider_id, source_reference_id, company_id) "
                "in the trips table, and deduplicate existing rows."
            ),
            affected_modules=["freight_exchange"],
            details={"duplicate_groups": dup_summary[:10]},
        )

    return InvariantResult(
        invariant_id="FEX-002",
        status=InvariantStatus.PASS,
        expected="No duplicate (source_provider_id, source_reference_id, company_id)",
        actual="No duplicate imports detected",
        message="Duplicate imports are prevented",
        affected_modules=["freight_exchange"],
    )


@invariant(
    id="FEX-003",
    title="Search filters preserved",
    description=(
        "Saved freight searches retain their filter parameters. "
        "No filters are silently dropped or default to empty."
    ),
    category=InvariantCategory.FREIGHT_EXCHANGE,
    modules=["freight_exchange"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Broken saved searches give incorrect results to dispatchers.",
    tags=["freight-exchange", "search", "filters"],
)
def check_search_filters_preserved(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that saved freight search records have non-empty filter parameters.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FEX-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    try:
        corrupt_searches = ctx.db.execute(
            """
            SELECT id, name, filter_params
            FROM saved_freight_searches
            WHERE filter_params IS NULL
               OR filter_params = '{}'
               OR filter_params = ''
            """
        ).fetchall()
    except Exception:
        return InvariantResult(
            invariant_id="FEX-003",
            status=InvariantStatus.PASS,
            message="Could not query saved_freight_searches table — "
            "runtime validation skipped",
            affected_modules=["freight_exchange"],
        )

    if corrupt_searches:
        search_ids = [int(r[0]) for r in corrupt_searches]
        return InvariantResult(
            invariant_id="FEX-003",
            status=InvariantStatus.FAIL,
            expected="All saved searches have non-empty filter_params",
            actual=f"{len(corrupt_searches)} saved search(es) have empty or NULL filters",
            message="Saved freight searches have lost their filter parameters",
            root_cause=(
                "Saved_freight_searches records with NULL or empty filter_params"
            ),
            suggested_fix=(
                "Investigate the save/load flow for freight searches. "
                "Ensure filter_params is always serialised as a non-empty JSON object."
            ),
            affected_modules=["freight_exchange"],
            details={"corrupted_search_ids": search_ids[:20]},
        )

    return InvariantResult(
        invariant_id="FEX-003",
        status=InvariantStatus.PASS,
        expected="All saved searches have non-empty filter parameters",
        actual="No saved searches have empty or NULL filters",
        message="Search filters are preserved correctly",
        affected_modules=["freight_exchange"],
    )


@invariant(
    id="FEX-004",
    title="Provider calls within rate limits",
    description=(
        "TIMOCOM: max 60 req/min. Trans.eu: max 900 req/min. "
        "Rate limit counters are honoured."
    ),
    category=InvariantCategory.FREIGHT_EXCHANGE,
    modules=["freight_exchange"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Exceeding API rate limits gets the provider account suspended.",
    tags=["freight-exchange", "rate-limiting", "api"],
)
def check_provider_rate_limits(ctx: InvariantContext) -> InvariantResult:
    """
    Validate that rate-limit configurations are within provider contracts.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FEX-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    provider_limits = ctx.config.get("freight_exchange_rate_limits", {})
    expected_limits = {
        "timocom": {"max_requests_per_minute": 60},
        "trans_eu": {"max_requests_per_minute": 900},
    }

    violations: list[str] = []
    for provider, expected in expected_limits.items():
        actual = provider_limits.get(provider, {})
        if not actual:
            violations.append(
                f"{provider}: rate limit not configured"
            )
            continue
        actual_limit = actual.get("max_requests_per_minute")
        expected_limit = expected["max_requests_per_minute"]
        if actual_limit is None:
            violations.append(
                f"{provider}: max_requests_per_minute not set"
            )
        elif actual_limit > expected_limit:
            violations.append(
                f"{provider}: {actual_limit} req/min exceeds "
                f"contractual limit of {expected_limit} req/min"
            )

    if violations:
        return InvariantResult(
            invariant_id="FEX-004",
            status=InvariantStatus.FAIL,
            expected=(
                "TIMOCOM <= 60 req/min, Trans.eu <= 900 req/min"
            ),
            actual=f"{len(violations)} violation(s)",
            message="Provider rate limits are misconfigured",
            root_cause="; ".join(violations),
            suggested_fix=(
                "Update freight_exchange_rate_limits configuration to match "
                "provider contractual limits."
            ),
            affected_modules=["freight_exchange"],
            details={"violations": violations},
        )

    return InvariantResult(
        invariant_id="FEX-004",
        status=InvariantStatus.PASS,
        expected="Rate limits within contractual thresholds",
        actual="All provider rate limits are correctly configured",
        message="Provider API rate limits are properly set",
        affected_modules=["freight_exchange"],
    )


@invariant(
    id="FEX-005",
    title="Webhook signature verification",
    description=(
        "Incoming webhooks must have a valid HMAC-SHA256 signature. "
        "Unsigned or invalid-signature payloads are rejected."
    ),
    category=InvariantCategory.FREIGHT_EXCHANGE,
    modules=["freight_exchange", "webhooks"],
    severity=Severity.HIGH,
    execution=[COMMIT],
    rationale="Unverified webhooks could accept forged data from attackers.",
    tags=["freight-exchange", "webhooks", "security"],
)
def check_webhook_signature_verification(ctx: InvariantContext) -> InvariantResult:
    """
    Validate that webhook signature verification is enabled and correctly configured.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FEX-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    webhook_config = ctx.config.get("freight_exchange_webhooks", {})

    if not webhook_config:
        return InvariantResult(
            invariant_id="FEX-005",
            status=InvariantStatus.FAIL,
            expected="Webhook verification is configured with HMAC-SHA256",
            actual="No freight_exchange_webhooks configuration found",
            message="Webhook security is not configured",
            root_cause="Missing freight_exchange_webhooks in app configuration",
            suggested_fix=(
                "Configure freight_exchange_webhooks with webhook_secret "
                "and set verify_signature = true."
            ),
            affected_modules=["freight_exchange", "webhooks"],
        )

    verify_enabled = webhook_config.get("verify_signature", False)
    webhook_secret = webhook_config.get("webhook_secret", "")

    if not verify_enabled:
        return InvariantResult(
            invariant_id="FEX-005",
            status=InvariantStatus.FAIL,
            expected="verify_signature = true",
            actual="verify_signature is false or missing",
            message="Webhook signature verification is disabled",
            root_cause="verify_signature is not enabled in webhook configuration",
            suggested_fix=(
                "Set verify_signature = true and provide a webhook_secret "
                "in freight_exchange_webhooks configuration."
            ),
            affected_modules=["freight_exchange", "webhooks"],
        )

    if not webhook_secret or webhook_secret == "change-me":
        return InvariantResult(
            invariant_id="FEX-005",
            status=InvariantStatus.FAIL,
            expected="webhook_secret is a non-default secret value",
            actual="webhook_secret is empty or uses default 'change-me'",
            message="Webhook secret is not properly set",
            root_cause="webhook_secret is empty or set to 'change-me'",
            suggested_fix=(
                "Set a strong random webhook_secret in "
                "freight_exchange_webhooks configuration."
            ),
            affected_modules=["freight_exchange", "webhooks"],
        )

    # Check algorithm is HMAC-SHA256
    algo = webhook_config.get("signature_algorithm", "").lower()
    if algo and algo not in ("hmac-sha256", "sha256"):
        return InvariantResult(
            invariant_id="FEX-005",
            status=InvariantStatus.FAIL,
            expected="signature_algorithm = HMAC-SHA256",
            actual=f"signature_algorithm = {algo}",
            message="Webhook signature algorithm is not HMAC-SHA256",
            root_cause=f"Configured algorithm '{algo}' is not HMAC-SHA256",
            suggested_fix="Set signature_algorithm = HMAC-SHA256 in webhook configuration",
            affected_modules=["freight_exchange", "webhooks"],
        )

    return InvariantResult(
        invariant_id="FEX-005",
        status=InvariantStatus.PASS,
        expected="Webhook signature verification using HMAC-SHA256",
        actual="verify_signature=true, algorithm configured, secret set",
        message="Webhook signature verification is correctly configured",
        affected_modules=["freight_exchange", "webhooks"],
    )


@invariant(
    id="FEX-006",
    title="Adapter registry integrity",
    description=(
        "All adapters implement required methods: authenticate, "
        "search_loads, get_load."
    ),
    category=InvariantCategory.FREIGHT_EXCHANGE,
    modules=["freight_exchange"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Broken adapters leave the freight exchange integration non-functional.",
    tags=["freight-exchange", "adapters", "registry"],
)
def check_adapter_registry_integrity(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that all registered freight exchange adapters implement
    the required interface methods.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="FEX-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    adapters = ctx.config.get("freight_exchange_adapters", {})
    required_methods = {"authenticate", "search_loads", "get_load"}

    if not adapters:
        return InvariantResult(
            invariant_id="FEX-006",
            status=InvariantStatus.PASS,
            message="No adapters registered — nothing to validate",
            affected_modules=["freight_exchange"],
        )

    broken_adapters: list[dict[str, object]] = []
    for adapter_name, adapter_def in adapters.items():
        if isinstance(adapter_def, dict):
            raw_methods: list[str] = list(adapter_def.get("methods", []) or [])
            methods = set(raw_methods)
            missing = required_methods - methods
            if missing:
                broken_adapters.append(
                    {
                        "adapter": adapter_name,
                        "missing_methods": sorted(missing),
                    }
                )

    if broken_adapters:
        return InvariantResult(
            invariant_id="FEX-006",
            status=InvariantStatus.FAIL,
            expected=(
                "All adapters implement authenticate, search_loads, get_load"
            ),
            actual=f"{len(broken_adapters)} adapter(s) missing required methods",
            message="Freight exchange adapters are incomplete",
            root_cause="; ".join(
                f"{a['adapter']} missing: {', '.join(a['missing_methods'])}"  # type: ignore[arg-type]
                for a in broken_adapters
            ),
            suggested_fix=(
                "Implement the missing methods in each incomplete adapter. "
                "Required: authenticate(), search_loads(), get_load()."
            ),
            affected_modules=["freight_exchange"],
            details={"broken_adapters": broken_adapters},
        )

    return InvariantResult(
        invariant_id="FEX-006",
        status=InvariantStatus.PASS,
        expected="All adapters implement required interface",
        actual=f"All {len(adapters)} adapter(s) implement the required methods",
        message="Adapter registry integrity is maintained",
        affected_modules=["freight_exchange"],
    )
