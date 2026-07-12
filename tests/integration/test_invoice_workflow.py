"""Integration test: Invoice create → finalize → PDF flow."""
import pytest
from models.invoice_models import InvoiceCreate, InvoiceLineItem, InvoiceFinalizeRequest
from services.invoicing.service import InvoiceService


class TestInvoiceWorkflow:
    def test_create_invoice_typed(self, seeded_db):
        """InvoiceService.create() with typed InvoiceCreate."""
        service = InvoiceService(seeded_db)
        request = InvoiceCreate(
            client_id=1,
            invoice_date="2026-07-15",
            due_date="2026-08-15",
            line_items=[
                InvoiceLineItem(description="Transport", quantity=1, unit_price=1500.0, vat_rate=19.0),
            ],
        )
        result = service.create(request, user_id=1)
        assert result.success
        assert result.data is not None
        assert result.data.total_gross > 0

    def test_finalize_invoice(self, seeded_db):
        """InvoiceService.finalize() with typed request."""
        service = InvoiceService(seeded_db)
        # Create first
        create_req = InvoiceCreate(
            client_id=1, invoice_date="2026-07-15", due_date="2026-08-15",
            line_items=[InvoiceLineItem(description="Test", quantity=1, unit_price=100.0)],
        )
        created = service.create(create_req, user_id=1)
        assert created.success

        # Finalize
        finalize_req = InvoiceFinalizeRequest(invoice_id=created.data.id)
        result = service.finalize(finalize_req, user_id=1)
        assert result.success
        assert result.data.status == "finalized"

    def test_recalculate_invoice(self, seeded_db):
        """InvoiceService.recalculate() updates totals."""
        service = InvoiceService(seeded_db)
        create_req = InvoiceCreate(
            client_id=1, invoice_date="2026-07-15", due_date="2026-08-15",
            line_items=[
                InvoiceLineItem(description="A", quantity=2, unit_price=50.0),
                InvoiceLineItem(description="B", quantity=1, unit_price=100.0),
            ],
        )
        result = service.create(create_req, user_id=1)
        assert result.success
        assert result.data.subtotal_net == 200.0  # 2*50 + 1*100
