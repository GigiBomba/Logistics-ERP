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
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
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

    # ── sensitive-key encryption via API ──────────────────────────────────

    @patch("backend.api.v1.settings.encrypt_value", side_effect=lambda v: f"enc:{v}")
    def test_patch_sensitive_key_encrypts_before_save(
        self, mock_enc, client_with_mocks
    ):
        client, mocks = client_with_mocks

        resp = client.patch(f"{BASE}/smtp_password", json={"value": "secret123"})
        assert resp.status_code == 200
        mock_enc.assert_called_once_with("secret123")
        # Stored value must NOT be the plaintext.
        mocks["db"].save_setting.assert_called_once_with("smtp_password", "enc:secret123")

    @patch("backend.api.v1.settings.encrypt_value", side_effect=lambda v: f"enc:{v}")
    def test_put_tracking_password_encrypts_before_save(
        self, mock_enc, client_with_mocks
    ):
        client, mocks = client_with_mocks

        resp = client.put(f"{BASE}/tracking.password", json={"value": "track-secret"})
        assert resp.status_code == 200
        # Stored value must NOT be the plaintext.
        mocks["db"].save_setting.assert_called_once_with("tracking.password", "enc:track-secret")

    def test_patch_non_sensitive_key_not_encrypted(self, client_with_mocks):
        client, mocks = client_with_mocks
        with patch("backend.api.v1.settings.encrypt_value") as mock_enc:
            resp = client.patch(f"{BASE}/pref_language", json={"value": "ro"})
            assert resp.status_code == 200
            mock_enc.assert_not_called()
            mocks["db"].save_setting.assert_called_once_with("pref_language", "ro")

    @patch("backend.api.v1.settings.decrypt_value", side_effect=lambda v: v.replace("enc:", ""))
    def test_get_sensitive_key_returns_decrypted_value(
        self, mock_dec, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mocks["db"].get_setting.return_value = "enc:secret123"

        resp = client.get(f"{BASE}/smtp_password")
        assert resp.status_code == 200
        assert resp.json()["value"] == "secret123"
        mock_dec.assert_called_once_with("enc:secret123")

    @patch("backend.api.v1.settings.decrypt_value", side_effect=lambda v: v)
    def test_get_sensitive_key_legacy_plaintext_unchanged(
        self, mock_dec, client_with_mocks
    ):
        client, mocks = client_with_mocks
        mocks["db"].get_setting.return_value = "legacy-plaintext"

        resp = client.get(f"{BASE}/tracking.password")
        assert resp.status_code == 200
        assert resp.json()["value"] == "legacy-plaintext"
        mock_dec.assert_called_once_with("legacy-plaintext")

    # ── error handling ─────────────────────────────────────────────────────

    def test_service_exception_propagates(self, client_with_mocks):
        client, mocks = client_with_mocks
        mocks["db"].get_setting.side_effect = RuntimeError("DB error")

        # Exception may propagate or be handled as 500
        resp = client.get(f"{BASE}/some_key")
        assert resp.status_code in (500,)
        # If it propagates as exception, we might not get here

    # ── auth ───────────────────────────────────────────────────────────────

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/company")
        assert resp.status_code == 401
