"""Co-Pilot authentication tests — §15 (§27.3 ``tests/copilot/test_authentication.py``).

Every endpoint (including the WebSocket handshake) must reject missing,
malformed and expired JWTs; a valid token for one company must never reach
another company's conversation; permission revocation must take effect on the
very next request; and the §26 admin kill-switch + §16 tier-gated endpoints
enforce their own authz/tier boundaries on real (decoded) JWTs.

Patterns follow ``tests/test_api/test_copilot_router.py`` (TestClient +
dependency overrides) and ``tests/security/test_auth*.py`` (real JWTs via
``create_access_token`` / ``decode_access_token`` against the same secret).
"""
from __future__ import annotations

import os
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

# Fixed JWT secret so create/decode stay consistent for this module, no matter
# what other modules (e.g. tests/security) set for their own runs.
os.environ["OPERION_JWT_SECRET_KEY"] = "test-auth-secret-key-0123456789abcdef0123456789abcdef"
# The env-admin identity path is not used by these tests — the DB-backed
# user lookup covers both normal and admin roles via the mocked user row.
os.environ.pop("OPERION_ADMIN_EMAIL", None)

from backend.dependencies import get_db  # noqa: E402
from backend.dependencies_security import get_current_user  # noqa: E402
from backend.security import create_access_token  # noqa: E402
from backend.copilot.schemas import CoPilotResponse  # noqa: E402

BASE = "/api/v1/copilot"


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    from fastapi import FastAPI

    from backend.api.v1.router import api_v1_router

    app = FastAPI()
    app.include_router(api_v1_router)
    return app


@pytest.fixture(autouse=True)
def _cleanup_copilot_state():
    """Clear in-memory copilot state between tests."""
    import backend.api.v1.copilot_router as cr

    cr._pending_plans.clear()
    cr._plan_owners.clear()
    cr._company_conversations.clear()
    cr._ws_connections.clear()
    yield


@pytest.fixture(autouse=True)
def _patch_cache():
    """Deterministic no-kill-switch cache; tests may re-configure the mock."""
    mock_cache = MagicMock()
    mock_cache.get.return_value = None  # no kill switch, no quota usage
    with patch("backend.cache.get_cache", return_value=mock_cache):
        yield mock_cache


@pytest.fixture
def mock_db():
    """Mock DatabaseManager: ``get_current_user`` reads ``fetchone()``; repo
    reads ``fetchall()`` / ``rowcount``."""
    db = MagicMock(spec_set=["conn", "execute", "row_to_dict", "rows_to_dicts"])
    db.conn = MagicMock()
    db.row_to_dict = lambda row: row
    db.rows_to_dicts = lambda rows: rows
    db.execute = db.conn.execute
    db.execute.return_value.fetchall.return_value = []
    db.execute.return_value.fetchone.return_value = None
    db.execute.return_value.rowcount = 1
    db.execute.return_value.lastrowid = 1
    return db


@pytest.fixture
def client(app, mock_db):
    """TestClient where ``get_db`` yields the mock DB for BOTH the router and
    ``get_current_user``.

    ``get_current_user`` calls ``get_db()`` directly (it is not a FastAPI
    dependency injection there), so the module-level name in
    ``backend.dependencies_security`` must be patched too — the
    ``dependency_overrides`` entry alone only reaches the router handlers.
    """

    async def _fake_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _fake_get_db
    with patch("backend.dependencies_security.get_db", new=_fake_get_db):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_db
    app.dependency_overrides.clear()


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_token(email: str = "user@test.com", role: str = "dispatcher",
                company_id: int = 1, tier: str = "business",
                expires: timedelta | None = None) -> str:
    return create_access_token(
        {
            "sub": email,
            "role": role,
            "company_id": company_id,
            "subscription_tier": tier,
        },
        expires_delta=expires,
    )


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user_row(email: str = "user@test.com", role: str = "dispatcher",
              company_id: int = 1, tier: str = "business") -> dict:
    return {
        "id": 10,
        "email": email,
        "role": role,
        "company_id": company_id,
        "company_name": "TestCo",
        "subscription_tier": tier,
    }


def _set_user(mock_db, row: dict) -> None:
    mock_db.execute.return_value.fetchone.return_value = row


# ═══════════════════════════════════════════════════════════════════════════
# JWT rejection — chat / voice / insights / WebSocket handshake (§15.1)
# ═══════════════════════════════════════════════════════════════════════════

class TestJwtRejection:
    """Endpoints reject missing / malformed / expired JWTs with 401."""

    @pytest.mark.parametrize(
        "method, path, body",
        [
            ("post", f"{BASE}/chat", {"utterance": "show trucks"}),
            ("post", f"{BASE}/voice", {"utterance": "where is truck 1"}),
            ("get", f"{BASE}/insights", None),
        ],
    )
    def test_missing_token_rejected(self, app, method, path, body):
        client = TestClient(app)
        resp = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
        assert resp.status_code == 401, resp.text

    @pytest.mark.parametrize(
        "method, path, body",
        [
            ("post", f"{BASE}/chat", {"utterance": "show trucks"}),
            ("post", f"{BASE}/voice", {"utterance": "where is truck 1"}),
            ("get", f"{BASE}/insights", None),
        ],
    )
    def test_malformed_token_rejected(self, app, method, path, body):
        client = TestClient(app)
        resp = getattr(client, method)(
            path, json=body, headers=_auth("not.a.valid.jwt")
        ) if body else getattr(client, method)(path, headers=_auth("not.a.valid.jwt"))
        assert resp.status_code == 401, resp.text

    def test_expired_token_rejected(self, app):
        client = TestClient(app)
        expired = _make_token(expires=timedelta(seconds=-60))
        resp = client.post(
            f"{BASE}/chat",
            json={"utterance": "show trucks"},
            headers=_auth(expired),
        )
        assert resp.status_code == 401, resp.text

    def test_websocket_missing_token_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client[0].websocket_connect(f"{BASE}/ws/conv-no-token"):
                pass
        assert exc_info.value.code == 4001

    def test_websocket_malformed_token_rejected(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client[0].websocket_connect(
                f"{BASE}/ws/conv-bad?token=not.a.valid.jwt"
            ):
                pass
        assert exc_info.value.code == 4001

    def test_websocket_valid_token_connects(self, client, mock_db):
        _set_user(mock_db, _user_row(company_id=1))
        token = _make_token(company_id=1)
        with client[0].websocket_connect(f"{BASE}/ws/conv-ok?token={token}") as ws:
            data = ws.receive_json()
        assert data["type"] == "connected"


# ═══════════════════════════════════════════════════════════════════════════
# Cross-company conversation isolation (§15.1)
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossCompanyIsolation:
    """A valid token for company B cannot reach company A's conversation."""

    def _store_plan(self, plan_id: str, owner_company: int) -> None:
        import backend.api.v1.copilot_router as cr
        from backend.copilot.schemas import (
            ConfirmationLevel, ExecutionPlan, ExecutionStep, Intent,
        )

        cr._pending_plans[plan_id] = ExecutionPlan(
            plan_id=plan_id,
            conversation_id=f"conv-{plan_id}",
            reasoning_graph_id=f"rg-{plan_id}",
            intent=Intent(
                name="vehicle.search", entities=[],
                missing_required_entities=[], raw_utterance="show trucks",
            ),
            steps=[ExecutionStep(
                step_id="step-0", tool_name="vehicle.search", tool_version="1.0.0",
                parameters={}, depends_on=[],
                confirmation_level=ConfirmationLevel.SAFE, status="pending",
            )],
            overall_confidence=0.95,
            requires_confirmation=True,
        )
        cr._plan_owners[plan_id] = owner_company
        cr._company_conversations.setdefault(owner_company, set()).add(plan_id)

    def test_company_b_cannot_cancel_company_a_plan(self, client, mock_db):
        self._store_plan("plan-secret", owner_company=1)
        _set_user(mock_db, _user_row(email="b@test.com", company_id=2))

        resp = client[0].post(f"{BASE}/plans/plan-secret/cancel",
                              headers=_auth(_make_token(email="b@test.com", company_id=2)))

        assert resp.status_code == 403
        assert resp.json()["detail"]["message_key"] == "copilot.plan.not_owned"

    def test_company_b_cannot_confirm_company_a_plan(self, client, mock_db):
        self._store_plan("plan-secret-confirm", owner_company=1)
        _set_user(mock_db, _user_row(email="b@test.com", company_id=2))

        resp = client[0].post(f"{BASE}/plans/plan-secret-confirm/confirm",
                              headers=_auth(_make_token(email="b@test.com", company_id=2)))

        assert resp.status_code == 403
        assert resp.json()["detail"]["message_key"] == "copilot.plan.not_owned"

    def test_owner_company_can_cancel_own_plan(self, client, mock_db):
        self._store_plan("plan-own", owner_company=1)
        _set_user(mock_db, _user_row(company_id=1))
        with patch("backend.copilot.executor.cancel_plan") as mock_cancel:
            from backend.copilot.schemas import ExecutionPlan
            mock_cancel.return_value = MagicMock(spec=ExecutionPlan)

            resp = client[0].post(f"{BASE}/plans/plan-own/cancel",
                                  headers=_auth(_make_token(company_id=1)))

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


# ═══════════════════════════════════════════════════════════════════════════
# Mid-session permission revocation (§15.2)
# ═══════════════════════════════════════════════════════════════════════════

class TestMidSessionRevocation:
    """Revocation takes effect on the very next request — no caching lag."""

    def test_deactivated_user_rejected_on_next_request(self, client, mock_db):
        row = _user_row(email="revoke@test.com")
        mock_db.execute.return_value.fetchone.side_effect = [row, None]

        with patch("backend.api.v1.copilot_router.process_utterance") as mock_process:
            mock_process.return_value = CoPilotResponse(
                conversation_id="conv-1",
                summary_key="copilot.summary.vehicle.search",
                summary_params={},
            )
            token = _make_token(email="revoke@test.com")

            first = client[0].post(
                f"{BASE}/chat", json={"utterance": "show trucks"}, headers=_auth(token),
            )
            # User is deactivated between the two requests → the SAME token is
            # rejected because the user row is no longer active.
            second = client[0].post(
                f"{BASE}/chat", json={"utterance": "show trucks"}, headers=_auth(token),
            )

        assert first.status_code == 200
        assert second.status_code == 401

    def test_jwt_role_claim_does_not_override_db_role(self, client, mock_db):
        """A JWT claiming role='admin' is not trusted — the DB role wins, so
        the admin kill-switch endpoint still rejects the call."""
        _set_user(mock_db, _user_row(email="impersonator@test.com", role="dispatcher"))

        token = create_access_token({
            "sub": "impersonator@test.com",
            "role": "admin",  # forged claim
            "company_id": 1,
            "subscription_tier": "business",
        })
        resp = client[0].post(
            f"{BASE}/admin/kill-switch",
            json={"enable": True, "scope": "company", "company_id": 1},
            headers=_auth(token),
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Admin kill-switch endpoint (§26)
# ═══════════════════════════════════════════════════════════════════════════

class TestAdminKillSwitch:
    """POST /copilot/admin/kill-switch is admin-only."""

    def test_non_admin_jwt_rejected(self, client, mock_db):
        _set_user(mock_db, _user_row(role="dispatcher"))
        resp = client[0].post(
            f"{BASE}/admin/kill-switch",
            json={"enable": True, "scope": "company", "company_id": 1},
            headers=_auth(_make_token(role="dispatcher")),
        )
        assert resp.status_code == 403

    def test_admin_jwt_allowed(self, client, mock_db):
        _set_user(mock_db, _user_row(role="admin"))
        resp = client[0].post(
            f"{BASE}/admin/kill-switch",
            json={"enable": True, "scope": "company", "company_id": 1},
            headers=_auth(_make_token(role="admin")),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scope"] == "company"
        assert body["company_id"] == 1
        assert body["enabled"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Tier gating (§16) — below-tier companies rejected, admins bypass
# ═══════════════════════════════════════════════════════════════════════════

class TestTierGating:
    """Tier-gated endpoints reject below-tier companies with i18n keys."""

    def test_starter_tier_chat_help_only_mode(self, client, mock_db):
        """Tiers without ``chat`` but with ``help_mode`` (starter/pro) get
        help-only chat (§33.4, §21 Ph1 item 3): /chat is allowed, and a
        non-help utterance returns ``copilot.error.help_only_tier`` (200)
        instead of a 403 — help requests are answered."""
        _set_user(mock_db, _user_row(tier="starter"))
        resp = client[0].post(
            f"{BASE}/chat",
            json={"utterance": "show trucks"},
            headers=_auth(_make_token(tier="starter")),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("clarification_question_key") == "copilot.error.help_only_tier"

    def test_pro_tier_voice_rejected(self, client, mock_db):
        _set_user(mock_db, _user_row(tier="pro"))
        resp = client[0].post(
            f"{BASE}/voice",
            json={"utterance": "show trucks"},
            headers=_auth(_make_token(tier="pro")),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["message_key"] == "copilot.error.feature_not_in_tier"

    def test_business_tier_insights_rejected(self, client, mock_db):
        """background_monitoring is Enterprise-only."""
        _set_user(mock_db, _user_row(tier="business"))
        resp = client[0].get(
            f"{BASE}/insights",
            headers=_auth(_make_token(tier="business")),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["message_key"] == "copilot.error.feature_not_in_tier"

    def test_enterprise_tier_insights_allowed(self, client, mock_db):
        _set_user(mock_db, _user_row(tier="enterprise"))
        resp = client[0].get(
            f"{BASE}/insights",
            headers=_auth(_make_token(tier="enterprise")),
        )
        assert resp.status_code == 200

    def test_business_tier_chat_allowed_when_quota_ok(self, client, mock_db):
        _set_user(mock_db, _user_row(tier="business"))
        with patch("backend.api.v1.copilot_router.process_utterance") as mock_process:
            mock_process.return_value = CoPilotResponse(
                conversation_id="conv-biz",
                summary_key="copilot.summary.vehicle.search",
                summary_params={},
            )
            resp = client[0].post(
                f"{BASE}/chat",
                json={"utterance": "show trucks"},
                headers=_auth(_make_token(tier="business")),
            )
        assert resp.status_code == 200
        assert resp.json()["conversation_id"] == "conv-biz"

    def test_business_tier_quota_exceeded_rejected(self, client, mock_db, _patch_cache):
        """Business monthly quota (300) exhausted → 429 quota_exceeded."""
        _set_user(mock_db, _user_row(tier="business"))
        _patch_cache.get.return_value = 300  # usage == monthly_quota

        resp = client[0].post(
            f"{BASE}/chat",
            json={"utterance": "show trucks"},
            headers=_auth(_make_token(tier="business")),
        )
        assert resp.status_code == 429
        assert resp.json()["detail"]["message_key"] == "copilot.error.quota_exceeded"

    def test_admin_bypasses_tier_gate(self, client, mock_db):
        _set_user(mock_db, _user_row(role="admin", tier="starter"))
        with patch("backend.api.v1.copilot_router.process_utterance") as mock_process:
            mock_process.return_value = CoPilotResponse(
                conversation_id="conv-admin",
                summary_key="copilot.summary.vehicle.search",
                summary_params={},
            )
            resp = client[0].post(
                f"{BASE}/chat",
                json={"utterance": "show trucks"},
                headers=_auth(_make_token(role="admin", tier="starter")),
            )
        assert resp.status_code == 200