"""Tests for the guarded backend.copilot imports in client/local_copilot.py.

Phase F: the packaged desktop build ships no ``backend`` package.  The lazy
``backend.copilot`` imports in LocalCopilotService must be guarded — a chat
message in LOCAL mode must return the standard ``copilot.error.unavailable``
response instead of raising ModuleNotFoundError.
"""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from client.local_copilot import LocalCopilotService


@pytest.fixture
def svc():
    return LocalCopilotService(db=None, prefs=None)


def _hide_backend_copilot():
    """Make ``from backend.copilot... import ...`` raise ImportError."""
    return patch.dict(
        sys.modules,
        {
            "backend.copilot": None,
            "backend.copilot.executor": None,
            "backend.copilot.context": None,
            "backend.copilot.planner": None,
            "backend.copilot.role_permissions": None,
            "backend.copilot.schemas": None,
        },
        clear=False,
    )


@pytest.mark.asyncio
async def test_chat_returns_unavailable_when_backend_missing(svc):
    with _hide_backend_copilot():
        resp = await svc.chat("hello")
    assert resp["summary_key"] == "copilot.error.unavailable"
    assert resp["timeline"] == []


@pytest.mark.asyncio
async def test_voice_input_returns_unavailable_when_backend_missing(svc):
    with _hide_backend_copilot():
        resp = await svc.voice_input("hello")
    assert resp["summary_key"] == "copilot.error.unavailable"


@pytest.mark.asyncio
async def test_confirm_plan_returns_unavailable_when_backend_missing(svc):
    with _hide_backend_copilot():
        resp = await svc.confirm_plan("plan-1")
    assert resp["status"] == "not_available"
    assert resp["message_key"] == "copilot.error.unavailable"


@pytest.mark.asyncio
async def test_cancel_plan_returns_unavailable_when_backend_missing(svc):
    with _hide_backend_copilot():
        resp = await svc.cancel_plan("plan-1")
    assert resp["status"] == "not_available"
    assert resp["message_key"] == "copilot.error.unavailable"