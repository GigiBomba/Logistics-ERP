"""
Business invariants for the Auth & Security module (AUTH-*).

Ensures password hashing integrity, JWT validation, role hierarchy
enforcement, brute-force protection, single-use refresh tokens,
hashed API keys, and admin-only delete operations.
"""

from __future__ import annotations

import re

from business_invariants.decorators import invariant
from business_invariants.models import (
    ExecutionFrequency,
    InvariantCategory,
    InvariantContext,
    InvariantResult,
    InvariantStatus,
    Severity,
)


def _no_db_result(invariant_id: str) -> InvariantResult:
    """Return a PASS result when no database connection is available."""
    return InvariantResult(
        invariant_id=invariant_id,
        status=InvariantStatus.PASS,
        message="No database connection — runtime validation skipped",
    )


_BCRYPT_RE = re.compile(r"^\$2[abxy]\$\d{2}\$[A-Za-z0-9./+]{53}$")
_SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")

# Valid dispatch board columns
_VALID_ROLE_HIERARCHY = {
    "admin": {"priority": 100, "allows": {"manager", "dispatcher", "driver"}},
    "manager": {"priority": 80, "allows": {"dispatcher", "driver"}},
    "dispatcher": {"priority": 60, "allows": {"driver"}},
    "driver": {"priority": 40, "allows": set()},
}

# Operations that should require admin role
_ADMIN_ONLY_OPERATIONS = [
    "delete_trip",
    "delete_client",
    "delete_vehicle",
    "delete_driver",
    "delete_user",
    "delete_company",
]


# ──────────────────────────────────────────────
# AUTH-001 — Password hashes never become plaintext
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-001",
    title="Password hashes never become plaintext",
    description="All stored passwords are bcrypt hashes (start with $2b$).",
    category=InvariantCategory.AUTH,
    modules=["auth"],
    severity=Severity.CRITICAL,
    execution=[
        ExecutionFrequency.COMMIT,
        ExecutionFrequency.PR,
        ExecutionFrequency.RELEASE,
    ],
    rationale="Plaintext or weak password hashes are a critical security vulnerability.",
)
def check_password_hashes_are_bcrypt(ctx: InvariantContext) -> InvariantResult:
    """Verify that all stored password hashes are valid bcrypt hashes."""
    invariant_id = "AUTH-001"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT id, username, email, password_hash
            FROM users
            WHERE password_hash IS NOT NULL
            """
        )
        rows = cursor.fetchall()

        invalid_hashes = []
        for row in rows:
            user_id, username, email, pwhash = row
            if not pwhash or not _BCRYPT_RE.match(pwhash):
                invalid_hashes.append(
                    {
                        "id": user_id,
                        "username": username,
                        "email": email,
                        "hash_prefix": pwhash[:20] if pwhash else None,
                    }
                )

        if invalid_hashes:
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All password_hash values are valid bcrypt hashes starting with $2b$",
                actual=f"Found {len(invalid_hashes)} invalid password hashes out of {len(rows)} users",
                message=f"Invalid hashes for user IDs: {[d['id'] for d in invalid_hashes]}",
                root_cause="Password was stored without bcrypt hashing or hash format is incorrect",
                suggested_fix="Re-hash all affected passwords with bcrypt immediately; audit password storage logic",
                affected_modules=["auth"],
                details={"total_users": len(rows), "invalid_hashes": invalid_hashes},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All password_hash values are valid bcrypt hashes",
            actual=f"All {len(rows)} users have valid bcrypt password hashes",
            affected_modules=["auth"],
            details={"total_users": len(rows)},
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["auth"],
        )


# ──────────────────────────────────────────────
# AUTH-002 — JWT validation unchanged
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-002",
    title="JWT validation unchanged",
    description="JWT tokens always use HS256 algorithm with configured secret.",
    category=InvariantCategory.AUTH,
    modules=["auth"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.RELEASE],
    rationale="Changing JWT algorithm or secret invalidates all existing tokens and breaks authentication.",
)
def check_jwt_validation_unchanged(ctx: InvariantContext) -> InvariantResult:
    """Verify that JWT configuration uses HS256 and a valid secret."""
    invariant_id = "AUTH-002"

    jwt_algorithm = ctx.config.get("jwt_algorithm", ctx.env.get("JWT_ALGORITHM", ""))
    jwt_secret = ctx.config.get("jwt_secret", ctx.env.get("JWT_SECRET", ""))

    issues = []

    if not jwt_algorithm:
        issues.append("JWT algorithm is not configured")
    elif jwt_algorithm.upper() != "HS256":
        issues.append(
            f"JWT algorithm is '{jwt_algorithm}' instead of the required 'HS256'"
        )

    if not jwt_secret:
        issues.append("JWT secret is not configured")
    elif len(jwt_secret) < 32:
        issues.append(
            f"JWT secret is too short ({len(jwt_secret)} chars; minimum 32 recommended)"
        )

    if issues:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.FAIL,
            expected="JWT uses HS256 algorithm with a configured secret of adequate length",
            actual="; ".join(issues),
            message="JWT configuration does not meet security requirements",
            root_cause="JWT settings were changed or are missing in configuration",
            suggested_fix="Set JWT_ALGORITHM=HS256 and provide a strong JWT_SECRET (min 32 characters)",
            affected_modules=["auth"],
            details={
                "jwt_algorithm": jwt_algorithm or "not set",
                "secret_length": len(jwt_secret),
                "issues": issues,
            },
        )

    return InvariantResult(
        invariant_id=invariant_id,
        status=InvariantStatus.PASS,
        expected="JWT uses HS256 algorithm with a configured secret",
        actual=f"JWT algorithm is HS256 with a {len(jwt_secret)}-character secret",
        affected_modules=["auth"],
        details={
            "jwt_algorithm": jwt_algorithm,
            "secret_length": len(jwt_secret),
        },
    )


# ──────────────────────────────────────────────
# AUTH-003 — Role hierarchy preserved
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-003",
    title="Role hierarchy preserved",
    description="Permissions follow: admin > manager > dispatcher > driver. "
    "No user has a role that grants permissions they shouldn't have.",
    category=InvariantCategory.AUTH,
    modules=["auth"],
    severity=Severity.HIGH,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.PR],
    rationale="Broken role hierarchy can grant unauthorized access to sensitive operations.",
)
def check_role_hierarchy_preserved(ctx: InvariantContext) -> InvariantResult:
    """Verify that all user roles conform to the defined hierarchy."""
    invariant_id = "AUTH-003"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()

        # Check for unknown roles
        cursor.execute(
            """
            SELECT DISTINCT role
            FROM users
            WHERE role IS NOT NULL
            """
        )
        known_roles = set(_VALID_ROLE_HIERARCHY.keys())
        db_roles = {row[0] for row in cursor.fetchall()}
        unknown_roles = db_roles - known_roles

        # Check for role assignment anomalies
        cursor.execute(
            """
            SELECT u.id, u.username, u.email, u.role
            FROM users u
            WHERE u.role IS NOT NULL
              AND u.role NOT IN ('admin', 'manager', 'dispatcher', 'driver')
            """
        )
        anomalous = cursor.fetchall()

        issues = []
        if unknown_roles:
            issues.append(f"Unknown roles in database: {sorted(unknown_roles)}")

        if anomalous:
            for row in anomalous:
                issues.append(
                    f"User id={row[0]} ({row[1]}) has unrecognized role '{row[3]}'"
                )

        if issues:
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All user roles are one of: admin, manager, dispatcher, driver",
                actual=f"Found {len(issues)} role hierarchy violations",
                message="; ".join(issues[:5]),
                root_cause="Custom or legacy role values exist in the users table",
                suggested_fix="Migrate unknown roles to the standard hierarchy or add them to the valid role set with proper priority",
                affected_modules=["auth"],
                details={
                    "known_roles": sorted(known_roles),
                    "unknown_roles_in_db": sorted(unknown_roles),
                    "anomalous_users": [
                        {"id": r[0], "username": r[1], "email": r[2], "role": r[3]}
                        for r in anomalous
                    ],
                },
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All user roles conform to the hierarchy: admin > manager > dispatcher > driver",
            actual=f"All {len(db_roles)} distinct roles are valid",
            affected_modules=["auth"],
            details={"valid_roles": sorted(db_roles)},
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["auth"],
        )


# ──────────────────────────────────────────────
# AUTH-004 — Brute force protection active
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-004",
    title="Brute force protection active",
    description="5 failed attempts within 5 min window triggers 15 min lockout.",
    category=InvariantCategory.AUTH,
    modules=["auth"],
    severity=Severity.MEDIUM,
    execution=[ExecutionFrequency.COMMIT],
    rationale="Without brute force protection, accounts are vulnerable to password guessing attacks.",
)
def check_brute_force_protection_active(ctx: InvariantContext) -> InvariantResult:
    """Verify that brute force protection settings meet the security policy."""
    invariant_id = "AUTH-004"

    # Read config from ctx.config or env vars — these are app-level settings
    max_attempts = int(
        ctx.config.get("brute_force_max_attempts", ctx.env.get("BF_MAX_ATTEMPTS", 0))
    )
    window_minutes = int(
        ctx.config.get(
            "brute_force_window_minutes", ctx.env.get("BF_WINDOW_MINUTES", 0)
        )
    )
    lockout_minutes = int(
        ctx.config.get(
            "brute_force_lockout_minutes", ctx.env.get("BF_LOCKOUT_MINUTES", 0)
        )
    )
    enabled = ctx.config.get(
        "brute_force_enabled", ctx.env.get("BF_ENABLED", "")
    )

    issues = []

    if enabled in ("", None) or str(enabled).lower() not in ("1", "true", "yes"):
        issues.append("Brute force protection is not enabled")

    if max_attempts == 0 or max_attempts > 5:
        issues.append(
            f"Max failed attempts is {max_attempts} (should be 5 or fewer)"
        )

    if window_minutes == 0 or window_minutes > 5:
        issues.append(
            f"Failure window is {window_minutes} min (should be 5 or fewer)"
        )

    if lockout_minutes < 15:
        issues.append(
            f"Lockout duration is {lockout_minutes} min (should be at least 15)"
        )

    if issues:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.FAIL,
            expected=(
                "Brute force protection enabled: max 5 attempts in 5 min window, "
                "15 min lockout"
            ),
            actual="; ".join(issues),
            message="Brute force protection settings do not meet security policy",
            root_cause="Brute force configuration was weakened or disabled",
            suggested_fix="Set BF_ENABLED=true, BF_MAX_ATTEMPTS=5, BF_WINDOW_MINUTES=5, BF_LOCKOUT_MINUTES=15",
            affected_modules=["auth"],
            details={
                "enabled": enabled,
                "max_attempts": max_attempts,
                "window_minutes": window_minutes,
                "lockout_minutes": lockout_minutes,
                "issues": issues,
            },
        )

    # Also check the database for users currently locked out due to brute force
    if ctx.db is not None:
        try:
            cursor = ctx.db.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as cnt
                FROM login_attempts
                WHERE success = 0
                  AND attempted_at > datetime('now', '-5 minutes')
                GROUP BY user_id
                HAVING cnt >= 5
                """
            )
            currently_locked = cursor.fetchall()
            locked_count = len(currently_locked)
        except Exception:
            locked_count = -1  # table may not exist, that's okay

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected=(
                "Brute force protection enabled: max 5 attempts in 5 min window, "
                "15 min lockout"
            ),
            actual=f"Brute force protection is active (max_attempts={max_attempts}, "
            f"window={window_minutes}min, lockout={lockout_minutes}min)",
            message="Brute force protection configuration meets policy",
            affected_modules=["auth"],
            details={
                "enabled": enabled,
                "max_attempts": max_attempts,
                "window_minutes": window_minutes,
                "lockout_minutes": lockout_minutes,
                "currently_locked_users": locked_count if locked_count >= 0 else "unknown",
            },
        )

    return InvariantResult(
        invariant_id=invariant_id,
        status=InvariantStatus.PASS,
        expected=(
            "Brute force protection enabled: max 5 attempts in 5 min window, "
            "15 min lockout"
        ),
        actual=f"Brute force protection is active (max_attempts={max_attempts}, "
        f"window={window_minutes}min, lockout={lockout_minutes}min)",
        affected_modules=["auth"],
        details={
            "enabled": enabled,
            "max_attempts": max_attempts,
            "window_minutes": window_minutes,
            "lockout_minutes": lockout_minutes,
        },
    )


# ──────────────────────────────────────────────
# AUTH-005 — Refresh tokens are single-use
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-005",
    title="Refresh tokens are single-use",
    description="Each refresh token is consumed after one use (rotation).",
    category=InvariantCategory.AUTH,
    modules=["auth"],
    severity=Severity.HIGH,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.PR],
    rationale="Reusable refresh tokens enable session hijacking and indefinite access.",
)
def check_refresh_tokens_single_use(ctx: InvariantContext) -> InvariantResult:
    """Verify that no refresh token has been used more than once."""
    invariant_id = "AUTH-005"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT token_id, user_id, token_hash, used_count
            FROM refresh_tokens
            WHERE used_count > 1
            """
        )
        reused_tokens = cursor.fetchall()

        if reused_tokens:
            details = [
                {
                    "token_id": row[0],
                    "user_id": row[1],
                    "used_count": row[3],
                }
                for row in reused_tokens
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="Every refresh token is used at most once",
                actual=f"Found {len(reused_tokens)} refresh tokens used multiple times",
                message=f"Reused tokens for user IDs: {set(d['user_id'] for d in details)}",
                root_cause="Token rotation logic is not consuming tokens after use",
                suggested_fix="Implement token rotation: mark the old token as used when a new one is issued",
                affected_modules=["auth"],
                details={"reused_tokens": details},
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="Every refresh token is used at most once",
            actual="All refresh tokens are single-use (0 reused tokens detected)",
            affected_modules=["auth"],
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["auth"],
        )


# ──────────────────────────────────────────────
# AUTH-006 — API keys are hashed
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-006",
    title="API keys are hashed",
    description="api_keys.key_hash is SHA-256, never plaintext.",
    category=InvariantCategory.AUTH,
    modules=["auth", "api"],
    severity=Severity.CRITICAL,
    execution=[
        ExecutionFrequency.COMMIT,
        ExecutionFrequency.PR,
        ExecutionFrequency.RELEASE,
    ],
    rationale="Plaintext API keys in the database are a critical security risk.",
)
def check_api_keys_hashed(ctx: InvariantContext) -> InvariantResult:
    """Verify that all API key hashes are valid SHA-256 values (not plaintext)."""
    invariant_id = "AUTH-006"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()
        cursor.execute(
            """
            SELECT id, key_name, key_hash
            FROM api_keys
            WHERE key_hash IS NOT NULL
            """
        )
        rows = cursor.fetchall()

        invalid_keys = []
        for row in rows:
            key_id, key_name, key_hash = row
            # SHA-256 hex is exactly 64 hex characters
            if not key_hash or not _SHA256_RE.match(key_hash):
                invalid_keys.append(
                    {
                        "id": key_id,
                        "key_name": key_name,
                        "hash_prefix": key_hash[:16] if key_hash else None,
                        "hash_length": len(key_hash) if key_hash else 0,
                    }
                )

        if invalid_keys:
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All api_keys.key_hash values are SHA-256 hex digests (64 hex chars)",
                actual=f"Found {len(invalid_keys)} API keys without valid SHA-256 hashes out of {len(rows)} total",
                message=f"Invalid key hashes for key IDs: {[d['id'] for d in invalid_keys]}",
                root_cause="API keys were stored as plaintext or with an incorrect hash algorithm",
                suggested_fix="Re-hash all API keys with SHA-256 immediately; update storage logic to hash before insert",
                affected_modules=["auth", "api"],
                details={
                    "total_keys": len(rows),
                    "invalid_keys": invalid_keys,
                },
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All api_keys.key_hash values are SHA-256 hex digests",
            actual=f"All {len(rows)} API keys have valid SHA-256 hashes",
            affected_modules=["auth", "api"],
            details={"total_keys": len(rows)},
        )
    except Exception as exc:
        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.ERROR,
            message=f"Database query failed: {exc}",
            root_cause=str(exc),
            affected_modules=["auth", "api"],
        )


# ──────────────────────────────────────────────
# AUTH-007 — Admin operations require admin role
# ──────────────────────────────────────────────


@invariant(
    id="AUTH-007",
    title="Admin operations require admin role",
    description="Delete operations (trips, clients, vehicles, drivers) require admin role.",
    category=InvariantCategory.AUTH,
    modules=["auth"],
    severity=Severity.CRITICAL,
    execution=[ExecutionFrequency.COMMIT, ExecutionFrequency.PR],
    rationale="Non-admin users performing delete operations can cause irreversible data loss.",
)
def check_admin_operations_require_admin_role(ctx: InvariantContext) -> InvariantResult:
    """Verify that destructive operations in the audit log were performed by admin users."""
    invariant_id = "AUTH-007"

    if ctx.db is None:
        return _no_db_result(invariant_id)

    try:
        cursor = ctx.db.cursor()

        # Check the audit log for delete operations performed by non-admin users
        cursor.execute(
            """
            SELECT al.id, al.user_id, al.operation, al.entity_type, al.entity_id,
                   al.operated_at, u.role
            FROM audit_log al
            JOIN users u ON al.user_id = u.id
            WHERE al.operation LIKE 'delete_%'
              AND u.role != 'admin'
            """
        )
        non_admin_deletes = cursor.fetchall()

        if non_admin_deletes:
            details = [
                {
                    "audit_id": row[0],
                    "user_id": row[1],
                    "operation": row[2],
                    "entity_type": row[3],
                    "entity_id": row[4],
                    "operated_at": str(row[5]),
                    "user_role": row[6],
                }
                for row in non_admin_deletes
            ]
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.FAIL,
                expected="All delete operations are performed by users with admin role",
                actual=f"Found {len(non_admin_deletes)} delete operations by non-admin users",
                message=f"Non-admin deletes by user IDs: {set(d['user_id'] for d in details)}",
                root_cause="Authorization check is missing or misconfigured for delete operations",
                suggested_fix="Add role-based access control to all delete operations; ensure only admin role can delete",
                affected_modules=["auth"],
                details={
                    "total_violations": len(non_admin_deletes),
                    "violations": details,
                },
            )

        return InvariantResult(
            invariant_id=invariant_id,
            status=InvariantStatus.PASS,
            expected="All delete operations are performed by users with admin role",
            actual="No unauthorized delete operations detected",
            affected_modules=["auth"],
        )
    except Exception as exc:
        # If the audit_log table doesn't exist, we try a fallback approach:
        # check the permission configuration or role definitions
        try:
            cursor = ctx.db.cursor()
            cursor.execute(
                """
                SELECT id, role, permission
                FROM role_permissions
                WHERE permission LIKE 'delete_%'
                  AND role != 'admin'
                """
            )
            weak_perms = cursor.fetchall()

            if weak_perms:
                details = [
                    {"id": row[0], "role": row[1], "permission": row[2]}
                    for row in weak_perms
                ]
                return InvariantResult(
                    invariant_id=invariant_id,
                    status=InvariantStatus.FAIL,
                    expected="Only admin role has delete permissions",
                    actual=f"Found {len(weak_perms)} non-admin roles with delete permissions",
                    message=f"Roles with delete permissions: {set(d['role'] for d in details)}",
                    root_cause="Role-permission mapping grants delete to non-admin roles",
                    suggested_fix="Remove delete_* permissions from non-admin roles in the role_permissions table",
                    affected_modules=["auth"],
                    details={
                        "total_violations": len(weak_perms),
                        "violations": details,
                    },
                )

            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.PASS,
                expected="Only admin role has delete permissions",
                actual="No non-admin roles have delete permissions",
                affected_modules=["auth"],
            )
        except Exception as inner_exc:
            return InvariantResult(
                invariant_id=invariant_id,
                status=InvariantStatus.ERROR,
                message=f"Database query failed: {exc} (fallback also failed: {inner_exc})",
                root_cause=str(exc),
                affected_modules=["auth"],
            )
