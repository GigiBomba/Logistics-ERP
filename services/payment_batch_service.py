"""Payment batch service — bulk payment logic."""
import csv
import io
import json
import logging
import os
import tempfile
import time
import warnings
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.db_manager import DatabaseManager
from models.common import ErrorDetail, ServiceResult
from models.payment_models import (
    PaymentBatchCreateResult,
    PaymentBatchRequest,
    PaymentBatchResult,
    PaymentProfileCreate,
    PaymentProfileResult,
)
from repositories.client_repository import ClientRepository
from repositories.driver_repository import DriverRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.payment_profile_repository import PaymentProfileRepository
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

# CSV columns for banking bulk payment export
BANK_CSV_COLUMNS = [
    "recipient_name", "bank_name", "bank_account", "bank_code",
    "bank_bic", "iban", "amount", "currency", "payment_reference",
    "recipient_type",
]

# Default export directory (can be overridden via env var)
_BATCH_EXPORT_DIR = os.environ.get("OPERION_BATCH_EXPORT_DIR", tempfile.gettempdir())


class PaymentBatchService:
    def __init__(self, db: DatabaseManager):
        self._db = db
        self._client_repo = ClientRepository(db)
        self._driver_repo = DriverRepository(db)
        self._invoice_repo = InvoiceRepository(db)
        self._profile_repo = PaymentProfileRepository(db)

    # ── Audit logging for financial exports ─────────────────────────────
    def _log_export(self, action: str, metadata: Dict[str, Any]) -> None:
        """Write a structured audit entry for sensitive financial data export.

        Logs are written to the application log at INFO level and also
        to a dedicated audit file if ``OPERION_AUDIT_LOG_DIR`` is configured.
        """
        entry = {
            "timestamp": time.time(),
            "action": action,
            "metadata": metadata,
        }
        logger.info("AUDIT payment_export %s", json.dumps(entry))

        audit_dir = os.environ.get("OPERION_AUDIT_LOG_DIR", "")
        if audit_dir:
            try:
                os.makedirs(audit_dir, exist_ok=True)
                log_path = os.path.join(audit_dir, "payment_exports.jsonl")
                with open(log_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as exc:
                logger.warning("Failed to write audit log to %s: %s", audit_dir, exc)

    # ═══════════════════════════════════════════════════════════════════
    # Typed interface methods (new, preferred)
    # ═══════════════════════════════════════════════════════════════════

    def generate_batch(
        self, request: PaymentBatchRequest, user_id: int
    ) -> PaymentBatchCreateResult:
        """Generate a payment batch CSV file from the typed request.

        Args:
            request: Typed batch request with profile_id, invoice_ids, driver_ids.
            user_id: ID of the user requesting the batch (for permission check).

        Returns:
            ServiceResult containing PaymentBatchResult with file_path, row_count, total_amount.
        """
        # Permission check
        perm = PermissionService(self._db).can_generate_payments(user_id)
        if not perm.allowed:
            logger.warning("Permission denied for user %d: %s", user_id, perm.reason)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm.reason, code="PERMISSION_DENIED")],
            )

        rows: List[Dict[str, Any]] = []
        total_amount = 0.0
        currency = "EUR"

        # Fetch profile for defaults
        profile = self._profile_repo.get_by_id(request.profile_id) if request.profile_id else None

        # Resolve invoices
        for inv_id in request.invoice_ids:
            invoice = self._invoice_repo.get_by_id(inv_id)
            if not invoice:
                logger.warning("Invoice %d not found, skipping", inv_id)
                continue
            client_id = invoice.get("client_id")
            client = self._client_repo.get_by_id(client_id) if client_id else None
            amount = float(invoice.get("total_amount", 0) or 0)
            currency = invoice.get("currency", currency)
            rows.append({
                "recipient_name": (client or {}).get("name", ""),
                "bank_name": (client or {}).get("bank_name", ""),
                "bank_account": (client or {}).get("bank_account", ""),
                "bank_code": (client or {}).get("bank_code", ""),
                "bank_bic": (client or {}).get("bank_bic", ""),
                "iban": (client or {}).get("iban", ""),
                "amount": amount,
                "currency": currency,
                "payment_reference": invoice.get("invoice_number", f"INV-{inv_id}"),
                "recipient_type": "client",
            })
            total_amount += amount

        # Resolve drivers
        for drv_id in request.driver_ids:
            driver = self._driver_repo.get_by_id(drv_id)
            if not driver:
                logger.warning("Driver %d not found, skipping", drv_id)
                continue
            amount = 0.0  # No amount in request; profile or caller determines this
            rows.append({
                "recipient_name": driver.get("name", ""),
                "bank_name": "",
                "bank_account": driver.get("bank_account", ""),
                "bank_code": driver.get("bank_code", ""),
                "bank_bic": driver.get("bank_bic", ""),
                "iban": driver.get("iban", ""),
                "amount": amount,
                "currency": currency,
                "payment_reference": f"DRV-{drv_id}",
                "recipient_type": "driver",
            })
            total_amount += amount

        if not rows:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(
                    message="No valid invoices or drivers found in request",
                    code="EMPTY_BATCH",
                )],
            )

        # Generate CSV file
        batch_id = int(time.time())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"payment_batch_{batch_id}_{timestamp}.csv"
        file_path = os.path.join(_BATCH_EXPORT_DIR, filename)

        csv_content = self.build_batch_csv(rows)
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8-sig") as f:
            f.write(csv_content)

        row_count = len(rows)
        logger.info(
            "Payment batch generated: profile_id=%d, invoices=%d, drivers=%d, "
            "rows=%d, total=%.2f %s, file=%s",
            request.profile_id,
            len(request.invoice_ids),
            len(request.driver_ids),
            row_count,
            total_amount,
            currency,
            file_path,
        )
        self._log_export("generate_batch", {
            "batch_id": batch_id,
            "profile_id": request.profile_id,
            "invoice_count": len(request.invoice_ids),
            "driver_count": len(request.driver_ids),
            "row_count": row_count,
            "total_amount": total_amount,
            "currency": currency,
            "file_path": file_path,
        })

        return ServiceResult(
            success=True,
            data=PaymentBatchResult(
                batch_id=batch_id,
                file_path=file_path,
                row_count=row_count,
                total_amount=total_amount,
                currency=currency,
                generated_at=datetime.utcnow(),
            ),
        )

    def validate_recipients(
        self, request: PaymentBatchRequest
    ) -> ServiceResult[List[str]]:
        """Validate that all referenced invoices/drivers exist and have payment info.

        Args:
            request: Typed batch request with invoice_ids and driver_ids.

        Returns:
            ServiceResult containing a list of validation error messages.
        """
        errors: List[str] = []

        for inv_id in request.invoice_ids:
            invoice = self._invoice_repo.get_by_id(inv_id)
            if not invoice:
                errors.append(f"Invoice {inv_id}: not found")
                continue
            client_id = invoice.get("client_id")
            if not client_id:
                errors.append(f"Invoice {inv_id}: no client associated")
                continue
            client = self._client_repo.get_by_id(client_id)
            if not client:
                errors.append(f"Invoice {inv_id}: client {client_id} not found")
                continue
            bank_account = (client.get("bank_account") or "").strip()
            iban = (client.get("iban") or "").strip()
            if not bank_account and not iban:
                name = client.get("name", str(client_id))
                errors.append(f"Invoice {inv_id} (client {name}): missing bank account or IBAN")

        for drv_id in request.driver_ids:
            driver = self._driver_repo.get_by_id(drv_id)
            if not driver:
                errors.append(f"Driver {drv_id}: not found")
                continue
            bank_account = (driver.get("bank_account") or "").strip()
            iban = (driver.get("iban") or "").strip()
            if not bank_account and not iban:
                name = driver.get("name", str(drv_id))
                errors.append(f"Driver {drv_id} ({name}): missing bank account or IBAN")

        return ServiceResult(success=len(errors) == 0, data=errors)

    def create_profile(
        self, request: PaymentProfileCreate, user_id: int
    ) -> ServiceResult[PaymentProfileResult]:
        """Create a new payment profile.

        Args:
            request: Payment profile data (name, bank_name, iban, swift, currency, is_default).
            user_id: ID of the user creating the profile (for permission check).

        Returns:
            ServiceResult containing the created PaymentProfileResult.
        """
        perm = PermissionService(self._db).can_generate_payments(user_id)
        if not perm.allowed:
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm.reason, code="PERMISSION_DENIED")],
            )

        data: Dict[str, Any] = {
            "profile_name": request.name,
            "bank_name": request.bank_name,
            "iban": request.iban,
            "bank_bic": request.swift,
            "recipient_type": "custom",
        }
        try:
            profile_id = self._profile_repo.create(data)
            logger.info(
                "Payment profile created: id=%d, name=%s",
                profile_id, request.name,
            )
            return ServiceResult(
                success=True,
                data=PaymentProfileResult(
                    id=profile_id,
                    name=request.name,
                    bank_name=request.bank_name,
                    iban=request.iban,
                    swift=request.swift,
                    currency=request.currency,
                    is_default=request.is_default,
                ),
            )
        except Exception as exc:
            logger.error("Failed to create payment profile: %s", exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="CREATE_FAILED")],
            )

    def list_profiles(self) -> ServiceResult[List[PaymentProfileResult]]:
        """List all active payment profiles.

        Returns:
            ServiceResult containing a list of PaymentProfileResult.
        """
        try:
            profiles = self._profile_repo.get_all(include_inactive=False)
            results = [
                PaymentProfileResult(
                    id=p["id"],
                    name=p.get("profile_name", ""),
                    bank_name=p.get("bank_name", ""),
                    iban=p.get("iban", ""),
                    swift=p.get("bank_bic", ""),
                    currency="EUR",
                    is_default=False,
                )
                for p in profiles
            ]
            return ServiceResult(success=True, data=results)
        except Exception as exc:
            logger.error("Failed to list payment profiles: %s", exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="LIST_FAILED")],
            )

    @staticmethod
    def calculate_total(batch_items: List[Dict[str, Any]]) -> float:
        """Calculate the sum of amounts from a list of batch items.

        Args:
            batch_items: List of payment batch item dicts with an 'amount' key.

        Returns:
            Total amount as a float.
        """
        return sum(float(item.get("amount", 0) or 0) for item in batch_items)

    # ═══════════════════════════════════════════════════════════════════
    # Existing dict-based methods (deprecated, kept for backward compat)
    # ═══════════════════════════════════════════════════════════════════

    def get_all_recipients(self, query: str = "") -> List[Dict[str, Any]]:
        """Get all payment recipients across clients, drivers, and custom profiles.

        .. deprecated::
            Use the typed Pydantic methods instead. This method is kept for
            backward compatibility and will be removed in a future version.

        Returns a unified list of dicts with keys:
        recipient_id, recipient_type, recipient_name, bank_name, bank_account,
        bank_code, bank_bic, iban, payment_reference
        """
        warnings.warn(
            "get_all_recipients is deprecated, use typed Pydantic methods instead",
            DeprecationWarning,
            stacklevel=2,
        )
        recipients: List[Dict[str, Any]] = []

        # 1. Active clients with bank info
        clients = self._client_repo.get_all(include_inactive=False, limit=2000)
        for c in clients:
            bank_account = (c.get("bank_account") or "").strip()
            iban = (c.get("iban") or "").strip()
            if not bank_account and not iban:
                continue  # skip clients without payment info
            if query and query.lower() not in (c.get("name") or "").lower():
                continue
            recipients.append({
                "recipient_id": c["id"],
                "recipient_type": "client",
                "recipient_name": c.get("name", ""),
                "bank_name": c.get("bank_name", ""),
                "bank_account": bank_account,
                "bank_code": c.get("bank_code", ""),
                "bank_bic": c.get("bank_bic", ""),
                "iban": iban,
                "payment_reference": c.get("payment_reference", ""),
            })

        # 2. Active drivers with bank info
        drivers = self._driver_repo.get_all(limit=2000)
        for d in drivers:
            if not d.get("is_active"):
                continue
            bank_account = (d.get("bank_account") or "").strip()
            iban = (d.get("iban") or "").strip()
            if not bank_account and not iban:
                continue
            if query and query.lower() not in (d.get("name") or "").lower():
                continue
            recipients.append({
                "recipient_id": d["id"],
                "recipient_type": "driver",
                "recipient_name": d.get("name", ""),
                "bank_name": "",
                "bank_account": bank_account,
                "bank_code": d.get("bank_code", ""),
                "bank_bic": d.get("bank_bic", ""),
                "iban": iban,
                "payment_reference": "",
            })

        # 3. Active custom payment profiles
        profiles = self._profile_repo.get_all(include_inactive=False, limit=2000)
        for p in profiles:
            bank_account = (p.get("bank_account") or "").strip()
            iban = (p.get("iban") or "").strip()
            if not bank_account and not iban:
                continue
            if query and query.lower() not in (p.get("profile_name") or "").lower():
                continue
            recipients.append({
                "recipient_id": p["id"],
                "recipient_type": p.get("recipient_type", "custom"),
                "recipient_name": p.get("profile_name", ""),
                "bank_name": p.get("bank_name", ""),
                "bank_account": bank_account,
                "bank_code": p.get("bank_code", ""),
                "bank_bic": p.get("bank_bic", ""),
                "iban": iban,
                "payment_reference": p.get("payment_reference", ""),
            })

        return recipients

    def build_batch_csv(self, batch_items: List[Dict[str, Any]]) -> str:
        """Build a CSV string from batch items for banking bulk payment import.

        .. deprecated::
            Prefer using ``generate_batch()`` which returns a typed result.
            Kept for backward compatibility.

        Args:
            batch_items: List of dicts with keys matching BANK_CSV_COLUMNS

        Returns:
            CSV string (including header row)
        """
        warnings.warn(
            "build_batch_csv is deprecated, use generate_batch() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._log_export("build_batch_csv", {
            "item_count": len(batch_items),
            "recipient_count": len(set(
                (i.get("recipient_type", ""), i.get("recipient_name", ""))
                for i in batch_items if i.get("recipient_name")
            )),
        })
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=BANK_CSV_COLUMNS,
            extrasaction='ignore',
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(batch_items)
        return output.getvalue()

    def build_batch_csv_from_request(self, items: List[Dict[str, Any]]) -> str:
        """Transform PaymentBatchItem dicts into CSV rows with resolved payment info.

        .. deprecated::
            Prefer using ``generate_batch()`` which accepts typed ``PaymentBatchRequest``.
            Kept for backward compatibility.

        Each item dict should have: recipient_id, recipient_type, amount, currency, payment_reference.
        This method resolves the actual banking details from the database.
        """
        warnings.warn(
            "build_batch_csv_from_request is deprecated, use generate_batch() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._log_export("build_batch_csv_from_request", {
            "item_count": len(items),
            "recipient_ids": [
                {"id": i.get("recipient_id"), "type": i.get("recipient_type")}
                for i in items if i.get("recipient_id") is not None
            ],
        })
        rows = []
        for item in items:
            raw_id = item.get("recipient_id")
            if raw_id is None:
                continue
            recipient_id = int(raw_id)
            recipient_type = item.get("recipient_type", "")
            amount = item.get("amount", 0.0)
            currency = item.get("currency", "EUR")
            reference = item.get("payment_reference", "")

            # Resolve banking info
            bank_name = ""
            bank_account = ""
            bank_code = ""
            bank_bic = ""
            iban = ""
            recipient_name = ""

            if recipient_type == "client":
                client = self._client_repo.get_by_id(recipient_id)
                if client:
                    recipient_name = client.get("name", "")
                    bank_name = client.get("bank_name", "")
                    bank_account = client.get("bank_account", "")
                    bank_code = client.get("bank_code", "")
                    bank_bic = client.get("bank_bic", "")
                    iban = client.get("iban", "")
                    reference = reference or client.get("payment_reference", "")
            elif recipient_type == "driver":
                driver = self._driver_repo.get_by_id(recipient_id)
                if driver:
                    recipient_name = driver.get("name", "")
                    bank_account = driver.get("bank_account", "")
                    bank_code = driver.get("bank_code", "")
                    bank_bic = driver.get("bank_bic", "")
                    iban = driver.get("iban", "")
            elif recipient_type in ("custom", "government", "supplier", "contractor", "other"):
                profile = self._profile_repo.get_by_id(recipient_id)
                if profile:
                    recipient_name = profile.get("profile_name", "")
                    bank_name = profile.get("bank_name", "")
                    bank_account = profile.get("bank_account", "")
                    bank_code = profile.get("bank_code", "")
                    bank_bic = profile.get("bank_bic", "")
                    iban = profile.get("iban", "")
                    reference = reference or profile.get("payment_reference", "")

            rows.append({
                "recipient_name": recipient_name,
                "bank_name": bank_name,
                "bank_account": bank_account,
                "bank_code": bank_code,
                "bank_bic": bank_bic,
                "iban": iban,
                "amount": amount,
                "currency": currency,
                "payment_reference": reference,
                "recipient_type": recipient_type,
            })

        return self.build_batch_csv(rows)

    def validate_recipient_payment_info(self, recipient_id: int, recipient_type: str) -> List[str]:
        """Validate that a recipient has sufficient payment info.

        .. deprecated::
            Use ``validate_recipients()`` which accepts typed ``PaymentBatchRequest``.
            Kept for backward compatibility.

        Returns list of error messages.
        """
        warnings.warn(
            "validate_recipient_payment_info is deprecated, use validate_recipients() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        errors = []
        if recipient_type == "client":
            entity = self._client_repo.get_by_id(recipient_id)
        elif recipient_type == "driver":
            entity = self._driver_repo.get_by_id(recipient_id)
        elif recipient_type in ("custom", "government", "supplier", "contractor", "other"):
            entity = self._profile_repo.get_by_id(recipient_id)
        else:
            return [f"Unknown recipient type: {recipient_type}"]

        if not entity:
            return [f"Recipient not found: {recipient_type}/{recipient_id}"]

        bank_account = (entity.get("bank_account") or "").strip()
        iban = (entity.get("iban") or "").strip()
        if not bank_account and not iban:
            name = entity.get("name") or entity.get("profile_name") or str(recipient_id)
            errors.append(f"{name}: Either bank_account or iban must be provided")

        return errors
