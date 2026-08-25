"""Local (in-process) Co-Pilot service — mirrors ``RemoteCopilotService``.

In LOCAL connection mode the desktop app runs without an API client / backend
URL (``ui/main_window._init_services`` sets ``copilot_service = None``), so
:class:`client.remote_copilot.RemoteCopilotService` cannot be used and the
Co-Pilot panel used to be wired with ``controller=None`` — making chat inert.

``LocalCopilotService`` implements the same surface as ``RemoteCopilotService``
(``chat``, ``voice_input``, plan ops, conversations, insights, ``ws_url``) by
running the Co-Pilot pipeline (``backend.copilot.planner.process_utterance``)
directly in-process against the local SQLite database.  This lets
:class:`ui.copilot.controllers.copilot_controller.CoPilotController` work
unchanged in local mode.

Phase-1 intent extraction is keyword-based and executes Level-0 read-only
tools, so the Co-Pilot works locally without a backend server or an LLM API
key.  The qwen API key (env ``OPERION_QWEN_API_KEY`` first, then the value
stored in preferences via Settings → AI Vision) is resolved for the
self-hosted LLM provider so any future LLM-backed phase picks up the
configured key automatically.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Plans awaiting user confirmation are held in-process (mirrors the FastAPI
# router's ``_pending_plans`` store).  Phase-1 tools are mostly SAFE and execute
# immediately, so this is only used by BUSINESS/DESTRUCTIVE tools.
_pending_plans: Dict[str, Any] = {}
_plan_owners: Dict[str, int] = {}


class LocalCopilotService:
    """API-free substitute for the Co-Pilot backend, executing in-process."""

    def __init__(
        self,
        db,
        prefs=None,
        role: str = "dispatcher",
        company_id: int = 0,
        user_id: int = 0,
        language: str = "en",
    ) -> None:
        self._db = db
        self._prefs = prefs
        self._role = role
        self._company_id = company_id
        self._user_id = user_id
        self._language = language
        self._providers_ready = False

        key_configured = bool(self.resolve_api_key("qwen"))
        logger.info(
            "LocalCopilotService initialised (role=%s company_id=%s qwen_key=%s)",
            role, company_id, "set" if key_configured else "not set",
        )

    # ── Chat / Voice ────────────────────────────────────────────────────

    async def chat(
        self,
        utterance: str,
        conversation_id: Optional[str] = None,
        language: str = "en",
    ) -> dict:
        """Run the in-process Co-Pilot pipeline for a text utterance."""
        return await self._process(utterance, conversation_id, language)

    async def voice_input(
        self,
        utterance: str,
        conversation_id: Optional[str] = None,
        language: str = "en",
    ) -> dict:
        """Voice transcript goes through the exact same local pipeline."""
        return await self._process(utterance, conversation_id, language)

    # ── API key resolution (env-first, preferences fallback) ─────────────

    def resolve_api_key(self, provider: str = "qwen") -> Optional[str]:
        """Return the configured API key for *provider*.

        Prefers the ``OPERION_<PROVIDER>_API_KEY`` environment variable and
        falls back to the value stored in preferences (``qwen_api_key``),
        matching the semantics of
        :func:`services.preferences.get_ai_api_key` without emitting the
        missing-key error log on every construction.
        """
        env_key = f"OPERION_{provider.upper()}_API_KEY"
        val = os.environ.get(env_key)
        if val:
            return val
        if self._prefs is not None:
            try:
                val = self._prefs.get_setting("qwen_api_key", "") or ""
            except Exception:
                val = ""
            if val:
                return val
        return None

    # ── Plan operations (in-process store, mirrors backend router) ───────

    def get_plan(self, plan_id: str) -> dict:
        plan = self._plan(plan_id)
        if plan is None:
            return {
                "plan_id": plan_id,
                "status": "not_found",
                "message_key": "copilot.plan.not_found",
                "message_params": {"plan_id": plan_id},
            }
        return {
            "plan_id": plan_id,
            "status": "awaiting_confirmation" if plan.requires_confirmation else "completed",
            "conversation_id": plan.conversation_id,
            "steps": [
                {
                    "step_id": s.step_id,
                    "tool_name": s.tool_name,
                    "status": s.status,
                    "result": s.result,
                    "error": s.error,
                }
                for s in plan.steps
            ],
            "intent": plan.intent.name,
            "overall_confidence": plan.overall_confidence,
        }

    async def confirm_plan(self, plan_id: str) -> dict:
        try:
            from backend.copilot.executor import confirm_and_execute
        except ImportError:
            # Packaged desktop build ships no backend package — surface the
            # same "unavailable" message the server uses when copilot is off.
            return {
                "plan_id": plan_id,
                "status": "not_available",
                "message_key": "copilot.error.unavailable",
            }

        plan = self._plan(plan_id)
        if plan is None:
            return {
                "plan_id": plan_id,
                "status": "not_found",
                "message_key": "copilot.plan.not_found",
                "message_params": {"plan_id": plan_id},
            }
        services = {
            "db": self._db,
            "company_id": self._company_id,
            "user_id": self._user_id,
            "role": self._role,
        }
        executed = await confirm_and_execute(plan, services=services)
        _pending_plans.pop(plan_id, None)
        _plan_owners.pop(plan_id, None)
        return {
            "plan_id": plan_id,
            "status": "completed",
            "steps": [
                {
                    "step_id": s.step_id,
                    "tool_name": s.tool_name,
                    "status": s.status,
                    "error": s.error,
                }
                for s in executed.steps
            ],
        }

    async def cancel_plan(self, plan_id: str) -> dict:
        try:
            from backend.copilot.executor import cancel_plan as do_cancel
        except ImportError:
            # Packaged desktop build ships no backend package.
            return {
                "plan_id": plan_id,
                "status": "not_available",
                "message_key": "copilot.error.unavailable",
            }

        plan = self._plan(plan_id)
        if plan is None:
            return {
                "plan_id": plan_id,
                "status": "not_found",
                "message_key": "copilot.plan.not_found",
                "message_params": {"plan_id": plan_id},
            }
        await do_cancel(plan)
        _pending_plans.pop(plan_id, None)
        _plan_owners.pop(plan_id, None)
        return {
            "plan_id": plan_id,
            "status": "cancelled",
            "message_key": "copilot.plan.cancelled",
            "message_params": {"plan_id": plan_id},
        }

    async def undo_plan(self, plan_id: str) -> dict:
        # Local mode has no persisted copilot_audit_log to source undo tokens
        # from — surface the same clear message the backend uses.
        return {
            "plan_id": plan_id,
            "status": "not_available",
            "message_key": "copilot.undo.not_available",
        }

    # ── Conversations / insights (not persisted locally) ─────────────────

    def list_conversations(self, limit: int = 20, cursor: Optional[str] = None) -> list:
        return []

    def get_conversation(self, conversation_id: str) -> dict:
        raise RuntimeError(
            "copilot.error.conversation_not_found"
        )

    def list_insights(
        self, limit: int = 20, status_filter: Optional[str] = None
    ) -> list:
        return []

    # ── WebSocket (no server in local mode) ──────────────────────────────

    def ws_url(self, conversation_id: str) -> str:
        """Local mode has no WebSocket endpoint — return an empty URL.

        ``CoPilotController._do_connect_ws`` treats an empty URL as "no live
        updates available" and skips connecting.
        """
        return ""

    # ── Internal helpers ─────────────────────────────────────────────────

    def _plan(self, plan_id: str) -> Optional[Any]:
        """Return the pending CoPilotResponse (or ``None``) for *plan_id*."""
        resp = _pending_plans.get(plan_id)
        if resp is None or resp.plan is None:
            return None
        if _plan_owners.get(plan_id, self._company_id) != self._company_id:
            return None
        return resp.plan

    async def _process(
        self,
        utterance: str,
        conversation_id: Optional[str],
        language: str,
    ) -> dict:
        """Run ``process_utterance`` in-process and return the response dict.

        The response is serialized with ``model_dump(mode="json")`` so it
        round-trips cleanly through ``CoPilotController._parse_response``.
        """
        try:
            from backend.copilot.context import resolve_available_tools
            from backend.copilot.planner import (
                _ensure_llm_providers_loaded,
                _ensure_tools_loaded,
                process_utterance,
            )
            from backend.copilot.role_permissions import get_role_permissions
            from backend.copilot.schemas import GlobalContext
        except ImportError:
            # Packaged desktop build ships no backend package — the in-process
            # copilot pipeline cannot run.  Surface the standard "unavailable"
            # summary (the UI renders summary_key via t()).
            logger.warning(
                "LocalCopilotService: backend.copilot unavailable in this build — "
                "returning copilot.error.unavailable"
            )
            return {
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "summary_key": "copilot.error.unavailable",
                "timeline": [],
            }

        # Ensure tool + LLM provider registries are populated and the
        # self-hosted provider picks up the DB/environment key configuration.
        _ensure_tools_loaded()
        _ensure_llm_providers_loaded()
        self._reload_provider_settings()

        global_ctx = GlobalContext(
            company_id=self._company_id,
            user_id=self._user_id,
            role=self._role,
            language=language or self._language,
            timezone="UTC",
            subscription_tier="enterprise",
            feature_flags={},
        )
        user_perms = get_role_permissions(self._role)
        tool_ctx = await resolve_available_tools(global_ctx, user_perms)
        permitted_tools = set(tool_ctx.available_tools)

        conv_id = conversation_id or str(uuid.uuid4())
        services: Dict[str, Any] = {
            "db": self._db,
            "role": self._role,
            "user_id": self._user_id,
            "company_id": self._company_id,
        }
        response = await process_utterance(
            utterance=utterance,
            global_ctx=global_ctx,
            conversation_id=conv_id,
            services=services,
            permitted_tools=permitted_tools,
        )

        if response.plan and response.plan.requires_confirmation:
            _pending_plans[response.plan.plan_id] = response
            _plan_owners[response.plan.plan_id] = self._company_id

        return response.model_dump(mode="json")

    def _reload_provider_settings(self) -> None:
        """Push DB/env key configuration into the self-hosted LLM provider.

        Safe when the settings table is missing or the provider registry is
        not yet populated — failures are logged at debug level only.
        """
        try:
            from backend.copilot.llm.registry import get_provider

            provider = get_provider("self_hosted")
            if provider is not None and hasattr(provider, "reload_settings"):
                provider.reload_settings(self._db)
        except Exception:
            logger.debug(
                "LocalCopilotService: LLM provider settings reload skipped",
                exc_info=True,
            )
