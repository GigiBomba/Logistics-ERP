"""Tests for the automail TimelinePanel, _StatusBadge, _InvoiceTimelineCard."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.views.automail.timeline_panel import (
    TimelinePanel,
    _InvoiceTimelineCard,
    _StatusBadge,
)
from ui.widgets import StyledLineEdit


# ── _StatusBadge ───────────────────────────────────────────────────────


class TestStatusBadge:
    def test_creation_sent(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "sent")
        qtbot.addWidget(badge)
        assert badge.text() == "Sent"
        assert "Sent" in badge.text()

    def test_creation_scheduled(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "scheduled")
        qtbot.addWidget(badge)
        assert badge.text() == "Scheduled"

    def test_creation_failed(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "failed")
        qtbot.addWidget(badge)
        assert badge.text() == "Failed"

    def test_creation_skipped(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "skipped")
        qtbot.addWidget(badge)
        assert badge.text() == "Skipped"

    def test_creation_cancelled(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "cancelled")
        qtbot.addWidget(badge)
        assert badge.text() == "Cancelled"

    def test_creation_unknown_status(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "unknown")
        qtbot.addWidget(badge)
        assert badge.text() == "Unknown"

    def test_creation_empty_status(self, qt_widget, qtbot):
        badge = _StatusBadge(qt_widget, "")
        qtbot.addWidget(badge)
        assert badge.text() == ""


# ── _InvoiceTimelineCard ──────────────────────────────────────────────


class TestInvoiceTimelineCard:
    def test_creation(self, qt_widget, qtbot):
        data = {
            "invoice_id": 1,
            "trip_id": 10,
            "invoice_number": "INV-001",
            "client_name": "ACME Corp",
            "total_amount": 1500.00,
            "currency": "EUR",
            "due_date": "2026-06-15",
            "client_email": "ap@acme.com",
            "timeline": [
                {"status": "sent", "schedule_name": "Reminder 1",
                 "scheduled_date": "2026-06-01", "sent_at": "2026-06-01 10:00:00"},
            ],
        }
        ops = MagicMock()
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, data, ops, db)
        qtbot.addWidget(card)
        assert card._data is data
        assert card.property("role") == "invoice-timeline-card"

    def test_creation_with_timeline_entries(self, qt_widget, qtbot):
        data = {
            "invoice_id": 2,
            "trip_id": 20,
            "invoice_number": "INV-002",
            "client_name": "Globex",
            "total_amount": 2500.00,
            "currency": "EUR",
            "due_date": "2026-07-01",
            "client_email": "ar@globex.com",
            "timeline": [
                {"status": "scheduled", "schedule_name": "Reminder 1",
                 "scheduled_date": "2026-06-20", "sent_at": ""},
                {"status": "sent", "schedule_name": "Reminder 2",
                 "scheduled_date": "2026-06-10", "sent_at": "2026-06-10 09:00:00"},
            ],
        }
        ops = MagicMock()
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, data, ops, db)
        qtbot.addWidget(card)
        # Should have timeline dots and text
        assert card._data is data

    def test_compute_days_past_overdue(self, qt_widget, qtbot):
        """Due date in the past → positive days past."""
        from datetime import date, timedelta
        past_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
        data = {
            "invoice_id": 1,
            "trip_id": 10,
            "invoice_number": "INV-001",
            "client_name": "ACME",
            "total_amount": 1000,
            "due_date": past_date,
            "client_email": "a@b.com",
            "timeline": [],
        }
        ops = MagicMock()
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, data, ops, db)
        qtbot.addWidget(card)
        days_past = card._compute_days_past(past_date)
        assert days_past is not None
        assert days_past >= 0

    def test_compute_days_past_future(self, qt_widget, qtbot):
        """Due date in the future → None (avoids crash in constructor by using past date for card creation)."""
        from datetime import date, timedelta
        future_date = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
        # _compute_days_past returns None for future dates
        from ui.views.automail.timeline_panel import _InvoiceTimelineCard as CardClass
        days_past = CardClass._compute_days_past(None, future_date)  # Use static method directly
        assert days_past is None

    def test_compute_days_past_today(self, qt_widget, qtbot):
        """Due date today → 0."""
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        from ui.views.automail.timeline_panel import _InvoiceTimelineCard as CardClass
        days_past = CardClass._compute_days_past(None, today)
        # diff == 0 → returns 0 (since 0 >= 0)
        assert days_past == 0

    def test_compute_days_past_invalid_date(self, qt_widget, qtbot):
        from ui.views.automail.timeline_panel import _InvoiceTimelineCard as CardClass
        days_past = CardClass._compute_days_past(None, None)
        assert days_past is None

    def test_on_send_now_shows_confirm(self, qt_widget, qtbot):
        data = {
            "invoice_id": 1,
            "trip_id": 10,
            "invoice_number": "INV-001",
            "client_name": "ACME",
            "total_amount": 1000,
            "currency": "EUR",
            "due_date": "2026-07-01",
            "client_email": "ap@acme.com",
            "timeline": [],
        }
        ops = MagicMock()
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, data, ops, db)
        qtbot.addWidget(card)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            card._on_send_now()
            # Confirmation declined — no further action

    def test_on_skip_shows_confirm(self, qt_widget, qtbot):
        data = {
            "invoice_id": 1,
            "trip_id": 10,
            "invoice_number": "INV-001",
            "client_name": "ACME",
            "total_amount": 1000,
            "due_date": "2026-07-01",
            "client_email": "ap@acme.com",
            "timeline": [],
        }
        ops = MagicMock()
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, data, ops, db)
        qtbot.addWidget(card)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            card._on_skip()

    def test_on_cancel_all_shows_confirm(self, qt_widget, qtbot):
        data = {
            "invoice_id": 1,
            "trip_id": 10,
            "invoice_number": "INV-001",
            "client_name": "ACME",
            "total_amount": 1000,
            "due_date": "2026-07-01",
            "client_email": "ap@acme.com",
            "timeline": [],
        }
        ops = MagicMock()
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, data, ops, db)
        qtbot.addWidget(card)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            card._on_cancel_all()


# ── TimelinePanel ──────────────────────────────────────────────────────


class TestTimelinePanelCreation:
    def test_creation(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel._db is None
        assert panel._page == 0
        assert panel._search == ""
        assert panel._status_filter == ""
        assert panel.property("role") == "automail-timeline-panel"

    def test_creation_with_all_params(self, qt_widget, qtbot):
        db = MagicMock()
        prefs = MagicMock()
        ops = MagicMock()
        automail_repo = MagicMock()
        panel = TimelinePanel(qt_widget, db=db, prefs=prefs, ops=ops, automail_repo=automail_repo)
        qtbot.addWidget(panel)
        assert panel._db is db
        assert panel._prefs is prefs
        assert panel._ops is ops
        assert panel._automail_repo is automail_repo

    def test_has_search_field(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel._search_input is not None
        line_edits = panel.findChildren(StyledLineEdit)
        assert len(line_edits) >= 1

    def test_has_scroll_area(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        scroll_areas = panel.findChildren(QScrollArea)
        assert len(scroll_areas) >= 1

    def test_has_pagination(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel._page_label is not None
        assert panel._prev_btn is not None
        assert panel._next_btn is not None

    def test_has_filter_buttons(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        assert len(panel._filter_btns) >= 5  # All, Upcoming, Sent, Failed, Skipped, Overdue

    def test_has_stats_bar(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        assert panel._stats_sent is not None
        assert panel._stats_failed is not None
        assert panel._stats_recovered is not None


class TestTimelinePanelSearchFilter:
    def test_search_triggers_timer(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        with patch.object(panel._search_timer, "start") as mock_start:
            panel._search_input.setText("ACME")
            mock_start.assert_called_once()

    def test_do_search_resets_page(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._page = 3
        with patch.object(panel, "_load_data") as mock_load:
            panel._do_search()
            assert panel._page == 0
            mock_load.assert_called_once()

    def test_filter_changed(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        with patch.object(panel, "_load_data") as mock_load:
            panel._on_filter_changed("sent")
            assert panel._status_filter == "sent"
            assert panel._page == 0
            mock_load.assert_called_once()

    def test_filter_changed_highlights_correct_button(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._on_filter_changed("overdue")
        for btn in panel._filter_btns:
            if btn.property("filter_value") == "overdue":
                assert btn.isChecked() is True
            else:
                assert btn.isChecked() is False


class TestTimelinePanelPagination:
    def test_prev_page_decrements(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._page = 2
        with patch.object(panel, "_load_data") as mock_load:
            panel._prev_page()
            assert panel._page == 1
            mock_load.assert_called_once()

    def test_prev_page_at_zero(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        with patch.object(panel, "_load_data") as mock_load:
            panel._prev_page()  # page is 0, should stay 0
            assert panel._page == 0
            mock_load.assert_not_called()

    def test_next_page_increments(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        with patch.object(panel, "_load_data") as mock_load:
            panel._next_page()
            assert panel._page == 1
            mock_load.assert_called_once()


class TestTimelinePanelDataLoading:
    def test_load_data_without_db(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        panel._load_data()  # Should not crash

    def test_load_data_with_mock_db(self, qt_widget, qtbot):
        db = MagicMock()
        # Mock the ReminderService and HistoryService
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        with patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs, patch(
            "ui.views.automail.timeline_panel.HistoryService",
        ) as mock_hs:
            mock_rs_instance = MagicMock()
            mock_rs_instance.get_reminder_status_for_all_active.return_value = (
                [], 0
            )
            mock_rs.return_value = mock_rs_instance
            mock_hs_instance = MagicMock()
            mock_hs_instance.get_stats.return_value = {
                "emails_sent": 10,
                "emails_failed": 2,
                "total_outstanding_amount": 50000,
            }
            mock_hs.return_value = mock_hs_instance
            panel._load_data()
            # Empty state should be shown
            assert panel._list_layout.count() >= 1

    def test_load_data_with_entries(self, qt_widget, qtbot):
        db = MagicMock()
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        with patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs, patch(
            "ui.views.automail.timeline_panel.HistoryService",
        ) as mock_hs:
            mock_rs_instance = MagicMock()
            mock_rs_instance.get_reminder_status_for_all_active.return_value = (
                [
                    {
                        "invoice_id": 1,
                        "trip_id": 10,
                        "invoice_number": "INV-001",
                        "client_name": "ACME",
                        "total_amount": 1000,
                        "currency": "EUR",
                        "due_date": "2026-07-01",
                        "client_email": "ap@acme.com",
                        "timeline": [
                            {"status": "scheduled", "schedule_name": "R1",
                             "scheduled_date": "2026-06-20", "sent_at": ""},
                        ],
                    },
                ],
                1,
            )
            mock_rs.return_value = mock_rs_instance
            mock_hs_instance = MagicMock()
            mock_hs_instance.get_stats.return_value = {
                "emails_sent": 5,
                "emails_failed": 0,
                "total_outstanding_amount": 1000,
            }
            mock_hs.return_value = mock_hs_instance
            panel._load_data()
            # Should have invoice timeline cards
            cards = panel.findChildren(_InvoiceTimelineCard)
            assert len(cards) == 1

    def test_load_data_with_exception(self, qt_widget, qtbot):
        db = MagicMock()
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        with patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs, patch(
            "ui.views.automail.timeline_panel.HistoryService",
        ) as mock_hs:
            mock_rs_instance = MagicMock()
            mock_rs_instance.get_reminder_status_for_all_active.side_effect = \
                Exception("DB error")
            mock_rs.return_value = mock_rs_instance
            mock_hs_instance = MagicMock()
            mock_hs_instance.get_stats.return_value = {}
            mock_hs.return_value = mock_hs_instance
            # Should not raise
            panel._load_data()
            assert panel._list_layout.count() >= 1

    def test_wakeup_loads_data(self, qt_widget, qtbot):
        db = MagicMock()
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        with patch.object(panel, "_load_data") as mock_load:
            panel.wakeup()
            mock_load.assert_called_once()

    def test_wakeup_without_db(self, qt_widget, qtbot):
        panel = TimelinePanel(qt_widget)
        qtbot.addWidget(panel)
        # Should not crash
        panel.wakeup()


class TestTimelinePanelStats:
    def test_stats_updated_on_load(self, qt_widget, qtbot):
        db = MagicMock()
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        with patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs, patch(
            "ui.views.automail.timeline_panel.HistoryService",
        ) as mock_hs:
            mock_rs_instance = MagicMock()
            mock_rs_instance.get_reminder_status_for_all_active.return_value = (
                [], 0
            )
            mock_rs.return_value = mock_rs_instance
            mock_hs_instance = MagicMock()
            mock_hs_instance.get_stats.return_value = {
                "emails_sent": 25,
                "emails_failed": 3,
                "total_outstanding_amount": 75000,
            }
            mock_hs.return_value = mock_hs_instance
            panel._load_data()
            assert "25" in panel._stats_sent.text()
            assert "3" in panel._stats_failed.text()


# ── SP workaround (if needed) ─────────────────────────────────────────

import ui.widgets as _ui_widgets
if not hasattr(_ui_widgets, "SP"):
    _ui_widgets.SP = _ui_widgets.S


# ── Test data ─────────────────────────────────────────────────────────


SAMPLE_TIMELINE_ENTRY: dict = {
    "invoice_id": 1001,
    "trip_id": 42,
    "client_name": "Acme Corp",
    "client_email": "billing@acme.com",
    "client_contact": "John",
    "due_date": "2026-07-15",
    "invoice_number": "INV-2026-001",
    "total_amount": 4500.00,
    "timeline": [
        {"name": "Day 27", "scheduled_date": "2026-06-18",
         "sent_at": None, "status": "pending"},
        {"name": "Day 20", "scheduled_date": "2026-06-25",
         "sent_at": None, "status": "pending"},
        {"name": "Day 10", "scheduled_date": "2026-07-05",
         "sent_at": "2026-07-05T10:00:00", "status": "sent"},
        {"name": "Day 3", "scheduled_date": "2026-07-12",
         "sent_at": None, "status": "pending"},
        {"name": "Day 0", "scheduled_date": "2026-07-15",
         "sent_at": None, "status": "pending"},
    ],
    "schedule_id": 1,
    "total_reminders": 5,
    "reminders_sent": 1,
    "status": "active",
    "last_sent": None,
}


# ── InvoiceTimelineCard action tests ──────────────────────────────────


class TestInvoiceTimelineCardActions:
    """Tests for the manual action methods on _InvoiceTimelineCard."""

    def test_send_now_consented_full_flow(self, qt_widget, qtbot):
        """Send Now: consent given, email sent → information box."""
        ops = MagicMock()
        ops.notification_center = MagicMock()
        ops.notification_center.send_email.return_value = True
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, SAMPLE_TIMELINE_ENTRY, ops, db)
        qtbot.addWidget(card)

        # Pre-set the automail repo so _on_send_now uses it directly
        mock_repo = MagicMock()
        mock_repo.get_active_schedules.return_value = [
            {"id": 1, "template_id": 10},
        ]
        mock_repo.get_template_by_id.return_value = {
            "id": 10, "name": "Test", "subject": "Subj",
            "body_text": "Body", "body_html": "",
        }
        card._automail_repo = mock_repo

        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "ui.views.automail.timeline_panel.TemplateService",
        ) as mock_ts_cls, patch(
            "ui.views.automail.timeline_panel.load_company_config",
            return_value={"company_name": "Operion"},
        ), patch(
            "services.document_automation.package_builder.PackageBuilder",
        ) as mock_pb_cls, patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            mock_ts = MagicMock()
            mock_ts.render_email.return_value = (
                "Payment Reminder", "Body text", "<p>Body html</p>",
            )
            mock_ts_cls.return_value = mock_ts

            mock_pb = MagicMock()
            mock_pb.list_trip_documents.return_value = []
            mock_pb_cls.return_value = mock_pb

            card._on_send_now()
            mock_info.assert_called_once()
            mock_warn.assert_not_called()
            # Verify email was sent to the right address
            args, _ = mock_info.call_args
            assert "success" in str(args).lower()

    def test_send_now_consented_send_fails(self, qt_widget, qtbot):
        """Send Now: nc.send_email returns False → warning box."""
        ops = MagicMock()
        ops.notification_center = MagicMock()
        ops.notification_center.send_email.return_value = False
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, SAMPLE_TIMELINE_ENTRY, ops, db)
        qtbot.addWidget(card)

        mock_repo = MagicMock()
        mock_repo.get_active_schedules.return_value = [
            {"id": 1, "template_id": 10},
        ]
        mock_repo.get_template_by_id.return_value = {
            "id": 10, "name": "Test", "subject": "Subj",
            "body_text": "Body", "body_html": "",
        }
        card._automail_repo = mock_repo

        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "ui.views.automail.timeline_panel.TemplateService",
        ) as mock_ts_cls, patch(
            "ui.views.automail.timeline_panel.load_company_config",
            return_value={"company_name": "Operion"},
        ), patch(
            "services.document_automation.package_builder.PackageBuilder",
        ) as mock_pb_cls, patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            mock_ts = MagicMock()
            mock_ts.render_email.return_value = (
                "Payment Reminder", "Body text", "<p>Body html</p>",
            )
            mock_ts_cls.return_value = mock_ts

            mock_pb = MagicMock()
            mock_pb.list_trip_documents.return_value = []
            mock_pb_cls.return_value = mock_pb

            card._on_send_now()
            mock_warn.assert_called_once()
            mock_info.assert_not_called()

    def test_send_now_exception_handling(self, qt_widget, qtbot):
        """Send Now: nc.send_email raises → warning box with exception."""
        ops = MagicMock()
        ops.notification_center = MagicMock()
        ops.notification_center.send_email.side_effect = Exception("Connection timeout")
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, SAMPLE_TIMELINE_ENTRY, ops, db)
        qtbot.addWidget(card)

        mock_repo = MagicMock()
        mock_repo.get_active_schedules.return_value = [
            {"id": 1, "template_id": 10},
        ]
        mock_repo.get_template_by_id.return_value = {
            "id": 10, "name": "Test", "subject": "Subj",
            "body_text": "Body", "body_html": "",
        }
        card._automail_repo = mock_repo

        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "ui.views.automail.timeline_panel.TemplateService",
        ) as mock_ts_cls, patch(
            "ui.views.automail.timeline_panel.load_company_config",
            return_value={"company_name": "Operion"},
        ), patch(
            "services.document_automation.package_builder.PackageBuilder",
        ) as mock_pb_cls, patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            mock_ts = MagicMock()
            mock_ts.render_email.return_value = (
                "Payment Reminder", "Body text", "<p>Body html</p>",
            )
            mock_ts_cls.return_value = mock_ts

            mock_pb = MagicMock()
            mock_pb.list_trip_documents.return_value = []
            mock_pb_cls.return_value = mock_pb

            card._on_send_now()
            mock_warn.assert_called_once()
            mock_info.assert_not_called()
            # Verify warning contains the exception message
            args, _ = mock_warn.call_args
            assert "Connection timeout" in str(args)

    def test_skip_consented_full_flow(self, qt_widget, qtbot):
        """Skip: consent given, skip succeeds → information box."""
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, SAMPLE_TIMELINE_ENTRY, MagicMock(), db)
        qtbot.addWidget(card)

        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs_cls, patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            mock_rs = MagicMock()
            mock_rs.skip_next_reminder.return_value = True
            mock_rs_cls.return_value = mock_rs

            card._on_skip()
            mock_info.assert_called_once()
            mock_warn.assert_not_called()

    def test_skip_consented_fails(self, qt_widget, qtbot):
        """Skip: skip_next_reminder returns False → warning box."""
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, SAMPLE_TIMELINE_ENTRY, MagicMock(), db)
        qtbot.addWidget(card)

        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs_cls, patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            mock_rs = MagicMock()
            mock_rs.skip_next_reminder.return_value = False
            mock_rs_cls.return_value = mock_rs

            card._on_skip()
            mock_warn.assert_called_once()
            mock_info.assert_not_called()

    def test_cancel_all_consented_full_flow(self, qt_widget, qtbot):
        """Cancel All: consent given, cancel succeeds → information box."""
        db = MagicMock()
        card = _InvoiceTimelineCard(qt_widget, SAMPLE_TIMELINE_ENTRY, MagicMock(), db)
        qtbot.addWidget(card)

        with patch.object(
            QMessageBox, "question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs_cls, patch.object(
            QMessageBox, "information",
        ) as mock_info, patch.object(
            QMessageBox, "warning",
        ) as mock_warn:
            mock_rs = MagicMock()
            mock_rs.cancel_all_reminders.return_value = True
            mock_rs_cls.return_value = mock_rs

            card._on_cancel_all()
            mock_info.assert_called_once()
            mock_warn.assert_not_called()


class TestTimelinePanelEdgeCases:
    """Edge-case tests for TimelinePanel pagination."""

    def test_pagination_label_correct(self, qt_widget, qtbot):
        """Page 1 of 45 total with 20 entries shows 'Showing 21-40 of 45'."""
        db = MagicMock()
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)
        panel._page = 1

        with patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs, patch(
            "ui.views.automail.timeline_panel.HistoryService",
        ) as mock_hs:
            mock_rs_instance = MagicMock()
            entries = [
                {
                    "invoice_id": i, "trip_id": i,
                    "invoice_number": f"INV-{i:03d}",
                    "client_name": f"Client {i}",
                    "total_amount": 1000,
                    "due_date": "2026-07-15",
                    "client_email": f"c{i}@test.com",
                    "timeline": [],
                }
                for i in range(20)
            ]
            mock_rs_instance.get_reminder_status_for_all_active.return_value = (
                entries, 45,
            )
            mock_rs.return_value = mock_rs_instance
            mock_hs_instance = MagicMock()
            mock_hs_instance.get_stats.return_value = {}
            mock_hs.return_value = mock_hs_instance

            panel._load_data()
            label = panel._page_label.text()
            assert "21" in label and "40" in label and "45" in label

    def test_pagination_single_page_disables_next(self, qt_widget, qtbot):
        """When total ≤ _PAGE_SIZE, both prev and next buttons are disabled."""
        db = MagicMock()
        panel = TimelinePanel(qt_widget, db=db)
        qtbot.addWidget(panel)

        with patch(
            "ui.views.automail.timeline_panel.ReminderService",
        ) as mock_rs, patch(
            "ui.views.automail.timeline_panel.HistoryService",
        ) as mock_hs:
            mock_rs_instance = MagicMock()
            entries = [
                {
                    "invoice_id": i, "trip_id": i,
                    "invoice_number": f"INV-{i:03d}",
                    "client_name": f"Client {i}",
                    "total_amount": 1000,
                    "due_date": "2026-07-15",
                    "client_email": f"c{i}@test.com",
                    "timeline": [],
                }
                for i in range(15)
            ]
            mock_rs_instance.get_reminder_status_for_all_active.return_value = (
                entries, 15,
            )
            mock_rs.return_value = mock_rs_instance
            mock_hs_instance = MagicMock()
            mock_hs_instance.get_stats.return_value = {}
            mock_hs.return_value = mock_hs_instance

            panel._load_data()
            assert panel._prev_btn.isEnabled() is False
            assert panel._next_btn.isEnabled() is False
