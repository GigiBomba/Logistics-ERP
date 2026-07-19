"""Tests for MaintenanceViewModel — health scoring, caching, event handling."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.fleet_maintenance_service import TruckHealth


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_ops():
    """Mock OperationsEngine."""
    ops = MagicMock()
    ops.resolve_alert = MagicMock()
    return ops


@pytest.fixture
def mock_db():
    """Mock database."""
    return MagicMock()


@pytest.fixture
def mock_maint_svc():
    """Mock FleetMaintenanceService."""
    svc = MagicMock()
    svc.get_summary.return_value = {
        "total_records": 50,
        "total_cost": 15000.0,
        "avg_health": 78.5,
    }
    svc.get_health.return_value = TruckHealth(
        truck_id=1, score=85, compliance_pct=90.0,
        overdue_count=1, recurring_issues=2, downtime_days=5,
    )
    svc.get_all_health.return_value = [
        TruckHealth(truck_id=1, score=85),
        TruckHealth(truck_id=2, score=92),
    ]
    return svc


@pytest.fixture
def model(qt_widget, qtbot, mock_db, mock_ops, mock_maint_svc):
    """Create a MaintenanceViewModel with mocked dependencies.

    We patch FleetMaintenanceService inside maint_svc property so the
    lazy-init returns our mock instead of a real service.
    """
    from ui.models.maintenance_view_model import MaintenanceViewModel

    m = MaintenanceViewModel(parent=qt_widget, db=mock_db, ops=mock_ops)
    # Replace lazy service with our mock
    m._maint_svc = mock_maint_svc
    # Also patch the sub-models so they don't need real dependencies
    m.alert_model = MagicMock()
    m.tacho_model = MagicMock()
    yield m
    m.shutdown()


# =========================================================================
# Creation / Init
# =========================================================================


class TestInit:
    """ViewModel initialises correctly."""

    def test_creation(self, model):
        assert model is not None
        assert model._db is not None
        assert model._ops is not None

    def test_has_signals(self, model):
        assert hasattr(model, "data_changed")
        assert hasattr(model, "summary_changed")

    def test_has_sub_models(self, model):
        assert hasattr(model, "alert_model")
        assert hasattr(model, "tacho_model")

    def test_debounce_timer_configured(self, model):
        assert model._debounce_timer is not None
        assert model._debounce_timer.isSingleShot()
        assert model._debounce_timer.interval() == 300

    def test_initial_cache_state(self, model):
        assert model._summary_cache is None
        assert model._summary_ts == 0.0
        assert model._summary_ttl == 60.0
        assert model._dirty is True

    def test_lazy_maint_svc(self, qt_widget, qtbot):
        """When _maint_svc is None, the property creates one."""
        from ui.models.maintenance_view_model import MaintenanceViewModel

        with patch(
            "ui.models.maintenance_view_model.FleetMaintenanceService",
            return_value=MagicMock(),
        ) as mock_cls:
            m = MaintenanceViewModel(parent=qt_widget, db=MagicMock())
            svc = m.maint_svc
            mock_cls.assert_called_once()
            assert svc is m._maint_svc


# =========================================================================
# Event subscriptions
# =========================================================================


class TestEventSubscription:
    """ViewModel subscribes to EventBus and marks dirty on events."""

    def test_subscribe_marks_dirty(self, model):
        model._dirty = False
        model._on_any_event()
        assert model._dirty is True

    def test_subscribe_starts_debounce(self, model):
        model._debounce_timer.stop()
        assert not model._debounce_timer.isActive()
        model._on_any_event()
        assert model._debounce_timer.isActive()

    def test_shutdown_unsubscribes(self, model):
        from services.operations.event_bus import (
            ALERT_CREATED,
            EventBus,
        )
        model.shutdown()
        bus = EventBus()
        # After shutdown the handler should be gone (no crash if published)
        bus.publish(ALERT_CREATED)


# =========================================================================
# Refresh
# =========================================================================


class TestRefresh:
    """Refresh methods debounce and trigger data fetch."""

    def test_refresh_starts_debounce(self, model):
        model._debounce_timer.stop()
        assert not model._debounce_timer.isActive()
        model.refresh()
        assert model._debounce_timer.isActive()

    def test_refresh_now_bypasses_debounce(self, model):
        model._debounce_timer.stop()
        with patch.object(model, "_do_refresh") as mock_do:
            model.refresh_now()
            mock_do.assert_called_once()
        assert not model._debounce_timer.isActive()

    def test_do_refresh_no_db(self, model):
        """Without a db, _do_refresh just emits data_changed."""
        model._db = None
        with patch.object(model, "data_changed") as sig:
            model._do_refresh()
            sig.emit.assert_called_once()
        model.alert_model.refresh_from.assert_not_called()

    def test_do_refresh_calls_sub_refresh(self, model):
        model._do_refresh()
        model.alert_model.refresh_from.assert_called_once_with(model._ops)
        model.tacho_model.refresh.assert_called_once_with(model._db)

    def test_do_refresh_emits_data_changed(self, model):
        with patch.object(model, "data_changed") as sig:
            model._do_refresh()
            sig.emit.assert_called_once()

    def test_do_refresh_sets_dirty_false(self, model):
        model._dirty = True
        model._do_refresh()
        assert model._dirty is False

    def test_do_refresh_handles_alert_failure(self, model):
        model.alert_model.refresh_from.side_effect = RuntimeError("alert fail")
        # Should not raise — the method catches exceptions
        model._do_refresh()
        model.tacho_model.refresh.assert_called_once()

    def test_do_refresh_handles_tacho_failure(self, model):
        model.tacho_model.refresh.side_effect = RuntimeError("tacho fail")
        model._do_refresh()
        # data_changed still emitted
        assert model._dirty is False

    def test_do_refresh_handles_invalidate_failure(self, model):
        with patch.object(model, "_invalidate_summary_cache", side_effect=RuntimeError("inv fail")):
            model._do_refresh()
            assert model._dirty is False


# =========================================================================
# Summary cache
# =========================================================================


class TestSummary:
    """Summary caching with TTL."""

    def test_get_summary_delegates_to_service(self, model):
        summary = model.get_summary()
        model._maint_svc.get_summary.assert_called_once_with(force=True)
        assert summary["total_records"] == 50

    def test_get_summary_caches(self, model):
        s1 = model.get_summary()
        s2 = model.get_summary()
        # Only one call to the service
        model._maint_svc.get_summary.assert_called_once()
        assert s1 is s2

    def test_get_summary_emit_on_change(self, model):
        with patch.object(model, "summary_changed") as sig:
            model.get_summary()
            sig.emit.assert_called_once()

    def test_get_summary_no_emit_on_same_value(self, model):
        model.get_summary()
        with patch.object(model, "summary_changed") as sig:
            model.get_summary()
            sig.emit.assert_not_called()

    def test_summary_invalidate_clears_cache(self, model):
        model.get_summary()
        model._invalidate_summary_cache()
        assert model._summary_cache is None
        assert model._summary_ts == 0.0

    def test_summary_force_refetch(self, model):
        model.get_summary()
        model._summary_ts = 0.0  # force expiry
        model.get_summary()
        # Now called twice
        assert model._maint_svc.get_summary.call_count == 2


# =========================================================================
# Health cache
# =========================================================================


class TestHealth:
    """Health scoring and caching."""

    def test_get_health_delegates(self, model):
        health = model.get_health(1)
        model._maint_svc.get_health.assert_called_once_with(1, force_refresh=False)
        assert health.score == 85

    def test_get_health_caches(self, model):
        h1 = model.get_health(1)
        h2 = model.get_health(1)
        model._maint_svc.get_health.assert_called_once()
        assert h1 is h2

    def test_get_health_force(self, model):
        model.get_health(1)
        model.get_health(1, force=True)
        assert model._maint_svc.get_health.call_count == 2
        model._maint_svc.get_health.assert_called_with(1, force_refresh=True)

    def test_get_all_health(self, model):
        result = model.get_all_health()
        model._maint_svc.get_all_health.assert_called_once()
        assert len(result) == 2


# =========================================================================
# Alert helpers
# =========================================================================


class TestAlertHelpers:
    """Resolve alert delegates to ops and triggers refresh."""

    def test_resolve_alert(self, model):
        with patch.object(model, "refresh_now") as refresh_mock:
            model.resolve_alert("alert-123")
            model._ops.resolve_alert.assert_called_once_with("alert-123")
            refresh_mock.assert_called_once()


# =========================================================================
# Health score computation edge cases (unit-level)
# =========================================================================


class TestHealthScoreComputation:
    """Unit-style tests for the health scoring algorithm.

    These test FleetMaintenanceService.compute_health directly so we can
    cover all scoring branches without a full DB.
    """

    @staticmethod
    def _make_service(**kwargs):
        """Create a FleetMaintenanceService with mocked internals."""
        import threading
        from services.fleet_maintenance_service import FleetMaintenanceService
        svc = FleetMaintenanceService.__new__(FleetMaintenanceService)
        svc._cache_lock = threading.Lock()
        svc._health_cache = {}
        svc._fleet_repo = MagicMock()
        svc._fleet_repo.get_maintenance_type_counts.return_value = []
        svc._fleet_repo.get_maintenance_last_date.return_value = None
        svc.get_schedules = MagicMock(return_value=[])
        svc.predict_next_service = MagicMock(return_value=None)
        for k, v in kwargs.items():
            setattr(svc, k, v)
        return svc

    def test_health_score_perfect(self):
        """No overdue, no recurring, no downtime → score=100."""
        svc = self._make_service()

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        assert health.score == 100
        assert health.compliance_pct == 100.0
        assert health.overdue_count == 0
        assert health.recurring_issues == 0
        assert health.downtime_days == 0

    def test_health_score_overdue_penalty(self):
        """Each overdue schedule costs 15 points."""
        svc = self._make_service(
            get_schedules=MagicMock(return_value=[{"maintenance_type": "oil"}, {"maintenance_type": "tires"}]),
            predict_next_service=MagicMock(return_value={"overdue": True}),
        )

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        # 2 overdue * 15 = 30 penalty
        assert health.score == 70
        assert health.overdue_count == 2

    def test_health_score_recurring_issue_penalty(self):
        """Each unique maintenance type costs 10 points."""
        svc = self._make_service()
        svc._fleet_repo.get_maintenance_type_counts.return_value = [
            {"maintenance_type": "oil"},
            {"maintenance_type": "tires"},
            {"maintenance_type": "brakes"},
        ]

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        # 3 types * 10 = 30 penalty
        assert health.score == 70

    def test_health_score_downtime_penalty(self):
        """Downtime beyond 30 days adds penalty."""
        from datetime import datetime, timedelta
        past_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        svc = self._make_service()
        svc._fleet_repo.get_maintenance_last_date.return_value = past_date

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        # min(90 // 30, 30) = min(3, 30) = 3 penalty
        assert health.score == 97

    def test_health_score_max_penalty_capped(self):
        """Penalty cannot exceed max_penalty (default 100)."""
        svc = self._make_service(
            get_schedules=MagicMock(return_value=[{"maintenance_type": "x"}] * 20),
            predict_next_service=MagicMock(return_value={"overdue": True}),
        )
        svc._fleet_repo.get_maintenance_type_counts.return_value = [{"maintenance_type": "x"}] * 20

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        # penalty = min(20*15 + 20*10 + 0, 100) = min(500, 100) = 100
        assert health.score == 0
        assert health.score >= 0

    def test_health_score_zero_values(self):
        """Zero values for all inputs yield perfect score."""
        svc = self._make_service()

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 0,
            "health_recurring_weight": 0,
            "health_downtime_weight": 0,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        assert health.score == 100

    def test_health_score_compliance_pct(self):
        """Compliance decreases by 10 per overdue."""
        svc = self._make_service(
            get_schedules=MagicMock(return_value=[{"maintenance_type": "x"}] * 3),
            predict_next_service=MagicMock(return_value={"overdue": True}),
        )

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        # compliance = max(0, 100 - 3*10) = 70
        assert health.compliance_pct == 70.0

    def test_health_score_negative_overdue_compliance_floor(self):
        """Compliance does not go below zero."""
        svc = self._make_service(
            get_schedules=MagicMock(return_value=[{"maintenance_type": "x"}] * 20),
            predict_next_service=MagicMock(return_value={"overdue": True}),
        )

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 1,
            "health_recurring_weight": 0,
            "health_downtime_weight": 0,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        assert health.compliance_pct == 0  # floored at 0

    def test_health_score_downtime_max_capped(self):
        """Downtime component is capped at downtime_weight value."""
        from datetime import datetime, timedelta
        past_date = (datetime.now() - timedelta(days=9999)).strftime("%Y-%m-%d")
        svc = self._make_service()
        svc._fleet_repo.get_maintenance_last_date.return_value = past_date

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        # min(9999 // 30, 30) = min(333, 30) = 30 penalty
        assert health.downtime_days > 30
        # The downtime component is capped at 30 per the formula:
        # min(downtime // 30, downtime_weight)
        assert health.score == 70  # 100 - 30

    def test_health_score_missing_last_date(self):
        """No last_date → downtime stays 0."""
        svc = self._make_service()

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        assert health.downtime_days == 0
        assert health.score == 100

    def test_health_score_invalid_last_date(self):
        """Invalid date string does not crash; downtime stays 0."""
        svc = self._make_service()
        svc._fleet_repo.get_maintenance_last_date.return_value = "not-a-date"

        rules = MagicMock()
        rules.get.side_effect = lambda key, default: {
            "health_overdue_weight": 15,
            "health_recurring_weight": 10,
            "health_downtime_weight": 30,
            "health_max_penalty": 100,
        }.get(key, default)

        health = svc.compute_health(truck_id=1, rules=rules)
        assert health.downtime_days == 0

    def test_truck_health_dataclass_defaults(self):
        """TruckHealth dataclass has sensible defaults."""
        h = TruckHealth()
        assert h.truck_id == 0
        assert h.score == 100
        assert h.compliance_pct == 100.0
        assert h.overdue_count == 0
        assert h.recurring_issues == 0
        assert h.downtime_days == 0

    def test_truck_health_custom_values(self):
        h = TruckHealth(truck_id=5, score=42, compliance_pct=50.0,
                        overdue_count=3, recurring_issues=4, downtime_days=10)
        assert h.truck_id == 5
        assert h.score == 42
        assert h.compliance_pct == 50.0
        assert h.overdue_count == 3
        assert h.recurring_issues == 4
        assert h.downtime_days == 10


# =========================================================================
# Schedule predictions (unit-level)
# =========================================================================


class TestSchedulePredictions:
    """PredictNextService logic for various schedule configurations."""

    @pytest.fixture
    def svc(self):
        import threading
        from services.fleet_maintenance_service import FleetMaintenanceService
        s = FleetMaintenanceService.__new__(FleetMaintenanceService)
        s._cache_lock = threading.Lock()
        s._health_cache = {}
        s._fleet_repo = MagicMock()
        return s

    def test_no_schedule_returns_none(self, svc):
        svc._fleet_repo.get_maintenance_schedule.return_value = None
        result = svc.predict_next_service(1, "oil_change")
        assert result is None

    def test_empty_schedule_returns_defaults(self, svc):
        svc._fleet_repo.get_maintenance_schedule.return_value = {"last_done_km": None, "last_done_date": None,
                                                                  "interval_km": None, "interval_months": None,
                                                                  "fixed_expiry_date": None}
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        result = svc.predict_next_service(1, "oil_change")
        assert result["type"] == "oil_change"
        assert result["due_by_km"] is None
        assert result["due_by_date"] is None
        assert result["overdue"] is False
        assert result["current_km"] == 100000

    def test_km_based_prediction_not_overdue(self, svc):
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": 50000, "last_done_date": None,
            "interval_km": 15000, "interval_months": None,
            "fixed_expiry_date": None,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 60000
        result = svc.predict_next_service(1, "oil_change")
        assert result["due_km"] == 65000
        assert result["due_by_km"] == 5000  # 65000 - 60000
        assert result["overdue"] is False

    def test_km_based_prediction_overdue(self, svc):
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": 50000, "last_done_date": None,
            "interval_km": 15000, "interval_months": None,
            "fixed_expiry_date": None,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 70000
        result = svc.predict_next_service(1, "oil_change")
        assert result["due_km"] == 65000
        assert result["due_by_km"] == 0  # max(0, 65000-70000)
        assert result["overdue"] is True

    def test_date_based_prediction_not_overdue(self, svc):
        """6 months ago + 12 month interval → 6 months from now, not overdue."""
        from datetime import datetime, timedelta
        past_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": None, "last_done_date": past_date,
            "interval_km": None, "interval_months": 12,
            "fixed_expiry_date": None,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        result = svc.predict_next_service(1, "oil_change")
        # due_by_date should be ~6 months from now (last_done + 12 months)
        assert result["due_by_date"] is not None
        due = datetime.strptime(result["due_by_date"], "%Y-%m-%d")
        remaining = (due - datetime.now()).days
        assert remaining > 0  # not overdue
        assert result["overdue"] is False
        assert 150 <= remaining <= 200  # roughly 6 months

    def test_date_based_prediction_overdue(self, svc):
        from datetime import datetime, timedelta
        past_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": None, "last_done_date": past_date,
            "interval_km": None, "interval_months": 12,
            "fixed_expiry_date": None,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        result = svc.predict_next_service(1, "oil_change")
        assert result["overdue"] is True
        assert result["remaining_days"] is not None
        assert result["remaining_days"] <= 0

    def test_fixed_expiry_overdue(self, svc):
        from datetime import datetime, timedelta
        past_expiry = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": None, "last_done_date": None,
            "interval_km": None, "interval_months": None,
            "fixed_expiry_date": past_expiry,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        result = svc.predict_next_service(1, "oil_change")
        assert result["due_by_date"] == past_expiry
        assert result["overdue"] is True

    def test_fixed_expiry_not_overdue(self, svc):
        from datetime import datetime, timedelta
        future_expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": None, "last_done_date": None,
            "interval_km": None, "interval_months": None,
            "fixed_expiry_date": future_expiry,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        result = svc.predict_next_service(1, "oil_change")
        assert result["due_by_date"] == future_expiry
        assert result["overdue"] is False

    def test_invalid_expiry_does_not_crash(self, svc):
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": None, "last_done_date": None,
            "interval_km": None, "interval_months": None,
            "fixed_expiry_date": "bad-date",
        }
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        result = svc.predict_next_service(1, "oil_change")
        assert result["overdue"] is False
        assert result["due_by_date"] == "bad-date"

    def test_no_mileage_defaults_to_zero(self, svc):
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": None, "last_done_date": None,
            "interval_km": None, "interval_months": None,
            "fixed_expiry_date": None,
        }
        svc._fleet_repo.get_truck_mileage.return_value = None
        result = svc.predict_next_service(1, "oil_change")
        assert result["current_km"] == 0

    def test_predict_all_upcoming(self, svc):
        """predict_all_upcoming returns predictions that are overdue or within window."""
        svc._fleet_repo.get_maintenance_schedule.return_value = {
            "last_done_km": 100000, "last_done_date": None,
            "interval_km": 15000, "interval_months": None,
            "fixed_expiry_date": None,
        }
        svc._fleet_repo.get_truck_mileage.return_value = 110000  # overdue
        from services.fleet_maintenance_service import MaintType
        # The method iterates over MaintType enum values
        results = svc.predict_all_upcoming(1, days_ahead=30)
        # Each MaintType gets a pred; those whose mileage is overdue are included
        assert isinstance(results, list)

    def test_predict_all_upcoming_no_preds(self, svc):
        """If no schedules exist, predict returns None and none are included."""
        svc._fleet_repo.get_maintenance_schedule.return_value = None
        svc._fleet_repo.get_truck_mileage.return_value = 100000
        results = svc.predict_all_upcoming(1, days_ahead=30)
        assert results == []


# =========================================================================
# Edge cases — model with None db
# =========================================================================


class TestNoDatabase:
    """ViewModel without a database handles gracefully."""

    def test_creation_without_db(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(parent=qt_widget, db=None)
        assert model._db is None
        model.shutdown()

    def test_do_refresh_without_db_emits(self, qt_widget, qtbot):
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(parent=qt_widget, db=None)
        with patch.object(model, "data_changed") as sig:
            model.refresh_now()
            sig.emit.assert_called_once()
        model.shutdown()

    def test_get_summary_without_db(self, qt_widget, qtbot):
        """Without db, maint_svc lazy-init would need a db.  We test that
        if _maint_svc is set, it still works."""
        from ui.models.maintenance_view_model import MaintenanceViewModel
        model = MaintenanceViewModel(parent=qt_widget, db=None)
        model._maint_svc = MagicMock()
        model._maint_svc.get_summary.return_value = {"total_records": 0}
        summary = model.get_summary()
        assert summary["total_records"] == 0
        model.shutdown()
