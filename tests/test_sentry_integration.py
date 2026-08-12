"""Sentry integration tests (Gate-31) — no-op behaviour without OPERION_SENTRY_DSN.

sentry-sdk is not installed in the dev/test environment, so ``sentry_sdk`` is
stubbed via ``sys.modules`` to assert the gating logic: init is skipped without
a DSN, called with the right options when a DSN is set, and ``capture_exception``
is a strict no-op when the SDK is absent / not initialised.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from backend.main import _capture_exception, _init_sentry


@pytest.fixture
def fake_sentry():
    """Install a fake ``sentry_sdk`` module into sys.modules (removed after)."""
    sentry_sdk = MagicMock(name="sentry_sdk")
    sentry_sdk.get_client.return_value.is_enabled.return_value = True
    installed = {"sentry_sdk": sentry_sdk}
    saved = sys.modules.get("sentry_sdk")
    sys.modules["sentry_sdk"] = sentry_sdk
    try:
        yield sentry_sdk
    finally:
        if saved is None:
            sys.modules.pop("sentry_sdk", None)
        else:
            sys.modules["sentry_sdk"] = saved


def test_init_sentry_skipped_without_dsn(monkeypatch, fake_sentry):
    monkeypatch.delenv("OPERION_SENTRY_DSN", raising=False)
    _init_sentry()
    fake_sentry.init.assert_not_called()


def test_init_sentry_called_with_dsn(monkeypatch, fake_sentry):
    monkeypatch.setenv("OPERION_SENTRY_DSN", "https://example@ingest.operionerp.xyz/1")
    monkeypatch.setenv("OPERION_ENV", "staging")
    _init_sentry()
    fake_sentry.init.assert_called_once_with(
        dsn="https://example@ingest.operionerp.xyz/1",
        traces_sample_rate=0.1,
        environment="staging",
    )


def test_capture_exception_when_enabled(fake_sentry):
    _capture_exception(ValueError("boom"))
    fake_sentry.capture_exception.assert_called_once()


def test_capture_exception_noop_when_disabled(monkeypatch, fake_sentry):
    fake_sentry.get_client.return_value.is_enabled.return_value = False
    _capture_exception(ValueError("boom"))
    fake_sentry.capture_exception.assert_not_called()


def test_capture_exception_noop_when_sdk_missing():
    """Without sentry_sdk installed, capture_exception must never raise."""
    sys.modules.pop("sentry_sdk", None)
    try:
        # Should swallow the import error and return None.
        assert _capture_exception(RuntimeError("x")) is None
    finally:
        pass  # leave sys.modules as-is (module was absent)


def test_create_app_works_without_sentry_dsn(monkeypatch):
    """Startup path stays green without the DSN (cheap regression guard)."""
    monkeypatch.delenv("OPERION_SENTRY_DSN", raising=False)
    from backend.main import create_app

    app = create_app()
    assert app is not None
    assert getattr(app, "openapi", None) is not None
