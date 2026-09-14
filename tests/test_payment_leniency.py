"""Tests for the rule-based payment-leniency engine and its dunner wiring.

Covers:
* grant / deny unit conditions for :class:`PaymentLeniencyEngine` (incl. the
  quarterly cap and the grant-window helper),
* dunner integration: reminder escalation is defused when the
  ``payment_leniency`` feature flag is ON and a grant applies, and the dunning
  behaviour is unchanged when the flag is OFF.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import ANY, MagicMock, patch

from services.feature_flags import FeatureFlagService
from services.operations.dunner_engine import DunnerEngine
from services.operations.event_bus import PAYMENT_LENIENCY_GRANTED, EventBus
from services.operations.payment_leniency import (
    ClientPaymentHistory,
    PaymentLeniencyEngine,
)

TODAY = date(2026, 9, 13)  # fixed "today" so the engine is fully deterministic


# ── Helpers ─────────────────────────────────────────────────────────────

def _invoice(overdue_days=10, age_days=40, invoice_id=1, status="Unpaid", **extra):
    """Build an invoice dict in the shape used by the dunner / repositories."""
    data = {
        "invoice_id": invoice_id,
        "id": invoice_id,
        "issue_date": (TODAY - timedelta(days=age_days)).isoformat(),
        "due_date": (TODAY - timedelta(days=overdue_days)).isoformat(),
        "status": status,
    }
    data.update(extra)
    return data


def _engine(**kwargs) -> PaymentLeniencyEngine:
    return PaymentLeniencyEngine(today=TODAY, **kwargs)


def _history(invoices=None, grants=None) -> ClientPaymentHistory:
    return ClientPaymentHistory(
        invoices=invoices or [],
        leniency_grants=grants or [],
    )


# ── Unit tests: PaymentLeniencyEngine ──────────────────────────────────

class TestPaymentLeniencyEngine:
    def test_grant_for_clean_track_record(self):
        grant = _engine().grant_leniency(1, _invoice(), _history())
        assert grant is not None
        assert grant.pause_days == 14
        assert grant.granted_at == TODAY
        assert grant.reason

    def test_pause_days_configurable(self):
        grant = _engine(pause_days=30).grant_leniency(1, _invoice(), _history())
        assert grant is not None
        assert grant.pause_days == 30

    def test_deny_when_invoice_not_overdue(self):
        grant = _engine().grant_leniency(1, _invoice(overdue_days=-5), _history())
        assert grant is None

    def test_deny_when_invoice_has_no_due_date(self):
        inv = _invoice()
        inv.pop("due_date")
        assert _engine().grant_leniency(1, inv, _history()) is None

    def test_deny_when_invoice_older_than_max_age(self):
        # 70 days old > 60-day one-off window.
        assert _engine().grant_leniency(1, _invoice(age_days=70), _history()) is None

    def test_deny_when_other_invoice_chronic_overdue(self):
        history = _history(invoices=[_invoice(invoice_id=99, overdue_days=45)])
        assert _engine().grant_leniency(1, _invoice(invoice_id=1), history) is None

    def test_allow_other_invoice_outside_lookback_window(self):
        # 200 days overdue is outside the 180-day track-record window.
        history = _history(invoices=[_invoice(invoice_id=99, overdue_days=200)])
        assert _engine().grant_leniency(1, _invoice(), history) is not None

    def test_allow_paid_invoices_in_history(self):
        history = _history(invoices=[_invoice(invoice_id=99, overdue_days=45, status="Paid")])
        assert _engine().grant_leniency(1, _invoice(), history) is not None

    def test_current_invoice_excluded_from_chronic_check(self):
        # The evaluated invoice itself is 45 days overdue; it is the one-off slip
        # and must not count against its own track record.
        inv = _invoice(invoice_id=7, overdue_days=45)
        history = _history(invoices=[inv])
        assert _engine().grant_leniency(1, inv, history) is not None

    def test_deny_when_grant_already_issued_this_quarter(self):
        history = _history(grants=[{"granted_at": TODAY - timedelta(days=30)}])
        assert _engine().grant_leniency(1, _invoice(), history) is None

    def test_allow_when_grant_issued_previous_quarter(self):
        history = _history(grants=[{"granted_at": date(2026, 6, 1)}])  # Q2
        assert _engine().grant_leniency(1, _invoice(), history) is not None

    def test_quarterly_cap_ignores_string_and_date_forms(self):
        for raw in (TODAY.isoformat(), TODAY):
            history = _history(grants=[{"granted_at": raw}])
            assert _engine().grant_leniency(1, _invoice(), history) is None

    def test_is_paused_within_grant_window(self):
        history = _history(grants=[{"granted_at": TODAY - timedelta(days=5)}])
        assert _engine().is_paused(1, history) is True

    def test_is_paused_after_grant_window(self):
        # granted 20 days ago, window is 14 days → not paused (but the quarterly
        # cap still denies a *new* grant).
        history = _history(grants=[{"granted_at": TODAY - timedelta(days=20)}])
        engine = _engine()
        assert engine.is_paused(1, history) is False
        assert engine.grant_leniency(1, _invoice(), history) is None

    def test_is_paused_ignores_previous_quarter(self):
        history = _history(grants=[{"granted_at": date(2026, 6, 15)}])
        assert _engine().is_paused(1, history) is False

    def test_has_grant_in_current_quarter(self):
        assert _engine().has_grant_in_current_quarter(
            _history(grants=[{"granted_at": TODAY}])
        ) is True
        assert _engine().has_grant_in_current_quarter(
            _history(grants=[{"granted_at": date(2026, 6, 15)}])
        ) is False


# ── Integration tests: dunner wiring ───────────────────────────────────

def _make_dunner(db, feature_flags=None, leniency_engine=None) -> DunnerEngine:
    return DunnerEngine(
        db,
        notification_center=MagicMock(),
        feature_flags=feature_flags,
        leniency_engine=leniency_engine,
    )


def _due_invoice(overdue_days=30, age_days=40, invoice_id=1, client_id=1) -> dict:
    """An invoice the dunner would dispatch a day-30 reminder for."""
    return {
        "invoice_id": invoice_id,
        "trip_id": 10,
        "client_id": client_id,
        "due_date": (date.today() - timedelta(days=overdue_days)).isoformat(),
        "issue_date": (date.today() - timedelta(days=age_days)).isoformat(),
        "invoice_number": f"INV-{invoice_id:04d}",
        "total_amount": 1000,
        "currency": "EUR",
        "client_email": "c@c.com",
        "client_company_name": "Client",
        "client_name": "Client",
        "client_contact": "",
        "truck_plate": "",
        "driver_name": "",
    }


def _setup_dunner(
    engine,
    mock_repo,
    mock_inv,
    invoices,
    client_history=None,
    template_instance=None,
):
    """Common mock wiring so a single schedule fires a day-30 reminder."""
    engine._rules = MagicMock()
    engine._rules.get.return_value = True

    mock_repo.get_active_schedules.return_value = [
        {"id": 1, "name": "day_30", "template_id": 1}
    ]
    mock_repo.get_all_templates.return_value = [
        {"id": 1, "subject": "Subject", "body_text": "Body", "body_html": ""}
    ]
    mock_repo.get_all_overrides.return_value = {}
    mock_repo.get_all_settings.return_value = {}

    if template_instance is not None:
        template_instance.render_email.return_value = ("Subject", "Body text", "<p>Body</p>")

    mock_inv.get_reminder_count.return_value = 0
    mock_inv.has_reminder_been_sent.return_value = False
    mock_inv.get_by_id.return_value = {"status": "Unpaid"}
    mock_inv.get_by_client_id.return_value = client_history or []
    mock_inv.insert_reminder.return_value = 1

    # The engine captures its invoice repository at construction time, so wire
    # the configured mock in explicitly (``get_by_id`` re-check and the
    # leniency history lookup both go through it).
    engine._invoice_repo = mock_inv

    engine._fetch_due_invoices = MagicMock(return_value=invoices)
    engine._resolve_client_email = MagicMock(return_value="c@c.com")


class TestDunnerLeniencyIntegration:
    @patch("services.operations.dunner_engine.InvoiceRepository")
    @patch("services.operations.dunner_engine.AutoMailRepository")
    @patch("services.operations.dunner_engine.TemplateService")
    def test_flag_on_grant_defuses_escalation(self, mock_template, mock_repo, mock_inv_cls):
        """Flag ON + rule-based grant → the day-30 reminder is never sent."""
        db = MagicMock()
        ff = FeatureFlagService(db=None)
        ff.enable_for_test("payment_leniency")

        engine = _make_dunner(db, feature_flags=ff)
        mock_inv = MagicMock()
        mock_inv_cls.return_value = mock_inv
        _setup_dunner(
            engine, mock_repo.return_value, mock_inv, [_due_invoice()],
            client_history=[],  # clean track record → grant applies
            template_instance=mock_template.return_value,
        )

        with patch("services.operations.dunner_engine.ReminderService") as mock_reminder, \
             patch("repositories.settings_repository.SettingsRepository") as mock_settings:
            mock_reminder._compute_target_days.return_value = 30
            result = engine.evaluate_all()

        assert result == 0  # nothing was sent
        engine._notification_center.send_email.assert_not_called()
        # The grant is persisted under the settings-table key namespace.
        mock_settings.return_value.upsert_setting.assert_called_once_with(
            "payment_leniency.granted.1", ANY
        )
        # A leniency event was emitted on the event bus.
        events = EventBus().get_history(PAYMENT_LENIENCY_GRANTED)
        assert events
        assert events[-1]["data"]["client_id"] == 1
        assert events[-1]["data"]["invoice_id"] == 1

    @patch("services.operations.dunner_engine.InvoiceRepository")
    @patch("services.operations.dunner_engine.AutoMailRepository")
    @patch("services.operations.dunner_engine.TemplateService")
    def test_flag_off_behaviour_unchanged(self, mock_template, mock_repo, mock_inv_cls):
        """Flag OFF (default) → the reminder is sent exactly as before."""
        db = MagicMock()
        ff = FeatureFlagService(db=None)  # default disabled

        engine = _make_dunner(db, feature_flags=ff)
        mock_inv = MagicMock()
        mock_inv_cls.return_value = mock_inv
        _setup_dunner(
            engine, mock_repo.return_value, mock_inv, [_due_invoice()],
            client_history=[],  # would qualify, but the flag is OFF
            template_instance=mock_template.return_value,
        )

        with patch("services.operations.dunner_engine.ReminderService") as mock_reminder, \
             patch("repositories.settings_repository.SettingsRepository") as mock_settings:
            mock_reminder._compute_target_days.return_value = 30
            result = engine.evaluate_all()

        assert result == 1  # reminder sent
        engine._notification_center.send_email.assert_called_once()
        mock_settings.return_value.upsert_setting.assert_not_called()
        assert not EventBus().get_history(PAYMENT_LENIENCY_GRANTED)

    @patch("services.operations.dunner_engine.InvoiceRepository")
    @patch("services.operations.dunner_engine.AutoMailRepository")
    @patch("services.operations.dunner_engine.TemplateService")
    def test_flag_on_denied_sends_reminder(self, mock_template, mock_repo, mock_inv_cls):
        """Flag ON but rules deny (chronic overdue) → dunning proceeds."""
        db = MagicMock()
        ff = FeatureFlagService(db=None)
        ff.enable_for_test("payment_leniency")

        engine = _make_dunner(db, feature_flags=ff)
        mock_inv = MagicMock()
        mock_inv_cls.return_value = mock_inv
        _setup_dunner(
            engine, mock_repo.return_value, mock_inv, [_due_invoice()],
            # Another invoice overdue 45 days → track record is NOT clean.
            client_history=[_invoice(invoice_id=99, overdue_days=45)],
            template_instance=mock_template.return_value,
        )

        with patch("services.operations.dunner_engine.ReminderService") as mock_reminder, \
             patch("repositories.settings_repository.SettingsRepository") as mock_settings:
            mock_reminder._compute_target_days.return_value = 30
            result = engine.evaluate_all()

        assert result == 1
        engine._notification_center.send_email.assert_called_once()
        mock_settings.return_value.upsert_setting.assert_not_called()

    @patch("services.operations.dunner_engine.InvoiceRepository")
    @patch("services.operations.dunner_engine.AutoMailRepository")
    @patch("services.operations.dunner_engine.TemplateService")
    def test_flag_on_active_window_defuses_without_new_grant(
        self, mock_template, mock_repo, mock_inv_cls
    ):
        """Flag ON + a grant already issued this quarter → still defused, but no
        second grant is persisted (one-time per quarter)."""
        db = MagicMock()
        ff = FeatureFlagService(db=None)
        ff.enable_for_test("payment_leniency")

        engine = _make_dunner(db, feature_flags=ff)
        mock_inv = MagicMock()
        mock_inv_cls.return_value = mock_inv
        _setup_dunner(
            engine, mock_repo.return_value, mock_inv, [_due_invoice()],
            client_history=[],
            template_instance=mock_template.return_value,
        )

        with patch("services.operations.dunner_engine.ReminderService") as mock_reminder, \
             patch("repositories.settings_repository.SettingsRepository") as mock_settings:
            mock_reminder._compute_target_days.return_value = 30
            # A prior grant (5 days ago) is persisted in the settings table and
            # is still inside the 14-day window.
            mock_settings.return_value.get_settings_by_key_pattern.return_value = {
                "payment_leniency.granted.1": (date.today() - timedelta(days=5)).isoformat(),
            }
            result = engine.evaluate_all()

        assert result == 0
        engine._notification_center.send_email.assert_not_called()
        mock_settings.return_value.upsert_setting.assert_not_called()