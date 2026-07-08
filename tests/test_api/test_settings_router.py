"""Tests for the settings API router (``/api/v1/settings``)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/settings"


class TestSettingsRouter:
    """Company config and key-value setting endpoints."""

    # ── company config: GET ────────────────────────────────────────────────

    @patch("os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=mock_open,
           read_data=json.dumps({"company_name": "Acme Corp", "vat": "12345"}))
    @patch.dict("os.environ", {"OPERION_REPORTS_DIR": "/some/reports"})
    def test_get_company_config_returns_config(
        self, mock_file, mock_isfile, client_with_mocks
    ):
        client, mocks = client_with_mocks

        resp = client.get(f"{BASE}/company")
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_name"] == "Acme Corp"
        assert data["vat"] == "12345"

    @patch("os.path.isfile", return_value=False)
    @patch.dict("os.environ", {}, clear=True)
    def test_get_company_config_returns_empty_when_no_file(
        self, mock_isfile, client_with_mocks
    ):
        client, mocks = client_with_mocks

        resp = client.get(f"{BASE}/company")
        assert resp.status_code == 200
        assert resp.json() == {}

    # ── company config: PUT ────────────────────────────────────────────────

    @patch("backend.api.v1.settings.Config")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_company_config_returns_saved(
        self, mock_file, mock_makedirs, mock_config, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mock_config.REPORTS_DIR = "/tmp/reports"

        payload = {"company_name": "New Corp", "vat": "67890"}
        resp = client.put(f"{BASE}/company", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "saved"}
        # Verify the file was written with the correct content
        handle = mock_file()
        written = "".join(call[0][0] for call in handle.write.call_args_list)
        assert "New Corp" in written
        assert "67890" in written

    # ── get setting by key ─────────────────────────────────────────────────

    def test_get_setting_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].get_setting.return_value = "some_value"

        resp = client.get(f"{BASE}/my_key")
        assert resp.status_code == 200
        assert resp.json() == {"key": "my_key", "value": "some_value"}
        mocks["db"].get_setting.assert_called_once_with("my_key")

    def test_get_setting_returns_404_when_missing(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].get_setting.return_value = None

        resp = client.get(f"{BASE}/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Setting not found"

    # ── save setting ───────────────────────────────────────────────────────

    def test_save_setting_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks

        resp = client.put(f"{BASE}/my_key", json={"value": "new_value"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "saved", "key": "my_key", "value": "new_value"}
        mocks["db"].save_setting.assert_called_once_with("my_key", "new_value")

    # ── error handling ─────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].get_setting.side_effect = RuntimeError("DB error")

        with pytest.raises(RuntimeError, match="DB error"):
            client.get(f"{BASE}/some_key")

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/company")
        assert resp.status_code == 401
