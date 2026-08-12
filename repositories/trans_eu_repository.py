"""Trans.eu integration repository — user tokens, freight offers, webhooks.

Multi-tenant filtering is applied manually via ``company_id = ?`` in
individual queries rather than the generic ``_company_filter`` helper
(because some methods are cross-tenant system operations).
# read-only
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from repositories import BaseRepository


class TransEuUserTokenRepository(BaseRepository):
    TABLE = "trans_eu_user_tokens"
    COLUMNS = [
        "id", "company_id", "access_token_encrypted", "refresh_token_encrypted",
        "expires_at", "created_at", "updated_at", "last_refreshed_at", "status",
    ]

    def get_by_company(self, company_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? ORDER BY created_at DESC LIMIT 1",
            (company_id,),
        )

    def get_active_expiring_before(self, cutoff: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE expires_at < ? AND (status = 'active' OR status IS NULL)",
            (cutoff,),
        )

    def upsert(self, company_id: int, access: str, refresh: str, expires_at: str) -> None:
        now = datetime.utcnow().isoformat()
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE} "
            f"(company_id, access_token_encrypted, refresh_token_encrypted, expires_at, created_at, updated_at) "
            f"VALUES (?, ?, ?, ?, ?, ?)",
            (company_id, access, refresh, expires_at, now, now), commit=True,
        )

    def update(self, token_id: int, **data) -> None:
        self._validate_columns(data)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (token_id,), commit=True,
        )

    def mark_needs_reauth(self, token_id: int) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET status = 'needs_reauth' WHERE id = ?",
            (token_id,), commit=True,
        )

    def delete_by_company(self, company_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE company_id = ?", (company_id,), commit=True,
        )

    def delete_revoked_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        """Delete revoked tokens older than *cutoff*, optionally tenant-scoped."""
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE status = 'revoked' AND updated_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )


class TransEuFreightOfferRepository(BaseRepository):
    TABLE = "trans_eu_freight_offers"
    COLUMNS = [
        "id", "company_id", "offer_id", "raw_json", "origin", "destination",
        "price_eur", "distance_km", "status", "matched_trip_id",
        "created_at", "expires_at",
    ]

    def get_by_company(self, company_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (company_id, limit, offset),
        )

    def get_by_offer_id(self, offer_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE offer_id = ?", (offer_id,),
        )

    def get_distinct_company_ids_by_status(self, statuses) -> List[int]:
        placeholders = ", ".join("?" for _ in statuses)
        if not statuses:
            return []
        rows = self._fetchall(
            f"SELECT DISTINCT company_id FROM {self.TABLE} WHERE status IN ({placeholders})",
            tuple(statuses),
        )
        return [r["company_id"] for r in rows]

    def get_freight_ids_by_company_and_status(self, company_id: int, statuses) -> List[str]:
        placeholders = ", ".join("?" for _ in statuses)
        if not statuses:
            return []
        rows = self._fetchall(
            f"SELECT offer_id FROM {self.TABLE} WHERE company_id = ? AND status IN ({placeholders})",
            (company_id,) + tuple(statuses),
        )
        return [r["offer_id"] for r in rows]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data, extra_allowed={"company_id"})
        data = self._set_company_from_context(data)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
        )

    def update_status(self, company_id: int, status: str, current_status: str) -> int:
        return self._execute_with_count(
            f"UPDATE {self.TABLE} SET status = ? WHERE company_id = ? AND status = ?",
            (status, company_id, current_status), commit=True,
        )

    def delete_expired(self, cutoff: str, company_id: Optional[int] = None) -> int:
        """Delete expired freight offers, optionally tenant-scoped.

        ``company_id`` scopes the delete via ``_company_filter_for``; ``None``
        keeps the context-based behaviour for desktop/local callers.
        """
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE expires_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )


class TransEuWebhookEventRepository(BaseRepository):
    TABLE = "trans_eu_webhook_events"
    COLUMNS = [
        "id", "company_id", "event_type", "payload_json", "signature",
        "processing_status", "received_at", "processed_at", "error_message",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data, extra_allowed={"company_id"})
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()), commit=True,
        )

    def get_unprocessed(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE processing_status = 'received' "
            f"ORDER BY received_at ASC LIMIT ?", (limit,),
        )

    def mark_processed(self, event_id: int, error: str = "") -> None:
        now = datetime.utcnow().isoformat()
        if error:
            self._execute(
                f"UPDATE {self.TABLE} SET processing_status = 'failed', "
                f"processed_at = ?, error_message = ? WHERE id = ?",
                (now, error, event_id), commit=True,
            )
        else:
            self._execute(
                f"UPDATE {self.TABLE} SET processing_status = 'processed', "
                f"processed_at = ? WHERE id = ?",
                (now, event_id), commit=True,
            )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        """Delete old webhook events, optionally tenant-scoped.

        ``company_id`` scopes the delete via ``_company_filter_for``; ``None``
        keeps the context-based behaviour for desktop/local callers.
        """
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE received_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )
