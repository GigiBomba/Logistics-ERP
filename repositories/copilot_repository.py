"""Copilot repository — audit log, conversation summary, insights, reasoning graphs.

Multi-tenant filtering is applied manually via ``company_id = ?`` or
``get_company_id()`` in individual queries.  Some methods (e.g. cleanup
jobs) intentionally operate across all tenants via ``# read-only``.
# read-only
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class CopilotAuditRepository(BaseRepository):
    TABLE = "copilot_audit_log"
    COLUMNS = [
        "id", "conversation_id", "action", "entity_type", "entity_id",
        "old_value", "new_value", "performed_by", "company_id", "created_at",
    ]

    def log_action(self, conversation_id: str, action: str, entity_type: str,
                   entity_id: str, old_value: str = "", new_value: str = "",
                   performed_by: str = "") -> int:
        from database.tenant_context import get_company_id
        data = {
            "conversation_id": conversation_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_value": old_value,
            "new_value": new_value,
            "performed_by": performed_by,
            "company_id": get_company_id() or 0,
            "created_at": datetime.utcnow().isoformat(),
        }
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
            commit=True,
        )

    def get_by_conversation(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        from database.tenant_context import get_company_id
        company_id = get_company_id()
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE conversation_id = ? "
            f"{'AND company_id = ?' if company_id else ''} "
            f"ORDER BY created_at DESC LIMIT ?",
            (conversation_id, company_id, limit) if company_id else (conversation_id, limit),
        )

    def get_undo_log(self, entity_type: str, entity_id: str, performed_by: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE entity_type = ? AND entity_id = ? "
            f"AND performed_by = ? AND action = 'update' ORDER BY created_at DESC LIMIT 1",
            (entity_type, str(entity_id), performed_by),
        )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        """Delete audit rows older than *cutoff*, optionally tenant-scoped.

        ``company_id`` scopes the delete via ``_company_filter_for``; ``None``
        keeps the context-based behaviour for desktop/local callers.
        """
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )

    def anonymize_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        return self._execute_with_count(
            f"UPDATE {self.TABLE} SET old_value = 'anonymized', new_value = 'anonymized', "
            f"performed_by = 'anonymized' WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )


class ConversationSummaryRepository(BaseRepository):
    TABLE = "conversation_summary"
    COLUMNS = [
        "id", "conversation_id", "summary", "model", "token_count",
        "company_id", "created_at",
    ]

    def get_by_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        from database.tenant_context import get_company_id
        company_id = get_company_id()
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE conversation_id = ? "
            f"{'AND company_id = ?' if company_id else ''} "
            f"ORDER BY created_at DESC LIMIT 1",
            (conversation_id, company_id) if company_id else (conversation_id,),
        )

    def list_by_company(self, company_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (company_id, limit, offset),
        )

    def create(self, data: Dict[str, Any]) -> int:
        from database.tenant_context import get_company_id
        company_id = get_company_id()
        if company_id is not None and "company_id" not in data:
            data["company_id"] = company_id
        self._validate_columns(data, extra_allowed={"company_id"})
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
            commit=True,
        )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )


class CopilotInsightRepository(BaseRepository):
    TABLE = "copilot_insights"
    COLUMNS = [
        "id", "company_id", "insight_type", "severity", "payload",
        "is_read", "created_at",
    ]

    def create(self, data: Dict[str, Any]) -> int:
        """Insert an insight, deduplicating against the unique index
        ``idx_copilot_insights_dedup(company_id, insight_type, payload)``.

        ``INSERT OR IGNORE`` (translated to ``ON CONFLICT DO NOTHING`` for
        PostgreSQL by ``_adapt_query``) makes replayed inserts after a partial
        job run idempotent — a retry never creates a duplicate row.
        """
        from database.tenant_context import get_company_id
        company_id = get_company_id()
        if company_id is not None and "company_id" not in data:
            data["company_id"] = company_id
        self._validate_columns(data, extra_allowed={"company_id"})
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        query = self._adapt_query(
            f"INSERT OR IGNORE INTO {self.TABLE} ({cols}) VALUES ({vals})"
        )
        return self._execute_insert(
            query,
            tuple(data.values()),
            commit=True,
        )

    def list_by_company(self, company_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE company_id = ? "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (company_id, limit, offset),
        )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )


class CopilotReasoningGraphRepository(BaseRepository):
    TABLE = "copilot_reasoning_graphs"
    COLUMNS = [
        "id", "conversation_id", "graph_json", "company_id", "created_at",
    ]

    def get_by_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        from database.tenant_context import get_company_id
        company_id = get_company_id()
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE conversation_id = ? "
            f"{'AND company_id = ?' if company_id else ''} LIMIT 1",
            (conversation_id, company_id) if company_id else (conversation_id,),
        )

    def upsert(self, conversation_id: str, graph_json: str) -> None:
        from database.tenant_context import get_company_id
        self._execute(
            f"INSERT OR REPLACE INTO {self.TABLE} "
            f"(conversation_id, graph_json, company_id, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, graph_json, get_company_id() or 0, datetime.utcnow().isoformat()),
            commit=True,
        )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )
