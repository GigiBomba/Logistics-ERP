"""Repository for freight load negotiation threads.

Company-scoped, provider-agnostic negotiation records (``freight_negotiations``).
There is NO external TransEu/TIMOCOM push — the thread is a LOCAL record of the
accept / reject / counter dialogue (the adapter push can come later).  Rows form
a linear chain via ``parent_negotiation_id``; ``latest()`` returns the tail so a
counter can link to it.
"""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class FreightNegotiationRepository(BaseRepository):
    TABLE = "freight_negotiations"
    COLUMNS = [
        "id", "company_id", "provider_id", "provider_load_id", "direction",
        "status", "amount_eur", "currency", "counterparty_name",
        "counterparty_id", "parent_negotiation_id", "created_by",
        "created_at", "updated_at",
    ]

    def get_thread(
        self, company_id: int, provider_id: str, provider_load_id: str
    ) -> List[Dict[str, Any]]:
        """Return the full negotiation thread (oldest → newest)."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE company_id = ? AND provider_id = ? AND provider_load_id = ? "
            f"ORDER BY created_at, id",
            (company_id, provider_id, provider_load_id),
        )

    def get_by_id(
        self, negotiation_id: int, company_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single negotiation record, company-scoped when provided."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE id = ? {self._company_filter_for(company_id)}",
            (negotiation_id,) + self._company_params_for(company_id),
        )

    def latest(
        self, company_id: int, provider_id: str, provider_load_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent record of a thread (None when empty)."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} "
            f"WHERE company_id = ? AND provider_id = ? AND provider_load_id = ? "
            f"ORDER BY created_at DESC, id DESC LIMIT 1",
            (company_id, provider_id, provider_load_id),
        )

    def create(self, data: Dict[str, Any]) -> int:
        """Insert a negotiation record and return its row id.

        ``company_id`` must be supplied by the caller (the API resolves it from
        the JWT); the HTTP path does not populate the tenant contextvars.
        """
        self._validate_columns(data)
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
            commit=True,
        )
