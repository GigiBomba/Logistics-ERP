"""Tests for the Stripe payment-methods API (/api/v1/payment-methods).

Stripe is always monkeypatched — no live Stripe calls are ever made.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import backend.api.v1.payment_methods as payment_methods

BASE = "/api/v1/payment-methods"

SECRET = "sk_test_123"


class _FakeStripeError(Exception):
    """Stand-in for stripe.error.InvalidRequestError (resource_missing)."""

    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


def _fake_stripe(payment_methods_data=None):
    """Build a MagicMock that stands in for the ``stripe`` module."""
    stripe = MagicMock()
    stripe.PaymentMethod.list.return_value = SimpleNamespace(
        data=payment_methods_data or []
    )
    stripe.PaymentMethod.detach.return_value = None
    stripe.SetupIntent.create.return_value = SimpleNamespace(
        client_secret="seti_123_secret",
        id="seti_123",
    )
    stripe.Customer.create.return_value = SimpleNamespace(id="cus_new_123")
    stripe.Customer.retrieve.return_value = SimpleNamespace(
        invoice_settings=SimpleNamespace(default_payment_method=None),
        default_source=None,
    )
    return stripe


def _db_execute_side_effect(sub_row=None, company_row=None):
    """Side effect for ``db.conn.execute`` keyed on the SQL prefix."""

    def execute(sql, *params):
        if sql.startswith("SELECT * FROM subscriptions"):
            return MagicMock(fetchone=lambda: sub_row)
        if sql.startswith("SELECT stripe_customer_id FROM subscriptions"):
            return MagicMock(fetchone=lambda: sub_row)
        if sql.startswith("SELECT company_name FROM companies"):
            return MagicMock(fetchone=lambda: company_row)
        return MagicMock(fetchone=lambda: None)

    return execute


class TestListPaymentMethods:
    """GET /api/v1/payment-methods"""

    def test_list_empty_when_stripe_not_configured(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        # _stripe_secret_key stays default (""): stripe unconfigured.
        resp = client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_empty_when_no_stripe_customer(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(sub_row=None)
        resp = client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_empty_when_no_payment_methods(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(
            sub_row={"id": 1, "stripe_customer_id": "cus_1"},
        )
        resp = client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == []
        fake_stripe.PaymentMethod.list.assert_called_once_with(
            customer="cus_1", type="card"
        )

    def test_list_populated(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        pm1 = SimpleNamespace(
            id="pm_1", type="card",
            card=SimpleNamespace(brand="visa", last4="4242", exp_month=12, exp_year=2030),
            billing_details={"name": "Test User"},
            created=1700000000,
        )
        pm2 = SimpleNamespace(
            id="pm_2", type="card",
            card=SimpleNamespace(brand="mastercard", last4="1111", exp_month=1, exp_year=2029),
            billing_details={},
            created=1700000001,
        )
        fake_stripe = _fake_stripe([pm1, pm2])
        fake_stripe.Customer.retrieve.return_value = SimpleNamespace(
            invoice_settings=SimpleNamespace(default_payment_method="pm_2"),
            default_source=None,
        )
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(
            sub_row={"id": 1, "stripe_customer_id": "cus_1"},
        )
        resp = client.get(BASE)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "pm_1"
        assert data[0]["type"] == "card"
        assert data[0]["card"] == {
            "brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2030,
        }
        assert data[0]["billing_details"] == {"name": "Test User"}
        assert data[0]["created"] == 1700000000
        assert data[0]["is_default"] is False
        assert data[1]["id"] == "pm_2"
        assert data[1]["is_default"] is True

    def test_list_returns_502_on_stripe_error(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        fake_stripe.PaymentMethod.list.side_effect = _FakeStripeError("boom")
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(
            sub_row={"id": 1, "stripe_customer_id": "cus_1"},
        )
        resp = client.get(BASE)
        assert resp.status_code == 502


class TestSetupIntent:
    """POST /api/v1/payment-methods/setup-intent"""

    def test_setup_intent_returns_mock_when_not_configured(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        resp = client.post(f"{BASE}/setup-intent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_intent_id"].startswith("seti_mock_")
        assert body["client_secret"].startswith("seti_mock_")

    def test_setup_intent_with_existing_customer(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(
            sub_row={"id": 1, "stripe_customer_id": "cus_existing"},
        )
        resp = client.post(f"{BASE}/setup-intent")
        assert resp.status_code == 200
        assert resp.json() == {
            "client_secret": "seti_123_secret",
            "setup_intent_id": "seti_123",
        }
        fake_stripe.Customer.create.assert_not_called()
        fake_stripe.SetupIntent.create.assert_called_once_with(
            customer="cus_existing", payment_method_types=["card"]
        )

    def test_setup_intent_creates_customer_when_missing(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(
            sub_row={"id": 1, "stripe_customer_id": None},
            company_row={"company_name": "Acme Ltd"},
        )
        resp = client.post(f"{BASE}/setup-intent")
        assert resp.status_code == 200
        assert resp.json() == {
            "client_secret": "seti_123_secret",
            "setup_intent_id": "seti_123",
        }
        fake_stripe.Customer.create.assert_called_once_with(
            name="Acme Ltd", metadata={"company_id": 1}
        )
        fake_stripe.SetupIntent.create.assert_called_once_with(
            customer="cus_new_123", payment_method_types=["card"]
        )
        # The new customer id is persisted on the subscription row.
        update_calls = [
            call.args[0]
            for call in mocks["db"].conn.execute.call_args_list
            if call.args and "UPDATE subscriptions" in str(call.args[0])
        ]
        assert len(update_calls) == 1
        assert "stripe_customer_id" in update_calls[0]

    def test_setup_intent_returns_502_on_stripe_error(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        fake_stripe.SetupIntent.create.side_effect = _FakeStripeError("boom")
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        mocks["db"].conn.execute.side_effect = _db_execute_side_effect(
            sub_row={"id": 1, "stripe_customer_id": "cus_existing"},
        )
        resp = client.post(f"{BASE}/setup-intent")
        assert resp.status_code == 502


class TestDeletePaymentMethod:
    """DELETE /api/v1/payment-methods/{payment_method_id}"""

    def test_delete_detaches_payment_method(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        resp = client.delete(f"{BASE}/pm_1")
        assert resp.status_code == 200
        assert resp.json() == {"status": "removed"}
        fake_stripe.PaymentMethod.detach.assert_called_once_with("pm_1")

    def test_delete_returns_404_when_not_found(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        fake_stripe.PaymentMethod.detach.side_effect = _FakeStripeError(
            "No such payment method: pm_missing", code="resource_missing"
        )
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        resp = client.delete(f"{BASE}/pm_missing")
        assert resp.status_code == 404

    def test_delete_returns_502_on_other_stripe_error(self, client_with_mocks, monkeypatch):
        client, mocks = client_with_mocks
        fake_stripe = _fake_stripe()
        fake_stripe.PaymentMethod.detach.side_effect = _FakeStripeError("network down")
        monkeypatch.setattr(payment_methods, "_get_stripe_module", lambda: fake_stripe)
        monkeypatch.setattr(payment_methods, "_stripe_secret_key", lambda: SECRET)
        resp = client.delete(f"{BASE}/pm_1")
        assert resp.status_code == 502


class TestPaymentMethodsAuth:
    """Auth guards on /api/v1/payment-methods"""

    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(BASE)
        assert resp.status_code == 401

    def test_non_dispatcher_returns_403(self, app):
        from backend.dependencies_security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {
            "id": 1,
            "email": "driver@test.com",
            "role": "driver",
            "is_admin": False,
            "company_id": 1,
        }
        client = TestClient(app)
        resp = client.get(BASE)
        assert resp.status_code == 403
        assert "Dispatcher or admin privileges required" in resp.json()["detail"]["detail"]