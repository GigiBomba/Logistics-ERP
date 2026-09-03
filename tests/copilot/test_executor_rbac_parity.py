"""Executor RBAC parity — executor gate must match the §8.3 permission matrix.

Regression test for the historical drift between the two RBAC gates:

- The PLANNER admits tools via ``resolve_available_tools`` using the §8.3
  permission matrix in ``backend/copilot/role_permissions.py``.
- The EXECUTOR enforces tools at execution time via
  ``backend/copilot/executor._check_tool_permission``.

They must never diverge again.  The executor derives its role→resource sets
at module load from ``role_permissions.py`` (single source of truth); this
test iterates EVERY registered copilot tool × EVERY role and asserts the
executor agrees with the declarative matrix (plus the executor's two
intentional operation-level layers: driver read-only, dispatcher no-delete,
and the admin bypass).

Roles covered: ``manager``, ``dispatcher``, ``driver``, ``admin``.
Tools covered: every registered production tool in the registry (lazy-loaded).
"""
from __future__ import annotations

from typing import List, Set

import pytest

from backend.copilot.context import resolve_available_tools
from backend.copilot.executor import (
    _ROLE_RESOURCE_ACCESS,
    _check_tool_permission,
)
from backend.copilot.role_permissions import (
    DRIVER_FORBIDDEN_TOOLS,
    get_role_permissions,
)
from backend.copilot.schemas import GlobalContext
from backend.copilot.tools.registry import all_tools, get_tool

# Roles the executor gate can be asked about (admin has a bypass, the others
# are declared in role_permissions.py).
ROLES = ("manager", "dispatcher", "driver", "admin")


# ── Tool registry ──────────────────────────────────────────────────────────
# ``all_tools()`` triggers the lazy import of every tool module so the whole
# registry is registered.  ``test.*`` fixture tools registered by other test
# modules on a shared xdist worker are excluded.
def _production_tools():
    return [t for t in all_tools() if not t.name.startswith("test.")]


# Independent re-derivation of the executor's resource sets — any future
# reintroduction of a hardcoded role_access dict that omits or adds a resource
# the §8.3 matrix grants (or doesn't) fails immediately.
def _derive_resource_sets() -> dict:
    return {
        role: {p.split(":")[0] for p in get_role_permissions(role)}
        for role in ("manager", "dispatcher", "driver")
    }


# ── Expected grant (declarative matrix + executor's op-level layers) ───────
def _expected_grant(tool, role: str) -> bool:
    """Expected executor verdict computed purely from role_permissions."""
    if role == "admin":
        return True  # admin bypass
    if not tool.required_permission:
        return True  # no permission required = accessible to all
    if role == "driver" and getattr(tool, "name", None) in DRIVER_FORBIDDEN_TOOLS:
        return False  # §8.3 "no confidential business info" boundary
    resource = tool.required_permission.split(":")[0]
    if resource not in _derive_resource_sets()[role]:
        return False
    operation = (
        tool.required_permission.split(":")[1]
        if ":" in tool.required_permission
        else ""
    )
    if role == "driver" and operation and operation != "read":
        return False  # drivers: read-only (§8.1)
    if role == "dispatcher" and operation == "delete":
        return False  # dispatchers: no delete (§8.1)
    return True


def _make_global_ctx(role: str) -> GlobalContext:
    return GlobalContext(
        company_id=1,
        user_id=1,
        role=role,
        language="en",
        timezone="UTC",
        subscription_tier="enterprise",
    )


def _executor_allowed_names(role: str) -> Set[str]:
    return {t.name for t in _production_tools() if _check_tool_permission(t, role)}


# ═══════════════════════════════════════════════════════════════════════════
# 1. Structural — executor resource sets match the §8.3 matrix
# ═══════════════════════════════════════════════════════════════════════════

class TestExecutorResourceSetsMatchRolePermissions:
    def test_executor_resource_sets_equal_derived_sets(self) -> None:
        """The executor's module-level role→resource table is exactly the
        union of resources of the §8.3 permission strings granted to each role.

        This is the assertion that would have caught the historical
        dispatcher omissions (``invoices``, ``maintenance``, ``tacho``,
        ``export``, ``email``, ``payments``, ``proforma``, ``automail``) and
        the ``analytics.query`` execution-time denial.
        """
        assert _ROLE_RESOURCE_ACCESS == _derive_resource_sets()

    def test_can_schedule_maintenance_stays_distinct_from_maintenance(
        self,
    ) -> None:
        """``can_schedule_maintenance`` (admin+manager only) is its own
        resource and must never merge with the ``maintenance`` resource that
        dispatcher holds via ``maintenance:write``."""
        manager = _derive_resource_sets()["manager"]
        dispatcher = _derive_resource_sets()["dispatcher"]
        assert "can_schedule_maintenance" in manager
        assert "can_schedule_maintenance" not in dispatcher
        assert "maintenance" in dispatcher
        # record_maintenance (single-segment, can_schedule_maintenance) is
        # admin+manager only; maintenance.schedule (maintenance:write) is
        # dispatcher-accessible.
        assert _check_tool_permission(get_tool("record_maintenance"), "manager") is True
        assert _check_tool_permission(get_tool("record_maintenance"), "dispatcher") is False
        assert _check_tool_permission(get_tool("maintenance.schedule"), "dispatcher") is True
        assert _check_tool_permission(get_tool("maintenance.schedule"), "driver") is False

    def test_system_resource_excluded_from_operational_roles(self) -> None:
        """``system:undo`` is excluded from manager/dispatcher/driver — no
        operational role holds the ``system`` resource."""
        for role in ("manager", "dispatcher", "driver"):
            assert "system" not in _derive_resource_sets()[role]
        assert _check_tool_permission(get_tool("system.undo"), "manager") is False
        assert _check_tool_permission(get_tool("system.undo"), "dispatcher") is False
        assert _check_tool_permission(get_tool("system.undo"), "driver") is False
        assert _check_tool_permission(get_tool("system.undo"), "admin") is True


# ═══════════════════════════════════════════════════════════════════════════
# 2. Per-tool parity — every tool × every role
# ═══════════════════════════════════════════════════════════════════════════

class TestExecutorToolRoleParity:
    @pytest.mark.parametrize("role", ROLES)
    def test_every_tool_matches_declarative_grant(self, role: str) -> None:
        """For every registered tool, the executor's verdict equals the
        declarative §8.3 matrix (plus the executor's op-level layers)."""
        tools = _production_tools()
        assert tools, "tool registry is empty — lazy module loading failed"
        for tool in tools:
            assert _check_tool_permission(tool, role) == _expected_grant(tool, role), (
                f"Executor/§8.3 parity broken for {tool.name} "
                f"(required_permission={tool.required_permission!r}, role={role})"
            )

    def test_dispatcher_gets_previously_omitted_resources(self) -> None:
        """Regression: dispatcher must be able to execute every tool its §8.3
        permission set grants (the historical execution-time denials)."""
        dispatcher_perms = set(get_role_permissions("dispatcher"))
        for tool in _production_tools():
            if tool.required_permission in dispatcher_perms:
                assert _check_tool_permission(tool, "dispatcher") is True, (
                    f"Dispatcher denied {tool.name} "
                    f"({tool.required_permission}) which §8.3 grants"
                )

    def test_driver_forbidden_tools_denied_by_executor(self) -> None:
        """§8.3 boundary: the driver's executor gate denies every
        ``DRIVER_FORBIDDEN_TOOLS`` tool (analytics / client-payment)."""
        for tool in _production_tools():
            if tool.name in DRIVER_FORBIDDEN_TOOLS:
                assert _check_tool_permission(tool, "driver") is False, tool.name


# ═══════════════════════════════════════════════════════════════════════════
# 3. Planner ↔ executor consistency (resolve_available_tools)
# ═══════════════════════════════════════════════════════════════════════════

class TestPlannerExecutorConsistency:
    @pytest.mark.parametrize("role", ["manager", "dispatcher"])
    @pytest.mark.asyncio
    async def test_planner_admitted_set_equals_executor_allowed_set(
        self, role: str,
    ) -> None:
        """For manager/dispatcher the planner-admitted tool set and the
        executor-allowed set are IDENTICAL — a plan the planner compiles can
        never be denied by the executor at execution time."""
        tool_ctx = await resolve_available_tools(
            _make_global_ctx(role=role), get_role_permissions(role)
        )
        # Same exclusion as ``_production_tools()`` (see module docstring): the
        # planner resolves against the FULL registry — including ``test.*``
        # fixture tools registered by other test modules on a shared xdist
        # worker — while the executor side only counts production tools.  Filter
        # the planner side identically so the comparison is apples-to-apples.
        production_names = {t.name for t in _production_tools()}
        planner_admitted = {
            name for name in tool_ctx.available_tools if name in production_names
        }
        executor_allowed = _executor_allowed_names(role)
        assert planner_admitted == executor_allowed, (
            f"{role}: planner admitted {sorted(planner_admitted - executor_allowed)} "
            f"but executor denies; executor allows "
            f"{sorted(executor_allowed - planner_admitted)} that planner omits"
        )

    @pytest.mark.asyncio
    async def test_driver_planner_and_executor_agree_on_boundary(self) -> None:
        """Driver: the planner and the executor both exclude the §8.3
        forbidden tools, and every planner-admitted driver tool passes the
        executor gate except the intentional driver read-only layer (the
        driver may PLAN own-scope write tools — trip/documents — but the
        executor enforces read-only at execution time; this asymmetry is
        intentional and pinned here)."""
        tool_ctx = await resolve_available_tools(
            _make_global_ctx(role="driver"), get_role_permissions("driver")
        )
        planner_admitted: List[str] = tool_ctx.available_tools

        # §8.3 boundary — never admitted, never allowed.
        assert DRIVER_FORBIDDEN_TOOLS.isdisjoint(planner_admitted)
        assert DRIVER_FORBIDDEN_TOOLS.isdisjoint(_executor_allowed_names("driver"))

        for name in planner_admitted:
            tool = get_tool(name)
            if _expected_grant(tool, "driver") is False:
                # The ONLY planner-admitted-but-executor-denied tools are the
                # driver's own-scope WRITE tools (read-only enforcement).
                op = tool.required_permission.split(":")[1]
                assert op != "read", (
                    f"Driver can plan {name} ({tool.required_permission}) "
                    f"but executor denies it — not a write-op denial"
                )
            else:
                assert _check_tool_permission(tool, "driver") is True, name

    def test_unknown_role_denies_everything(self) -> None:
        """A role with no §8.3 grants gets an empty resource set → all tools
        denied (fail closed), mirroring resolve_available_tools([])."""
        for tool in _production_tools():
            assert _check_tool_permission(tool, "nobody") is False