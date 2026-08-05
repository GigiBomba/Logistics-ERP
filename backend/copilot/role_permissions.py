"""AI Copilot role permissions — the authoritative RBAC matrix (§8.1 / §8.3).

Single source of truth for two consumers:

1. ``AI_ROLE_PERMISSIONS`` — the role capability matrix consumed by the
   AI-002 business invariant (``business_invariants/checks/ai_argo.py``):
   driver = read-only, dispatcher = no deletes, manager = all except system.

2. ``AI_ROLE_TOOL_PERMISSIONS`` — the permission-string sets handed to
   ``resolve_available_tools()`` (``backend/copilot/context.py``) when a
   session is built for a given role.  ``driver`` gets a read-only +
   own-trip subset; ``dispatcher``/``manager`` get the broader operational
   set (the tool registry is intersected with these at request time).

This module is deliberately a pure-constants module (no imports from the
tool registry or services) so it can be imported by the business-invariant
framework without side effects.
"""

from __future__ import annotations

from typing import Dict, List

# ── §8.1 role capability matrix (AI-002) ─────────────────────────────────
# driver:      read-only — may view/confirm own-trip operations, never delete
#              or touch system scope.
# dispatcher:  operational — writes allowed, but NEVER deletes and never
#              system-scope operations.
# manager:     broad — delete allowed for operational records, but still no
#              system-scope operations.
AI_ROLE_PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "driver": {"read_only": True, "can_delete": False, "can_system": False},
    "dispatcher": {"read_only": False, "can_delete": False, "can_system": False},
    "manager": {"read_only": False, "can_delete": True, "can_system": False},
}

# ── §8.3 tool-level permission sets ──────────────────────────────────────
# Each entry is the list of ``required_permission`` strings granted to that
# role.  ``resolve_available_tools()`` intersects the tool registry with the
# role's set.  The driver set deliberately EXCLUDES ``analytics:read``,
# ``clients:read`` and ``payments:write`` — the "no confidential business
# info" boundary (§8.3) — so ``analytics.query``, ``client.payment_summary``
# and ``payment.generate_bulk_csv`` never resolve for a driver session.

# Full permission universe declared by the tool registry.  Keeping it as a
# single list here makes the dispatcher/manager variants self-documenting.
_ALL_TOOL_PERMISSIONS: List[str] = [
    # read-only domains
    "analytics:read",
    "clients:read",
    "currency:read",
    "documents:read",
    "drivers:read",
    "freight:read",
    "help:read",
    "invoices:read",
    "receipts:read",
    "routes:read",
    "tracking:read",
    "trips:read",
    "fleet:read",
    # write domains
    "automail:write",
    "automail:send",
    "clients:write",
    "dispatch:write",
    "documents:write",
    "drivers:write",
    "email:send_bulk",
    "export:write",
    "fleet:write",
    "freight:write",
    "invoices:write",
    "maintenance:write",
    "payments:write",
    "proforma:write",
    "receipts:write",
    "routes:write",
    "tacho:write",
    "trips:write",
    # delete domains (dispatcher has none; manager has all)
    "clients:delete",
    "drivers:delete",
    "fleet:delete",
    "invoices:delete",
    "routes:delete",
    "trips:delete",
    # system scope (no operational role)
    "system:undo",
    # Phase-5 mobile-integration permission (record_maintenance tool).
    # Grants admin+manager in the mobile PermissionService; here it maps to
    # the broadest copilot role (manager).  Excluded from the dispatcher set
    # below to mirror the mobile RBAC exactly.
    "can_schedule_maintenance",
]

# driver: read-only + own-trip write capabilities only (help, own hours,
# own route, own vehicle, own uploads, own trip status transitions).
DRIVER_TOOL_PERMISSIONS: List[str] = [
    "help:read",
    "drivers:read",
    "routes:read",
    "tracking:read",
    "documents:read",
    "documents:write",
    "currency:read",
    "trips:write",
]

# dispatcher: everything except deletes and system scope.
DISPATCHER_TOOL_PERMISSIONS: List[str] = [
    p for p in _ALL_TOOL_PERMISSIONS
    if not p.endswith(":delete") and p != "system:undo"
    # can_schedule_maintenance is admin+manager only in the mobile RBAC.
    and p != "can_schedule_maintenance"
]

# manager: everything except system scope.
MANAGER_TOOL_PERMISSIONS: List[str] = [
    p for p in _ALL_TOOL_PERMISSIONS
    if p != "system:undo"
]

AI_ROLE_TOOL_PERMISSIONS: Dict[str, List[str]] = {
    "driver": DRIVER_TOOL_PERMISSIONS,
    "dispatcher": DISPATCHER_TOOL_PERMISSIONS,
    "manager": MANAGER_TOOL_PERMISSIONS,
}

# Sensitive tools that must never resolve for a driver session (§8.3).
DRIVER_FORBIDDEN_TOOLS = frozenset({
    "analytics.query",
    "client.payment_summary",
    "payment.generate_bulk_csv",
})


def get_role_permissions(role: str) -> List[str]:
    """Return the tool-permission list for *role* (empty list if unknown)."""
    return list(AI_ROLE_TOOL_PERMISSIONS.get(role, []))


def get_ai_role_permissions() -> Dict[str, Dict[str, bool]]:
    """Return the §8.1 role capability matrix (for the AI-002 invariant)."""
    return {
        role: dict(caps) for role, caps in AI_ROLE_PERMISSIONS.items()
    }
