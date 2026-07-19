"""Comprehensive unit tests for FeatureFlagService.

Tests cover scope-based flag evaluation (GLOBAL, PER_COMPANY, PER_USER,
PERCENTAGE), in-memory and DB overrides, percentage-rollout determinism,
flag metadata, and all specified edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.feature_flags import (
    FEATURE_FLAGS,
    FeatureFlagService,
    FlagScope,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def service() -> FeatureFlagService:
    """Return a FeatureFlagService with no DB / no Redis (in-memory only)."""
    return FeatureFlagService(db=None)


@pytest.fixture
def service_with_db() -> FeatureFlagService:
    """Return a FeatureFlagService backed by a mock DB."""
    return FeatureFlagService(db=MagicMock())


# ── Helpers ──────────────────────────────────────────────────────────


def _flag_keys() -> set[str]:
    return set(FEATURE_FLAGS.keys())


# ─────────────────────────────────────────────────────────────────────
# Basic is_enabled – GLOBAL flags
# ─────────────────────────────────────────────────────────────────────


class TestGlobalFlags:
    """GLOBAL-scoped flags are simply on/off based on their default."""

    def test_global_flag_default_true(self, service: FeatureFlagService):
        assert service.is_enabled("background_pdf_generation") is True

    def test_global_flag_default_false(self, service: FeatureFlagService):
        assert service.is_enabled("analytics_cache") is False

    def test_global_flag_can_be_overridden_in_memory(self, service: FeatureFlagService):
        service.enable_for_test("analytics_cache")
        assert service.is_enabled("analytics_cache") is True

    def test_global_flag_disabled_via_override(self, service: FeatureFlagService):
        service.disable_for_test("background_pdf_generation")
        assert service.is_enabled("background_pdf_generation") is False

    def test_reset_overrides_restores_default(self, service: FeatureFlagService):
        service.enable_for_test("analytics_cache")
        service.reset_test_overrides()
        assert service.is_enabled("analytics_cache") is False

    def test_ocr_auto_process_default_true(self, service: FeatureFlagService):
        assert service.is_enabled("ocr_auto_process") is True


# ─────────────────────────────────────────────────────────────────────
# PER_COMPANY scope
# ─────────────────────────────────────────────────────────────────────


class TestPerCompanyFlags:
    """PER_COMPANY flags respect their default but allow overrides."""

    def test_default_disabled(self, service: FeatureFlagService):
        # timocom_integration defaults to False
        assert service.is_enabled("timocom_integration") is False

    def test_in_memory_override_for_company(self, service: FeatureFlagService):
        service.enable_for_test("timocom_integration")
        assert service.is_enabled("timocom_integration", company_id=42) is True

    def test_different_companies_see_same_default(self, service: FeatureFlagService):
        assert service.is_enabled("timocom_integration", company_id=1) is False
        assert service.is_enabled("timocom_integration", company_id=99) is False

    def test_api_v2_default_false(self, service: FeatureFlagService):
        assert service.is_enabled("api_v2") is False

    def test_strict_validation_default_false(self, service: FeatureFlagService):
        assert service.is_enabled("strict_validation") is False


# ─────────────────────────────────────────────────────────────────────
# PER_USER scope
# ─────────────────────────────────────────────────────────────────────


class TestPerUserFlags:
    """No flag currently uses PER_USER scope, but the service supports it."""

    def test_user_param_does_not_break_evaluation(self, service: FeatureFlagService):
        # GLOBAL flags should work even when user_id is provided
        assert service.is_enabled("background_pdf_generation", user_id=7) is True

    def test_user_override_is_possible_in_memory(self, service: FeatureFlagService):
        service.enable_for_test("api_v2")
        assert service.is_enabled("api_v2", user_id=100) is True


# ─────────────────────────────────────────────────────────────────────
# PERCENTAGE scope
# ─────────────────────────────────────────────────────────────────────


class TestPercentageRollout:
    """PERCENTAGE-scoped flags use deterministic company_id hashing."""

    def test_rollout_10_percent_some_included(self, service: FeatureFlagService):
        """Roughly 10% of company_ids should get the feature (ids 0-9)."""
        enabled = sum(
            1 for cid in range(100)
            if service.is_enabled("new_route_planner", company_id=cid)
        )
        # With pct=10 and (id % 100) < 10, exactly 10 out of 100.
        assert enabled == 10

    def test_rollout_10_percent_specific_ids(self, service: FeatureFlagService):
        # company_id % 100 < 10 => ids 0..9
        for cid in range(10):
            assert service.is_enabled("new_route_planner", company_id=cid) is True
        # company_id % 100 >= 10 => ids 10..99
        for cid in range(10, 100):
            assert service.is_enabled("new_route_planner", company_id=cid) is False

    @patch.dict("services.feature_flags.FEATURE_FLAGS", {
        "pct_zero": type("FF", (), {"key": "pct_zero", "description": "", "default": False,
                                     "scope": FlagScope.PERCENTAGE,
                                     "metadata": {"rollout_pct": 0}})(),
    })
    def test_rollout_zero_percent(self, service: FeatureFlagService):
        assert not service.is_enabled("pct_zero", company_id=5)

    @patch.dict("services.feature_flags.FEATURE_FLAGS", {
        "pct_full": type("FF", (), {"key": "pct_full", "description": "", "default": False,
                                     "scope": FlagScope.PERCENTAGE,
                                     "metadata": {"rollout_pct": 100}})(),
    })
    def test_rollout_one_hundred_percent(self, service: FeatureFlagService):
        assert service.is_enabled("pct_full", company_id=42)

    @patch.dict("services.feature_flags.FEATURE_FLAGS", {
        "pct_above": type("FF", (), {"key": "pct_above", "description": "", "default": False,
                                      "scope": FlagScope.PERCENTAGE,
                                      "metadata": {"rollout_pct": 150}})(),
    })
    def test_rollout_above_100_is_enabled(self, service: FeatureFlagService):
        assert service.is_enabled("pct_above", company_id=42)

    @patch.dict("services.feature_flags.FEATURE_FLAGS", {
        "pct_below": type("FF", (), {"key": "pct_below", "description": "", "default": False,
                                      "scope": FlagScope.PERCENTAGE,
                                      "metadata": {"rollout_pct": -5}})(),
    })
    def test_rollout_negative_is_disabled(self, service: FeatureFlagService):
        assert not service.is_enabled("pct_below", company_id=42)

    @patch.dict("services.feature_flags.FEATURE_FLAGS", {
        "pct_missing": type("FF", (), {"key": "pct_missing", "description": "", "default": False,
                                        "scope": FlagScope.PERCENTAGE,
                                        "metadata": {}})(),
    })
    def test_rollout_missing_metadata_defaults_to_zero(self, service: FeatureFlagService):
        assert not service.is_enabled("pct_missing", company_id=5)


# ─────────────────────────────────────────────────────────────────────
# DB overrides
# ─────────────────────────────────────────────────────────────────────


class TestDbOverrides:
    """When a DB is supplied, SettingsRepository lookups can override flags."""

    def test_set_override_no_db_does_nothing(self, service: FeatureFlagService):
        # No db configured – should return silently
        service.set_override("timocom_integration", True, company_id=1)
        assert service.is_enabled("timocom_integration", company_id=1) is False

    def test_set_override_with_calls_repo(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            service_with_db.set_override("analytics_cache", True)
            mock_repo.upsert_setting.assert_called_once_with(
                "feature_flag.analytics_cache", "1"
            )

    def test_set_override_with_company_scopes_key(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            service_with_db.set_override("api_v2", False, company_id=10)
            mock_repo.upsert_setting.assert_called_once_with(
                "feature_flag.api_v2.company.10", "0"
            )

    def test_set_override_with_user_scopes_key(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            service_with_db.set_override("api_v2", True, user_id=7)
            mock_repo.upsert_setting.assert_called_once_with(
                "feature_flag.api_v2.user.7", "1"
            )

    def test_get_db_override_most_specific_wins(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            # user override matches first => used
            mock_repo.get_setting_value.side_effect = [
                "1",  # user.{user_id}
            ]
            result = service_with_db._get_db_override("api_v2", company_id=5, user_id=3)
            assert result is True
            calls = mock_repo.get_setting_value.call_args_list
            assert calls[0][0][0] == "feature_flag.api_v2.user.3"

    def test_get_db_override_company_when_no_user(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_setting_value.side_effect = [
                None,  # user.{user_id} (no override)
                "0",   # company.{company_id} (disabled)
            ]
            result = service_with_db._get_db_override("api_v2", company_id=5, user_id=3)
            assert result is False

    def test_get_db_override_falls_back_to_none(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_setting_value.return_value = None
            result = service_with_db._get_db_override("api_v2", company_id=5, user_id=3)
            assert result is None

    def test_db_override_exception_returns_none(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            MockRepo.side_effect = RuntimeError("DB unavailable")
            result = service_with_db._get_db_override("api_v2", company_id=1, user_id=1)
            assert result is None


# ─────────────────────────────────────────────────────────────────────
# Non-existent flags
# ─────────────────────────────────────────────────────────────────────


class TestNonExistentFlag:
    def test_unknown_flag_returns_false(self, service: FeatureFlagService):
        assert service.is_enabled("nonexistent_flag") is False

    def test_unknown_flag_logs_warning(self, service: FeatureFlagService, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        service.is_enabled("bogus_flag")
        assert "Unknown feature flag" in caplog.text
        assert "bogus_flag" in caplog.text

    def test_override_unknown_flag_returns_default(self, service: FeatureFlagService):
        """Non-existent flags return False even with an override set
        because the FEATURE_FLAGS registry lookup happens first."""
        service.enable_for_test("ad_hoc_flag")
        assert service.is_enabled("ad_hoc_flag") is False


# ─────────────────────────────────────────────────────────────────────
# _is_in_percentage – direct unit tests
# ─────────────────────────────────────────────────────────────────────


class TestIsInPercentage:
    def test_exactly_100_is_enabled(self, service: FeatureFlagService):
        assert service._is_in_percentage(42, 100) is True

    def test_above_100_is_enabled(self, service: FeatureFlagService):
        assert service._is_in_percentage(42, 200) is True

    def test_zero_is_disabled(self, service: FeatureFlagService):
        assert service._is_in_percentage(42, 0) is False

    def test_negative_is_disabled(self, service: FeatureFlagService):
        assert service._is_in_percentage(42, -1) is False

    def test_deterministic_same_input_same_output(self, service: FeatureFlagService):
        assert service._is_in_percentage(17, 25) == service._is_in_percentage(17, 25)

    def test_boundary_just_below(self, service: FeatureFlagService):
        # (17 % 100) = 17 < 25 => True
        assert service._is_in_percentage(17, 25) is True

    def test_boundary_at_threshold(self, service: FeatureFlagService):
        # (25 % 100) = 25, pct = 25.  25 < 25 => False
        assert service._is_in_percentage(25, 25) is False


# ─────────────────────────────────────────────────────────────────────
# Flag metadata and list_flags
# ─────────────────────────────────────────────────────────────────────


class TestFlagMetadata:
    def test_list_flags_returns_all_registered(self, service: FeatureFlagService):
        flags = service.list_flags()
        keys = {f["key"] for f in flags}
        assert keys == _flag_keys()

    def test_list_flags_includes_metadata(self, service: FeatureFlagService):
        flags = service.list_flags()
        timocom = next(f for f in flags if f["key"] == "timocom_integration")
        assert timocom["description"] == "TIMOCOM freight exchange integration"
        assert timocom["default"] is False
        assert timocom["scope"] == FlagScope.PER_COMPANY

    def test_list_flags_shows_current_state(self, service: FeatureFlagService):
        service.enable_for_test("analytics_cache")
        flags = service.list_flags()
        ac = next(f for f in flags if f["key"] == "analytics_cache")
        assert ac["current"] is True

    def test_new_route_planner_metadata(self, service: FeatureFlagService):
        flags = service.list_flags()
        nrp = next(f for f in flags if f["key"] == "new_route_planner")
        assert nrp["scope"] == FlagScope.PERCENTAGE
        assert nrp["default"] is False


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_company_id_and_user_id(self, service: FeatureFlagService):
        # Default company/user = 0
        assert service.is_enabled("background_pdf_generation") is True

    def test_overrides_empty_after_reset(self, service: FeatureFlagService):
        service.enable_for_test("ocr_auto_process")
        assert service._overrides != {}
        service.reset_test_overrides()
        assert service._overrides == {}

    def test_enable_for_then_disable_restores_default(self, service: FeatureFlagService):
        service.enable_for_test("ocr_auto_process")
        service.disable_for_test("ocr_auto_process")
        # Default is True, but override is set to False
        assert service.is_enabled("ocr_auto_process") is False

    def test_disable_for_then_enable(self, service: FeatureFlagService):
        service.disable_for_test("background_pdf_generation")
        service.enable_for_test("background_pdf_generation")
        assert service.is_enabled("background_pdf_generation") is True

    def test_set_override_exception_logged(self, service_with_db: FeatureFlagService, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        with patch(
            "repositories.settings_repository.SettingsRepository",
            side_effect=Exception("fail"),
        ):
            service_with_db.set_override("api_v2", True)
        assert "Failed to set feature flag override" in caplog.text


# ─────────────────────────────────────────────────────────────────────
# priority: in-memory override > DB override > percentage > default
# ─────────────────────────────────────────────────────────────────────


class TestOverridePriority:
    def test_in_memory_beats_db(self, service_with_db: FeatureFlagService):
        service_with_db.enable_for_test("analytics_cache")
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_setting_value.return_value = "0"
            assert service_with_db.is_enabled("analytics_cache") is True

    def test_db_beats_default(self, service_with_db: FeatureFlagService):
        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_setting_value.side_effect = [
                None, "1", None,
            ]
            assert service_with_db.is_enabled("analytics_cache", company_id=5) is True

    def test_percentage_applied_when_no_override(self, service: FeatureFlagService):
        # new_route_planner has pct=10, company 5 => enabled
        assert service.is_enabled("new_route_planner", company_id=5) is True

    def test_in_memory_beats_percentage(self, service: FeatureFlagService):
        service.disable_for_test("new_route_planner")
        assert service.is_enabled("new_route_planner", company_id=5) is False
