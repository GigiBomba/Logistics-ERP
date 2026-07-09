"""Center panel — invoice reminder timeline with search, filters, manual controls.

Displays the complete reminder status for ALL unpaid invoices,
paginated, with past/scheduled/future indicator, manual Send Now,
Skip, and Cancel All controls.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from repositories.automail_repository import AutoMailRepository
from services.automail.history_service import HistoryService
from services.automail.reminder_service import ReminderService
from services.automail.template_service import TemplateService
from services.i18n import t
from services.invoicing.config_manager import load_company_config
from services.operations.notification_center import NotificationCenter
from ui.components import Btn
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_TEXT,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    RADIUS_LG,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)
from ui.widgets import StyledLineEdit

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20


class _StatusBadge(QLabel):
    """Small coloured badge for reminder status."""

    def __init__(self, parent: QWidget, status: str) -> None:
        super().__init__(parent)
        styles = {
            "sent":       (COLOR_SUCCESS_TEXT, "rgba(16,185,129,0.12)"),
            "scheduled":  (COLOR_ACCENT_PRIMARY, COLOR_ACCENT_SUBTLE),
            "failed":     (COLOR_ERROR_TEXT, "rgba(239,68,68,0.12)"),
            "skipped":    (COLOR_NEUTRAL_TEXT, "rgba(107,114,128,0.12)"),
            "cancelled":  (COLOR_NEUTRAL_TEXT, "rgba(107,114,128,0.12)"),
        }
        text_color, bg = styles.get(status, (COLOR_TEXT_SECONDARY, COLOR_BG_OVERLAY))
        label = status.capitalize()
        self.setText(label)
        self.setStyleSheet(
            f"color: {text_color}; background: {bg}; "
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: {FONT_WEIGHT_MEDIUM};"
        )


class _InvoiceTimelineCard(QFrame):
    """A single invoice entry in the timeline list."""

    def __init__(
        self,
        parent: QWidget,
        data: dict[str, Any],
        ops,
        db,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._ops = ops
        self._db = db
        self._automail_repo = None
        self.setProperty("role", "invoice-timeline-card")
        self.setStyleSheet(
            f"background: {COLOR_BG_OVERLAY}; border: 1px solid {COLOR_BORDER_SUBTLE}; "
            f"border-radius: {RADIUS_LG}px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        layout.setSpacing(SPACE_2)

        # Header
        header = QHBoxLayout()
        header.setSpacing(SPACE_3)

        inv_num = data.get("invoice_number", "?")
        client_name = data.get("client_name", "") or data.get("client_company_name", "")
        total = data.get("total_amount", 0) or 0
        due = data.get("due_date", "")

        info = QLabel(f"<b>{inv_num}</b>  {client_name}  —  €{total:,.2f}", self)
        info.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px;")
        header.addWidget(info, 1)
        layout.addLayout(header)

        # Due date + overdue badge
        due_row = QHBoxLayout()
        due_row.setSpacing(SPACE_2)
        due_lbl = QLabel(t("automail.due", "Due") + f": {due}", self)
        due_lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        due_row.addWidget(due_lbl)

        days_past = self._compute_days_past(due)
        if days_past > 0:
            badge = QLabel(f"{days_past} day(s) overdue", self)
            badge.setStyleSheet(
                f"color: {COLOR_ERROR_TEXT}; background: rgba(239,68,68,0.1); "
                f"border-radius: 4px; padding: 1px 6px; font-size: 10px;"
            )
            due_row.addWidget(badge)
        elif not days_past:
            badge = QLabel(t("automail.due_today", "Due today"), self)
            badge.setStyleSheet(
                f"color: {COLOR_WARNING_TEXT}; background: rgba(245,158,11,0.1); "
                f"border-radius: 4px; padding: 1px 6px; font-size: 10px;"
            )
            due_row.addWidget(badge)
        due_row.addStretch()
        layout.addLayout(due_row)

        # Timeline entries for this invoice
        timeline = data.get("timeline", [])
        for entry in timeline:
            entry_row = QHBoxLayout()
            entry_row.setSpacing(SPACE_2)

            status = entry.get("status", "scheduled")
            schedule_name = entry.get("schedule_name", "")
            scheduled_date = entry.get("scheduled_date", "")
            sent_at = entry.get("sent_at", "")
            self._add_timeline_dot(entry_row, status)
            self._add_timeline_text(entry_row, schedule_name, scheduled_date, sent_at, status)
            entry_row.addStretch()
            layout.addLayout(entry_row)

        # Manual controls
        actions = QHBoxLayout()
        actions.setSpacing(SPACE_2)
        actions.addStretch()

        send_now_btn = Btn(
            self, text=t("automail.send_now", "Send Now"),
            variant="primary", size="sm",
            command=self._on_send_now,
        )
        actions.addWidget(send_now_btn)

        skip_btn = Btn(
            self, text=t("automail.skip", "Skip"),
            variant="ghost", size="sm",
            command=self._on_skip,
        )
        actions.addWidget(skip_btn)

        cancel_btn = Btn(
            self, text=t("automail.cancel_all", "Cancel All"),
            variant="ghost", size="sm",
            command=self._on_cancel_all,
        )
        actions.addWidget(cancel_btn)

        layout.addLayout(actions)

    def _compute_days_past(self, due_date_str: str) -> Optional[int]:
        if not due_date_str:
            return None
        try:
            due = datetime.strptime(str(due_date_str)[:10], "%Y-%m-%d").date()
            diff = (date.today() - due).days
            return diff if diff >= 0 else None
        except (ValueError, TypeError):
            return None

    def _add_timeline_dot(self, layout: QHBoxLayout, status: str) -> None:
        colors = {
            "sent": COLOR_SUCCESS_TEXT,
            "scheduled": COLOR_ACCENT_PRIMARY,
            "failed": COLOR_ERROR_TEXT,
            "skipped": COLOR_NEUTRAL_TEXT,
            "cancelled": COLOR_NEUTRAL_TEXT,
        }
        c = colors.get(status, COLOR_TEXT_TERTIARY)
        dot = QLabel("●", self)
        dot.setStyleSheet(f"color: {c}; font-size: 8px;")
        layout.addWidget(dot)

    def _add_timeline_text(
        self,
        layout: QHBoxLayout,
        name: str,
        scheduled_date: str,
        sent_at: str,
        status: str,
    ) -> None:
        if sent_at and status == "sent":
            text = f"{name} — Sent {sent_at[:10]}"
        elif scheduled_date:
            text = f"{name} — Scheduled {scheduled_date}"
        else:
            text = f"{name} — {status.capitalize()}"
        color = COLOR_TEXT_SECONDARY if status in ("sent", "scheduled") else COLOR_NEUTRAL_TEXT
        lbl = QLabel(text, self)
        lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        layout.addWidget(lbl)

    def _on_send_now(self) -> None:
        if self._ops is None or self._db is None:
            return
        invoice_id = self._data.get("invoice_id")
        trip_id = self._data.get("trip_id")
        client_email = self._data.get("client_email")
        if not invoice_id or not client_email:
            return

        reply = QMessageBox.question(
            self,
            t("common.confirm", "Confirm"),
            t("automail.confirm_send_now",
              "Send this reminder email now?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            template_service = TemplateService(self._db)
            repo = self._automail_repo if self._automail_repo is not None else AutoMailRepository(self._db)
            schedules = repo.get_active_schedules()
            if not schedules:
                return

            # Find the next unsent schedule for this invoice
            sched = schedules[0]
            timeline = self._data.get("timeline", [])
            for entry in timeline:
                if entry.get("status") in ("scheduled",):
                    sid = entry.get("schedule_id")
                    for s in schedules:
                        if s["id"] == sid:
                            sched = s
                            break
                    break
            template = repo.get_template_by_id(sched["template_id"])
            if not template:
                return

            company_name = load_company_config().get("company_name", "Operion ERP")
            total_amount_val = self._data.get("total_amount") or 0
            ctx = {
                "invoice_number": self._data.get("invoice_number", ""),
                "total_amount": f"{total_amount_val:,.2f}",
                "currency": self._data.get("currency", "EUR"),
                "due_date": self._data.get("due_date", ""),
                "days_overdue": "0",
                "company_name": company_name,
                "client_name": self._data.get("client_name", ""),
                "client_contact": "",
                "trip_id": str(trip_id or ""),
                "truck_plate": "",
                "driver_name": "",
            }
            subject, body_text, body_html = template_service.render_email(template, ctx)
            has_html = bool(body_html and body_html.strip())

            nc = self._ops.notification_center if self._ops else NotificationCenter(self._db)
            import os as _os
            from services.document_automation.package_builder import PackageBuilder
            builder = PackageBuilder(self._db)
            docs = builder.list_trip_documents(trip_id)
            paths = [d["file_path"] for d in docs if d.get("file_path") and _os.path.isfile(d["file_path"])]

            ok = nc.send_email(
                to_address=client_email,
                subject=subject,
                body=body_html if has_html else body_text,
                attachments=paths,
                html=has_html,
            )
            if ok:
                self._log_manual_send(invoice_id, trip_id, client_email)
                QMessageBox.information(self, t("common.success", "Success"),
                                        t("automail.email_sent", "Email sent successfully."))
            else:
                QMessageBox.warning(self, t("common.error", "Error"),
                                    t("automail.send_failed", "Failed to send email."))
        except Exception as exc:
            logger.exception("Send Now failed: %s", exc)
            QMessageBox.warning(self, t("common.error", "Error"), str(exc))

    def _log_manual_send(self, invoice_id: int, trip_id: int, recipient: str) -> None:
        try:
            repo = self._automail_repo if self._automail_repo is not None else AutoMailRepository(self._db)
            repo.log_manual_send(invoice_id, trip_id, recipient)
        except Exception as exc:
            logger.error("Failed to log manual send: %s", exc)

    def _on_skip(self) -> None:
        reply = QMessageBox.question(
            self, t("common.confirm", "Confirm"),
            t("automail.confirm_skip", "Skip the next scheduled reminder?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        svc = ReminderService(self._db)
        ok = svc.skip_next_reminder(
            self._data.get("invoice_id"),
            self._data.get("trip_id"),
        )
        if ok:
            QMessageBox.information(self, t("common.success", "Success"),
                                    t("automail.skipped", "Reminder skipped."))
        else:
            QMessageBox.warning(self, t("common.error", "Error"),
                                t("automail.skip_failed", "Failed to skip."))

    def _on_cancel_all(self) -> None:
        reply = QMessageBox.question(
            self, t("common.confirm", "Confirm"),
            t("automail.confirm_cancel_all",
              "Cancel ALL future reminders for this invoice?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        svc = ReminderService(self._db)
        ok = svc.cancel_all_reminders(
            self._data.get("invoice_id"),
            self._data.get("trip_id"),
        )
        if ok:
            QMessageBox.information(self, t("common.success", "Success"),
                                    t("automail.cancelled", "All reminders cancelled."))
        else:
            QMessageBox.warning(self, t("common.error", "Error"),
                                t("automail.cancel_failed", "Failed to cancel."))


class TimelinePanel(QFrame):
    """Center timeline panel for the AutoMail tab."""

    def __init__(
        self,
        parent: QWidget,
        db=None,
        prefs=None,
        ops=None,
        automail_repo=None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._prefs = prefs
        self._ops = ops
        self._automail_repo = automail_repo
        self.setProperty("role", "automail-timeline-panel")
        self.setStyleSheet(f"background: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_LG}px;")

        self._page = 0
        self._search = ""
        self._status_filter = ""

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stats bar
        self._stats_bar = QWidget(self)
        self._stats_bar.setStyleSheet("background: transparent;")
        self._stats_layout = QHBoxLayout(self._stats_bar)
        self._stats_layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_2)
        self._stats_layout.setSpacing(SPACE_3)
        self._stats_sent = QLabel("0 sent", self)
        self._stats_failed = QLabel("0 failed", self)
        self._stats_recovered = QLabel("€0 outstanding", self)
        for lbl in (self._stats_sent, self._stats_failed, self._stats_recovered):
            lbl.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._stats_layout.addStretch(1)
        self._stats_layout.addWidget(self._stats_sent)
        self._stats_layout.addStretch(1)
        self._stats_layout.addWidget(self._stats_failed)
        self._stats_layout.addStretch(1)
        self._stats_layout.addWidget(self._stats_recovered)
        self._stats_layout.addStretch(1)
        layout.addWidget(self._stats_bar)

        # Search + Filter
        search_row = QHBoxLayout()
        search_row.setContentsMargins(SPACE_4, SPACE_2, SPACE_4, SPACE_2)
        search_row.setSpacing(SPACE_2)

        self._search_input = StyledLineEdit(
            self, placeholder=t("automail.search_placeholder", "Search invoices, clients...")
        )
        self._search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search_input, 1)
        layout.addLayout(search_row)

        # Filter pills
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(SPACE_4, 0, SPACE_4, SPACE_2)
        filter_row.setSpacing(SPACE_2)
        filters = [
            ("", t("automail.filter_all", "All")),
            ("scheduled", t("automail.filter_scheduled", "Upcoming")),
            ("sent", t("automail.filter_sent", "Sent")),
            ("failed", t("automail.filter_failed", "Failed")),
            ("skipped", t("automail.filter_skipped", "Skipped")),
            ("overdue", t("automail.filter_overdue", "Overdue")),
        ]
        self._filter_btns: list[QPushButton] = []
        for fvalue, flabel in filters:
            btn = QPushButton(flabel, self)
            btn.setCheckable(True)
            btn.setProperty("filter_value", fvalue)
            btn.setChecked(fvalue == "")
            btn.setStyleSheet(self._filter_style(fvalue == ""))
            btn.clicked.connect(lambda checked, v=fvalue: self._on_filter_changed(v))
            self._filter_btns.append(btn)
            filter_row.addWidget(btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Timeline scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._list_content = QWidget(scroll)
        self._list_content.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_content)
        self._list_layout.setContentsMargins(SPACE_4, SPACE_2, SPACE_4, SPACE_2)
        self._list_layout.setSpacing(SPACE_2)
        self._list_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self._list_content)
        layout.addWidget(scroll, 1)

        # Pagination
        self._pager = QWidget(self)
        pager_layout = QHBoxLayout(self._pager)
        pager_layout.setContentsMargins(SPACE_4, SPACE_2, SPACE_4, SPACE_3)
        pager_layout.setSpacing(SPACE_2)

        self._page_label = QLabel("", self)
        self._page_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
        pager_layout.addWidget(self._page_label)

        pager_layout.addStretch()

        self._prev_btn = Btn(self, text=t("common.prev", "← Previous"), variant="ghost", size="sm",
                             command=self._prev_page)
        pager_layout.addWidget(self._prev_btn)

        self._next_btn = Btn(self, text=t("common.next", "Next →"), variant="ghost", size="sm",
                             command=self._next_page)
        pager_layout.addWidget(self._next_btn)

        layout.addWidget(self._pager)

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

    def _filter_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {COLOR_ACCENT_PRIMARY}; color: white; "
                f"border: none; border-radius: 12px; padding: 4px 12px; font-size: 11px; }}"
            )
        return (
            f"QPushButton {{ background: transparent; color: {COLOR_TEXT_SECONDARY}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 12px; padding: 4px 12px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {COLOR_BG_HOVER}; }}"
        )

    # ── Data loading ───────────────────────────────────────────────

    def wakeup(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        if self._db is None:
            return

        svc = ReminderService(self._db)
        try:
            entries, total = svc.get_reminder_status_for_all_active(
                page=self._page,
                search=self._search,
                status_filter=self._status_filter,
                limit=_PAGE_SIZE,
            )
        except Exception as exc:
            logger.exception("Failed to load timeline: %s", exc)
            entries, total = [], 0

        # Clear
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not entries:
            empty = QLabel(
                t("automail.timeline_empty",
                  "No reminders match your filters."),
                self._list_content,
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 13px; padding: 40px;")
            self._list_layout.addWidget(empty)
        else:
            for entry in entries:
                card = _InvoiceTimelineCard(
                    self._list_content, entry, self._ops, self._db,
                )
                self._list_layout.addWidget(card)

        if total == 0:
            self._page_label.setText(
                t("automail.pagination_empty", "No reminders")
            )
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
        else:
            start = self._page * _PAGE_SIZE + 1
            end = min(start + len(entries) - 1, total)
            self._page_label.setText(
                t("automail.pagination", "Showing {start}-{end} of {total}")
                .replace("{start}", str(start)).replace("{end}", str(end)).replace("{total}", str(total))
            )
            self._prev_btn.setEnabled(self._page > 0)
            self._next_btn.setEnabled(end < total)

        # Update stats
        hsvc = HistoryService(self._db)
        stats = hsvc.get_stats()
        self._stats_sent.setText(t("automail.emails_sent", "{count} sent").replace("{count}", str(stats.get("emails_sent", 0))))
        self._stats_failed.setText(t("automail.emails_failed", "{count} failed").replace("{count}", str(stats.get("emails_failed", 0))))
        outstanding = stats.get("total_outstanding_amount", stats.get("total_overdue_amount", 0))
        self._stats_recovered.setText(
            t("automail.outstanding", "€{amount} outstanding")
            .replace("{amount}", f"{outstanding:,.0f}")
        )

    # ── Handlers ───────────────────────────────────────────────────

    def _on_search_changed(self, text: str) -> None:
        self._search = text
        self._search_timer.start()

    def _do_search(self) -> None:
        self._page = 0
        self._load_data()

    def _on_filter_changed(self, filter_value: str) -> None:
        self._status_filter = filter_value
        for btn in self._filter_btns:
            matches = btn.property("filter_value") == filter_value
            btn.setChecked(matches)
            btn.setStyleSheet(self._filter_style(matches))
        self._page = 0
        self._load_data()

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._load_data()

    def _next_page(self) -> None:
        self._page += 1
        self._load_data()
