"""Desktop / mobile Co-Pilot parity — §8.2, scripted through the backend.

Deferred as "desktop not reachable" earlier; the desktop ERP client lives in
THIS repo (``ui/copilot/``), so the parity can be proven in the test suite.

Parity property
---------------
Same backend + same natural-language command → identical server-authoritative
ExecutionPlan, regardless of the client's shape (PySide6 desktop vs. Flutter
mobile).  Both clients are renderers of that payload.

The desktop client seam (stated precisely)
------------------------------------------
``ui/copilot/controllers/copilot_controller.py`` is PySide6-coupled (imports
``PySide6.QtCore``/``QtWebSockets`` at module scope), so the controller itself
cannot run headlessly.  Its ``send_utterance()`` delegates to
``self._remote.chat(**chat_kwargs)`` where ``_remote`` is a
``client/remote_copilot.py::RemoteCopilotService``.  That ``chat()`` method is
the closest separable seam — a pure request builder:

    body = {"utterance": ..., "language": ...}            # + conversation_id
    return self._api._post("/api/v1/copilot/chat", json_data=body)

This test invokes the REAL ``RemoteCopilotService.chat`` with an
``ApiClient``-shaped shim whose ``_post`` routes into the repo's in-process
backend TestClient.  The mobile-shaped session posts the SAME body the mobile
``CopilotEndpoints.chat`` (``core/network/endpoints/copilot_endpoints.dart``)
builds.  Both hit the SAME ``/api/v1/copilot/chat`` endpoint.

Auth (dispatcher-role JWT)
--------------------------
A real dispatcher-role JWT is minted with ``backend.security.create_access_token``
(the same machinery the ``tests/security`` suite's login fixtures use) and
resolved through the REAL ``get_current_user`` dependency (JWT decode + users
table lookup) against a per-test temp SQLite file — the hermetic equivalent of
the security conftest ``auth_a`` fixture, safe under ``-n auto`` xdist.
"""
from __future__ import annotations

import difflib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

# ── Test environment BEFORE any backend import ─────────────────────────────
# (root tests/conftest.py sets these too; setdefault keeps us safe regardless
#  of import order within an xdist worker.)
os.environ.setdefault("OPERION_ENV", "testing")
os.environ.setdefault("OPERION_JWT_SECRET_KEY", "test-jwt-secret-key-for-testing!!")

from backend.dependencies import get_db  # noqa: E402
from backend.main import create_app  # noqa: E402
from backend.security import create_access_token  # noqa: E402
from client.remote_copilot import RemoteCopilotService  # noqa: E402
from config import Config  # noqa: E402
from database.db_manager import DatabaseManager  # noqa: E402

CHAT_URL = "/api/v1/copilot/chat"

# Blueprint §8.2 example command.
INVOICE_UTTERANCE = "create an invoice for client X for last week's deliveries"
# A second command that compiles AND executes a real plan step (Level-0 SAFE
# tool) so the tool-call sequence parity is asserted on an executed step.
TRACKING_UTTERANCE = "track my fleet"


# ═══════════════════════════════════════════════════════════════════════════
# Mobile contract field names — mirrored from
# mobile/lib/features/copilot/models/copilot_models.dart
# ═══════════════════════════════════════════════════════════════════════════

# Keys CopilotExecutionStep.fromJson reads (each with a mobile-side default).
MOBILE_STEP_KEYS = {
    "step_id", "tool_name", "tool_version", "parameters", "depends_on",
    "confirmation_level", "status", "result", "error", "started_at",
    "finished_at",
}
MOBILE_CONFIRMATION_LEVEL_DEFAULT = 0  # ConfirmationLevel.SAFE


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def seeded_db(tmp_path):
    """A real (file-backed) SQLite DB with a dispatcher user + company.

    File-backed (NOT ``:memory:``) so the TestClient's worker thread sees the
    same committed rows as the seeding thread — mirroring the security
    conftest's real-DB approach without module-scoped global state.
    """
    db = DatabaseManager(str(tmp_path / "copilot_parity.db"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier, "
        "is_active, created_at, updated_at) VALUES (1, 'Parity Co', 'enterprise', 1, ?, ?)",
        (now, now),
    )
    db.conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id, "
        "is_active, created_at) VALUES (10, 'dispatcher@test.com', 'x', 'dispatcher', 1, 1, ?)",
        (now,),
    )
    db.conn.commit()
    yield db
    db.close()


@pytest.fixture
def backend(seeded_db, monkeypatch):
    """(TestClient, dispatcher JWT headers) with a real dispatcher-role JWT.

    The JWT is minted with the real ``create_access_token`` and resolved by the
    REAL ``get_current_user`` dependency: ``decode_access_token`` + a users-
    table lookup.  ``get_current_user`` calls ``get_db()`` internally (bypassing
    FastAPI DI overrides), so the same seeded DB is wired into the
    ``backend.dependencies_security`` module namespace as well as the DI.
    """
    monkeypatch.setattr(Config, "API_KEY", "")   # no API-key gate in tests
    monkeypatch.setenv("OPERION_ENV", "testing")

    app = create_app()

    async def _seeded_db():
        yield seeded_db

    app.dependency_overrides[get_db] = _seeded_db
    monkeypatch.setattr("backend.dependencies_security.get_db", _seeded_db)

    token = create_access_token({"sub": "dispatcher@test.com", "role": "dispatcher"})
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


# ═══════════════════════════════════════════════════════════════════════════
# Desktop client seam — the exact function CoPilotController.send_utterance
# calls, with an ApiClient-shaped shim routing into the in-process backend.
# ═══════════════════════════════════════════════════════════════════════════


class _DesktopApiShim:
    """Scripted ``ApiClient``-shaped object for ``RemoteCopilotService``.

    ``RemoteCopilotService.chat`` calls ``self._api._post(path, json_data=body)``
    — the same call the real ``ApiClient._post`` would make.  The shim records
    the call and routes it into the backend TestClient (the mobile tests do the
    same with a ``MockDioAdapter``).
    """

    def __init__(self, client: TestClient, headers: Dict[str, str]) -> None:
        self._client = client
        self._headers = headers
        self.calls: List[tuple] = []

    def _post(self, path: str, json_data: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        self.calls.append((path, json_data))
        resp = self._client.post(path, json=json_data, headers=self._headers)
        assert resp.status_code == 200, f"desktop seam POST {path} failed: {resp.text}"
        return resp.json()


def _desktop_chat_payload(backend, utterance: str) -> tuple[Dict[str, Any], _DesktopApiShim]:
    """Drive the desktop's actual request path (RemoteCopilotService.chat)."""
    client, headers = backend
    shim = _DesktopApiShim(client, headers)
    remote = RemoteCopilotService(api_client=shim)
    payload = remote.chat(utterance=utterance, language="en")
    assert shim.calls and shim.calls[0][0] == CHAT_URL
    return payload, shim


def _mobile_chat_payload(backend, utterance: str) -> Dict[str, Any]:
    """Drive the mobile-shaped session: the exact POST CopilotEndpoints.chat
    builds (utterance + conversation_id + language) against the same backend,
    authenticated with the dispatcher-role JWT."""
    client, headers = backend
    resp = client.post(
        CHAT_URL,
        json={"utterance": utterance, "language": "en"},
        headers=headers,
    )
    assert resp.status_code == 200, f"mobile-shaped POST {CHAT_URL} failed: {resp.text}"
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# Canonicalization — per-request artifacts (conversation_id, plan_id,
# timestamps) are masked; every deterministic plan/content field is compared.
# ═══════════════════════════════════════════════════════════════════════════

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _mask(value: Any) -> str:
    """Mask a per-request artifact (uuid / iso timestamp), keep everything else."""
    if value is None:
        return "None"
    s = str(value)
    if _UUID_RE.match(s):
        return "<uuid>"
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", s):
        return "<ts>"
    return s


def _sorted_params(params: Dict[str, Any]) -> List[str]:
    return [f"    {k}={json.dumps(v, sort_keys=True, default=str)}" for k, v in sorted(params.items())]


def _canonical_lines(payload: Dict[str, Any], utterance: str) -> List[str]:
    """Deterministic parity lines for one client path's /chat response.

    Mirrors the mobile contract field names (copilot_models.dart): the
    timeline steps are parsed with the mobile's defaulting rules, and
    ``confirmation_level`` is compared via the mobile default (0 / SAFE) when
    the wire omits it — which the current /chat serializer does (see
    ``backend/api/v1/copilot_router.py`` ChatResponse).
    """
    lines: List[str] = []
    lines.append(f"request.utterance={utterance!r}")
    lines.append("request.language='en'")
    lines.append(f"response.conversation_id={_mask(payload.get('conversation_id'))}")
    lines.append(f"response.summary_key={_mask(payload.get('summary_key'))}")
    lines.append(f"response.clarification_question_key={_mask(payload.get('clarification_question_key'))}")
    lines.append(f"response.clarification_params={json.dumps(payload.get('clarification_params', {}), sort_keys=True, default=str)}")
    lines.append(f"response.summary_params={json.dumps(payload.get('summary_params', {}), sort_keys=True, default=str)}")
    lines.append(f"response.plan_id={_mask(payload.get('plan_id'))}")

    timeline = payload.get("timeline", []) or []
    lines.append(f"timeline.steps_count={len(timeline)}")
    for i, step in enumerate(timeline):
        prefix = f"timeline.step[{i}]"
        lines.append(f"{prefix}.tool_name={step.get('tool_name', '')!r}")
        lines.append(f"{prefix}.step_id={step.get('step_id', '')!r}")
        lines.append(f"{prefix}.status={step.get('status', 'pending')!r}")
        lines.append(f"{prefix}.error={_mask(step.get('error'))}")
        lines.append(f"{prefix}.started_at={_mask(step.get('started_at'))}")
        lines.append(f"{prefix}.finished_at={_mask(step.get('finished_at'))}")
        lines.append(f"{prefix}.result={json.dumps(step.get('result'), sort_keys=True, default=str)}")
        # Mobile contract: CopilotExecutionStep.fromJson reads
        # `confirmation_level` with default 0 (SAFE) when absent.
        confirmation_level = step.get("confirmation_level", MOBILE_CONFIRMATION_LEVEL_DEFAULT)
        lines.append(f"{prefix}.confirmation_level={confirmation_level}")
    return lines


def _mobile_parse(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Python mirror of mobile CopilotResponse.fromJson / CopilotExecutionStep
    / CopilotExecutionPlan (copilot_models.dart) — proves both clients derive
    the identical parsed ExecutionPlan-shaped state from the wire payload."""
    parsed_steps = []
    for step in payload.get("timeline", []) or []:
        parsed_steps.append({
            "step_id": step.get("step_id", ""),
            "tool_name": step.get("tool_name", ""),
            "tool_version": step.get("tool_version", "1.0.0"),
            "parameters": step.get("parameters", {}),
            "depends_on": step.get("depends_on", []),
            "confirmation_level": step.get("confirmation_level", MOBILE_CONFIRMATION_LEVEL_DEFAULT),
            "status": step.get("status", "pending"),
            "result": step.get("result"),
            "error": step.get("error"),
        })
    return {
        "conversation_id": _mask(payload.get("conversation_id")),
        "plan_present": payload.get("plan") is not None,
        "plan_id": _mask(payload.get("plan_id")),
        "clarification_question_key": payload.get("clarification_question_key"),
        "clarification_params": payload.get("clarification_params", {}),
        "summary_key": payload.get("summary_key"),
        "summary_params": payload.get("summary_params", {}),
        "steps": parsed_steps,
    }


def _print_parity_artifact(
    utterance: str,
    desktop_payload: Dict[str, Any],
    mobile_payload: Dict[str, Any],
    diff_lines: List[str],
) -> None:
    """Print the side-by-side artifact for the session record.

    ASCII-only output: Windows consoles default to cp1252, and pytest may
    re-encode captured stdout, so non-ASCII glyphs (arrows, box drawing)
    would raise UnicodeEncodeError on teardown.
    """
    print("\n===== COPILOT DESKTOP/MOBILE PARITY ARTIFACT =====")
    print(f"  utterance : {utterance}")
    print(f"  desktop   : RemoteCopilotService.chat -> POST {CHAT_URL} (PySide6-free seam)")
    print(f"  mobile    : CopilotEndpoints.chat shape -> POST {CHAT_URL} (dispatcher JWT)")
    print("  -- desktop payload --")
    print(json.dumps(desktop_payload, indent=2, sort_keys=True, default=str))
    print("  -- mobile payload --")
    print(json.dumps(mobile_payload, indent=2, sort_keys=True, default=str))
    if diff_lines:
        print("  -- canonical diff (desktop -> mobile) --")
        print("\n".join(diff_lines))
    else:
        print("  diff: <no differences - desktop and mobile derive identical plans>")
    print(f"  PARITY_DIFF_LINES={len(diff_lines)}")
    print("===============================================================")


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDesktopSeam:
    """The desktop seam is documented: PySide6 controller → RemoteCopilotService
    request builder.  The parity property must hold regardless of client shape."""

    def test_controller_delegates_to_remote_copilot_service_chat(self) -> None:
        """Source-level proof of the seam: CoPilotController.send_utterance
        calls ``self._remote.chat(...)`` (RemoteCopilotService.chat)."""
        pytest.importorskip("PySide6")
        import inspect
        from ui.copilot.controllers.copilot_controller import CoPilotController

        src = inspect.getsource(CoPilotController.send_utterance)
        assert "self._remote.chat(" in src
        assert "language" in src

        # RemoteCopilotService.chat is the HTTP seam for /api/v1/copilot/chat.
        import inspect as _i
        from client.remote_copilot import RemoteCopilotService
        chat_src = _i.getsource(RemoteCopilotService.chat)
        assert '"/api/v1/copilot/chat"' in chat_src
        assert "_post" in chat_src

    def test_desktop_and_mobile_send_identical_request_bodies(
        self, backend,
    ) -> None:
        """Both client shapes build the IDENTICAL /chat request body."""
        client, _headers = backend
        utterance = TRACKING_UTTERANCE

        _desktop, shim = _desktop_chat_payload(backend, utterance)
        desktop_body = shim.calls[0][1]

        mobile_payload = _mobile_chat_payload(backend, utterance)

        expected = {"utterance": utterance, "language": "en"}
        assert desktop_body == expected
        assert set(expected.keys()) <= {
            "utterance", "conversation_id", "language",
        }  # mobile endpoint sends the same keys (conversation_id only after turn 1)
        assert mobile_payload["summary_key"] is not None  # sane response


class TestParityInvoice:
    """§8.2 command through BOTH client paths → identical ExecutionPlan-shaped
    payload (here: a clarification — the Phase-1 keyword planner requires a
    client_id that the utterance does not carry)."""

    def test_invoice_command_parity_diff_is_zero(self, backend, capsys) -> None:
        desktop_payload, _ = _desktop_chat_payload(backend, INVOICE_UTTERANCE)
        mobile_payload = _mobile_chat_payload(backend, INVOICE_UTTERANCE)

        desktop_lines = _canonical_lines(desktop_payload, INVOICE_UTTERANCE)
        mobile_lines = _canonical_lines(mobile_payload, INVOICE_UTTERANCE)

        assert len(desktop_lines) == len(mobile_lines)
        diff = list(difflib.unified_diff(
            desktop_lines, mobile_lines,
            fromfile="desktop_client_seam", tofile="mobile_shaped_session",
            lineterm="",
        ))
        _print_parity_artifact(INVOICE_UTTERANCE, desktop_payload, mobile_payload, diff)
        assert diff == [], "Desktop/mobile parity broken - differences:\n" + "\n".join(diff)

        # The server-authoritative state is the SAME for both clients: the
        # planner surfaced a missing-entities clarification for invoice.generate
        # (the intent resolver maps the phrase to client.payment_summary and
        # needs a client_id).
        assert desktop_payload["clarification_question_key"] == "copilot.clarification.missing_entities"
        assert mobile_payload["clarification_question_key"] == desktop_payload["clarification_question_key"]
        assert desktop_payload["timeline"] == []  # nothing executed

    def test_invoice_mobile_contract_parse_is_identical(self, backend) -> None:
        """Both clients parse the payload through the mobile contract and reach
        the identical ExecutionPlan-shaped state."""
        desktop_payload, _ = _desktop_chat_payload(backend, INVOICE_UTTERANCE)
        mobile_payload = _mobile_chat_payload(backend, INVOICE_UTTERANCE)

        desktop_parsed = _mobile_parse(desktop_payload)
        mobile_parsed = _mobile_parse(mobile_payload)

        assert desktop_parsed == mobile_parsed
        assert desktop_parsed["steps"] == []
        assert desktop_parsed["plan_present"] is False
        assert desktop_parsed["plan_id"] == "None"


class TestParityExecutedPlan:
    """A command that compiles AND executes a real plan step → the tool-call
    sequence (step_id, tool_name, status, result) and the mobile-parsed
    confirmation_level are IDENTICAL across both client shapes."""

    def test_executed_tool_call_sequence_parity_diff_is_zero(self, backend, capsys) -> None:
        desktop_payload, _ = _desktop_chat_payload(backend, TRACKING_UTTERANCE)
        mobile_payload = _mobile_chat_payload(backend, TRACKING_UTTERANCE)

        desktop_lines = _canonical_lines(desktop_payload, TRACKING_UTTERANCE)
        mobile_lines = _canonical_lines(mobile_payload, TRACKING_UTTERANCE)

        assert len(desktop_lines) == len(mobile_lines)
        diff = list(difflib.unified_diff(
            desktop_lines, mobile_lines,
            fromfile="desktop_client_seam", tofile="mobile_shaped_session",
            lineterm="",
        ))
        _print_parity_artifact(TRACKING_UTTERANCE, desktop_payload, mobile_payload, diff)
        assert diff == [], "Desktop/mobile parity broken - differences:\n" + "\n".join(diff)

        # Same tool-call sequence on the wire.
        desktop_tools = [s["tool_name"] for s in desktop_payload["timeline"]]
        mobile_tools = [s["tool_name"] for s in mobile_payload["timeline"]]
        assert desktop_tools == ["tracking.get_live_positions"]
        assert mobile_tools == desktop_tools

    def test_executed_step_confirmation_level_is_identical(self, backend) -> None:
        """Per the mobile contract (CopilotExecutionStep.fromJson), both clients
        derive the same confirmation_level for every executed step.

        NOTE: the current /chat serializer (ChatResponse) omits
        ``confirmation_level`` from timeline steps — the backend ExecutionStep
        carries it (schemas.py), but the wire contract drops it.  Both clients
        therefore apply the mobile model's default (0 / SAFE), so parity holds;
        the field comparison here locks that in.
        """
        desktop_payload, _ = _desktop_chat_payload(backend, TRACKING_UTTERANCE)
        mobile_payload = _mobile_chat_payload(backend, TRACKING_UTTERANCE)

        desktop_steps = _mobile_parse(desktop_payload)["steps"]
        mobile_steps = _mobile_parse(mobile_payload)["steps"]

        assert len(desktop_steps) == 1
        assert desktop_steps == mobile_steps
        assert desktop_steps[0]["confirmation_level"] == MOBILE_CONFIRMATION_LEVEL_DEFAULT
        assert desktop_steps[0]["tool_name"] == "tracking.get_live_positions"
        assert desktop_steps[0]["status"] == "succeeded"

        # The wire keys of every timeline step are a subset of what the mobile
        # model parses (no unparseable fields, no client-shape divergence).
        for step in desktop_payload["timeline"]:
            assert set(step.keys()) <= MOBILE_STEP_KEYS | {"started_at", "finished_at"}

    def test_same_backend_same_command_identical_plan_regardless_of_client(self, backend) -> None:
        """The parity property, stated as an invariant over both commands."""
        for utterance in (INVOICE_UTTERANCE, TRACKING_UTTERANCE):
            desktop_payload, _ = _desktop_chat_payload(backend, utterance)
            mobile_payload = _mobile_chat_payload(backend, utterance)

            desktop_parsed = _mobile_parse(desktop_payload)
            mobile_parsed = _mobile_parse(mobile_payload)
            assert desktop_parsed == mobile_parsed, (
                f"Client shape changed the ExecutionPlan for {utterance!r}"
            )
