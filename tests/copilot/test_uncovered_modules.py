"""Tests for previously uncovered Co-Pilot modules.

Covers: reasoning.py, tier_gate.py, audit.py, voice/*.py, i18n_scope.py, context.py
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from backend.copilot.schemas import Intent


# ── reasoning.py (§5) ──────────────────────────────────────────────────────

class TestReasoningGraph:
    """Reasoning graph construction and resolution."""

    @pytest.mark.asyncio
    async def test_build_reasoning_graph_creates_graph(self):
        """build_reasoning_graph creates a ReasoningGraph with correct structure."""
        from backend.copilot.reasoning import build_reasoning_graph
        intent = Intent(name="dispatch.create", raw_utterance="test",
                        entities=[], missing_required_entities=["destination"])
        graph = await build_reasoning_graph("test-conv", intent)
        assert graph.graph_id is not None
        assert graph.conversation_id == "test-conv"
        assert graph.root_node_id == "goal-dispatch.create"
        assert len(graph.nodes) >= 1
        # Should have a GOAL node
        assert any(n.type.value == "goal" for n in graph.nodes.values())

    @pytest.mark.asyncio
    async def test_build_reasoning_graph_with_entities(self):
        """Entities become resolved REQUIREMENT nodes."""
        from backend.copilot.reasoning import build_reasoning_graph
        from backend.copilot.schemas import Entity
        intent = Intent(name="vehicle.search", raw_utterance="find truck 42",
                        entities=[Entity(type="vehicle", value=42, source="extracted", confidence=0.9)],
                        missing_required_entities=[])
        graph = await build_reasoning_graph("test-conv-2", intent)
        assert graph.graph_id is not None
        # There should be a resolved node for the vehicle entity
        resolved_nodes = [n for n in graph.nodes.values() if n.status == "resolved"]
        assert len(resolved_nodes) >= 1

    @pytest.mark.asyncio
    async def test_resolve_reasoning_graph_finalizes(self):
        """resolve_reasoning_graph finalizes a fully-resolved graph."""
        from backend.copilot.reasoning import build_reasoning_graph, resolve_reasoning_graph
        from backend.copilot.schemas import Entity
        intent = Intent(name="vehicle.search", raw_utterance="find truck 42",
                        entities=[Entity(type="vehicle", value=42, source="extracted", confidence=0.9)],
                        missing_required_entities=[])
        graph = await build_reasoning_graph("test-conv-3", intent)
        resolved = await resolve_reasoning_graph(graph, company_id=1, user_id=1, role="dispatcher")
        assert resolved.finalized_at is not None

    @pytest.mark.asyncio
    async def test_resolve_reasoning_graph_does_not_finalize_unresolved(self):
        """Unresolved nodes should prevent finalization."""
        from backend.copilot.reasoning import build_reasoning_graph, resolve_reasoning_graph
        intent = Intent(name="dispatch.create", raw_utterance="test",
                        entities=[], missing_required_entities=["destination"])
        graph = await build_reasoning_graph("test-conv-4", intent)
        resolved = await resolve_reasoning_graph(graph, company_id=1, user_id=1, role="dispatcher")
        assert resolved.finalized_at is None  # Still has unresolved nodes


# ── tier_gate.py (§16) ────────────────────────────────────────────────────

class TestTierGate:
    """Subscription tier feature gating."""

    def test_tier_features_pro(self):
        """Pro tier: utility AI only."""
        from backend.copilot.tier_gate import TIER_FEATURES
        pro = TIER_FEATURES["pro"]
        assert pro["utility_ai_only"] is True
        assert pro["chat"] is False
        assert pro["voice"] is False

    def test_tier_features_business(self):
        """Business tier: chat + voice with push-to-talk."""
        from backend.copilot.tier_gate import TIER_FEATURES
        bus = TIER_FEATURES["business"]
        assert bus["chat"] is True
        assert bus["voice"] is True
        assert bus["voice_activation"] == "push_to_talk"
        assert bus["autonomous"] is False
        assert bus["monthly_quota"] == 300

    def test_tier_features_enterprise(self):
        """Enterprise tier: all features with continuous wake word."""
        from backend.copilot.tier_gate import TIER_FEATURES
        ent = TIER_FEATURES["enterprise"]
        assert ent["chat"] is True
        assert ent["voice"] is True
        assert ent["voice_activation"] == "continuous_wake_word"
        assert ent["autonomous"] is True
        assert ent["monthly_quota"] == 5000
        assert ent["quota_enforcement"] == "soft"

    def test_require_feature_returns_dependency(self):
        """require_feature returns a FastAPI dependency function."""
        from backend.copilot.tier_gate import require_feature
        dep = require_feature("chat")
        assert callable(dep)


# ── audit.py (§14) ─────────────────────────────────────────────────────────

class TestAuditLogger:
    """Audit logging stubs and contracts."""

    @pytest.mark.asyncio
    async def test_log_step_start_does_not_crash(self):
        """log_step_start should not raise exceptions."""
        from backend.copilot.audit import log_step_start
        from backend.copilot.schemas import ExecutionStep, ConfirmationLevel
        step = ExecutionStep(step_id="s1", tool_name="test", tool_version="1.0.0",
                             parameters={}, confirmation_level=ConfirmationLevel.SAFE, status="pending")
        try:
            await log_step_start(1, 1, "conv", "plan", step, "model", "provider", "v1")
        except Exception:
            pytest.fail("log_step_start raised unexpectedly")

    @pytest.mark.asyncio
    async def test_log_step_complete_does_not_crash(self):
        """log_step_complete should not raise exceptions."""
        from backend.copilot.audit import log_step_complete
        from backend.copilot.schemas import ExecutionStep, ConfirmationLevel
        step = ExecutionStep(step_id="s1", tool_name="test", tool_version="1.0.0",
                             parameters={}, confirmation_level=ConfirmationLevel.SAFE, status="succeeded")
        try:
            await log_step_complete(1, 1, "conv", "plan", step, "model", "provider", "v1", result={"ok": True})
        except Exception:
            pytest.fail("log_step_complete raised unexpectedly")


# ── voice/ package (§3) ────────────────────────────────────────────────────

class TestVoiceSchemas:
    """Voice interaction schemas."""

    def test_voice_input_result_creation(self):
        """VoiceInputResult can be created with required fields."""
        from backend.copilot.voice.schemas import VoiceInputResult
        result = VoiceInputResult(transcript="test", detected_language="en",
                                  detection_confidence=0.95, audio_duration_ms=1000,
                                  stt_model_version="faster-whisper-v1")
        assert result.transcript == "test"
        assert result.detected_language == "en"
        assert 0.0 <= result.detection_confidence <= 1.0

    def test_wake_word_config_defaults(self):
        """WakeWordConfig has sensible defaults."""
        from backend.copilot.voice.schemas import WakeWordConfig
        cfg = WakeWordConfig(enabled=True, phrase="hey operion")
        assert cfg.enabled is True
        assert cfg.phrase == "hey operion"
        assert 0.0 <= cfg.sensitivity <= 1.0

    def test_tts_provider_interface(self):
        """TTSProvider ABC has required abstract methods."""
        from backend.copilot.voice.tts import TTSProvider
        assert hasattr(TTSProvider, "synthesize")
        assert hasattr(TTSProvider, "supported_languages")

    def test_voice_language_tiers_all_languages(self):
        """All 22 languages have a voice language tier entry."""
        from backend.copilot.voice.language_tiers import VOICE_LANGUAGE_TIER
        from backend.copilot.schemas import SUPPORTED_LANGUAGES
        for lang in SUPPORTED_LANGUAGES:
            assert lang in VOICE_LANGUAGE_TIER, f"Missing tier for {lang}"

    def test_voice_language_tier_values(self):
        """Voice language tiers are valid enum values."""
        from backend.copilot.voice.language_tiers import (
            VOICE_LANGUAGE_TIER, VoiceLanguageTier,
        )
        for lang, tier in VOICE_LANGUAGE_TIER.items():
            assert isinstance(tier, VoiceLanguageTier)

    def test_get_voice_tier_defaults_to_unsupported(self):
        """get_voice_tier returns UNSUPPORTED for unknown languages."""
        from backend.copilot.voice.language_tiers import get_voice_tier, VoiceLanguageTier
        tier = get_voice_tier("xx")
        assert tier == VoiceLanguageTier.UNSUPPORTED


# ── i18n_scope.py (§3.1) ──────────────────────────────────────────────────

class TestI18nScope:
    """i18n language scope."""

    def test_supported_languages_exported(self):
        """i18n_scope re-exports SUPPORTED_LANGUAGES."""
        from backend.copilot.i18n_scope import SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) == 22

    def test_all_languages_two_char_codes(self):
        """All language codes are 2-character ISO codes."""
        from backend.copilot.i18n_scope import SUPPORTED_LANGUAGES
        for lang in SUPPORTED_LANGUAGES:
            assert len(lang) == 2, f"{lang} is not 2 chars"


# ── context.py (§8) ────────────────────────────────────────────────────────

class TestContext:
    """Context architecture."""

    @pytest.mark.asyncio
    async def test_build_global_context_async(self):
        """build_global_context returns a GlobalContext."""
        from backend.copilot.context import build_global_context
        ctx = await build_global_context(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        assert ctx.company_id == 1
        assert ctx.subscription_tier == "business"
        assert ctx.language == "en"

    @pytest.mark.asyncio
    async def test_resolve_available_tools_filters_permissions(self):
        """resolve_available_tools only returns tools the user has permission for."""
        # Ensure all tool modules are loaded so the registry is populated
        from backend.copilot.planner import _ensure_tools_loaded
        _ensure_tools_loaded()

        from backend.copilot.context import resolve_available_tools
        from backend.copilot.schemas import GlobalContext
        
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        # User only has fleet:read permission
        tool_ctx = await resolve_available_tools(ctx, user_permissions=["fleet:read"])
        assert "vehicle.search" in tool_ctx.available_tools
        assert "dispatch.create" not in tool_ctx.available_tools

    @pytest.mark.asyncio
    async def test_resolve_available_tools_excludes_unpermitted(self):
        """Tools without the required permission should be excluded."""
        from backend.copilot.context import resolve_available_tools
        from backend.copilot.schemas import GlobalContext
        
        ctx = GlobalContext(
            company_id=1, user_id=1, role="dispatcher",
            language="en", timezone="UTC", subscription_tier="business",
        )
        # User has no permissions — should only see tools with empty
        # required_permission (which are accessible to all)
        tool_ctx = await resolve_available_tools(ctx, user_permissions=[])
        # Production tools all have non-empty permissions, so no production
        # tools should be available. Test fixture tools with empty permission
        # (like test.no_permission) may still appear.
        has_production_tool = any(not t.startswith("test.") for t in tool_ctx.available_tools)
        assert not has_production_tool, f"Production tools found with no permissions: {tool_ctx.available_tools}"
