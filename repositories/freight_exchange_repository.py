"""Repository for freight exchange connections and saved searches.

Manages two UUID-keyed tables (``freight_exchange_connections``,
``saved_searches``) with dual SQLite / PostgreSQL support.
"""
from typing import Any, Dict, List, Optional

from database.uuid_helpers import is_postgresql, new_uuid
from repositories import BaseRepository


class FreightExchangeRepository(BaseRepository):
    TABLE_CONNECTIONS = "freight_exchange_connections"
    TABLE_SEARCHES = "saved_searches"
    COLUMNS = [
        "id", "company_id", "provider_id", "user_id", "credentials_encrypted",
        "session_state", "status", "last_health_check_at",
        "last_health_check_status", "connected_at", "created_at",
    ]
    COLUMNS_SEARCHES = [
        "id", "company_id", "user_id", "label", "filters",
        "provider_ids", "created_at", "last_refreshed_at",
    ]

    # ── Connections ──────────────────────────────────────────────────

    def get_connection(self, company_id: int, provider_id: str) -> Optional[Dict[str, Any]]:
        """Return a single freight exchange connection by company + provider."""
        # Enforce tenant isolation for non-admin users
        if self._scoped and company_id != self._user_company_id:
            return None
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_CONNECTIONS} "
            f"WHERE company_id = ? AND provider_id = ?",
            (company_id, provider_id),
        )

    def list_connections(self, company_id: int) -> List[Dict[str, Any]]:
        """Return all connections for a company, newest first."""
        # Enforce tenant isolation for non-admin users
        if self._scoped and company_id != self._user_company_id:
            return []
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_CONNECTIONS} "
            f"WHERE company_id = ? ORDER BY created_at DESC",
            (company_id,),
        )

    def create_connection(self, data: dict) -> str:
        """Create a new freight exchange connection and return its UUID.

        For PostgreSQL the database generates the UUID via
        ``gen_random_uuid()``; for SQLite it is supplied by Python.
        """
        self._validate_columns(data, columns=self.COLUMNS)
        data = self._set_company_from_context(data)

        if is_postgresql(self.db):
            data.pop("id", None)   # DB generates via DEFAULT gen_random_uuid()
        else:
            data.setdefault("id", new_uuid(self.db))   # supply UUID for SQLite

        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        raw_id = self._execute_insert(
            f"INSERT INTO {self.TABLE_CONNECTIONS} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

        if is_postgresql(self.db):
            return str(raw_id)      # UUID string from RETURNING id
        return data["id"]           # Python-generated UUID for SQLite

    def update_connection(self, connection_id: str, data: dict) -> None:
        """Update columns of a freight exchange connection."""
        self._validate_columns(data, columns=self.COLUMNS)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE_CONNECTIONS} SET {sets} "
            f"WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (connection_id,) + self._company_params(),
        )

    def delete_connection(self, connection_id: str) -> None:
        """Delete a freight exchange connection by UUID."""
        self._execute(
            f"DELETE FROM {self.TABLE_CONNECTIONS} "
            f"WHERE id = ? {self._company_filter()}",
            (connection_id,) + self._company_params(),
        )

    def get_connected_providers(self, company_id: int) -> List[Dict[str, Any]]:
        """Return only connections where ``status = 'connected'``."""
        # Enforce tenant isolation for non-admin users
        if self._scoped and company_id != self._user_company_id:
            return []
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_CONNECTIONS} "
            f"WHERE company_id = ? AND status = 'connected'",
            (company_id,),
        )

    def update_health(self, connection_id: str, status: str, checked_at: str) -> None:
        """Set the last health check status and timestamp on a connection."""
        self._execute(
            f"UPDATE {self.TABLE_CONNECTIONS} "
            f"SET last_health_check_status = ?, last_health_check_at = ? "
            f"WHERE id = ? {self._company_filter()}",
            (status, checked_at, connection_id) + self._company_params(),
        )

    # ── Saved Searches ───────────────────────────────────────────────

    def get_search(self, search_id: str) -> Optional[Dict[str, Any]]:
        """Return a single saved search by UUID."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_SEARCHES} "
            f"WHERE id = ? {self._company_filter()}",
            (search_id,) + self._company_params(),
        )

    def list_searches(self, company_id: int, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent saved searches for a company + user."""
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_SEARCHES} "
            f"WHERE company_id = ? AND user_id = ? "
            f"ORDER BY created_at DESC LIMIT ?",
            (company_id, user_id, limit),
        )

    def create_search(self, data: dict) -> str:
        """Create a new saved search and return its UUID.

        For PostgreSQL the database generates the UUID via
        ``gen_random_uuid()``; for SQLite it is supplied by Python.
        """
        self._validate_columns(data, columns=self.COLUMNS_SEARCHES)
        data = self._set_company_from_context(data)

        if is_postgresql(self.db):
            data.pop("id", None)
        else:
            data.setdefault("id", new_uuid(self.db))

        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        raw_id = self._execute_insert(
            f"INSERT INTO {self.TABLE_SEARCHES} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        )

        if is_postgresql(self.db):
            return str(raw_id)
        return data["id"]

    def update_search(self, search_id: str, data: dict) -> None:
        """Update columns of a saved search."""
        self._validate_columns(data, columns=self.COLUMNS_SEARCHES)
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE_SEARCHES} SET {sets} "
            f"WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (search_id,) + self._company_params(),
        )

    def delete_search(self, search_id: str) -> None:
        """Delete a saved search by UUID."""
        self._execute(
            f"DELETE FROM {self.TABLE_SEARCHES} "
            f"WHERE id = ? {self._company_filter()}",
            (search_id,) + self._company_params(),
        )
