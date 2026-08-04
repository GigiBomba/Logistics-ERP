"""Copilot RBAC scope — driver ``available_tools`` excludes sensitive tools.

Blueprint §8.3: ``available_tools`` is resolved server-side by
``backend/copilot/context.py:resolve_available_tools``, which intersects the
tool registry with the session role's permission set.  A driver-role session
must NOT resolve the analytics + client-payment tools
(``analytics.query``, ``client.payment_summary``, ``payment.generate_bulk_csv``
— the "no confidential business info" boundary), while dispatcher/manager
sessions include them.

Permission sets come from the authoritative §8.1/§8.3 matrix in
``backend/copilot/role_permissions.py`` (also consumed by the AI-002
business invariant).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.copilot.context import resolve_available_tools
from backend.copilot.role_permissions import (
    DRIVER_FORBIDDEN_TOOLS,
    get_role_permissions,
)
from backend.copilot.schemas import GlobalContext
from backend.copilot.tools.registry import (
    all_tools,
    run_startup_validation,
)

# Importing every tool module registers the full registry (§9).  Registry
# validation must pass — any error here would be a tool-definition defect.
_validation_errors = run_startup_validation()
assert not _validation_errors, (
    f"Tool registry failed startup validation: {_validation_errors}"
)

# Tools that must never resolve for a driver session (§8.3 boundary).
SENSITIVE_TOOL_IDS = frozenset({
    "analytics.query",       # requires analytics:read
    "client.payment_summary",  # requires clients:read
    "payment.generate_bulk_csv",  # requires payments:write
})


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_global_ctx(role: str = "dispatcher") -> GlobalContext:
    return GlobalContext(
        company_id=1,
        user_id=1,
        role=role,
        language="en",
        timezone="UTC",
        subscription_tier="enterprise",
    )


def _real_tools():
    """Registry tools excluding ``test.*`` fixtures registered by other
    test modules that may share the same xdist worker."""
    return [t for t in all_tools() if not t.name.startswith("test.")]


def _excluded_for(perms: list[str]) -> set[str]:
    """Mechanical expectation: tools whose required_permission is missing."""
    return {t.name for t in _real_tools() if t.required_permission not in perms}


# ── Tests ─────────────────────────────────────────────────────────────────

class TestDriverRbacScope:
    """Driver sessions exclude analytics + client-payment tools."""

    @pytest.mark.asyncio
    async def test_driver_available_tools_excludes_sensitive_tools(self) -> None:
        ctx = _make_global_ctx(role="driver")
        tool_ctx = await resolve_available_tools(ctx, get_role_permissions("driver"))

        available = set(tool_ctx.available_tools)
        # Exact forbidden set: the "no confidential business info" tools.
        assert not SENSITIVE_TOOL_IDS & available, (
            f"Driver session must not resolve sensitive tools, got: "
            f"{sorted(SENSITIVE_TOOL_IDS & available)}"
        )
        for tool_id in sorted(SENSITIVE_TOOL_IDS):
            assert tool_id not in available, (
                f"Driver session resolved forbidden tool '{tool_id}'"
            )

    @pytest.mark.asyncio
    async def test_driver_excludes_exactly_the_unpermitted_tools(self) -> None:
        """The filter is purely permission-driven — no tool is hidden or
        leaked beyond the driver permission set."""
        driver_perms = get_role_permissions("driver")
        ctx = _make_global_ctx(role="driver")
        tool_ctx = await resolve_available_tools(ctx, driver_perms)

        resolved = set(tool_ctx.available_tools)
        expected_excluded = _excluded_for(driver_perms)
        actual_excluded = {t.name for t in _real_tools()} - resolved

        assert actual_excluded == expected_excluded, (
            f"Excluded tools mismatch:\n  actual  = {sorted(actual_excluded)}\n"
            f"  expected= {sorted(expected_excluded)}"
        )

    @pytest.mark.asyncio
    async def test_driver_retains_own_trip_read_tools(self) -> None:
        """The driver still resolves its own-scope tools (help, own hours,
        own route, own vehicle)."""
        ctx = _make_global_ctx(role="driver")
        tool_ctx = await resolve_available_tools(ctx, get_role_permissions("driver"))
        available = set(tool_ctx.available_tools)

        for expected in (
            "help.answer_question",
            "help.guide_workflow",
            "driver.check_hours",
            "route.calculate",
            "route.estimate_cost",
            "tracking.get_live_positions",
            "document.search",
        ):
            assert expected in available, (
                f"Driver session should resolve '{expected}' but it is missing"
            )

    @pytest.mark.asyncio
    async def test_empty_permission_set_resolves_no_tools(self) -> None:
        """A session with no permissions resolves nothing (registry tools all
        declare a required_permission).

        ``test.*`` fixture tools registered by other test modules that share
        this xdist worker may leak into the registry and are excluded.
        """
        ctx = _make_global_ctx(role="unknown")
        tool_ctx = await resolve_available_tools(ctx, [])
        leaked_real = [t for t in tool_ctx.available_tools if not t.startswith("test.")]
        assert leaked_real == [], (
            f"No-permission session resolved real tools: {leaked_real}"
        )


class TestDispatcherManagerRbacScope:
    """Dispatcher and manager sessions include the sensitive tools."""

    @pytest.mark.parametrize("role", ["dispatcher", "manager"])
    @pytest.mark.asyncio
    async def test_dispatcher_and_manager_include_sensitive_tools(self, role: str) -> None:
        ctx = _make_global_ctx(role=role)
        tool_ctx = await resolve_available_tools(ctx, get_role_permissions(role))
        available = set(tool_ctx.available_tools)

        for tool_id in sorted(SENSITIVE_TOOL_IDS):
            assert tool_id in available, (
                f"{role} session must resolve '{tool_id}' but it is missing"
            )

    @pytest.mark.asyncio
    async def test_manager_includes_delete_tools_but_not_system(self) -> None:
        """§8.1: manager can delete operational records, but never system-scope."""
        ctx = _make_global_ctx(role="manager")
        tool_ctx = await resolve_available_tools(ctx, get_role_permissions("manager"))
        available = set(tool_ctx.available_tools)

        assert "trip.delete" in available
        assert "invoice.delete" in available
        assert "system.undo" not in available, (
            "Manager must not resolve the system-scope undo tool"
        )

    @pytest.mark.asyncio
    async def test_dispatcher_has_no_delete_tools(self) -> None:
        """§8.1: dispatcher never resolves delete tools."""
        ctx = _make_global_ctx(role="dispatcher")
        tool_ctx = await resolve_available_tools(ctx, get_role_permissions("dispatcher"))
        available = set(tool_ctx.available_tools)

        delete_tools = {t.name for t in all_tools() if t.name.endswith(".delete")}
        assert not delete_tools & available, (
            f"Dispatcher must not resolve delete tools, got: "
            f"{sorted(delete_tools & available)}"
        )


class TestPermissionMatrixConsistency:
    """The role_permissions matrix stays consistent with the tool registry."""

    def test_driver_forbidden_tools_are_declared_in_registry(self) -> None:
        registry_ids = {t.name for t in all_tools()}
        assert DRIVER_FORBIDDEN_TOOLS <= registry_ids, (
            f"Forbidden tool ids not in registry: "
            f"{sorted(DRIVER_FORBIDDEN_TOOLS - registry_ids)}"
        )

    def test_every_forbidden_tool_requires_a_driver_excluded_permission(self) -> None:
        """Each forbidden tool's permission must be absent from the driver set."""
        driver_perms = set(get_role_permissions("driver"))
        for tool in all_tools():
            if tool.name in DRIVER_FORBIDDEN_TOOLS:
                assert tool.required_permission not in driver_perms, (
                    f"'{tool.name}' requires '{tool.required_permission}' which "
                    f"is granted to the driver role — the §8.3 boundary is broken"
                )


# ═══════════════════════════════════════════════════════════════════════════
# Runtime enforcement (F1) — the production /chat handler resolves the
# caller's permitted tools from the JWT role and the planner rejects any
# forbidden intent BEFORE a plan is compiled or a tool executes.
# ═══════════════════════════════════════════════════════════════════════════

class TestRuntimeRBACEnforcement:
    """End-to-end proof that RBAC is enforced in the HTTP request path.

    Before the F1 fix, ``process_utterance`` → ``get_tool(intent.name)`` →
    ``compile_execution_plan`` ran without any role/permission check, so a
    driver could execute ``analytics.query`` / ``client.payment_summary``.
    These tests drive ``POST /api/v1/copilot/chat`` with a driver JWT and
    assert the tool is NOT executed and the denial is surfaced in the
    response.
    """

    @staticmethod
    def _build_app(role: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        from unittest.mock import MagicMock

        from backend.dependencies import get_db
        from backend.dependencies_security import get_current_user
        from backend.main import create_app
        from config import Config

        # Disable the API-key middleware deterministically regardless of
        # module import order (the middleware reads Config.API_KEY once at
        # instantiation).
        monkeypatch.setattr(Config, "API_KEY", "")

        app = create_app()

        async def _override_get_db():
            yield MagicMock()

        async def _mock_current_user() -> dict:
            return {
                "id": 10,
                "email": f"{role}@test.com",
                "role": role,
                "is_admin": False,
                "company_id": 1,
                "timezone": "UTC",
                "subscription_tier": "enterprise",
            }

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _mock_current_user
        return TestClient(app)

    @pytest.mark.parametrize(
        ("utterance", "forbidden_intent"),
        [
            # "no confidential business info" boundary (§8.3)
            ("show me the analytics report", "analytics.query"),
            ("what is the client payment summary for client 3", "client.payment_summary"),
        ],
    )
    def test_driver_forbidden_intent_is_denied_without_execution(
        self, monkeypatch: pytest.MonkeyPatch, utterance: str, forbidden_intent: str
    ) -> None:
        """Driver → analytics/client-payment intent → NOT executed.

        The denial surfaces as an HTTP 200 with an i18n clarification key
        (``copilot.error.permission_denied``) + the intent name, an EMPTY
        timeline (nothing executed) and no plan id — the planner's standard
        graceful-denial shape, NOT a crash and NOT a 500.
        """
        client = self._build_app("driver", monkeypatch)

        resp = client.post(
            "/api/v1/copilot/chat",
            json={"utterance": utterance, "language": "en"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Denial surfaced in the response body.
        assert body["clarification_question_key"] == "copilot.error.permission_denied", body
        assert body["clarification_params"]["intent"] == forbidden_intent
        assert body["clarification_params"]["role"] == "driver"
        # Tool NOT executed: no steps, no plan.
        assert body["timeline"] == [], (
            f"Driver executed forbidden tool '{forbidden_intent}': {body}"
        )
        assert body["plan_id"] is None, body

    def test_driver_allowed_intent_is_not_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Positive control: a driver-allowed intent (``driver.check_hours``)
        must NOT surface the permission-denied key."""
        client = self._build_app("driver", monkeypatch)

        resp = client.post(
            "/api/v1/copilot/chat",
            json={"utterance": "check driver hours", "language": "en"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["clarification_question_key"] != "copilot.error.permission_denied", body

    def test_dispatcher_analytics_intent_is_not_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Positive control: the SAME analytics intent is allowed for a
        dispatcher (whose §8.3 permission set includes ``analytics:read``)."""
        client = self._build_app("dispatcher", monkeypatch)

        resp = client.post(
            "/api/v1/copilot/chat",
            json={"utterance": "show me the analytics report", "language": "en"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["clarification_question_key"] != "copilot.error.permission_denied", body
