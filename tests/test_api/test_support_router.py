"""Tests for the support router — tickets (POST/GET) and messages proxy."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestCreateSupportTicket:
    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_create_ticket_forwards_category_and_priority(self, mock_client, client):
        """POST /support/tickets proxies the payload (incl. category) downstream
        and returns the mapped TicketResponse."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "T-1001",
            "subject": "Scanner keeps dropping Wi-Fi",
            "status": "open",
            "priority": "high",
            "category": "bug",
            "created_at": "2026-09-11T09:00:00Z",
            "updated_at": "2026-09-11T09:00:00Z",
        }
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_resp
        )

        resp = client.post(
            "/api/v1/support/tickets",
            json={
                "subject": "Scanner keeps dropping Wi-Fi",
                "description": "Scanner drops off Wi-Fi every ~20 minutes.",
                "priority": "high",
                "category": "bug",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "T-1001"
        assert body["subject"] == "Scanner keeps dropping Wi-Fi"
        assert body["status"] == "open"
        assert body["priority"] == "high"
        assert body["category"] == "bug"

        req = mock_client.return_value.__aenter__.return_value.request
        req.assert_called_once()
        args, kwargs = req.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/v1/tickets")
        # category must survive end-to-end (it was silently dropped before)
        assert kwargs["json"] == {
            "subject": "Scanner keeps dropping Wi-Fi",
            "description": "Scanner drops off Wi-Fi every ~20 minutes.",
            "priority": "high",
            "category": "bug",
        }
        assert kwargs["headers"]["X-Company-Id"] == "1"
        assert kwargs["headers"]["X-Customer-Id"] == "1"
        assert "X-Internal-Auth" in kwargs["headers"]

    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_create_ticket_omits_optional_fields(self, mock_client, client):
        """Minimal payload (no priority/category) is forwarded as-is."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": "T-1002",
            "subject": "Billing question",
            "status": "open",
        }
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_resp
        )

        resp = client.post(
            "/api/v1/support/tickets",
            json={"subject": "Billing question", "description": "Invoice unclear."},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "T-1002"
        assert body["status"] == "open"
        assert body["priority"] is None
        assert body["category"] is None

        req = mock_client.return_value.__aenter__.return_value.request
        args, kwargs = req.call_args
        assert kwargs["json"] == {
            "subject": "Billing question",
            "description": "Invoice unclear.",
        }

    def test_create_ticket_validation_error(self, client):
        """Empty subject/description are rejected with 422."""
        resp = client.post(
            "/api/v1/support/tickets",
            json={"subject": "", "description": ""},
        )
        assert resp.status_code == 422

    def test_create_ticket_rejects_invalid_priority(self, client):
        """Priority outside low|medium|high|urgent is rejected with 422."""
        resp = client.post(
            "/api/v1/support/tickets",
            json={
                "subject": "Urgent issue",
                "description": "Something broke.",
                "priority": "critical",
            },
        )
        assert resp.status_code == 422

    def test_create_ticket_requires_auth(self, app):
        """No bearer token → 401 before any downstream call."""
        resp = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/support/tickets",
            json={"subject": "S", "description": "D"},
        )
        assert resp.status_code == 401

    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_create_ticket_maps_downstream_unreachable_to_503(self, mock_client, client):
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            side_effect=__import__("httpx").RequestError("boom")
        )

        resp = client.post(
            "/api/v1/support/tickets",
            json={"subject": "S", "description": "D"},
        )

        assert resp.status_code == 503
        assert resp.json()["detail"]["error_code"] == "service-unavailable"


class TestListSupportTickets:
    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_list_tickets(self, mock_client, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "id": "T-1",
                "subject": "Scanner issue",
                "status": "open",
                "priority": "low",
                "category": "bug",
                "created_at": "2026-09-11T09:00:00Z",
                "updated_at": "2026-09-11T09:00:00Z",
            }
        ]
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_resp
        )

        resp = client.get("/api/v1/support/tickets")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body[0]["id"] == "T-1"
        assert body[0]["category"] == "bug"

        req = mock_client.return_value.__aenter__.return_value.request
        args, _ = req.call_args
        assert args[0] == "GET"
        assert args[1].endswith("/v1/tickets")

    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_list_tickets_rejects_non_list_response(self, mock_client, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"unexpected": "shape"}
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_resp
        )

        resp = client.get("/api/v1/support/tickets")

        assert resp.status_code == 502


class TestGetSupportTicket:
    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_get_ticket_by_id(self, mock_client, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "T-7",
            "subject": "Single ticket",
            "status": "resolved",
            "priority": "medium",
            "category": "feature",
            "created_at": "2026-09-10T09:00:00Z",
            "updated_at": "2026-09-11T09:00:00Z",
        }
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_resp
        )

        resp = client.get("/api/v1/support/tickets/T-7")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "T-7"
        assert body["status"] == "resolved"
        assert body["category"] == "feature"

        req = mock_client.return_value.__aenter__.return_value.request
        args, _ = req.call_args
        assert args[0] == "GET"
        assert args[1].endswith("/v1/tickets/T-7")

    @patch("backend.api.v1.support.httpx.AsyncClient")
    def test_get_ticket_maps_downstream_error_to_502(self, mock_client, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"
        mock_resp.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
            "404", request=MagicMock(), response=mock_resp
        )
        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_resp
        )

        resp = client.get("/api/v1/support/tickets/T-7")

        assert resp.status_code == 502
        assert resp.json()["detail"]["error_code"] == "internal-error"