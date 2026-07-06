"""Proforma service — proforma invoice lifecycle: create, generate PDF, save draft, email."""
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

from repositories.client_repository import ClientRepository
from repositories.proforma_repository import (
    DEFAULT_PROFORMA_FORMAT_KEY,
    PROFORMA_NUMBER_FORMATS,
    ProformaRepository,
)
from services.invoicing.config_manager import load_company_config
from services.invoicing.generator import InvoiceGenerator
from services.operations.event_bus import PROFORMA_CREATED, EventBus
from services.operations.notification_center import NotificationCenter
from utils.resource_path import data_path

class ProformaService:
    def get_format_key(self) -> str:
        if self.prefs:
            return self.prefs.get_setting("proforma_number_format") or DEFAULT_PROFORMA_FORMAT_KEY
        return DEFAULT_PROFORMA_FORMAT_KEY

    def set_format_key(self, fmt_key: str) -> None:
        if self.prefs and fmt_key in PROFORMA_NUMBER_FORMATS:
            self.prefs.save_setting("proforma_number_format", fmt_key)

    def __init__(self, db, prefs=None):
        self.db = db
        self.prefs = prefs
        self.generator = InvoiceGenerator()
        self._event_bus = EventBus()
        self._client_repo = ClientRepository(db)
        self._proforma_repo = ProformaRepository(db)
        self._drafts_dir = data_path("proforma_drafts")
        if not os.path.exists(self._drafts_dir):
            os.makedirs(self._drafts_dir)

    def generate(self, proforma_data: dict[str, Any], mode: str = "client") -> str:
        """Generate a proforma invoice PDF (does not persist to DB or Document Center)."""
        return self.generator.generate_rich(proforma_data, document_type="proforma")

    def generate_and_record(self, proforma_data: dict[str, Any]) -> str:
        """Generate proforma PDF, persist to DB, register in Document Center, publish event."""
        mode = proforma_data.get("mode", "client")

        # Resolve proforma number
        pf_number = proforma_data.get("proforma_number", "")
        if not pf_number:
            pf_number = self._proforma_repo.get_next_number()
            proforma_data["proforma_number"] = pf_number

        # Set issue_date if missing
        if not proforma_data.get("issue_date"):
            proforma_data["issue_date"] = datetime.now().strftime("%Y-%m-%d")

        # Generate PDF
        path = self.generator.generate_rich(proforma_data, document_type="proforma")

        # Persist to DB
        client = proforma_data.get("client", {})
        line_items = proforma_data.get("addon_items") or proforma_data.get("line_items", [])

        pf_id = self._proforma_repo.create(
            proforma_number=pf_number,
            issue_date=proforma_data.get("issue_date", ""),
            valid_until=proforma_data.get("valid_until", ""),
            client_name=client.get("name", ""),
            client_address=client.get("address", ""),
            client_vat=client.get("vat_number", ""),
            client_phone=client.get("phone", ""),
            client_email=client.get("email", ""),
            description=proforma_data.get("description", ""),
            notes=proforma_data.get("notes", ""),
            line_items=line_items,
            subtotal=proforma_data.get("subtotal", 0),
            discount_type=proforma_data.get("discount_type", ""),
            discount_value=proforma_data.get("discount_value", 0),
            discount_amount=proforma_data.get("discount", 0),
            tax_rate=proforma_data.get("tax_rate", 0),
            tax_amount=proforma_data.get("total_tax", 0),
            grand_total=proforma_data.get("grand_total", 0),
            currency=proforma_data.get("currency", "EUR"),
            mode=mode,
            status="Draft",
            logo_path=proforma_data.get("logo_path", ""),
            signature_path=proforma_data.get("signature_path", ""),
            stamp_path=proforma_data.get("stamp_path", ""),
            company_color=proforma_data.get("company_color", "#6366f1"),
        )

        if pf_id is not None:
            proforma_data["_record_id"] = pf_id
            self._event_bus.publish(PROFORMA_CREATED, {
                "proforma_id": pf_id,
                "proforma_number": pf_number,
                "grand_total": proforma_data.get("grand_total", 0),
                "client_name": client.get("name", ""),
            })
        else:
            logger.warning("Proforma DB record creation failed — PDF exists at %s without DB entry", path)

        # Register in Document Center
        if os.path.isfile(path):
            try:
                from services.document_service import DocumentService
                ds = DocumentService(self.db)
                ds.register_existing(
                    file_path=path,
                    title=f"Proforma {os.path.basename(path)}",
                    category="proformas",
                    tags=["proforma", mode],
                )
            except Exception:
                logger.warning("Failed to register proforma in Document Center", exc_info=True)

        return path

    def save_draft(self, data: dict[str, Any], name: str) -> bool:
        """Save a proforma draft JSON file."""
        if not name.strip():
            return False
        draft = dict(data)
        draft["_draft_saved_at"] = datetime.now().isoformat()
        path = os.path.join(self._drafts_dir, f"{name.strip()}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(draft, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def load_draft(self, name: str) -> Optional[dict[str, Any]]:
        """Load a proforma draft by name (without .json)."""
        path = os.path.join(self._drafts_dir, f"{name}.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_drafts(self) -> list[str]:
        """Return draft names sorted newest-first."""
        if not os.path.isdir(self._drafts_dir):
            return []
        try:
            drafts = []
            for fn in os.listdir(self._drafts_dir):
                if fn.endswith(".json"):
                    drafts.append(fn[:-5])
            return sorted(drafts, reverse=True)
        except Exception:
            return []

    def send_email(
        self,
        proforma_id: int,
        recipient: str,
        smtp_config: Optional[dict[str, str]] = None,
        proforma_data: Optional[dict[str, Any]] = None,
        include_linked_docs: bool = False,
        skip_generate: bool = False,
    ) -> bool:
        """Send the proforma PDF by email. Optionally include linked CMR/invoice documents.

        If *skip_generate* is True, *proforma_data* is expected to contain
        an already-generated PDF path under the ``_generated_path`` key.
        """
        data = proforma_data or {}
        if not recipient:
            raise ValueError("Recipient email address is required")

        if smtp_config is None and self.prefs:
            smtp_config = self.prefs.get_smtp_config()
        if not smtp_config or not smtp_config.get("smtp_server") or not smtp_config.get("smtp_user"):
            raise ValueError("SMTP not configured")

        if skip_generate:
            path = data.get("_generated_path", "")
        else:
            path = self.generate_and_record(data)
            # Capture the generated path for downstream use
            data["_generated_path"] = path
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Proforma PDF not found: {path}")

        nc = NotificationCenter(self.db)
        nc.configure_smtp(
            smtp_config.get("smtp_server", ""),
            int(smtp_config.get("smtp_port", "587")),
            smtp_config.get("smtp_user", ""),
            smtp_config.get("smtp_password", ""),
        )

        attachments = [path]

        # Conditionally include linked documents
        if include_linked_docs and proforma_id:
            try:
                from repositories.document_repository import DocumentRepository
                doc_repo = DocumentRepository(self.db)
                linked_docs = doc_repo.get_documents_for_entity("proforma", proforma_id)
                for ld in linked_docs:
                    fp = ld.get("file_path", "")
                    if fp and os.path.isfile(fp):
                        attachments.append(fp)
            except Exception:
                logger.warning("Failed to fetch linked docs for proforma %s", proforma_id, exc_info=True)

        conf = load_company_config()
        client_name = data.get("client", {}).get("name", "")
        pf_number = data.get("proforma_number", "Proforma")
        grand_total = data.get("grand_total", 0)
        valid_until = data.get("valid_until", "")

        subject = f"Proforma {pf_number} — {client_name}" if client_name else f"Proforma {pf_number}"
        body = (
            f"Dear Sir/Madam,\n\n"
            f"Please find attached proforma {pf_number}.\n"
        )
        if grand_total:
            body += f"Total amount: {grand_total:.2f} {data.get('currency', 'EUR')}\n"
        if valid_until:
            body += f"Valid until: {valid_until}\n"
        body += (
            f"\nThank you for your business.\n\n"
            f"Best regards,\n"
            f"{conf.get('company_name', '')}"
        )

        if nc.send_email(recipient, subject, body, attachments=attachments):
            try:
                self._proforma_repo.update_status(proforma_id, "Sent")
            except Exception:
                pass
            return True
        return False
