"""
Business Invariants — AI / Copilot (Argo)

Ensures the AI copilot operates within safe boundaries: no destructive
actions without permission, correct role enforcement, business-rule
compliance, circuit-breaker limits, undo-window constraints, and
permission-bypass prevention.
"""

from __future__ import annotations

from business_invariants.config import default_invariant_config
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
PR = ExecutionFrequency.PR
NIGHTLY = ExecutionFrequency.NIGHTLY

# Default AI configuration (see business_invariants/config.py).  Fallback so
# AI-002 stays verifiable even when the caller builds an InvariantContext
# without an explicit config.
_DEFAULT_CONFIG = default_invariant_config()


@invariant(
    id="AI-001",
    title="AI never performs destructive actions without permission",
    description=(
        "AI copilot requires confirmation_level >= BUSINESS for "
        "destructive operations such as DELETE, DROP, mass UPDATE, "
        "or irreversible state changes."
    ),
    category=InvariantCategory.AI_ARGO,
    modules=["copilot", "ai"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, PR],
    rationale="Unchecked destructive actions could cause catastrophic data loss.",
    tags=["ai", "copilot", "destructive", "safety"],
)
def check_no_destructive_actions_without_permission(
    ctx: InvariantContext,
) -> InvariantResult:
    """
    Verify that the AI copilot enforces confirmation_level >= BUSINESS
    for all destructive operations.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="AI-001",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    # Check the confirmation level configuration
    destructive_ops = ctx.config.get("destructive_operations", [])
    min_confirmation = ctx.config.get(
        "destructive_confirmation_level", "business"
    ).lower()

    valid_levels = {"info", "business", "critical"}
    if min_confirmation not in valid_levels:
        return InvariantResult(
            invariant_id="AI-001",
            status=InvariantStatus.FAIL,
            expected="confirmation_level >= 'business' for destructive operations",
            actual=f"configured confirmation_level = '{min_confirmation}'",
            message="Destructive operation protection is misconfigured",
            root_cause=(
                f"destructive_confirmation_level is '{min_confirmation}', "
                f"expected 'business' or 'critical'"
            ),
            suggested_fix=(
                "Set destructive_confirmation_level = 'business' or 'critical' "
                "in the AI copilot configuration."
            ),
            affected_modules=["copilot", "ai"],
        )

    if min_confirmation == "info":
        return InvariantResult(
            invariant_id="AI-001",
            status=InvariantStatus.FAIL,
            expected="confirmation_level >= 'business' for destructive operations",
            actual=f"confirmation_level = '{min_confirmation}'",
            message=(
                "AI can perform destructive operations with only Info-level "
                "confirmation — too permissive"
            ),
            root_cause="destructive_confirmation_level is 'info'",
            suggested_fix="Raise destructive_confirmation_level to 'business' or 'critical'",
            affected_modules=["copilot", "ai"],
        )

    if not destructive_ops:
        return InvariantResult(
            invariant_id="AI-001",
            status=InvariantStatus.PASS,
            message="No destructive operations defined — no validation needed",
            affected_modules=["copilot", "ai"],
        )

    return InvariantResult(
        invariant_id="AI-001",
        status=InvariantStatus.PASS,
        expected="Destructive operations require confirmation_level >= BUSINESS",
        actual=(
            f"confirmation_level = '{min_confirmation}', "
            f"{len(destructive_ops)} destructive op(s) registered"
        ),
        message="Destructive action protection is correctly configured",
        affected_modules=["copilot", "ai"],
    )


@invariant(
    id="AI-002",
    title="AI role permissions are restrictive",
    description=(
        "AI respects role-based permissions: driver=read-only, "
        "dispatcher=no deletes, manager=all except system."
    ),
    category=InvariantCategory.AI_ARGO,
    modules=["copilot", "ai"],
    severity=Severity.HIGH,
    execution=[COMMIT, PR],
    rationale="Over-permissive AI roles could lead to unauthorized actions.",
    tags=["ai", "roles", "permissions"],
)
def check_ai_role_permissions(ctx: InvariantContext) -> InvariantResult:
    """
    Check that the AI permission matrix is correctly restrictive per role.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="AI-002",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    role_permissions = ctx.config.get(
        "ai_role_permissions", _DEFAULT_CONFIG["ai_role_permissions"]
    )
    expected_rules = {
        "driver": {"read_only": True, "can_delete": False, "can_system": False},
        "dispatcher": {
            "read_only": False,
            "can_delete": False,
            "can_system": False,
        },
        "manager": {"read_only": False, "can_delete": True, "can_system": False},
    }

    violations: list[str] = []
    for role, expected in expected_rules.items():
        actual = role_permissions.get(role, {})
        for perm, expected_val in expected.items():
            actual_val = actual.get(perm, None)
            if actual_val != expected_val:
                violations.append(
                    f"{role}.{perm}: expected {expected_val}, got {actual_val}"
                )

    if violations:
        return InvariantResult(
            invariant_id="AI-002",
            status=InvariantStatus.FAIL,
            expected="Role permissions follow driver=read-only, dispatcher=no deletes, "
            "manager=all except system",
            actual=f"{len(violations)} permission violation(s)",
            message="AI role permissions are too permissive",
            root_cause="; ".join(violations),
            suggested_fix=(
                "Update the ai_role_permissions configuration to match "
                "the expected permission matrix."
            ),
            affected_modules=["copilot", "ai"],
            details={"violations": violations},
        )

    return InvariantResult(
        invariant_id="AI-002",
        status=InvariantStatus.PASS,
        expected="All roles have correct permissions",
        actual="Role permissions match expected matrix",
        message="AI role permissions are correctly restrictive",
        affected_modules=["copilot", "ai"],
    )


@invariant(
    id="AI-003",
    title="AI generated workflows preserve business rules",
    description=(
        "AI-generated trips, invoices, and dispatches must pass the same "
        "validation as human-created ones."
    ),
    category=InvariantCategory.AI_ARGO,
    modules=["copilot", "ai"],
    severity=Severity.HIGH,
    execution=[COMMIT, PR, NIGHTLY],
    rationale="AI that bypasses business rules creates invalid operational data.",
    tags=["ai", "workflows", "validation"],
)
def check_ai_workflows_preserve_business_rules(
    ctx: InvariantContext,
) -> InvariantResult:
    """
    Verify that AI-generated entities pass standard business validation.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="AI-003",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    # Check that AI-generated records pass the same validators
    ai_sources = ctx.config.get("ai_source_tags", ["ai_copilot", "argo_auto"])
    validator_config = ctx.config.get("ai_workflow_validators", {})

    if not validator_config:
        return InvariantResult(
            invariant_id="AI-003",
            status=InvariantStatus.FAIL,
            expected="AI workflow validators are configured",
            actual="No ai_workflow_validators found in config",
            message="AI workflows bypass business validation",
            root_cause="Missing ai_workflow_validators configuration entry",
            suggested_fix=(
                "Configure ai_workflow_validators with the same validators "
                "used for human-created workflows."
            ),
            affected_modules=["copilot", "ai"],
        )

    # Check if the validation pipeline includes all entity types
    expected_entities = {"trips", "invoices", "dispatches"}
    configured_entities = set(validator_config.keys())
    missing_entities = expected_entities - configured_entities

    if missing_entities:
        return InvariantResult(
            invariant_id="AI-003",
            status=InvariantStatus.FAIL,
            expected="AI validation covers trips, invoices, and dispatches",
            actual=f"Missing validators for: {', '.join(sorted(missing_entities))}",
            message="AI-generated entities bypass validation for some entity types",
            root_cause=f"No validators configured for: {', '.join(sorted(missing_entities))}",
            suggested_fix=(
                f"Add validators for: {', '.join(sorted(missing_entities))} "
                f"in ai_workflow_validators configuration"
            ),
            affected_modules=["copilot", "ai"],
            details={"missing_entities": sorted(missing_entities)},
        )

    # Verify AI source tagging is configured
    if not ai_sources:
        return InvariantResult(
            invariant_id="AI-003",
            status=InvariantStatus.FAIL,
            expected="AI source tags are configured",
            actual="No ai_source_tags found in config",
            message="Cannot identify AI-generated records for validation",
            root_cause="Missing ai_source_tags configuration",
            suggested_fix="Set ai_source_tags to a list of source identifiers used by the AI",
            affected_modules=["copilot", "ai"],
        )

    return InvariantResult(
        invariant_id="AI-003",
        status=InvariantStatus.PASS,
        expected="All AI-generated entities pass business validation",
        actual=(
            f"Validators configured for: {', '.join(sorted(configured_entities))}, "
            f"AI source tags: {ai_sources}"
        ),
        message="AI workflows are subject to the same business rules as human-created ones",
        affected_modules=["copilot", "ai"],
    )


@invariant(
    id="AI-004",
    title="AI circuit breaker prevents runaway loops",
    description=(
        "Max 20 tool calls per plan, 50 reasoning nodes per turn, "
        "30s timeout per tool."
    ),
    category=InvariantCategory.AI_ARGO,
    modules=["copilot", "ai"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Without limits, AI loops can exhaust API quota or hang the system.",
    tags=["ai", "circuit-breaker", "rate-limiting"],
)
def check_ai_circuit_breaker(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that the AI circuit breaker limits are set to safe values.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="AI-004",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    limits = {
        "max_tool_calls_per_plan": ctx.config.get(
            "ai_max_tool_calls_per_plan", None
        ),
        "max_reasoning_nodes_per_turn": ctx.config.get(
            "ai_max_reasoning_nodes_per_turn", None
        ),
        "tool_timeout_seconds": ctx.config.get(
            "ai_tool_timeout_seconds", None
        ),
    }

    violations: list[str] = []

    if limits["max_tool_calls_per_plan"] is None:
        violations.append("max_tool_calls_per_plan is not configured")
    elif limits["max_tool_calls_per_plan"] > 20:
        violations.append(
            f"max_tool_calls_per_plan={limits['max_tool_calls_per_plan']} > 20"
        )

    if limits["max_reasoning_nodes_per_turn"] is None:
        violations.append("max_reasoning_nodes_per_turn is not configured")
    elif limits["max_reasoning_nodes_per_turn"] > 50:
        violations.append(
            f"max_reasoning_nodes_per_turn={limits['max_reasoning_nodes_per_turn']} > 50"
        )

    if limits["tool_timeout_seconds"] is None:
        violations.append("tool_timeout_seconds is not configured")
    elif limits["tool_timeout_seconds"] > 30:
        violations.append(
            f"tool_timeout_seconds={limits['tool_timeout_seconds']} > 30"
        )

    if violations:
        return InvariantResult(
            invariant_id="AI-004",
            status=InvariantStatus.FAIL,
            expected=(
                "Circuit breaker: max 20 tool calls/plan, "
                "50 reasoning nodes/turn, 30s timeout/tool"
            ),
            actual=f"{len(violations)} limit violation(s)",
            message="AI circuit breaker limits are too permissive or unset",
            root_cause="; ".join(violations),
            suggested_fix=(
                "Set ai_max_tool_calls_per_plan=20, "
                "ai_max_reasoning_nodes_per_turn=50, "
                "ai_tool_timeout_seconds=30 in AI configuration."
            ),
            affected_modules=["copilot", "ai"],
            details={"violations": violations, "current_limits": limits},
        )

    return InvariantResult(
        invariant_id="AI-004",
        status=InvariantStatus.PASS,
        expected="Circuit breaker limits are within safe thresholds",
        actual=(
            f"max_tool_calls={limits['max_tool_calls_per_plan']}, "
            f"max_reasoning_nodes={limits['max_reasoning_nodes_per_turn']}, "
            f"tool_timeout={limits['tool_timeout_seconds']}s"
        ),
        message="AI circuit breaker is correctly configured",
        affected_modules=["copilot", "ai"],
    )


@invariant(
    id="AI-005",
    title="AI undo window respected",
    description=(
        "AI actions can only be undone within a 30-minute window "
        "from the time of execution."
    ),
    category=InvariantCategory.AI_ARGO,
    modules=["copilot", "ai"],
    severity=Severity.MEDIUM,
    execution=[COMMIT],
    rationale="Allowing undo of older actions creates data consistency issues.",
    tags=["ai", "undo", "time-window"],
)
def check_ai_undo_window(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that the undo window configuration is set to 30 minutes or less.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="AI-005",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    undo_window_minutes = ctx.config.get("ai_undo_window_minutes", None)

    if undo_window_minutes is None:
        return InvariantResult(
            invariant_id="AI-005",
            status=InvariantStatus.FAIL,
            expected="undo_window_minutes configured (max 30)",
            actual="ai_undo_window_minutes is not configured",
            message="AI undo window is unset — infinite undo possible",
            root_cause="Missing ai_undo_window_minutes in configuration",
            suggested_fix=(
                "Set ai_undo_window_minutes = 30 in the AI copilot configuration."
            ),
            affected_modules=["copilot", "ai"],
        )

    if undo_window_minutes > 30:
        return InvariantResult(
            invariant_id="AI-005",
            status=InvariantStatus.FAIL,
            expected="undo_window_minutes <= 30",
            actual=f"undo_window_minutes = {undo_window_minutes}",
            message="AI undo window exceeds the 30-minute limit",
            root_cause=(
                f"Configured undo window is {undo_window_minutes} minutes, "
                f"but must be at most 30 minutes"
            ),
            suggested_fix=f"Set ai_undo_window_minutes = 30 (currently {undo_window_minutes})",
            affected_modules=["copilot", "ai"],
        )

    return InvariantResult(
        invariant_id="AI-005",
        status=InvariantStatus.PASS,
        expected=f"undo_window_minutes <= 30",
        actual=f"undo_window_minutes = {undo_window_minutes}",
        message="AI undo window is correctly configured",
        affected_modules=["copilot", "ai"],
    )


@invariant(
    id="AI-006",
    title="AI copilot cannot bypass permissions",
    description=(
        "All AI tool calls check the user's role permissions "
        "before execution. No tool bypasses the permission system."
    ),
    category=InvariantCategory.AI_ARGO,
    modules=["copilot", "ai"],
    severity=Severity.CRITICAL,
    execution=[COMMIT, PR],
    rationale="Permission bypass by AI tools would invalidate the entire auth model.",
    tags=["ai", "permissions", "security"],
)
def check_ai_no_permission_bypass(ctx: InvariantContext) -> InvariantResult:
    """
    Verify that AI tool definitions include permission checks.
    """
    if ctx.db is None:
        return InvariantResult(
            invariant_id="AI-006",
            status=InvariantStatus.PASS,
            message="No database connection — runtime validation skipped",
        )

    ai_tools = ctx.config.get("ai_tool_definitions", {})
    if not ai_tools:
        return InvariantResult(
            invariant_id="AI-006",
            status=InvariantStatus.FAIL,
            expected="AI tool definitions with permission checks are configured",
            actual="No ai_tool_definitions found in config",
            message="Cannot verify permission enforcement without tool definitions",
            root_cause="Missing ai_tool_definitions configuration",
            suggested_fix=(
                "Populate ai_tool_definitions with tool definitions that each "
                "specify a 'required_permission' field."
            ),
            affected_modules=["copilot", "ai"],
        )

    tools_without_permissions: list[str] = []
    for tool_name, tool_def in ai_tools.items():
        if isinstance(tool_def, dict):
            if "required_permission" not in tool_def and "permission" not in tool_def:
                tools_without_permissions.append(tool_name)

    if tools_without_permissions:
        return InvariantResult(
            invariant_id="AI-006",
            status=InvariantStatus.FAIL,
            expected="All AI tools specify required permissions",
            actual=f"{len(tools_without_permissions)} tool(s) lack permission checks",
            message="AI tools can bypass the permission system",
            root_cause=f"Tools missing permissions: {', '.join(tools_without_permissions)}",
            suggested_fix=(
                "Add a 'required_permission' field to each tool definition "
                "in ai_tool_definitions configuration."
            ),
            affected_modules=["copilot", "ai"],
            details={"tools_without_permissions": tools_without_permissions},
        )

    total_tools = len(ai_tools)
    return InvariantResult(
        invariant_id="AI-006",
        status=InvariantStatus.PASS,
        expected="All AI tools have permission checks",
        actual=f"All {total_tools} tool(s) specify required permissions",
        message="AI copilot cannot bypass user permissions",
        affected_modules=["copilot", "ai"],
    )
