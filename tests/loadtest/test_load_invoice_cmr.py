from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.router import api_v1_router
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from tests.loadtest.conftest import run_concurrent

pytestmark = pytest.mark.slow


class TestLoadInvoiceCmr:
    """Load tests for /api/v1/invoices/ and /api/v1/cmr/ endpoints."""

    MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}

    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(api_v1_router)
        return app

    @pytest.fixture
    def client(self, app):
        app.dependency_overrides[get_current_user] = lambda: self.MOCK_USER
        app.dependency_overrides[require_dispatcher] = lambda: self.MOCK_USER
        app.dependency_overrides[require_admin] = lambda: self.MOCK_USER

        yield TestClient(app)
        app.dependency_overrides.clear()

    INVOICE_PAYLOAD = {
        "trip_id": 1,
        "client_name": "Acme Corp",
        "amount": 1500.00,
        "mode": "client",
        "lines": [{"description": "Transport service", "quantity": 1, "unit_price": 1500.00}],
    }

    CMR_PAYLOAD = {
        "trip_data": {
            "id": 1,
            "client_name": "Acme Corp",
            "loading_country": "Germany",
            "delivery_country": "France",
            "cargo_description": "Electronics",
            "gross_weight_kg": 5000.0,
            "volume_m3": 20.0,
        }
    }

    SEND_PAYLOAD = {
        "recipient": "client@example.com",
        "trip_data": {"id": 1},
        "mode": "client",
    }

    # ── test 1: invoice generation concurrency ────────────────────────────

    @patch("services.invoicing.service.InvoiceService.generate_and_record")
    def test_invoice_generation_concurrency(self, mock_generate, client):
        # Create a real temp file so FileResponse can read it
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmp.name
        tmp.write(b"%PDF-1.4 fake invoice\n")
        tmp.close()

        mock_generate.return_value = tmp_path

        def make_request():
            return client.post("/api/v1/invoices/generate", json=self.INVOICE_PAYLOAD)

        try:
            for n in [1, 5, 10]:
                results, timings, errors, elapsed = run_concurrent(make_request, n)
                success_rate = len(results) / n if n else 1.0
                assert success_rate >= 0.95, f"invoice_generation success_rate={success_rate:.3f} < 0.95 at n={n}"
        finally:
            os.unlink(tmp_path)

    # ── test 2: CMR generation concurrency ────────────────────────────────

    @patch("services.invoicing.cmr_generator.CMRGenerator.generate_all_copies")
    def test_cmr_generation_concurrency(self, mock_generate, client):
        # Create a real temp file so FileResponse can read it
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmp.name
        tmp.write(b"%PDF-1.4 fake cmr\n")
        tmp.close()

        mock_generate.return_value = {"original": tmp_path}

        def make_request():
            return client.post("/api/v1/cmr/generate", json=self.CMR_PAYLOAD)

        try:
            for n in [1, 5, 10]:
                results, timings, errors, elapsed = run_concurrent(make_request, n)
                success_rate = len(results) / n if n else 1.0
                assert success_rate >= 0.95, f"cmr_generation success_rate={success_rate:.3f} < 0.95 at n={n}"
        finally:
            os.unlink(tmp_path)

    # ── test 3: send invoice email concurrency ────────────────────────────

    @patch("services.invoicing.service.InvoiceService.send_invoice_email")
    def test_send_invoice_email_concurrency(self, mock_send, client):
        mock_send.return_value = True

        def make_request():
            return client.post("/api/v1/invoices/1/send", json=self.SEND_PAYLOAD)

        for n in [1, 10, 20]:
            results, timings, errors, elapsed = run_concurrent(make_request, n)
            success_rate = len(results) / n if n else 1.0
            assert success_rate >= 0.95, f"send_invoice_email success_rate={success_rate:.3f} < 0.95 at n={n}"
