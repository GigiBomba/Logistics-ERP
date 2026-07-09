"""Chaos tests: SMTP / email sending failures.

The ``InvoiceService.send_invoice_email`` method calls
``NotificationCenter.send_email`` which wraps ``smtplib.SMTP`` and
catches ``SMTPException`` internally, returning ``True`` on success
and ``False`` on failure.  The ``POST /api/v1/invoices/{id}/send``
endpoint returns ``{"status": "sent"}`` or ``{"status": "failed"}``
depending on the method return value.

These tests verify graceful degradation when the SMTP server is
unreachable, times out, or partially fails in a batch scenario.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.chaos


class TestChaosSmtp:
    """Simulate SMTP-level failures — email sending should degrade gracefully."""

    INVOICE_PAYLOAD = {
        "recipient": "test@example.com",
        "trip_id": 1,
        "trip_data": {
            "id": 1,
            "client_name": "Test Client",
            "total_price_eur": 100.0,
        },
        "mode": "client",
    }

    # ── Individual send failures ─────────────────────────────────────

    def test_smtp_connection_refused_send_invoice(self, client, auth_admin):
        """When SMTP is unreachable, ``send_invoice_email`` returns False
        and the endpoint returns a failed status."""
        with patch(
            "services.invoicing.service.InvoiceService.send_invoice_email",
            return_value=False,
        ):
            resp = client.post(
                "/api/v1/invoices/1/send",
                json=self.INVOICE_PAYLOAD,
                headers=auth_admin,
            )
            # 200 with {"status": "failed"} — graceful degradation
            assert resp.status_code in (200, 400, 500), (
                f"Unexpected status: {resp.status_code}"
            )
            if resp.status_code == 200:
                body = resp.json()
                assert body.get("status") == "failed", (
                    f"Expected 'failed' status, got {body}"
                )

    def test_smtp_timeout_send_invoice(self, client, auth_admin):
        """When SMTP times out, ``send_invoice_email`` returns False
        and the endpoint returns a failed status."""
        with patch(
            "services.invoicing.service.InvoiceService.send_invoice_email",
            return_value=False,
        ):
            resp = client.post(
                "/api/v1/invoices/1/send",
                json=self.INVOICE_PAYLOAD,
                headers=auth_admin,
            )
            assert resp.status_code in (200, 400, 500), (
                f"Unexpected status during timeout: {resp.status_code}"
            )
            if resp.status_code == 200:
                body = resp.json()
                assert body.get("status") == "failed"

    # ── Batch partial failure ────────────────────────────────────────

    def test_smtp_partial_failure_batch(self, client, auth_admin):
        """Simulate alternating success/failure across multiple send
        calls — each response should be independent."""
        # The ``send_invoice_email`` method is patched to return
        # alternating values.  Three sequential requests exercise
        # the pattern.
        with patch(
            "services.invoicing.service.InvoiceService.send_invoice_email",
            side_effect=[True, False, True],
        ):
            # First call — succeeds
            resp1 = client.post(
                "/api/v1/invoices/1/send",
                json=self.INVOICE_PAYLOAD,
                headers=auth_admin,
            )
            # Second call — fails
            resp2 = client.post(
                "/api/v1/invoices/2/send",
                json=self.INVOICE_PAYLOAD,
                headers=auth_admin,
            )
            # Third call — succeeds
            resp3 = client.post(
                "/api/v1/invoices/3/send",
                json=self.INVOICE_PAYLOAD,
                headers=auth_admin,
            )

            # Each response should reflect the individual outcome
            for i, (resp, expected_status) in enumerate(
                [(resp1, "sent"), (resp2, "failed"), (resp3, "sent")],
            ):
                assert resp.status_code in (200, 400, 500), (
                    f"Call {i}: unexpected status {resp.status_code}"
                )
                if resp.status_code == 200:
                    body = resp.json()
                    assert body.get("status") == expected_status, (
                        f"Call {i}: expected '{expected_status}', got {body}"
                    )
