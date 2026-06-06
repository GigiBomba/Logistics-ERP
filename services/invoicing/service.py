from datetime import datetime, timedelta
import os
from typing import Any, Dict, Optional

from services.invoicing.generator import InvoiceGenerator
from services.invoicing.config_manager import load_company_config
from services.operations.event_bus import EventBus, INVOICE_CREATED, INVOICE_EMAILED
from services.operations.notification_center import NotificationCenter
from services.i18n import t
from repositories.client_repository import ClientRepository


class InvoiceService:
    def __init__(self, db, prefs=None):
        self.db = db
        self.prefs = prefs
        self.generator = InvoiceGenerator()
        self._event_bus = EventBus()
        self._client_repo = ClientRepository(db)

    def _enrich_trip_with_client(self, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        client_id = trip_data.get("client_id")
        if not client_id:
            return trip_data
        client = self._client_repo.get_by_id(client_id)
        if not client:
            return trip_data
        enriched = dict(trip_data)
        enriched["client_vat"] = client.get("vat_number") or ""
        enriched["client_address"] = client.get("address") or ""
        enriched["client_phone"] = client.get("phone") or ""
        enriched["client_email"] = client.get("email") or ""
        enriched["client_contact"] = client.get("contact_person") or ""
        return enriched

    def generate(self, trip_data: Dict[str, Any], mode: str = "client") -> str:
        enriched = self._enrich_trip_with_client(trip_data)
        return self.generator.generate(enriched, mode=mode)

    def create_record(self, trip_id: int, inv_number: str, amount: float, due_date: str) -> None:
        self.db.create_invoice_record(trip_id, inv_number, amount, due_date)

    def generate_and_record(self, trip_data: Dict[str, Any], mode: str = "client") -> str:
        path = self.generate(trip_data, mode=mode)
        if mode == "client":
            due_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            trip_id = trip_data.get("id", 0)
            inv_number = f"INV-{datetime.now().year}-{trip_id:04d}"
            total_price = trip_data.get("total_price_eur", 0) or 0
            self.create_record(
                trip_id=trip_id,
                inv_number=inv_number,
                amount=total_price,
                due_date=due_date,
            )
            self._event_bus.publish(INVOICE_CREATED, {
                "trip_id": trip_id,
                "invoice_number": inv_number,
                "amount": total_price,
                "due_date": due_date,
            })
        if os.path.isfile(path):
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ds.register_existing(
                    file_path=path,
                    title=f"Invoice {os.path.basename(path)}",
                    category="invoices",
                    entity_type="invoice",
                    entity_id=trip_data.get("id", 0),
                    tags=["invoice", mode],
                )
            except Exception:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Failed to register invoice in Document Center", exc_info=True)
        return path

    def send_invoice_email(
        self,
        trip_id: int,
        recipient: str,
        smtp_config: Optional[Dict[str, str]] = None,
        trip_data: Optional[Dict[str, Any]] = None,
        mode: str = "client",
    ) -> bool:
        trip = trip_data or {}
        if not recipient:
            raise ValueError("Recipient email address is required")

        if smtp_config is None and self.prefs:
            smtp_config = self.prefs.get_smtp_config()
        if not smtp_config or not smtp_config.get("smtp_server") or not smtp_config.get("smtp_user"):
            raise ValueError("SMTP not configured")

        path = self.generate_and_record(trip, mode=mode)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Invoice PDF not found: {path}")

        nc = NotificationCenter(self.db)
        nc.configure_smtp(
            smtp_config.get("smtp_server", ""),
            int(smtp_config.get("smtp_port", "587")),
            smtp_config.get("smtp_user", ""),
            smtp_config.get("smtp_password", ""),
        )

        conf = load_company_config()
        client_name = trip.get("client_name", t("invoice.default_client"))
        filename = os.path.basename(path)
        subject = t("email.invoice_subject").format(filename=filename, client=client_name)
        body = t("email.invoice_body").format(
            trip_id=trip_id,
            company=conf.get("company_name", ""),
        )

        if nc.send_email(recipient, subject, body, attachments=[path]):
            self._event_bus.publish(INVOICE_EMAILED, {
                "trip_id": trip_id,
                "invoice_number": filename.replace(".pdf", ""),
                "recipient": recipient,
            })
            return True
        return False
