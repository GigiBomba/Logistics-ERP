"""Expiry service — document expiry tracking and alert evaluation."""

from __future__ import annotations

from datetime import datetime

from repositories.document_repository import DocumentRepository

class ExpiryService:

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    def set_expiry_date(self, doc_id: int, expiry_date: str) -> None:
        self._repo.update(doc_id, expiry_date=expiry_date,
                          updated_at=datetime.now().isoformat())

    def get_expiring(self, days_ahead: int = 30):
        return self._repo.get_expiring_documents(days_ahead)

    def get_overdue(self):
        return self._repo.get_overdue_documents()

    def evaluate_document_expiries(self, alert_mgr=None, db=None) -> int:
        from services.operations.alert_manager import (
            AlertManager,
            AlertType,
            Severity,
        )
        if alert_mgr is None:
            alert_mgr = AlertManager()
        count = 0
        overdue = self.get_overdue()
        for doc in overdue:
            alert_mgr.create_alert(
                alert_type=AlertType.DOCUMENT_EXPIRY.value if hasattr(AlertType, 'DOCUMENT_EXPIRY') else "document_expiry",
                severity=Severity.CRITICAL.value,
                title=f"Document expired: {doc.get('title', doc.get('file_name', ''))}",
                message=f"Document {doc.get('doc_number')} expired on {doc.get('expiry_date')}",
                truck_id=None,
                trip_id=None,
                metadata={"document_id": doc["id"], "doc_number": doc.get("doc_number", "")},
            )
            count += 1
        expiring = self.get_expiring(30)
        for doc in expiring:
            alert_mgr.create_alert(
                alert_type=AlertType.DOCUMENT_EXPIRY.value if hasattr(AlertType, 'DOCUMENT_EXPIRY') else "document_expiry",
                severity=Severity.WARNING.value,
                title=f"Document expiring: {doc.get('title', doc.get('file_name', ''))}",
                message=f"Document {doc.get('doc_number')} expires on {doc.get('expiry_date')}",
                truck_id=None, trip_id=None,
                metadata={"document_id": doc["id"], "doc_number": doc.get("doc_number", "")},
            )
            count += 1
        return count
