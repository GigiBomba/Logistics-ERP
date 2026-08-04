"""Mobile company settings endpoint tests (blueprint §6.10, Phase 4A) — real DB.

Covers: GET maps real settings keys and NEVER returns secret values; the three
write-only behaviors for secrets (omitted -> unchanged, explicit "" -> cleared,
real value -> encrypted-stored + is_set true); test-email (bounded smtplib);
and the can_view/can_manage_company_settings gates (dispatcher 403).
"""
from __future__ import annotations

import pytest

from tests.mobile.conftest import seed_company_settings

BASE = "/api/v1/mobile/settings/company"
TEST_EMAIL = "/api/v1/mobile/settings/test-email"


@pytest.fixture
def settings_seed(real_db):
    seed_company_settings(real_db, company_id=1)


class _FakeSMTP:
    """In-process stand-in for smtplib.SMTP."""

    def __init__(self, *args, **kwargs):
        self.port = kwargs.get("port")
        self.host = args[0] if args else None
        self.login_calls = 0
        self.sendmail_calls = 0
        self.fail_send = kwargs.pop("_fail_send", False)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        return None

    def login(self, user, password):
        self.login_calls += 1

    def sendmail(self, sender, recipients, msg):
        self.sendmail_calls += 1
        if self.fail_send:
            import smtplib
            raise smtplib.SMTPException("550 relay denied")
        return {}


class TestGetCompanySettings:
    def test_maps_real_settings_keys(self, mobile_app, real_db, settings_seed, manager_client):
        resp = manager_client.get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["legal_name"] == "Operion Logistics SRL"
        assert body["vat_number"] == "RO12345678"
        assert body["address"] == "Str. Testului 1, Bucuresti"
        assert body["invoice_footer"] == "Multumim pentru colaborare!"
        assert body["smtp_server"] == "smtp.example.com"
        assert body["smtp_port"] == "587"
        assert body["smtp_user"] == "alerts@example.com"
        assert body["smtp_password_is_set"] is True
        assert body["tracking_provider"] == "Wialon / GPS-Trace (Gurtam)"
        assert body["tracking_api_key_is_set"] is True
        assert body["maintenance_alert_days_ahead"] == 30
        assert body["tacho_warning_days"] == 45
        assert body["tacho_critical_days"] == 15

    def test_get_never_returns_secret_values(self, mobile_app, real_db, settings_seed, manager_client):
        resp = manager_client.get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        # Only *_is_set booleans — never the secret keys themselves.
        assert "smtp_password" not in body
        assert "tracking_api_key" not in body
        assert "tracking.token" not in body
        # The plaintext secrets must not appear anywhere in the payload.
        assert "super-secret-smtp" not in resp.text
        assert "wialon-api-token-123" not in resp.text

    def test_get_defaults_when_unset(self, mobile_app, real_db, manager_client):
        resp = manager_client.get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["smtp_password_is_set"] is False
        assert body["tracking_api_key_is_set"] is False
        assert body["maintenance_alert_days_ahead"] == 30
        assert body["smtp_server"] == ""

    def test_company_isolation(self, mobile_app, real_db, settings_seed, manager_client):
        # Seed the same keys for company 2 with DIFFERENT values.
        seed_company_settings(real_db, company_id=2)
        real_db.execute(
            "UPDATE settings SET value = ? WHERE key = 'smtp_server' AND company_id = 2",
            ("other.example.com",),
        )
        real_db.conn.commit()
        resp = manager_client.get(BASE)
        assert resp.json()["smtp_server"] == "smtp.example.com"  # company 1 value

    def test_get_dispatcher_403(self, mobile_app, real_db, settings_seed, dispatcher_client):
        assert dispatcher_client.get(BASE).status_code == 403

    def test_get_driver_403(self, mobile_app, real_db, settings_seed, driver_client):
        assert driver_client.get(BASE).status_code == 403


class TestPatchWriteOnlySemantics:
    def test_write_only_omitted_secret_unchanged(self, mobile_app, real_db, settings_seed, manager_client):
        """WRITE-ONLY #1: smtp_password / tracking_api_key OMITTED -> unchanged."""
        assert manager_client.get(BASE).json()["smtp_password_is_set"] is True

        resp = manager_client.patch(BASE, json={"smtp_server": "new-smtp.example.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["smtp_server"] == "new-smtp.example.com"
        # The secret was omitted -> still set, still the same value.
        assert body["smtp_password_is_set"] is True
        assert body["tracking_api_key_is_set"] is True
        stored = dict(real_db.execute(
            "SELECT value FROM settings WHERE key = 'smtp_password' AND company_id = 1",
        ).fetchone())
        assert stored["value"]  # untouched

    def test_write_only_empty_secret_cleared(self, mobile_app, real_db, settings_seed, manager_client):
        """WRITE-ONLY #2: explicit \"\" -> cleared (is_set false)."""
        resp = manager_client.patch(
            BASE, json={"smtp_password": "", "tracking_api_key": ""},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["smtp_password_is_set"] is False
        assert body["tracking_api_key_is_set"] is False
        # Other settings untouched.
        assert body["smtp_server"] == "smtp.example.com"

    def test_write_only_real_secret_encrypted_and_set(
        self, mobile_app, real_db, settings_seed, manager_client,
    ):
        """WRITE-ONLY #3: real value -> stored via the sensitive path + is_set true."""
        resp = manager_client.patch(BASE, json={"smtp_password": "brand-new-secret"})
        assert resp.status_code == 200
        assert resp.json()["smtp_password_is_set"] is True

        stored = dict(real_db.execute(
            "SELECT value FROM settings WHERE key = 'smtp_password' AND company_id = 1",
        ).fetchone())
        # Roundtrip through the REAL encryption service proves the sensitive path.
        from services.encryption_service import decrypt_value

        assert decrypt_value(stored["value"]) == "brand-new-secret"

    def test_patch_identity_and_thresholds(self, mobile_app, real_db, manager_client):
        resp = manager_client.patch(
            BASE, json={
                "legal_name": "New Legal Name",
                "vat_number": "RO999",
                "address": "Other St",
                "invoice_footer": "Footer!",
                "maintenance_alert_days_ahead": 60,
                "tacho_warning_days": 30,
                "tacho_critical_days": 10,
                "tracking_provider": "Frotcom",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["legal_name"] == "New Legal Name"
        assert body["vat_number"] == "RO999"
        assert body["address"] == "Other St"
        assert body["invoice_footer"] == "Footer!"
        assert body["tracking_provider"] == "Frotcom"
        assert body["maintenance_alert_days_ahead"] == 60
        assert body["tacho_warning_days"] == 30
        assert body["tacho_critical_days"] == 10

    def test_patch_dispatcher_403(self, mobile_app, real_db, settings_seed, dispatcher_client):
        assert dispatcher_client.patch(BASE, json={"legal_name": "Nope"}).status_code == 403

    def test_patch_driver_403(self, mobile_app, real_db, settings_seed, driver_client):
        assert driver_client.patch(BASE, json={"legal_name": "Nope"}).status_code == 403


class TestSendTestEmail:
    def test_smtp_not_configured_400(self, mobile_app, real_db, manager_client):
        resp = manager_client.post(TEST_EMAIL, json={"recipient": "x@y.z"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "smtp_not_configured"

    def test_send_success(self, mobile_app, real_db, settings_seed, manager_client, monkeypatch):
        monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
        resp = manager_client.post(TEST_EMAIL, json={"recipient": "ops@test.com"})
        assert resp.status_code == 200
        assert "ops@test.com" in resp.json()["detail"]

    def test_send_defaults_to_smtp_user(self, mobile_app, real_db, settings_seed, manager_client, monkeypatch):
        monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
        resp = manager_client.post(TEST_EMAIL, json={})
        assert resp.status_code == 200
        assert "alerts@example.com" in resp.json()["detail"]  # smtp_user default

    def test_send_failure_502(self, mobile_app, real_db, settings_seed, manager_client, monkeypatch):
        def _failing(*args, **kwargs):
            return _FakeSMTP(*args, _fail_send=True, **kwargs)

        monkeypatch.setattr("smtplib.SMTP", _failing)
        resp = manager_client.post(TEST_EMAIL, json={"recipient": "ops@test.com"})
        assert resp.status_code == 502
        assert resp.json()["detail"]["error_code"] in ("smtp_send_failed", "smtp_connection_failed")

    def test_dispatcher_403(self, mobile_app, real_db, settings_seed, dispatcher_client):
        assert dispatcher_client.post(TEST_EMAIL, json={"recipient": "x@y.z"}).status_code == 403
