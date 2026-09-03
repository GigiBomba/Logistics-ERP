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
                   performed_by: str = "", user_id: int = 0) -> int:
        from database.tenant_context import get_company_id
        now = datetime.utcnow().isoformat()
        data = {
            "conversation_id": conversation_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_value": old_value,
            "new_value": new_value,
            "performed_by": performed_by,
            "user_id": user_id,
            "status": "recorded",
            "parameters": "{}",
            "permission_checked": "not_recorded",
            "permission_granted": 0,
            "confirmation_level": 0,
            "model_used": "",
            "provider_id": "",
            "prompt_version": "",
            "started_at": now,
            "company_id": get_company_id() or 0,
            "created_at": now,
        }
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
            commit=True,
        )

    def log_step_execution(
        self,
        *,
        conversation_id: str,
        plan_id: str,
        step_id: str,
        tool_name: str,
        tool_version: str,
        status: str,
        parameters: Optional[Dict[str, Any]] = None,
        company_id: int = 0,
        user_id: int = 0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        model_used: str = "",
        provider_id: str = "",
        prompt_version: str = "",
        permission_checked: Optional[str] = None,
        permission_granted: Optional[bool] = None,
        confirmation_level: Optional[int] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
    ) -> int:
        """Insert a full copilot_audit_log row for one tool-execution step.

        Writes the dedicated columns (``plan_id``, ``step_id``, ``tool_name``,
        ``status``, ``result``, ``error``, ``started_at``, ``finished_at`` …)
        so the /undo endpoint and retention queries can read execution
        metadata without parsing the ``new_value`` JSON blob.

        ``company_id`` is passed explicitly (resolved from the JWT services
        dict by the executor) rather than from tenant context, keeping the
        row findable by the same request-scoped company id later.
        """
        import json

        data = {
            "conversation_id": conversation_id,
            "plan_id": plan_id,
            "step_id": step_id,
            "tool_name": tool_name,
            "tool_version": tool_version,
            "parameters": json.dumps(parameters) if parameters is not None else "{}",
            "status": status,
            "permission_checked": permission_checked if permission_checked is not None else "not_recorded",
            "permission_granted": 1 if permission_granted else 0,
            "confirmation_level": confirmation_level if confirmation_level is not None else 0,
            "result": json.dumps(result) if result is not None else None,
            "error": error,
            "model_used": model_used,
            "provider_id": provider_id,
            "prompt_version": prompt_version,
            "company_id": company_id,
            "user_id": user_id,
            "performed_by": str(user_id),
            "started_at": started_at,
            "finished_at": finished_at,
            "execution_time_ms": execution_time_ms,
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

    def update_status(self, insight_id: int, company_id: int, status: str) -> bool:
        """Set an insight's queue status (``new``/``reviewed``/``dismissed``).

        Tenant-scoped on ``company_id`` so one company can never touch
        another's insight. Returns True when exactly one row was updated.
        """
        cur = self._execute_with_count(
            f"UPDATE {self.TABLE} SET status = ? WHERE id = ? AND company_id = ?",
            (status, insight_id, company_id),
            commit=True,
        )
        return cur > 0

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
        """Persist one graph per ``(company_id, conversation_id)``.

        Uses an explicit ``ON CONFLICT (company_id, conversation_id) DO
        UPDATE`` (the same shape ``CopilotAutonomyApprovalRepository``
        uses) so a re-run REPLACES the previous graph instead of appending a
        duplicate row.  On SQLite this requires the unique index
        ``uq_copilot_reasoning_company_conversation`` (database/schema.py);
        on PostgreSQL the equivalent index comes from the Alembic migration.
        """
        from database.tenant_context import get_company_id
        company_id = get_company_id() or 0
        self._execute(
            f"INSERT INTO {self.TABLE} "
            f"(conversation_id, graph_json, company_id, created_at) VALUES (?, ?, ?, ?) "
            f"ON CONFLICT (company_id, conversation_id) DO UPDATE SET "
            f"graph_json = excluded.graph_json, created_at = excluded.created_at",
            (conversation_id, graph_json, company_id, datetime.utcnow().isoformat()),
            commit=True,
        )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )


class CopilotAutonomyApprovalRepository(BaseRepository):
    """Per-company pre-approvals for autonomous workflow execution (§21 Ph.4).

    A row ``(company_id, workflow) -> enabled`` opts a company into running a
    workflow without the manual confirmation step.  ``workflow`` is the plan's
    ``intent.name`` (e.g. ``"dispatch.cancel"``).  The autonomous execution
    path in the planner consults :meth:`is_approved` after the tier feature
    flag and circuit-breaker checks (§23.1).
    """
    TABLE = "copilot_autonomy_approvals"
    COLUMNS = [
        "id", "company_id", "workflow", "enabled", "created_by",
        "created_at", "updated_at",
    ]

    def is_approved(self, company_id: int, workflow: str) -> bool:
        """Return whether *workflow* is enabled for *company_id*."""
        row = self._fetchone(
            f"SELECT enabled FROM {self.TABLE} WHERE company_id = ? AND workflow = ? LIMIT 1",
            (company_id, workflow),
        )
        return bool(row and row.get("enabled"))

    def set_approved(
        self,
        company_id: int,
        workflow: str,
        enabled: bool,
        performed_by: str = "",
    ) -> None:
        """Insert or update the approval for one (company_id, workflow) pair.

        Uses ``ON CONFLICT (company_id, workflow) DO UPDATE`` so the unique
        index (see the Alembic migration) is honoured on both SQLite and
        PostgreSQL; ``created_at`` is preserved across re-enables.
        """
        now = datetime.utcnow().isoformat()
        self._execute(
            f"INSERT INTO {self.TABLE} "
            f"(company_id, workflow, enabled, created_by, created_at, updated_at) "
            f"VALUES (?, ?, ?, ?, ?, ?) "
            f"ON CONFLICT (company_id, workflow) DO UPDATE SET "
            f"enabled = excluded.enabled, updated_at = excluded.updated_at, "
            f"created_by = excluded.created_by",
            (company_id, workflow, 1 if enabled else 0, performed_by, now, now),
            commit=True,
        )

    def list_by_company(self, company_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT workflow, enabled, created_by, created_at, updated_at "
            f"FROM {self.TABLE} WHERE company_id = ? ORDER BY workflow LIMIT ?",
            (company_id, limit),
        )

    def delete_older_than(self, cutoff: str, company_id: Optional[int] = None) -> int:
        return self._execute_with_count(
            f"DELETE FROM {self.TABLE} WHERE created_at < ? "
            f"{self._company_filter_for(company_id)}",
            (cutoff,) + self._company_params_for(company_id),
            commit=True,
        )
