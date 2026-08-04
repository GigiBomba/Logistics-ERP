"""Business Invariant Framework — default runtime configuration.

The invariant checks read operational configuration from
``InvariantContext.config``.  Historically no config source existed, so
``ctx.config`` always defaulted to ``{}`` and the AI invariants (AI-001…
AI-006) could not verify anything at runtime — the audit (OD-4) flagged
``ai_role_permissions`` in particular, which made AI-002 unable to enforce
the driver=read-only matrix.

This module is the minimal, clearly-located default.  Every value is a
literal constant already stated in the invariant definitions themselves
(see ``business_invariants/checks/ai_argo.py``); nothing here invents new
policy.  Consumers that construct an ``InvariantContext`` should pass
``config=default_invariant_config()`` (already wired into the CLI, the
pytest conftest and the test suite); checks additionally fall back to it
so ad-hoc contexts stay verifiable.
"""

from __future__ import annotations

from typing import Any, Dict

from backend.copilot.role_permissions import get_ai_role_permissions

__all__ = ["default_invariant_config", "AI_INVARIANT_CONFIG_KEYS"]


def default_invariant_config() -> Dict[str, Any]:
    """Return the default ``InvariantContext.config`` dict.

    AI block values mirror the constants embedded in the AI-001/AI-003/
    AI-004/AI-005/AI-006 invariant definitions; ``ai_role_permissions``
    is sourced from the authoritative §8.1 matrix in
    ``backend/copilot/role_permissions.py``.
    """
    return {
        # §8.1 AI role capability matrix (AI-002).
        "ai_role_permissions": get_ai_role_permissions(),
        # AI-001 — destructive operations require >= business confirmation.
        "destructive_confirmation_level": "business",
        # AI-003 — records produced by the AI are tagged with these sources.
        "ai_source_tags": ["ai_copilot", "argo_auto"],
        # AI-004 — circuit breaker limits (max 20 tool calls/plan,
        # 50 reasoning nodes/turn, 30s tool timeout).
        "ai_max_tool_calls_per_plan": 20,
        "ai_max_reasoning_nodes_per_turn": 50,
        "ai_tool_timeout_seconds": 30,
        # AI-005 — undo window (30 minutes).
        "ai_undo_window_minutes": 30,
    }


# Keys provided by the default config — used by tests to assert the config
# module covers every config the AI invariants read.
AI_INVARIANT_CONFIG_KEYS = frozenset(default_invariant_config().keys())
