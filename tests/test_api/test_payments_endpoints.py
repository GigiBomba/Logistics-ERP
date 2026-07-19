"""Integration tests for the payments API endpoints (/api/v1/payments)."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from tests.test_api.conftest import StrippedMock

BASE = "/api/v1/payments"


class TestPaymentsRecipients:
    """GET /api/v1/payments/recipients"""

    def test_list_recipients_returns_200(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = StrippedMock()
        mock_svc.get_all_recipients.return_value = [
            {"id": 1, "name": "Client A", "type": "client"},
        ]
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        resp = client.get(f"{BASE}/recipients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_recipients_with_query(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = StrippedMock()
        mock_svc.get_all_recipients.return_value = []
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        resp = client.get(f"{BASE}/recipients?query=acme")
        assert resp.status_code == 200
        mock_svc.get_all_recipients.assert_called_once()

    def test_list_recipients_empty(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = StrippedMock()
        mock_svc.get_all_recipients.return_value = []
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        resp = client.get(f"{BASE}/recipients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestPaymentsExportCSV:
    """POST /api/v1/payments/export-csv"""

    def test_export_csv_returns_stream(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = MagicMock()
        mock_svc.build_batch_csv_from_request.return_value = "name,amount\nClient,100.00\n"
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        payload = {
            "batch_name": "test_batch",
            "items": [
                {"recipient_id": 1, "recipient_type": "client",
                 "recipient_name": "Client A", "amount": 100.0, "currency": "EUR"},
            ],
        }
        resp = client.post(f"{BASE}/export-csv", json=payload)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_export_csv_empty_items(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = MagicMock()
        mock_svc.build_batch_csv_from_request.return_value = "name,amount\n"
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        payload = {
            "batch_name": "empty",
            "items": [],
        }
        resp = client.post(f"{BASE}/export-csv", json=payload)
        assert resp.status_code == 200


class TestPaymentsValidateRecipient:
    """POST /api/v1/payments/validate-recipient"""

    def test_validate_recipient_returns_valid(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = StrippedMock()
        mock_svc.validate_recipient_payment_info.return_value = []
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        resp = client.post(f"{BASE}/validate-recipient?recipient_id=1&recipient_type=client")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_recipient_returns_invalid(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = StrippedMock()
        mock_svc.validate_recipient_payment_info.return_value = ["Missing IBAN"]
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        resp = client.post(f"{BASE}/validate-recipient?recipient_id=1&recipient_type=client")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False
        assert "Missing IBAN" in resp.json()["errors"]


class TestPaymentsExportCSVDirect:
    """POST /api/v1/payments/export-csv-direct"""

    def test_export_csv_direct_returns_stream(self, client_with_mocks):
        client, mocks = client_with_mocks
        from backend.dependencies import get_payment_batch_service
        mock_svc = MagicMock()
        mock_svc.build_batch_csv.return_value = "name,amount\nClient,100.00\n"
        client.app.dependency_overrides[get_payment_batch_service] = lambda: mock_svc
        payload = {
            "batch_name": "direct",
            "items": [
                {"recipient_id": 1, "recipient_type": "client",
                 "recipient_name": "Client A", "amount": 100.0,
                 "currency": "EUR", "iban": "DE123"},
            ],
        }
        resp = client.post(f"{BASE}/export-csv-direct", json=payload)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


class TestPaymentsAuth:
    def test_unauthorized_without_token(self, app):
        client = TestClient(app)
        resp = client.get(f"{BASE}/recipients")
        assert resp.status_code == 401
