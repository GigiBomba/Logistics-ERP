"""Per-client detail tabs — profile, KPIs, contacts, tags, payment, timeline."""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta

from services.i18n import t
from ui.components import (
    Btn,
    KPICard,
    SectionTitle,
)
from ui.design_tokens import (
    BTN_HEIGHT_SM,
    COLOR_ACCENT_PRIMARY,
    COLOR_ACCENT_SUBTLE,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_SIZE_BASE,
    FONT_SIZE_SM,
    RADIUS_SM,
    SP,
    SPACE_1,
    SPACE_2,
    SPACE_3,
)
from ui.form_utils import add_required_indicator
from ui.widgets import (
    ScrollableFormContainer,
    StyledComboBox,
    StyledLineEdit,
    field,
)
from ui.widgets.client_activity_timeline import QtClientActivityTimeline
from ui.widgets.toast import Toast


# ======================================================================
# Inline-editable field helper
# ======================================================================


class InlineEditableField(QWidget):
    """A field row with a label and a double-click-editable value.

    Double-click the value label to switch to a ``QLineEdit`` with inline
    Save (check icon) / Cancel (times icon) buttons.  Enter confirms,
    Escape cancels.
    """

    def __init__(
        self,
        parent: QWidget | None,
        label_text: str,
        field_name: str,
        value: str,
        on_save: Callable[[str, str], None],
        required: bool = False,
    ):
        super().__init__(parent)
        self._field_name = field_name
        self._original_value = str(value or "")
        self._on_save = on_save
        self._required = required
        self._editing = False

        # Outer vertical layout: [row] + [error_label]
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(SPACE_1)

        # Top row: label + editable value
        row_widget = QWidget()
        layout = QHBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_3)
        outer_layout.addWidget(row_widget)

        # Field label
        self._label = QLabel(label_text)
        self._label.setProperty("role", "field-label")
        self._label.setFixedWidth(140)
        if required:
            add_required_indicator(self._label)
        layout.addWidget(self._label)

        # Value label (visible by default)
        self._value_lbl = QLabel(self._original_value)
        self._value_lbl.setProperty("role", "body")
        self._value_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._value_lbl.setCursor(Qt.PointingHandCursor)
        self._value_lbl.mouseDoubleClickEvent = lambda e: self._start_edit()  # type: ignore[method-assign]
        layout.addWidget(self._value_lbl, 1)

        # Edit field (hidden until double-click)
        self._edit = QLineEdit()
        self._edit.setFixedHeight(28)
        self._edit.returnPressed.connect(self._save)
        self._edit.installEventFilter(self)
        layout.addWidget(self._edit, 1)
        self._edit.hide()

        # Save button (hidden)
        self._save_btn = QPushButton()
        self._save_btn.setIcon(qta.icon("fa5s.check"))
        self._save_btn.setFixedSize(BTN_HEIGHT_SM, BTN_HEIGHT_SM)
        self._save_btn.setProperty("variant", "success")
        self._save_btn.clicked.connect(self._save)
        layout.addWidget(self._save_btn)
        self._save_btn.hide()

        # Cancel button (hidden)
        self._cancel_btn = QPushButton()
        self._cancel_btn.setIcon(qta.icon("fa5s.times"))
        self._cancel_btn.setFixedSize(BTN_HEIGHT_SM, BTN_HEIGHT_SM)
        self._cancel_btn.setProperty("variant", "ghost")
        self._cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self._cancel_btn)
        self._cancel_btn.hide()

        # Error label (hidden by default)
        self._error_lbl = QLabel()
        self._error_lbl.setProperty("role", "field-error")
        self._error_lbl.setVisible(False)
        self._error_lbl.setWordWrap(True)
        outer_layout.addWidget(self._error_lbl)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_value(self, value: str) -> None:
        """Update the displayed value (without triggering a save)."""
        self._original_value = str(value or "")
        self._value_lbl.setText(self._original_value)

    # ------------------------------------------------------------------
    # Edit lifecycle
    # ------------------------------------------------------------------

    def _start_edit(self) -> None:
        if self._editing:
            return
        self._editing = True
        self._value_lbl.hide()
        self._edit.setText(self._value_lbl.text())
        self._edit.show()
        self._save_btn.show()
        self._cancel_btn.show()
        self._edit.setFocus()
        self._edit.selectAll()
        # Clear any previous error
        self._error_lbl.setVisible(False)
        self._edit.setProperty("validation", "")
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)

    def _save(self) -> None:
        new_value = self._edit.text().strip()

        # ── Validation ────────────────────────────────────────────────────
        error: str | None = None
        if self._required and not new_value:
            error = "This field is required"
        elif self._field_name == "email" and new_value:
            if "@" not in new_value or "." not in new_value.split("@")[-1]:
                error = "Enter a valid email address"
        elif self._field_name == "phone" and new_value and len(new_value) < 7:
            error = "Enter a valid phone number"

        if error:
            self._error_lbl.setText(error)
            self._error_lbl.setVisible(True)
            self._edit.setProperty("validation", "error")
            self._edit.style().unpolish(self._edit)
            self._edit.style().polish(self._edit)
            return

        # ── Success ───────────────────────────────────────────────────────
        self._error_lbl.setVisible(False)
        self._edit.setProperty("validation", "")
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)

        self._original_value = new_value
        self._value_lbl.setText(new_value)
        self._end_edit()
        if self._on_save is not None:
            self._on_save(self._field_name, new_value)

    def _cancel(self) -> None:
        self._edit.setText(self._original_value)
        self._value_lbl.setText(self._original_value)
        self._end_edit()

    def _end_edit(self) -> None:
        self._editing = False
        self._edit.hide()
        self._save_btn.hide()
        self._cancel_btn.hide()
        self._value_lbl.show()

    # ------------------------------------------------------------------
    # Event handling — escape key on the QLineEdit
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self._edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self._cancel()
                return True
        return super().eventFilter(obj, event)


# ======================================================================
# Client detail tab  (profile + KPIs + contacts + tags + payment + timeline)
# ======================================================================


class _QtClientDetailsTab(QWidget):
    """Scrollable detail tab showing profile, KPIs, contacts, tags, payment
    summary, and activity timeline for a selected client."""

    _CACHE_MAX_SIZE = 10

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self)
        self._content = scroll.content
        layout.addWidget(scroll, 1)

        self._current_client_id: int | None = None
        self._service = None
        self._widget_cache: dict[int, QWidget] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, service, client_id: int) -> None:
        """Rebuild the entire detail tab for the given client.

        Shows skeleton loading placeholders immediately, then builds
        the real content on the next event loop iteration.
        Uses a widget cache to avoid full rebuilds when switching
        between recently viewed clients.
        """
        self._service = service
        self._current_client_id = client_id

        # Check cache first — avoid full rebuild
        if client_id in self._widget_cache:
            cached = self._widget_cache[client_id]
            cl = self._content.layout()
            if cl:
                self._clear_content()
                cl.addWidget(cached)
            self._refresh_data_labels()
            return

        self._show_skeleton()
        QTimer.singleShot(0, lambda: self._build(service, client_id))

    # ------------------------------------------------------------------
    # Content management
    # ------------------------------------------------------------------

    def _clear_content(self) -> None:
        layout = self._content.layout()
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                # Preserve cached containers — they are stored in _widget_cache
                # and will be re-used. Non-cached widgets (skeletons, old builds)
                # are safely deleted.
                if w not in self._widget_cache.values():
                    w.deleteLater()

    def _show_skeleton(self) -> None:
        """Replace content with skeleton loading placeholders."""
        from ui.skeleton_widgets import SkeletonLine, SkeletonWidget

        self._clear_content()
        cl = self._content.layout()

        # Skeleton section title
        title_skel = SkeletonWidget(self._content, height=18, rounded=True)
        title_skel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cl.addWidget(title_skel)

        cl.addSpacing(8)

        # Profile fields: 8 rows of label + value skeleton
        for _ in range(8):
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SPACE_3)

            label_skel = SkeletonWidget(row, width=140, height=12, rounded=True)
            label_skel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            row_layout.addWidget(label_skel)

            value_skel = SkeletonWidget(row, height=12, rounded=True)
            value_skel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row_layout.addWidget(value_skel, 1)

            cl.addWidget(row)

        cl.addSpacing(16)

        # KPI section skeleton (2 rows of 4 cards)
        for _ in range(2):
            kpi_row = QFrame()
            kpi_layout = QHBoxLayout(kpi_row)
            kpi_layout.setContentsMargins(0, 0, 0, 0)
            kpi_layout.setSpacing(SP["2"])
            for _ in range(4):
                card = SkeletonWidget(kpi_row, height=60, rounded=True)
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                kpi_layout.addWidget(card)
            cl.addWidget(kpi_row)

        cl.addStretch()

    def _build(self, service, client_id: int) -> None:
        """Fetch dashboard data and build all sections."""
        dash = service.get_client_dashboard(client_id)
        client = dash.get("client", {})
        contacts = dash.get("contacts", [])
        tags = dash.get("tags", [])

        # Build into the content layout as before
        self._build_profile_section(client, dash, service)
        self._build_kpi_section(dash)
        self._build_contacts_section(contacts, service, client_id)
        self._build_tags_section(tags, service, client_id)

        with contextlib.suppress(Exception):
            self._build_payment_summary(service, client_id)

        with contextlib.suppress(Exception):
            self._build_timeline(service, client_id)

        cl = self._content.layout()
        if cl:
            cl.addStretch()

        # Wrap all built widgets in a container and cache it
        self._cache_current(client_id)

    def _cache_current(self, client_id: int) -> None:
        """Move all widgets from content layout into a cached container."""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        cl = self._content.layout()
        if cl is None:
            return

        # Transfer all items from content layout to container layout
        while cl.count():
            item = cl.takeAt(0)
            w = item.widget()
            if w is not None:
                container_layout.addWidget(w)
            elif item.layout():
                container_layout.addLayout(item.layout())
            elif item.spacerItem():
                container_layout.addSpacerItem(item.spacerItem())

        # Add the container back to content layout
        cl.addWidget(container)

        # Cache it
        self._widget_cache[client_id] = container

        # Enforce max cache size — evict oldest entry
        if len(self._widget_cache) > self._CACHE_MAX_SIZE:
            oldest = next(iter(self._widget_cache))
            del self._widget_cache[oldest]

    def _refresh_data_labels(self) -> None:
        """Update data labels in the currently displayed cached widget.

        Called after switching to a cached client view so that
        the values reflect the latest state from the service.
        """
        if self._service is None or self._current_client_id is None:
            return
        try:
            dash = self._service.get_client_dashboard(self._current_client_id)
            client = dash.get("client", {})
            # Update inline fields in the cached widget
            self._update_profile_labels(client)
            self._update_kpi_labels(dash)
        except Exception:
            logger.debug("Could not refresh data labels", exc_info=True)

    def _update_profile_labels(self, client: dict) -> None:
        """Walk child widgets and update InlineEditableField values."""
        cached = self._widget_cache.get(self._current_client_id)
        if cached is None:
            return
        for field_widget in cached.findChildren(InlineEditableField):
            field_name = getattr(field_widget, "_field_name", None)
            if field_name and field_name in client:
                field_widget.set_value(str(client.get(field_name, "")))

    def _update_kpi_labels(self, dash: dict) -> None:
        """Update KPI card values in the cached widget."""
        from ui.components import KPICard

        cached = self._widget_cache.get(self._current_client_id)
        if cached is None:
            return
        kpi_cards = cached.findChildren(KPICard)
        # Re-read values from dash and update in order
        values: list[str] = []
        total_rev = dash.get("total_revenue", 0) or 0
        total_trips = dash.get("total_trips", 0) or 0
        total_km = dash.get("total_km", 0) or 0
        last_30 = dash.get("trips_last_30_days", 0) or 0
        total_profit = dash.get("total_profit", 0) or 0
        avg_profit = dash.get("avg_profit", 0) or 0
        outstanding = dash.get("outstanding_balance", 0) or 0
        last_trip = dash.get("last_trip_date", "\u2014")
        if last_trip and len(str(last_trip)) > 10:
            last_trip = str(last_trip)[:10]

        values = [
            f"\u20ac {total_rev:,.0f}",
            str(total_trips),
            f"{total_km:,.0f} km",
            str(last_30),
            f"\u20ac {total_profit:,.0f}",
            f"\u20ac {avg_profit:,.0f}",
            f"\u20ac {outstanding:,.0f}",
            str(last_trip),
        ]
        for card, val in zip(kpi_cards, values):
            card._value_lbl.setText(val) if hasattr(card, '_value_lbl') else None

    def clear_cache(self) -> None:
        """Clear the widget cache. Called from parent when data changes."""
        self._widget_cache.clear()

    # ------------------------------------------------------------------
    # Profile section
    # ------------------------------------------------------------------

    def _build_profile_section(self, client: dict, dash: dict,
                                service) -> None:
        cl = self._content.layout()

        # Section header
        header_widget = SectionTitle(
            self._content, t("client.section_profile", default="Profile"),
        )
        cl.addWidget(header_widget)

        # Client type badge + rating + status row (not editable).
        meta_row = QFrame()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(SP["2"])

        c_type = client.get("client_type", "")
        if c_type:
            type_lbl = QLabel(c_type)
            type_lbl.setProperty("fontRole", "label")
            type_lbl.setStyleSheet(f"color: {COLOR_ACCENT_PRIMARY};")
            meta_layout.addWidget(type_lbl)

        rating = client.get("rating") or 0
        if rating:
            stars = "\u2605" * int(rating) + "\u2606" * (5 - int(rating))
            star_lbl = QLabel(stars)
            star_lbl.setProperty("fontRole", "small")
            star_lbl.setStyleSheet(f"color: {COLOR_WARNING_DEFAULT};")
            meta_layout.addWidget(star_lbl)

        meta_layout.addStretch()

        is_active = client.get("is_active", 1)
        status_text = "Active" if is_active else "Inactive"
        status_color = COLOR_SUCCESS_DEFAULT if is_active else COLOR_TEXT_TERTIARY
        status_lbl = QLabel(status_text)
        status_lbl.setProperty("fontRole", "label")
        status_lbl.setStyleSheet(f"color: {status_color};")
        meta_layout.addWidget(status_lbl)

        cl.addWidget(meta_row)

        # ── Inline-editable fields ────────────────────────────────────
        # Each tuple: (field_key, label_or_i18n_key, required)
        _EDITABLE_FIELDS: list[tuple[str, str, bool]] = [
            ("name",            "client.field_name",    True),
            ("contact_person",  "client.field_contact",  False),
            ("email",           "client.field_email",    False),
            ("phone",           "client.field_phone",    False),
            ("address",         "client.field_address",  False),
            ("country",         "client.field_country",  False),
            ("vat_number",      "client.field_vat",      False),
            ("eori_number",     "Registration number",   False),
            ("notes",           "client.field_notes",    False),
        ]

        for field_key, label_or_key, required in _EDITABLE_FIELDS:
            # Resolve label: if it starts with "client." treat as i18n key
            label = (
                t(label_or_key)
                if label_or_key.startswith("client.")
                else label_or_key
            )
            value = client.get(field_key, "")
            fw = InlineEditableField(
                self._content,
                label_text=label,
                field_name=field_key,
                value=str(value or ""),
                on_save=self._save_client_field,
                required=required,
            )
            cl.addWidget(fw)

        # ── Non-editable info row ─────────────────────────────────────
        extra_parts = []
        if client.get("payment_terms_days"):
            extra_parts.append(
                t("client.terms_days", default="Terms: {} days").format(
                    client["payment_terms_days"],
                ),
            )
        if client.get("credit_limit_eur"):
            extra_parts.append(
                "Limit: \u20ac{:,}".format(int(client["credit_limit_eur"])),
            )

        if extra_parts:
            extra_row = QFrame()
            extra_layout = QHBoxLayout(extra_row)
            extra_layout.setContentsMargins(0, 0, 0, 0)
            extra_layout.setSpacing(SP["3"])
            for part in extra_parts:
                lbl = QLabel(part)
                lbl.setProperty("fontRole", "small")
                extra_layout.addWidget(lbl)
            extra_layout.addStretch()
            cl.addWidget(extra_row)

    # ------------------------------------------------------------------
    # Inline edit save
    # ------------------------------------------------------------------

    def _save_client_field(self, field_name: str, value: str) -> None:
        """Persist a single client field update to the database."""
        if self._service is None or self._current_client_id is None:
            return
        try:
            self._service.update(
                self._current_client_id, **{field_name: value},
            )
            Toast.show_success(
                self, t("client.save_success", default="Field updated"),
            )
        except Exception as e:
            Toast.show_error(self, str(e))

    # ------------------------------------------------------------------
    # KPI section
    # ------------------------------------------------------------------

    def _build_kpi_section(self, dash: dict) -> None:
        cl = self._content.layout()

        header_widget = SectionTitle(self._content, t("client.section_kpis"))
        cl.addWidget(header_widget)

        total_rev = dash.get("total_revenue", 0) or 0
        total_trips = dash.get("total_trips", 0) or 0
        total_km = dash.get("total_km", 0) or 0
        last_30 = dash.get("trips_last_30_days", 0) or 0
        total_profit = dash.get("total_profit", 0) or 0
        avg_profit = dash.get("avg_profit", 0) or 0
        outstanding = dash.get("outstanding_balance", 0) or 0
        last_trip = dash.get("last_trip_date", "\u2014")
        if last_trip and len(str(last_trip)) > 10:
            last_trip = str(last_trip)[:10]

        row1 = QFrame()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(SP["2"])

        row1_layout.addWidget(KPICard(self._content, t("client.kpi_total_revenue"),
                                       f"\u20ac {total_rev:,.0f}"))
        row1_layout.addWidget(KPICard(self._content, t("client.kpi_total_trips"),
                                       str(total_trips)))
        row1_layout.addWidget(KPICard(self._content, t("client.kpi_total_km"),
                                       f"{total_km:,.0f} km"))
        row1_layout.addWidget(KPICard(self._content, t("client.kpi_last_30d"),
                                       str(last_30)))
        cl.addWidget(row1)

        row2 = QFrame()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(SP["2"])

        profit_card = KPICard(self._content, t("client.kpi_total_profit"),
                               f"\u20ac {total_profit:,.0f}")
        profit_card.setProperty("role", "kpi-card")

        row2_layout.addWidget(profit_card)
        row2_layout.addWidget(KPICard(self._content, t("client.kpi_avg_profit"),
                                       f"\u20ac {avg_profit:,.0f}"))
        row2_layout.addWidget(KPICard(self._content, t("client.kpi_outstanding"),
                                       f"\u20ac {outstanding:,.0f}"))
        row2_layout.addWidget(KPICard(self._content, t("client.kpi_last_trip"),
                                       str(last_trip)))
        cl.addWidget(row2)

    # ------------------------------------------------------------------
    # Contacts section
    # ------------------------------------------------------------------

    def _build_contacts_section(self, contacts: list, service,
                                 client_id: int) -> None:
        if not contacts:
            return

        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_contacts"))
        cl.addWidget(header_widget)

        for c in contacts:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SP["2"])

            name_text = c.get("full_name", "")
            if c.get("is_primary"):
                name_text += " \u2605"
            name_lbl = QLabel(name_text)
            name_lbl.setProperty("fontRole", "body_bold")
            row_layout.addWidget(name_lbl)

            title = c.get("title", "")
            if title:
                title_lbl = QLabel(title)
                title_lbl.setProperty("fontRole", "small")
                row_layout.addWidget(title_lbl)

            phone = c.get("phone", "")
            email = c.get("email", "")
            contact_info = "  ".join(p for p in (phone, email) if p)
            if contact_info:
                info_lbl = QLabel(contact_info)
                info_lbl.setProperty("fontRole", "small")
                row_layout.addWidget(info_lbl)

            row_layout.addStretch()

            row_layout.addWidget(Btn(
                row, text=t("common.edit", default="Edit"),
                command=lambda cid=c["id"]: self._edit_contact(cid, service, client_id),
                variant="secondary",
            ))
            row_layout.addWidget(Btn(
                row, text="\u2716",
                command=lambda cid=c["id"]: self._delete_contact(cid, service),
                variant="danger",
            ))
            cl.addWidget(row)

        cl.addWidget(Btn(
            self._content, text="+ " + t("client.add_contact"),
            command=lambda: self._add_contact(service, client_id),
            variant="secondary",
        ))

    def _add_contact(self, service, client_id: int) -> None:
        dialog = _QtContactDialog(
            self._content, service, client_id=client_id,
            on_save=lambda: self._rebuild(service),
        )
        dialog.exec()

    def _edit_contact(self, contact_id: int, service, client_id: int) -> None:
        contacts = service.get_contacts(client_id)
        ct_data = next((c for c in contacts if c["id"] == contact_id), None)
        dialog = _QtContactDialog(
            self._content, service, client_id=client_id,
            contact_data=ct_data,
            on_save=lambda: self._rebuild(service),
        )
        dialog.exec()

    def _delete_contact(self, contact_id: int, service) -> None:
        reply = QMessageBox.question(
            self._content, t("common.confirm"),
            t("client.confirm_delete_contact"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            service.delete_contact(contact_id)
            if self._current_client_id is not None:
                self._rebuild(service)

    def _rebuild(self, service) -> None:
        if self._current_client_id is not None:
            self.refresh(service, self._current_client_id)

    # ------------------------------------------------------------------
    # Tags section
    # ------------------------------------------------------------------

    def _build_tags_section(self, tags: list, service, client_id: int) -> None:
        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_tags"))
        cl.addWidget(header_widget)

        tag_names = [t_row.get("tag", t_row) for t_row in tags]
        if not tag_names:
            no_tags = QLabel(t("client.no_tags"))
            no_tags.setProperty("fontRole", "small")
            cl.addWidget(no_tags)
        else:
            chips_row = QFrame()
            chips_layout = QHBoxLayout(chips_row)
            chips_layout.setContentsMargins(0, 0, 0, 0)
            chips_layout.setSpacing(SP["1"])
            for tag in tag_names:
                chip = QLabel(f"  {tag}  ")
                chip.setProperty("fontRole", "label")
                chip.setStyleSheet(
                f"background-color: {COLOR_ACCENT_SUBTLE}; "
                f"color: {COLOR_ACCENT_PRIMARY}; "
                    f"border-radius: 4px; padding: 2px 4px;"
                )
                chips_layout.addWidget(chip)
            cl.addWidget(chips_row)

        # Add-tag row
        add_row = QFrame()
        add_layout = QHBoxLayout(add_row)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(SP["1"])

        self._tag_entry = StyledLineEdit(
            placeholder=t("client.tag_placeholder"),
        )
        add_layout.addWidget(self._tag_entry)

        add_layout.addWidget(Btn(
            add_row, text="+",
            command=lambda: self._add_tag(service, client_id),
            variant="secondary",
        ))
        cl.addWidget(add_row)

    def _add_tag(self, service, client_id: int) -> None:
        tag = (self._tag_entry.text() or "").strip()
        if tag:
            service.add_tag(client_id, tag)
            self._tag_entry.clear()
            if self._current_client_id is not None:
                self._rebuild(service)

    # ------------------------------------------------------------------
    # Payment summary section
    # ------------------------------------------------------------------

    def _build_payment_summary(self, service, client_id: int) -> None:
        pay = service.get_payment_summary(client_id)
        if not pay or not pay.get("invoice_count"):
            return

        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_payment"))
        cl.addWidget(header_widget)

        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SP["2"])

        row_layout.addWidget(KPICard(
            self._content, t("client.billed", default="Billed"), f"\u20ac {pay['total_billed']:,.0f}",
        ))
        row_layout.addWidget(KPICard(
            self._content, t("client.paid", default="Paid"), f"\u20ac {pay['total_paid']:,.0f}",
        ))
        row_layout.addWidget(KPICard(
            self._content, t("client.unpaid", default="Unpaid"), f"\u20ac {pay['unpaid']:,.0f}",
        ))
        overdue_card = KPICard(
            self._content, t("client.overdue", default="Overdue"), f"\u20ac {pay['overdue']:,.0f}",
        )
        row_layout.addWidget(overdue_card)
        cl.addWidget(row)

    # ------------------------------------------------------------------
    # Activity timeline section
    # ------------------------------------------------------------------

    def _build_timeline(self, service, client_id: int) -> None:
        cl = self._content.layout()
        header_widget = SectionTitle(self._content, t("client.section_timeline"))
        cl.addWidget(header_widget)

        timeline = QtClientActivityTimeline(
            self._content, service=service, client_id=client_id,
        )
        cl.addWidget(timeline)


# ======================================================================
# Contact dialog  (used by details tab)
# ======================================================================


class _QtContactDialog(QDialog):
    """Add / edit contact dialog."""

    FIELDS: list[tuple] = [
        ("full_name",    "client.field_full_name"),
        ("title",        "client.field_title"),
        ("phone",        "client.field_phone"),
        ("email",        "client.field_email"),
        ("contact_type", "client.field_contact_type"),
    ]

    COMBO_FIELDS = {"contact_type"}

    def __init__(
        self,
        parent: QWidget | None,
        service: Any,
        client_id: int,
        contact_data: dict[str, Any] | None = None,
        on_save=None,
    ):
        super().__init__(parent)
        self.service = service
        self.client_id = client_id
        self.contact_data = contact_data
        self.on_save = on_save
        self._editing = contact_data is not None

        self.setWindowTitle(
            t("client.edit_contact") if self._editing else t("client.new_contact"),
        )
        self.setMinimumSize(400, 380)
        self.setModal(True)

        self._entries: dict[str, Any] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = ScrollableFormContainer(self, max_width=400)
        layout.addWidget(scroll, 1)

        # Store error labels per field for inline validation
        self._error_labels: dict[str, QLabel] = {}

        for key, i18n_key in self.FIELDS:
            if key in self.COMBO_FIELDS:
                entry = StyledComboBox(
                    values=["primary", "billing", "operations", "management", "other"],
                )
                default = (self.contact_data or {}).get(key, "operations")
                idx = entry.findText(default)
                if idx >= 0:
                    entry.setCurrentIndex(idx)
            else:
                entry = StyledLineEdit()
                if self.contact_data is not None:
                    val = self.contact_data.get(key) or ""
                    entry.setText(str(val))

            self._entries[key] = entry
            fw = field(scroll.content, t(i18n_key), entry)
            scroll.add_widget(fw)

            # Required indicator on full_name
            if key == "full_name":
                label_item = fw.layout().itemAt(0)
                if label_item and label_item.widget():
                    add_required_indicator(label_item.widget())

            # Error label (hidden by default)
            err_lbl = QLabel()
            err_lbl.setProperty("role", "field-error")
            err_lbl.setVisible(False)
            err_lbl.setWordWrap(True)
            fw.layout().addWidget(err_lbl)
            self._error_labels[key] = err_lbl

            # Clear error on edit
            if hasattr(entry, "textChanged"):
                entry.textChanged.connect(lambda _k=key: self._clear_field_error(_k))

        scroll.add_stretch()

        btn_bar = QFrame()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(SP["5"], 0, SP["5"], SP["4"])
        btn_layout.addStretch()
        btn_layout.addWidget(Btn(
            btn_bar, text=t("client.save_button"),
            command=self._save, variant="success",
        ))
        layout.addWidget(btn_bar)

    def _clear_field_error(self, key: str) -> None:
        err_lbl = self._error_labels.get(key)
        if err_lbl and err_lbl.isVisible():
            err_lbl.setVisible(False)
            entry = self._entries.get(key)
            if entry and hasattr(entry, "setProperty"):
                entry.setProperty("validation", "")
                entry.style().unpolish(entry)
                entry.style().polish(entry)

    def _show_field_error(self, key: str, message: str) -> None:
        err_lbl = self._error_labels.get(key)
        if err_lbl:
            err_lbl.setText(message)
            err_lbl.setVisible(True)
        entry = self._entries.get(key)
        if entry and hasattr(entry, "setProperty"):
            entry.setProperty("validation", "error")
            entry.style().unpolish(entry)
            entry.style().polish(entry)

    def _save(self) -> None:
        has_errors = False

        # Validate full_name (required)
        name_entry = self._entries["full_name"]
        name_val = name_entry.currentText() if isinstance(name_entry, StyledComboBox) else name_entry.text()
        name_val = name_val.strip()
        if not name_val:
            self._show_field_error("full_name", "This field is required")
            has_errors = True
        else:
            self._clear_field_error("full_name")

        # Validate email format
        email_entry = self._entries.get("email")
        if email_entry:
            email_val = email_entry.text().strip() if hasattr(email_entry, "text") else ""
            if email_val and ("@" not in email_val or "." not in email_val.split("@")[-1]):
                self._show_field_error("email", "Enter a valid email address")
                has_errors = True
            else:
                self._clear_field_error("email")

        # Validate phone length
        phone_entry = self._entries.get("phone")
        if phone_entry:
            phone_val = phone_entry.text().strip() if hasattr(phone_entry, "text") else ""
            if phone_val and len(phone_val) < 7:
                self._show_field_error("phone", "Enter a valid phone number")
                has_errors = True
            else:
                self._clear_field_error("phone")

        if has_errors:
            return

        data: dict[str, str] = {}
        for k, v in self._entries.items():
            val = v.currentText().strip() if isinstance(v, StyledComboBox) else v.text().strip()
            data[k] = val

        if self._editing and self.contact_data is not None:
            self.service.update_contact(self.contact_data["id"], **data)
        else:
            self.service.add_contact(self.client_id, **data)

        if self.on_save is not None:
            self.on_save()
        self.accept()
