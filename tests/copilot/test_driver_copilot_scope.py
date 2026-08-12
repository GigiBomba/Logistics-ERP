"""Driver Co-Pilot scope — hermetic real-JWT proof (§8.3 boundary).

Drives ``POST /api/v1/copilot/chat`` with a REAL driver-role JWT (minted with
``backend.security.create_access_token`` and resolved through the real
``get_current_user`` dependency against a seeded temp SQLite users table — the
same hermetic pattern as ``test_desktop_mobile_parity.py``).

(a) a driver-permitted intent (``tracking.get_live_positions``) returns HTTP
    200 (NOT 403) and every executed tool is a SUBSET of the driver's
    permitted tools derived from ``DRIVER_TOOL_PERMISSIONS``;
(b) a driver asking for a forbidden capability (analytics / invoicing) gets a
    clarification question (``copilot.error.permission_denied``) — NOT 403 and
    NOT execution (empty timeline, no plan id).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Tuple

import pytest
from fastapi.testclient import TestClient

# ── Test environment BEFORE any backend import ─────────────────────────────
# (root tests/conftest.py sets these too; setdefault keeps us safe regardless
#  of import order within an xdist worker.)
os.environ.setdefault("OPERION_ENV", "testing")
os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing!!")

from backend.copilot.context import resolve_available_tools  # noqa: E402
from backend.copilot.role_permissions import DRIVER_TOOL_PERMISSIONS  # noqa: E402
from backend.copilot.schemas import GlobalContext  # noqa: E402
from backend.dependencies import get_db  # noqa: E402
from backend.main import create_app  # noqa: E402
from backend.security import create_access_token  # noqa: E402
from config import Config  # noqa: E402
from database.db_manager import DatabaseManager  # noqa: E402

CHAT_URL = "/api/v1/copilot/chat"

FORBIDDEN_UTTERANCES = [
    # analytics — requires analytics:read (excluded from DRIVER_TOOL_PERMISSIONS)
    "show me the analytics report",
    # invoicing — maps to client.payment_summary (requires clients:read)
    "create an invoice for client X for last week's deliveries",
]


@pytest.fixture
def driver_db(tmp_path):
    """A real (file-backed) SQLite DB with a DRIVER user + company.

    File-backed (NOT ``:memory:``) so the TestClient's worker thread sees the
    same committed rows as the seeding thread.
    """
    db = DatabaseManager(str(tmp_path / "copilot_driver.db"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier, "
        "is_active, created_at, updated_at) VALUES (1, 'Driver Co', 'enterprise', 1, ?, ?)",
        (now, now),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id, "
        "is_active, created_at) VALUES (10, 'driver@test.com', 'x', 'driver', 1, 1, ?)",
        (now,),
    )
    db.conn.commit()
    yield db
    db.close()


@pytest.fixture
def driver_backend(driver_db, monkeypatch) -> Tuple[TestClient, Dict[str, str]]:
    """(TestClient, driver JWT headers) with a real driver-role JWT.

    The JWT is minted with the real ``create_access_token`` and resolved by the
    REAL ``get_current_user`` dependency (decode + users-table lookup).  The
    same DB is wired into the DI and the ``dependencies_security`` module
    namespace.
    """
    monkeypatch.setattr(Config, "API_KEY", "")  # no API-key gate in tests
    monkeypatch.setenv("OPERION_ENV", "testing")

    app = create_app()

    async def _seeded_db():
        yield driver_db

    app.dependency_overrides[get_db] = _seeded_db
    monkeypatch.setattr("backend.dependencies_security.get_db", _seeded_db)

    token = create_access_token({"sub": "driver@test.com", "role": "driver"})
    headers = {"Authorization": f"Bearer {token}"}

    client = TestClient(app, raise_server_exceptions=False)
    return client, headers


@pytest.fixture(autouse=True)
def _cleanup_copilot_state():
    """Clear in-process copilot state so runs do not pollute each other."""
    import backend.api.v1.copilot_router as cr

    cr._pending_plans.clear()
    cr._plan_owners.clear()
    cr._company_conversations.clear()
    cr._ws_connections.clear()
    yield


def _driver_permitted_tools() -> set:
    """The server-authoritative permitted tool set for a driver session —
    derived the same way the /chat handler derives it (resolve_available_tools
    ∩ DRIVER_TOOL_PERMISSIONS)."""
    ctx = GlobalContext(
        company_id=1, user_id=10, role="driver", language="en",
        timezone="UTC", subscription_tier="enterprise",
    )
    tool_ctx = asyncio.run(resolve_available_tools(ctx, DRIVER_TOOL_PERMISSIONS))
    return set(tool_ctx.available_tools)


class TestDriverCopilotScope:
    def test_driver_chat_returns_200_not_403(self, driver_backend) -> None:
        """(a) A driver-role JWT is AUTHORIZED for /copilot/chat (200, not 403)."""
        client, headers = driver_backend
        resp = client.post(
            CHAT_URL,
            json={"utterance": "track my fleet", "language": "en"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    def test_driver_permitted_tool_set_is_subset_of_driver_permissions(
        self, driver_backend,
    ) -> None:
        """(a) Every tool a driver actually executes is within the
        DRIVER_TOOL_PERMISSIONS-derived permitted set."""
        client, headers = driver_backend
        resp = client.post(
            CHAT_URL,
            json={"utterance": "track my fleet", "language": "en"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        timeline_tools = {s["tool_name"] for s in body.get("timeline", [])}
        assert timeline_tools, f"expected a permitted tool to execute: {body}"
        permitted = _driver_permitted_tools()
        assert timeline_tools <= permitted, (
            f"Driver executed tools outside its permitted set: "
            f"{sorted(timeline_tools - permitted)}"
        )

    @pytest.mark.parametrize("utterance", FORBIDDEN_UTTERANCES)
    def test_driver_forbidden_capability_yields_clarification_not_execution(
        self, driver_backend, utterance: str,
    ) -> None:
        """(b) A driver asking for analytics/invoicing gets a clarification
        question — NOT 403, NOT execution (empty timeline, no plan id)."""
        client, headers = driver_backend
        resp = client.post(
            CHAT_URL,
            json={"utterance": utterance, "language": "en"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text  # NOT 403
        body = resp.json()

        assert body["clarification_question_key"] is not None, body
        assert body["timeline"] == [], body  # nothing executed
        assert body["plan_id"] is None, body

    def test_driver_analytics_intent_is_permission_denied(self, driver_backend) -> None:
        """The analytics intent is pinned to the permission-denied key."""
        client, headers = driver_backend
        resp = client.post(
            CHAT_URL,
            json={"utterance": "show me the analytics report", "language": "en"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["clarification_question_key"] == "copilot.error.permission_denied", body
        assert body["clarification_params"]["intent"] == "analytics.query"
        assert body["clarification_params"]["role"] == "driver"
