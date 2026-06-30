"""Contract service — contract CRUD operations."""

from __future__ import annotations

from datetime import datetime

from repositories.document_repository import DocumentRepository

class ContractService:

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    def create_contract(self, doc_id: int, client_id: int,
                        contract_type: str = "transport",
                        start_date: str = "", end_date: str = "",
                        value_eur: float = 0, payment_terms: str = "",
                        auto_renewal: bool = False,
                        renewal_notice_days: int = 30,
                        notes: str = "") -> int:
        now = datetime.now().isoformat()
        return self._repo.create_contract(
            doc_id, client_id, contract_type, start_date, end_date,
            value_eur, payment_terms, 1 if auto_renewal else 0,
            renewal_notice_days, notes, now, now,
        )

    def get_contracts(self, client_id: int | None = None,
                      status: str = "") -> list[dict[str, object]]:
        return self._repo.get_contracts(client_id, status)

    def get_contract(self, contract_id: int) -> dict[str, object] | None:
        return self._repo.get_contract_by_id(contract_id)

    def update_contract_status(self, contract_id: int, status: str) -> None:
        now = datetime.now().isoformat()
        self._repo.update_contract(contract_id, status=status, updated_at=now)

    def get_expiring_contracts(self, days_ahead: int = 30) -> list[dict[str, object]]:
        return self._repo.get_expiring_contracts(days_ahead)
