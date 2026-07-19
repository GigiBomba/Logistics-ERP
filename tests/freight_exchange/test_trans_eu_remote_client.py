"""Tests for remote_freight_exchange.py Trans.eu methods.

Covers: connect_trans_eu(), get_trans_eu_status().
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


class FakeApiClient:
    """Simulates the minimal API client interface used by RemoteFreightExchangeService."""
    def __init__(self):
        self.last_url = None
        self.last_body = None
        self._responses = {}

    def _post(self, url, body=None):
        self.last_url = url
        self.last_body = body
        return self._responses.get(url, {"status": "connected"})

    def _get(self, url):
        self.last_url = url
        return self._responses.get(url, {"status": "disconnected"})


class TestRemoteTransEuConnect:
    def test_connect_trans_eu_correct_endpoint(self):
        from client.remote_freight_exchange import RemoteFreightExchangeService
        api = FakeApiClient()
        svc = RemoteFreightExchangeService(api)
        svc.connect_trans_eu("auth123", "http://localhost:19999/callback")
        assert api.last_url == "/api/v1/freight/providers/connect_trans_eu"
        assert api.last_body == {
            "authorization_code": "auth123",
            "redirect_uri": "http://localhost:19999/callback",
        }

    def test_connect_trans_eu_returns_status(self):
        from client.remote_freight_exchange import RemoteFreightExchangeService
        api = FakeApiClient()
        api._responses["/api/v1/freight/providers/connect_trans_eu"] = {
            "status": "connected", "provider_id": "trans_eu", "user_id": 42,
        }
        svc = RemoteFreightExchangeService(api)
        result = svc.connect_trans_eu("auth123", "http://localhost:19999/callback")
        assert result["status"] == "connected"
        assert result["user_id"] == 42


class TestRemoteTransEuStatus:
    def test_get_status_correct_endpoint(self):
        from client.remote_freight_exchange import RemoteFreightExchangeService
        api = FakeApiClient()
        svc = RemoteFreightExchangeService(api)
        svc.get_trans_eu_status()
        assert api.last_url == "/api/v1/freight/providers/trans_eu/status"

    def test_get_status_returns_disconnected(self):
        from client.remote_freight_exchange import RemoteFreightExchangeService
        api = FakeApiClient()
        api._responses["/api/v1/freight/providers/trans_eu/status"] = {
            "provider_id": "trans_eu", "status": "disconnected",
        }
        svc = RemoteFreightExchangeService(api)
        result = svc.get_trans_eu_status()
        assert result["status"] == "disconnected"
