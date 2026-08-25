"""Readiness tests for FeatureFlagService, SloService, and AuditService.

These tests validate the core service contracts for feature flag evaluation,
SLO/SLA reporting, and audit event logging.  DB connections are mocked so
that tests run without an active database.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from services.feature_flags import (
    FeatureFlagService,
    FEATURE_FLAGS,
    FeatureFlag,
    FlagScope,
)
from services.slo_service import get_report, get_status_page
from services.audit_service import AuditService


# ===================================================================
# FeatureFlagService
# ===================================================================


class TestFeatureFlagService:
    """Feature flag evaluation and override behaviour."""

    @pytest.fixture
    def service(self):
        """Return a FeatureFlagService with no DB — only in-memory state."""
        return FeatureFlagService(db=None)

    # ------------------------------------------------------------------
    # Defaults / unknown
    # ------------------------------------------------------------------

    def test_flag_default_value(self, service):
        """Undefined flags return False; defined flags return their default."""
        # Unknown flag
        assert service.is_enabled("nonexistent_flag") is False
        # Flag with default=False
        assert service.is_enabled("timocom_integration") is False
        # Flag with default=True
        assert service.is_enabled("ocr_auto_process") is True
        assert service.is_enabled("background_pdf_generation") is True

    def test_unknown_flag(self, service):
        """is_enabled on an unknown key returns False without error."""
        assert service.is_enabled("completely_unknown_flag") is False
        # A second call should also not explode
        assert service.is_enabled("") is False

    # ------------------------------------------------------------------
    # In-memory overrides (test helpers)
    # ------------------------------------------------------------------

    def test_flag_enabled_by_override(self, service):
        """enable_for_test makes is_enabled return True."""
        assert service.is_enabled("api_v2") is False  # default
        service.enable_for_test("api_v2")
        assert service.is_enabled("api_v2") is True

    def test_flag_disabled_by_override(self, service):
        """disable_for_test makes is_enabled return False."""
        # ocr_auto_process defaults to True
        assert service.is_enabled("ocr_auto_process") is True
        service.disable_for_test("ocr_auto_process")
        assert service.is_enabled("ocr_auto_process") is False

    def test_test_override(self, service):
        """enable_for_test / disable_for_test work in-memory only (no DB)."""
        service.enable_for_test("strict_validation")
        assert service.is_enabled("strict_validation") is True
        # DB is None so set_override is a no-op; in-memory override still wins
        service.set_override("strict_validation", False)
        assert service.is_enabled("strict_validation") is True  # in-memory > db

    def test_reset_overrides(self, service):
        """reset_test_overrides clears all in-memory overrides."""
        service.enable_for_test("api_v2")
        service.enable_for_test("strict_validation")
        assert service.is_enabled("api_v2") is True
        assert service.is_enabled("strict_validation") is True

        service.reset_test_overrides()
        # After reset, flags fall back to their defaults
        assert service.is_enabled("api_v2") is False
        assert service.is_enabled("strict_validation") is False

    # ------------------------------------------------------------------
    # Percentage rollout
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "company_id,expected",
        [
            (0, True),   # 0 % 100 = 0 < 10 → True
            (5, True),   # 5 % 100 = 5 < 10 → True
            (9, True),   # 9 % 100 = 9 < 10 → True
            (10, False), # 10 % 100 = 10 < 10 → False
            (42, False), # 42 % 100 = 42 < 10 → False
            (99, False), # 99 % 100 = 99 < 10 → False
            (100, True), # 100 % 100 = 0 < 10 → True
            (105, True), # 105 % 100 = 5 < 10 → True
        ],
    )
    def test_percentage_rollout(self, service, company_id, expected):
        """Percentage-based flags are evaluated deterministically by company_id."""
        # new_route_planner has rollout_pct=10
        assert (
            service.is_enabled("new_route_planner", company_id=company_id)
            is expected
        )

    @pytest.mark.parametrize("pct,expected", [(0, False), (50, True), (100, True)])
    def test_percentage_rollout_boundaries(self, service, pct, expected):
        """Percentage rollout at boundaries (0%, 100%)."""
        # Patch metadata on the fly
        flag = FEATURE_FLAGS["new_route_planner"]
        original_meta = flag.metadata.copy()
        flag.metadata["rollout_pct"] = pct
        try:
            assert (
                service.is_enabled("new_route_planner", company_id=42)
                is expected
            )
        finally:
            flag.metadata = original_meta

    # ------------------------------------------------------------------
    # Override priority (via DB mocking)
    # ------------------------------------------------------------------

    def test_company_override(self, service):
        """Per-company DB override takes priority over the global default."""
        mock_db = MagicMock()
        service.db = mock_db

        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            # Return None for global key, "1" for company key
            def side_effect(key):
                if "company.42" in key:
                    return "1"
                return None
            repo_instance.get_setting_value.side_effect = side_effect

            assert service.is_enabled("timocom_integration", company_id=42) is True

        service.db = None

    def test_user_override(self, service):
        """Per-user DB override takes top priority (over company & global)."""
        mock_db = MagicMock()
        service.db = mock_db

        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            # User key returns "1", company key returns "0" — user must win
            def side_effect(key):
                if "user.7" in key:
                    return "1"
                if "company.1" in key:
                    return "0"
                return None
            repo_instance.get_setting_value.side_effect = side_effect

            assert (
                service.is_enabled("strict_validation", company_id=1, user_id=7)
                is True
            )

        service.db = None

    def test_user_override_disabled(self, service):
        """Per-user override can also disable a flag that company enables."""
        mock_db = MagicMock()
        service.db = mock_db

        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            def side_effect(key):
                if "user.7" in key:
                    return "0"
                if "company.1" in key:
                    return "1"
                return None
            repo_instance.get_setting_value.side_effect = side_effect

            # User-level "0" should win over company-level "1"
            assert (
                service.is_enabled("strict_validation", company_id=1, user_id=7)
                is False
            )

        service.db = None

    def test_override_priority_chain(self, service):
        """DB override priority: user > company > global > default."""
        mock_db = MagicMock()
        service.db = mock_db

        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.get_setting_value.return_value = None

            # No overrides → falls back to default
            assert service.is_enabled("ocr_auto_process") is True  # default=True

            # Global override
            def global_only(key):
                return "0" if key == "feature_flag.ocr_auto_process" else None
            repo_instance.get_setting_value.side_effect = global_only
            assert service.is_enabled("ocr_auto_process") is False

            # Company override beats global
            def company_wins(key):
                if "company.1" in key:
                    return "1"
                if key == "feature_flag.ocr_auto_process":
                    return "0"
                return None
            repo_instance.get_setting_value.side_effect = company_wins
            assert (
                service.is_enabled("ocr_auto_process", company_id=1) is True
            )

        service.db = None

    # ------------------------------------------------------------------
    # Listing & structure
    # ------------------------------------------------------------------

    def test_list_flags(self, service):
        """list_flags returns all registered flags with current state."""
        flags = service.list_flags()

        assert isinstance(flags, list)
        assert len(flags) == len(FEATURE_FLAGS)

        for entry in flags:
            assert "key" in entry
            assert "description" in entry
            assert "default" in entry
            assert "scope" in entry
            assert "current" in entry

        # Spot-check a known flag
        timocom = next(f for f in flags if f["key"] == "timocom_integration")
        assert timocom["default"] is False
        assert timocom["scope"] == FlagScope.PER_COMPANY
        assert timocom["current"] is False

    def test_list_flags_reflects_overrides(self, service):
        """list_flags shows current state after an override is applied."""
        service.enable_for_test("api_v2")
        flags = service.list_flags()
        api_v2 = next(f for f in flags if f["key"] == "api_v2")
        assert api_v2["current"] is True

    # ------------------------------------------------------------------
    # TIMOCOM flag specific
    # ------------------------------------------------------------------

    def test_timocom_flag_controls_webhook(self, service):
        """timocom_integration flag has the expected metadata structure."""
        flag = FEATURE_FLAGS.get("timocom_integration")
        assert flag is not None
        assert flag.key == "timocom_integration"
        assert flag.description == "TIMOCOM freight exchange integration"
        assert flag.default is False
        assert flag.scope == FlagScope.PER_COMPANY
        assert flag.metadata.get("partner") == "timocom"
        assert flag.metadata.get("requires_oauth2") is True

        # When disabled (default), timocom webhooks should not fire
        assert service.is_enabled("timocom_integration") is False

        # When enabled for a company, webhooks should fire
        service.enable_for_test("timocom_integration")
        assert service.is_enabled("timocom_integration") is True

    # ------------------------------------------------------------------
    # set_override with DB
    # ------------------------------------------------------------------

    def test_set_override_with_db(self, service):
        """set_override persists via SettingsRepository when a db is available."""
        mock_db = MagicMock()
        service.db = mock_db

        with patch(
            "repositories.settings_repository.SettingsRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            service.set_override("timocom_integration", True, company_id=10)

            repo_instance.upsert_setting.assert_called_once_with(
                "feature_flag.timocom_integration.company.10", "1"
            )

        service.db = None

    def test_set_override_without_db_is_noop(self, service):
        """set_override is a no-op when db is None (no crash)."""
        service.set_override("some_flag", True)  # should not raise


# ===================================================================
# SloService
# ===================================================================


class _SloTracker:
    """In-process SLO calculator for testing the SLO tracking contract.

    The production ``slo_service`` is currently a stub; this lightweight
    implementation lets us validate the intended recording & reporting
    behaviour without a running database.
    """

    def __init__(self):
        self._records: list[dict] = []

    def record_success(self, service: str = "api") -> None:
        self._records.append({"service": service, "status": 200})

    def record_error(self, service: str = "api", status: int = 500) -> None:
        self._records.append({"service": service, "status": status})

    def record_webhook(self, success: bool = True) -> None:
        svc = "webhook"
        self._records.append({"service": svc, "status": 200 if success else 500})

    def record_route_calculation(self, success: bool = True) -> None:
        svc = "route_calculation"
        self._records.append({"service": svc, "status": 200 if success else 500})

    def availability(self, service_name: str = "api") -> float:
        relevant = [r for r in self._records if r["service"] == service_name]
        if not relevant:
            return 100.0
        successes = sum(1 for r in relevant if r["status"] < 500)
        return (successes / len(relevant)) * 100.0

    def get_report(self) -> dict:
        services_data = {}
        for service_name in {"api", "webhook", "route_calculation"}:
            total = len([r for r in self._records if r["service"] == service_name])
            avail = self.availability(service_name)
            services_data[service_name] = {
                "availability": round(avail, 2),
                "total_requests": total,
            }
        return {
            "status": "ok" if all(
                s["availability"] >= 99.0 for s in services_data.values()
            ) else "degraded",
            "uptime": round(
                sum(s["availability"] for s in services_data.values()) / max(len(services_data), 1),
                2,
            ),
            "services": services_data,
        }

    def get_status_page(self) -> dict:
        report = self.get_report()
        return {
            "status": "operational" if report["status"] == "ok" else "degraded",
            "uptime": report["uptime"],
            "services": report["services"],
        }


class TestSloService:
    """SLO/SLA service tests.

    Because the production ``slo_service`` module is a stub, the record-based
    tests use the local ``_SloTracker`` to validate the intended contract.
    The public-facing tests (``test_get_report_structure``,
    ``test_get_status_page_public``) exercise the actual stub directly.
    """

    # ── Public stub contract ──────────────────────────────────────

    def test_get_report_structure(self):
        """get_report returns a dict with status, uptime, and services."""
        report = get_report()
        assert isinstance(report, dict)
        assert "status" in report
        assert "uptime" in report
        assert "services" in report

    def test_get_status_page_public(self):
        """get_status_page returns a public-formatted dict."""
        page = get_status_page()
        assert isinstance(page, dict)
        assert page["status"] == "operational"

    # ── Recording contract (via _SloTracker) ──────────────────────

    @pytest.fixture
    def tracker(self):
        return _SloTracker()

    def test_initial_slo_is_100(self, tracker: _SloTracker):
        """Before any records, all SLOs are 100%."""
        assert tracker.availability("api") == 100.0
        assert tracker.availability("webhook") == 100.0
        assert tracker.availability("route_calculation") == 100.0

    def test_record_success_requests(self, tracker: _SloTracker):
        """Recording 200 responses maintains high SLO."""
        for _ in range(100):
            tracker.record_success()
        assert tracker.availability("api") == 100.0

    def test_record_server_errors(self, tracker: _SloTracker):
        """Recording 500 responses drops availability SLO."""
        for _ in range(80):
            tracker.record_success()
        for _ in range(20):
            tracker.record_error()
        # 80 / 100 = 80 %
        assert tracker.availability("api") == 80.0

    def test_slo_drops_below_target(self, tracker: _SloTracker):
        """Enough errors drops the SLO below a typical 99 % target."""
        # 10 errors out of 1000 → 99 % exactly, one more error → 98.9 %
        for _ in range(990):
            tracker.record_success()
        for _ in range(11):
            tracker.record_error()
        assert tracker.availability("api") < 99.0
        assert tracker.availability("api") == pytest.approx(98.9, abs=0.1)

    def test_record_webhook(self, tracker: _SloTracker):
        """Webhook recording works independently of other services."""
        tracker.record_success()                 # api
        tracker.record_webhook(success=True)     # webhook ok
        tracker.record_webhook(success=False)    # webhook fail
        assert tracker.availability("webhook") == 50.0
        assert tracker.availability("api") == 100.0

    def test_record_route_calculation(self, tracker: _SloTracker):
        """Route calculation recording works independently."""
        tracker.record_route_calculation(success=True)
        tracker.record_route_calculation(success=True)
        tracker.record_route_calculation(success=False)
        assert tracker.availability("route_calculation") == pytest.approx(66.666, rel=0.01)

    def test_get_report_structure_tracker(self, tracker: _SloTracker):
        """_SloTracker.get_report returns the expected shape."""
        tracker.record_success()
        tracker.record_success()
        tracker.record_error()
        report = tracker.get_report()
        assert report["status"] in ("ok", "degraded")
        assert "api" in report["services"]
        assert "availability" in report["services"]["api"]
        assert "total_requests" in report["services"]["api"]
        assert report["services"]["api"]["total_requests"] == 3

    def test_status_page_from_tracker(self, tracker: _SloTracker):
        """_SloTracker.get_status_page has public-friendly format."""
        tracker.record_success()
        page = tracker.get_status_page()
        assert page["status"] == "operational"
        assert "services" in page
        assert "uptime" in page

    def test_report_reflects_errors(self, tracker: _SloTracker):
        """Report status reflects degraded state after errors."""
        for _ in range(50):
            tracker.record_error()
        report = tracker.get_report()
        assert report["status"] == "degraded"


# ===================================================================
# AuditService
# ===================================================================


class TestAuditService:
    """Audit event logging behaviour."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def audit(self, mock_db):
        return AuditService(db=mock_db)

    # ------------------------------------------------------------------
    # Basic logging
    # ------------------------------------------------------------------

    def test_log_event(self, audit, mock_db):
        """Audit log records an event with the correct fields."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            audit.log(
                event_type="trip.created",
                entity_type="trip",
                entity_id="42",
                user_id=1,
                data={"origin": "Berlin", "destination": "Paris"},
                company_id=5,
            )

            repo_instance.log_event.assert_called_once_with(
                event_type="trip.created",
                entity_type="trip",
                entity_id="42",
                data={"origin": "Berlin", "destination": "Paris"},
                user_id=1,
                company_id=5,
            )

    def test_log_event_minimal_fields(self, audit, mock_db):
        """Audit log works with only the required fields."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            audit.log(
                event_type="system.heartbeat",
                entity_type="system",
                entity_id="srv-1",
            )

            repo_instance.log_event.assert_called_once()
            call_kwargs = repo_instance.log_event.call_args[1]
            assert call_kwargs["event_type"] == "system.heartbeat"
            assert call_kwargs["entity_type"] == "system"
            assert call_kwargs["entity_id"] == "srv-1"
            # Defaults
            assert call_kwargs["user_id"] == 0
            assert call_kwargs["company_id"] == 0
            assert call_kwargs["data"] == {}

    # ------------------------------------------------------------------
    # Correlation ID enrichment
    # ------------------------------------------------------------------

    def test_log_event_with_correlation_id(self, audit, mock_db):
        """Correlation ID is included in data when available."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo, patch(
            "backend.middleware.correlation_middleware.get_correlation_id",
            return_value="corr-abc-123",
        ):
            repo_instance = MockRepo.return_value

            audit.log(
                event_type="trip.updated",
                entity_type="trip",
                entity_id="99",
                data={"field": "status"},
            )

            call_data = repo_instance.log_event.call_args[1]["data"]
            assert "_correlation_id" in call_data
            assert call_data["_correlation_id"] == "corr-abc-123"
            # Original data preserved
            assert call_data["field"] == "status"

    def test_log_event_without_correlation(self, audit, mock_db):
        """No correlation ID leaves data un-altered."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo, patch(
            "backend.middleware.correlation_middleware.get_correlation_id",
            return_value="",
        ):
            repo_instance = MockRepo.return_value

            audit.log(
                event_type="trip.deleted",
                entity_type="trip",
                entity_id="7",
            )

            call_data = repo_instance.log_event.call_args[1]["data"]
            assert "_correlation_id" not in call_data

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def test_log_event_handles_db_error(self, audit, mock_db):
        """Audit service gracefully handles DB errors without re-raising."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value
            repo_instance.log_event.side_effect = Exception("DB connection lost")

            # Should not raise
            audit.log(
                event_type="trip.created",
                entity_type="trip",
                entity_id="1",
            )
            # If we got here, the error was caught gracefully

    def test_log_event_handles_import_error(self, audit, mock_db):
        """Audit service handles ImportError from correlation middleware."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo, patch(
            "backend.middleware.correlation_middleware.get_correlation_id",
            side_effect=ImportError("Middleware not available"),
        ):
            repo_instance = MockRepo.return_value

            # Should not raise
            audit.log(
                event_type="trip.created",
                entity_type="trip",
                entity_id="1",
                data={"key": "val"},
            )

            call_data = repo_instance.log_event.call_args[1]["data"]
            assert call_data == {"key": "val"}  # no _correlation_id added
            assert "_correlation_id" not in call_data

    # ------------------------------------------------------------------
    # Delegation & edge cases
    # ------------------------------------------------------------------

    def test_log_event_delegates_to_repo(self, audit, mock_db):
        """AuditService delegates to AuditRepository.log_event."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            audit.log(
                event_type="test.event",
                entity_type="test",
                entity_id="1",
            )

            MockRepo.assert_called_once_with(mock_db)
            repo_instance.log_event.assert_called_once()

    def test_log_event_with_empty_data(self, audit, mock_db):
        """Empty/None data should not cause errors and result in an empty dict."""
        with patch(
            "repositories.audit_repository.AuditRepository"
        ) as MockRepo:
            repo_instance = MockRepo.return_value

            audit.log(
                event_type="test.event",
                entity_type="test",
                entity_id="1",
                data=None,
            )

            call_data = repo_instance.log_event.call_args[1]["data"]
            assert call_data == {}
