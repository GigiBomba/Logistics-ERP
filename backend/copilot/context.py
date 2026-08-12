"""Context Architecture — four-layer context with strict shapes and TTLs.

SessionContext and ConversationContext stored in Redis (reuse existing RedisCache).
Key pattern: copilot:session:{company_id}:{user_id}:{session_id}
TTL: 4 hours, sliding on activity.

Blueprint: §8
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.cache import get_cache
from backend.copilot.schemas import (
    ConversationContext,
    GlobalContext,
    SessionContext,
    ToolContext,
)

logger = logging.getLogger(__name__)

# ── Redis key builders ─────────────────────────────────────────────────────

def _session_key(company_id: int, user_id: int, session_id: str) -> str:
    return f"copilot:session:{company_id}:{user_id}:{session_id}"

def _conversation_key(company_id: int, user_id: int, conversation_id: str) -> str:
    return f"copilot:conversation:{company_id}:{user_id}:{conversation_id}"

# ── Session Context ────────────────────────────────────────────────────────

async def load_session_context(
    company_id: int, user_id: int, session_id: str
) -> SessionContext:
    """Load or create a SessionContext from Redis."""
    cache = get_cache()
    raw = cache.get(_session_key(company_id, user_id, session_id))
    if raw:
        try:
            return SessionContext(**raw)
        except Exception:
            logger.warning("Corrupt SessionContext for %s, creating fresh", session_id)

    ctx = SessionContext(expires_at=datetime.utcnow() + timedelta(hours=4))
    await save_session_context(company_id, user_id, session_id, ctx)
    return ctx


async def save_session_context(
    company_id: int, user_id: int, session_id: str, ctx: SessionContext
) -> None:
    """Persist SessionContext to Redis with sliding TTL."""
    cache = get_cache()
    ctx.expires_at = datetime.utcnow() + timedelta(hours=4)
    cache.set(
        _session_key(company_id, user_id, session_id),
        ctx.model_dump(mode="json"),
        ttl=4 * 3600,  # 4 hours
    )


# ── Conversation Context ───────────────────────────────────────────────────

async def load_conversation_context(
    company_id: int, user_id: int, conversation_id: str,
    provider_id: str = "", model_id: str = "", prompt_version: str = "",
) -> ConversationContext:
    """Load or create a ConversationContext from Redis.

    Model/prompt version pinning: set on the FIRST turn, never changed mid-conversation.
    """
    cache = get_cache()
    raw = cache.get(_conversation_key(company_id, user_id, conversation_id))
    if raw:
        try:
            return ConversationContext(**raw)
        except Exception:
            logger.warning("Corrupt ConversationContext for %s, creating fresh", conversation_id)

    ctx = ConversationContext(
        conversation_id=conversation_id,
        pinned_provider_id=provider_id,
        pinned_model_id=model_id,
        pinned_prompt_version=prompt_version,
    )
    await save_conversation_context(company_id, user_id, ctx)
    return ctx


async def save_conversation_context(
    company_id: int, user_id: int, ctx: ConversationContext
) -> None:
    """Persist ConversationContext to Redis with sliding TTL."""
    cache = get_cache()
    cache.set(
        _conversation_key(company_id, user_id, ctx.conversation_id),
        ctx.model_dump(mode="json"),
        ttl=4 * 3600,
    )


async def delete_conversation_context(
    company_id: int, user_id: int, conversation_id: str
) -> None:
    """Remove a conversation context from Redis."""
    cache = get_cache()
    cache.delete(_conversation_key(company_id, user_id, conversation_id))


# ── Global Context ─────────────────────────────────────────────────────────

async def build_global_context(
    company_id: int,
    user_id: int,
    role: str,
    language: str = "en",
    timezone: str = "UTC",
    subscription_tier: str = "pro",
    feature_flags: Optional[Dict[str, bool]] = None,
) -> GlobalContext:
    """Build GlobalContext from JWT claims / user record.

    company_id is derived server-side from the JWT on every single request —
    never from a stored session value that could go stale after a company switch.
    """
    return GlobalContext(
        company_id=company_id,
        user_id=user_id,
        role=role,
        language=language,
        timezone=timezone,
        subscription_tier=subscription_tier,  # type: ignore[arg-type]
        feature_flags=feature_flags or {},
    )


# ── Tool Context ───────────────────────────────────────────────────────────

async def resolve_available_tools(
    ctx: GlobalContext, user_permissions: List[str]
) -> ToolContext:
    """Compute ToolContext server-side per request from actual RBAC role.

    available_tools is resolved AFTER permission check, not before.
    Never cached client-side, never trusted from a prior turn.

    Blueprint: §15 — Permission System.
    """
    # Deferred import to avoid circular dependency
    from backend.copilot.tools.registry import available_tools

    all_available = available_tools()
    permitted_names: List[str] = []

    for tool in all_available:
        # If a tool has no required_permission, it's accessible to all.
        # Otherwise the user must have the exact permission.
        if not tool.required_permission:
            permitted_names.append(tool.name)
        elif tool.required_permission in user_permissions:
            permitted_names.append(tool.name)

    # Build parameter schemas for permitted tools
    param_schemas: Dict[str, dict] = {}
    for tool in all_available:
        if tool.name in permitted_names and hasattr(tool.parameters_schema, "model_json_schema"):
            try:
                param_schemas[tool.name] = tool.parameters_schema.model_json_schema()
            except Exception:
                param_schemas[tool.name] = {}

    return ToolContext(
        available_tools=permitted_names,
        tool_parameters_schema=param_schemas,
    )
