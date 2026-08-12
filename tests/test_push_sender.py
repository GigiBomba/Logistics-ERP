"""Tests for the FCM PushSender (Gate-31).

firebase-admin is not installed in the dev/test environment, so these tests
install a fake ``firebase_admin`` package (real exception classes + a
``MulticastMessage`` that captures its kwargs) and exercise the sender against
mocked ``firebase_admin.messaging``.  The lazy-import design is what makes
this possible — the module itself never imports firebase-admin at import time.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services.operations.push_sender import BATCH_SIZE, PushSender


# ── Fake firebase_admin plumbing ─────────────────────────────────────────

class _UnregisteredError(Exception):
    pass


class _InvalidArgumentError(Exception):
    pass


class _UnavailableError(Exception):
    pass


class _InternalError(Exception):
    pass


class _SendResponse:
    def __init__(self, success=True, exception=None):
        self.success = success
        self.exception = exception


class _BatchResponse:
    def __init__(self, responses):
        self.responses = responses


@pytest.fixture
def fake_firebase():
    """Install a fake ``firebase_admin`` package into sys.modules.

    Yields a namespace with the fake ``firebase_admin`` package, the mocked
    ``firebase_admin.messaging`` module and the mocked ``credentials`` module.
    The messaging error classes are REAL ``Exception`` subclasses so the
    sender's ``except`` clauses behave exactly as with the real SDK.
    """
    messaging = MagicMock(name="firebase_admin.messaging")
    messaging.UnregisteredError = _UnregisteredError
    messaging.InvalidArgumentError = _InvalidArgumentError
    messaging.UnavailableError = _UnavailableError
    messaging.InternalError = _InternalError
    # Capture the kwargs the sender passes to MulticastMessage so tests can
    # assert the payload/tokens directly.
    messaging.MulticastMessage = lambda **kwargs: SimpleNamespace(**kwargs)

    credentials = MagicMock(name="firebase_admin.credentials")
    credentials.Certificate.return_value = object()

    firebase_admin = MagicMock(name="firebase_admin")
    firebase_admin.messaging = messaging
    firebase_admin.credentials = credentials

    installed = {
        "firebase_admin": firebase_admin,
        "firebase_admin.messaging": messaging,
        "firebase_admin.credentials": credentials,
    }
    saved = {name: sys.modules.get(name) for name in installed}
    sys.modules.update(installed)
    try:
        yield SimpleNamespace(
            firebase_admin=firebase_admin, messaging=messaging, credentials=credentials
        )
    finally:
        for name, mod in installed.items():
            if saved[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved[name]


@pytest.fixture
def sender(tmp_path, monkeypatch, fake_firebase):
    """An ENABLED PushSender (real credentials file, faked firebase package)."""
    creds = tmp_path / "firebase-service-account.json"
    creds.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPERION_FIREBASE_CREDENTIALS", str(creds))
    return PushSender(notification_center=None)


def _mock_db(tokens):
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [{"token": t} for t in tokens]
    return db


# ── Payload contract ─────────────────────────────────────────────────────

def test_payload_shape_matches_contract():
    sender = PushSender()
    payload = sender._build_payload(
        "alert_created",
        {"id": "alert-42", "title": "Tacho expiry", "message": "Driver card expires soon"},
        "alert-42",
    )
    assert set(payload.keys()) == {"type", "alert_id", "title", "message", "message_id"}
    assert payload["type"] == "alert"
    assert payload["alert_id"] == "alert-42"
    assert payload["title"] == "Tacho expiry"
    assert payload["message"] == "Driver card expires soon"
    assert payload["message_id"].startswith("alert-42-")


def test_approval_payload_type():
    sender = PushSender()
    payload = sender._build_payload(
        "alert_created",
        {"id": "a9", "type": "approval", "title": "Approve", "message": "150 EUR"},
        "a9",
    )
    assert payload["type"] == "approval"
    assert payload["alert_id"] == "a9"


def test_message_id_uniqueness():
    sender = PushSender()
    ids = {sender._new_message_id("a1") for _ in range(20)}
    assert len(ids) == 20
    assert all(i.startswith("a1-") for i in ids)


# ── Batching / delivery ──────────────────────────────────────────────────

def test_multicast_token_batching(sender, fake_firebase):
    tokens = [f"tok-{i}" for i in range(BATCH_SIZE * 2 + 200)]  # 500 + 500 + 200
    sender._db = _mock_db(tokens)
    fake_firebase.messaging.send_each_for_multicast.return_value = _BatchResponse(
        [_SendResponse(True)] * len(tokens)
    )

    sender._dispatch_alert("alert_created", {"id": "a1", "title": "T", "message": "M"})

    calls = fake_firebase.messaging.send_each_for_multicast.call_args_list
    assert len(calls) == 3
    for call, expected_size in zip(calls, (BATCH_SIZE, BATCH_SIZE, 200)):
        msg = call.args[0]
        assert len(msg.tokens) == expected_size
        assert msg.data["type"] == "alert"
        assert msg.data["alert_id"] == "a1"
        assert msg.data["message_id"].startswith("a1-")


def test_company_scoped_token_query(sender, fake_firebase):
    db = _mock_db(["tok-1"])
    sender._db = db
    fake_firebase.messaging.send_each_for_multicast.return_value = _BatchResponse(
        [_SendResponse(True)]
    )

    sender._dispatch_alert(
        "alert_created", {"id": "a1", "metadata": {"company_id": 7}, "title": "T", "message": "M"}
    )

    select = [c for c in db.execute.call_args_list if "SELECT token" in c.args[0]]
    assert len(select) == 1
    assert select[0].args[0].endswith("company_id = ?")
    assert select[0].args[1] == (7,)


# ── Token cleanup ────────────────────────────────────────────────────────

def test_token_deactivation_on_unregistered(sender, fake_firebase):
    tokens = ["tok-0", "tok-1", "tok-2"]
    db = _mock_db(tokens)
    sender._db = db
    fake_firebase.messaging.send_each_for_multicast.return_value = _BatchResponse([
        _SendResponse(True),
        _SendResponse(False, _UnregisteredError("unregistered")),
        _SendResponse(False, _InvalidArgumentError("invalid")),
    ])

    sender._dispatch_alert("alert_created", {"id": "a1", "title": "T", "message": "M"})

    updates = [c for c in db.execute.call_args_list if "UPDATE mobile_devices" in c.args[0]]
    assert len(updates) == 1
    assert "tok-1" in updates[0].args[1]
    assert "tok-2" in updates[0].args[1]
    assert "tok-0" not in updates[0].args[1]
    db.commit.assert_called()


# ── Retry / backoff ──────────────────────────────────────────────────────

def test_retry_count_on_transient(sender, fake_firebase):
    sender._retry_delays = [0.0, 0.0, 0.0]
    sender._db = _mock_db(["tok-1"])
    err = _UnavailableError("boom")
    fake_firebase.messaging.send_each_for_multicast.side_effect = [
        err, err, err, _BatchResponse([_SendResponse(True)]),
    ]

    with patch("time.sleep") as mock_sleep:
        sender._dispatch_alert("alert_created", {"id": "a1", "title": "T", "message": "M"})

    # initial attempt + 3 retries
    assert fake_firebase.messaging.send_each_for_multicast.call_count == 4
    assert mock_sleep.call_count == 3


# ── No-credentials no-op ─────────────────────────────────────────────────

def test_no_creds_is_noop(monkeypatch, fake_firebase):
    monkeypatch.delenv("OPERION_FIREBASE_CREDENTIALS", raising=False)
    sender = PushSender()
    assert sender.enabled is False
    fake_firebase.firebase_admin.initialize_app.assert_not_called()
    # dispatching through a disabled sender must never touch messaging
    sender._on_alert_event("alert_created", {"id": "a1", "title": "T", "message": "M"})
    fake_firebase.messaging.send_each_for_multicast.assert_not_called()


def test_disabled_sender_does_not_subscribe(monkeypatch, fake_firebase):
    monkeypatch.delenv("OPERION_FIREBASE_CREDENTIALS", raising=False)
    nc = MagicMock()
    sender = PushSender(notification_center=nc)
    assert sender.enabled is False
    assert sender._subscribed is False
    nc.subscribe.assert_not_called()


# ── Event subscription ───────────────────────────────────────────────────

def test_event_subscription_drives_send(tmp_path, monkeypatch, fake_firebase):
    creds = tmp_path / "firebase-service-account.json"
    creds.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPERION_FIREBASE_CREDENTIALS", str(creds))

    nc = MagicMock()
    sender = PushSender(notification_center=nc)
    assert sender.enabled is True
    assert sender._subscribed is True
    nc.subscribe.assert_called_once_with(sender._on_alert_event)

    sender._db = _mock_db(["tok-1"])
    fake_firebase.messaging.send_each_for_multicast.return_value = _BatchResponse(
        [_SendResponse(True)]
    )

    # Simulate NotificationCenter calling its in-process subscribers.
    sender._on_alert_event("alert_created", {"id": "a1", "title": "T", "message": "M"})

    assert fake_firebase.messaging.send_each_for_multicast.called
    msg = fake_firebase.messaging.send_each_for_multicast.call_args.args[0]
    assert msg.data["alert_id"] == "a1"
    assert msg.data["message_id"].startswith("a1-")
