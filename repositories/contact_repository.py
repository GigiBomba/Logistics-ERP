"""Contact repository — CRUD for client_contacts table."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class ContactRepository(BaseRepository):
    TABLE = "client_contacts"

    def get_by_id(self, contact_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (contact_id,)
        )

    def get_by_client(self, client_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE client_id = ? ORDER BY is_primary DESC, created_at ASC",
            (client_id,),
        )

    def get_primary_for_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Return the contact marked is_primary=1 for the given client."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} "
            "WHERE client_id = ? AND is_primary = 1 "
            "ORDER BY id ASC LIMIT 1",
            (client_id,),
        )

    def create(self, data: Dict[str, Any]) -> int:
        from datetime import datetime
        data = dict(data)
        data.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})", tuple(data.values())
        )

    def update(self, contact_id: int, data: Dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(data.values()) + (contact_id,),
        )

    def delete(self, contact_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (contact_id,))

    def set_primary(self, client_id: int, contact_id: int) -> None:
        self.begin_transaction()
        self._execute(
            f"UPDATE {self.TABLE} SET is_primary = 0 WHERE client_id = ?", (client_id,),
            commit=False,
        )
        self._execute(
            f"UPDATE {self.TABLE} SET is_primary = 1 WHERE id = ?", (contact_id,),
            commit=False,
        )
        self.commit_transaction()
