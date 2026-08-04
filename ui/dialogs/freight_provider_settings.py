"""Freight Exchange provider settings dialog.

Lets the dispatcher connect, disconnect, and test connections to
freight exchange providers (TIMOCOM, Trans.eu, etc.).
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.components import (
    Btn,
    Card,
    Divider,
    EmptyState,
    FieldLabel,
    Label,
    PageTitle,
)
from ui.form_utils import add_required_indicator
from ui.design_tokens import (
    COLOR_BG_OVERLAY,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_NEUTRAL_SUBTLE,
    COLOR_NEUTRAL_TEXT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_WEIGHT_SEMIBOLD,
    INPUT_HEIGHT,
    RADIUS_LG,
    RADIUS_PILL,
    SPACE_1,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
)

logger = logging.getLogger(__name__)

_NAME_MAP = {
    "timocom": "TIMOCOM",
    "trans_eu": "Trans.eu",
    "teleroute": "Teleroute",
}

_STATUS_BADGE_STYLES = {
    "connected": {
        "bg": COLOR_SUCCESS_SUBTLE,
        "text": COLOR_SUCCESS_TEXT,
        "border": f"{COLOR_SUCCESS_TEXT}4D",
    },
    "degraded": {
        "bg": COLOR_WARNING_SUBTLE,
        "text": COLOR_WARNING_TEXT,
        "border": f"{COLOR_WARNING_TEXT}4D",
    },
    "disconnected": {
        "bg": COLOR_NEUTRAL_SUBTLE,
        "text": COLOR_NEUTRAL_TEXT,
        "border": f"{COLOR_NEUTRAL_TEXT}4D",
    },
    "error": {
        "bg": COLOR_ERROR_SUBTLE,
        "text": COLOR_ERROR_TEXT,
        "border": f"{COLOR_ERROR_TEXT}4D",
    },
}


class FreightProviderSettingsDialog(QDialog):
    """Modal dialog for managing freight exchange provider connections."""

    def __init__(self, db, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(t("freight.provider_settings.title"))
        self.setMinimumSize(600, 480)

        self._open_form_card: Optional[QWidget] = None

        self._build_ui()
        self._provider_cards: list = []
        self._load_providers()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_5, SPACE_5, SPACE_5, SPACE_5)
        layout.setSpacing(SPACE_4)

        # ── Header ──
        layout.addWidget(PageTitle(self, t("freight.provider_settings.title")))
        layout.addWidget(
            Label(self, t("freight.provider_settings.subtitle"), role="muted")
        )
        layout.addWidget(Divider(self))
        layout.addSpacing(SPACE_3)

        # ── Provider list (scroll area) ──
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(SPACE_3)

        self._scroll_area.setWidget(self._scroll_content)
        layout.addWidget(self._scroll_area, 1)

        # ── Empty state (hidden by default) ──
        self._empty_container = QWidget()
        empty_layout = QVBoxLayout(self._empty_container)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.addStretch()

        add_first_btn = Btn(
            self._empty_container,
            text=t("freight.connection.add_first"),
            variant="primary",
            icon_name="mdi6.plus",
        )
        self._empty_state = EmptyState(
            self._empty_container,
            icon_name="mdi6.cloud-off-outline",
            title=t("freight.connection.no_providers"),
            subtitle=t("freight.connection.no_providers_hint"),
            cta_button=add_first_btn,
        )
        empty_layout.addWidget(self._empty_state, 0, Qt.AlignCenter)
        empty_layout.addStretch()
        self._empty_container.setVisible(False)
        layout.addWidget(self._empty_container, 1)

        # ── Bottom bar ──
        layout.addWidget(Divider(self))
        layout.addSpacing(SPACE_3)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        bottom_row.addWidget(
            Btn(
                self,
                text=t("common.close"),
                variant="secondary",
                size="md",
                command=self.accept,
            )
        )
        layout.addLayout(bottom_row)

    # ── Data loading ─────────────────────────────────────────────────

    def _load_providers(self):
        """Load providers from the database and build cards."""
        self._open_form_card = None

        # Clean up old cards
        for card in self._provider_cards:
            card.deleteLater()
        self._provider_cards.clear()

        self._clear_provider_cards()

        try:
            from services.freight_exchange.connection_manager import (
                ConnectionManagerService,
            )

            conn_mgr = ConnectionManagerService(self.db)
            # Get company_id from DB context or session
            company_id = getattr(self.db, 'user_company_id', None) or 0
            providers = conn_mgr.list_connected_providers(company_id=company_id)
        except Exception as e:
            logger.warning("Could not load providers: %s", e)
            providers = []

        if providers:
            self._scroll_area.setVisible(True)
            self._empty_container.setVisible(False)
            for p in providers:
                card = self._build_provider_card(p)
                self._scroll_layout.addWidget(card)
            self._scroll_layout.addStretch()
        else:
            self._scroll_area.setVisible(False)
            self._empty_container.setVisible(True)

    def _clear_provider_cards(self):
        """Remove all widgets from the scroll layout."""
        while True:
            item = self._scroll_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    # ── Provider card builder ────────────────────────────────────────

    def _build_provider_card(self, provider: dict) -> QWidget:
        pid = provider.get("provider_id", "unknown")
        status = provider.get("status", "disconnected")
        display_name = _NAME_MAP.get(pid, pid.upper())

        card = Card(parent=None, padding=True)
        self._provider_cards.append(card)
        card_layout = card.layout()

        # ── Main row ─────────────────────────────────────────────────
        main_row = QHBoxLayout()
        main_row.setSpacing(SPACE_3)

        # Left: identity
        left_col = QVBoxLayout()
        left_col.setSpacing(SPACE_1)

        name_lbl = Label(None, display_name)
        name_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_MD}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; "
            f"color: {COLOR_TEXT_PRIMARY};"
        )
        left_col.addWidget(name_lbl)

        pid_lbl = Label(None, pid, role="muted")
        left_col.addWidget(pid_lbl)

        main_row.addLayout(left_col)
        main_row.addStretch()

        # Middle: status badge
        badge_style = _STATUS_BADGE_STYLES.get(
            status, _STATUS_BADGE_STYLES["disconnected"]
        )
        badge = QLabel(t(f"freight.status.{status}").upper())
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {badge_style['bg']}; "
            f"color: {badge_style['text']}; "
            f"border-radius: {RADIUS_PILL}px; "
            f"border: 1px solid {badge_style['border']}; "
            f"padding: 2px 8px; "
            f"font-size: {FONT_SIZE_SM}px; "
            f"font-weight: {FONT_WEIGHT_SEMIBOLD}; "
            f"letter-spacing: 0.04em;"
        )
        badge.setFixedHeight(20)
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        main_row.addWidget(badge)

        # Right: actions
        right_col = QHBoxLayout()
        right_col.setSpacing(SPACE_2)

        if status in ("disconnected", "error"):
            btn_connect = Btn(
                None,
                text=t("freight.connection.connect"),
                variant="primary",
                size="sm",
                command=lambda c=card: self._on_card_connect_clicked(c),
            )
            right_col.addWidget(btn_connect)
        elif status in ("connected", "degraded"):
            btn_disconnect = Btn(
                None,
                text=t("freight.connection.disconnect"),
                variant="ghost",
                size="sm",
                command=lambda p=pid: self._on_card_disconnect_clicked(p),
            )
            btn_test = Btn(
                None,
                text=t("freight.connection.test"),
                variant="secondary",
                size="sm",
                command=lambda p=pid: self._on_card_test_clicked(p),
            )
            right_col.addWidget(btn_disconnect)
            right_col.addWidget(btn_test)

        main_row.addLayout(right_col)
        card_layout.addLayout(main_row)

        # ── Credential form (hidden initially) ──────────────────────
        form_widget = QWidget()
        form_widget.setObjectName("credentialForm")
        form_widget.setStyleSheet(
            "#credentialForm {"
            f"  background: {COLOR_BG_OVERLAY};"
            f"  border-top: 1px solid {COLOR_BORDER_SUBTLE};"
            f"  border-bottom-left-radius: {RADIUS_LG}px;"
            f"  border-bottom-right-radius: {RADIUS_LG}px;"
            "}"
        )
        form_widget.setVisible(False)

        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        form_layout.setSpacing(SPACE_3)

        form_layout.addWidget(Divider(form_widget))

        form_fields = QFormLayout()
        form_fields.setSpacing(SPACE_3)

        # ── Client ID ──
        client_id_input = QLineEdit()
        client_id_input.setPlaceholderText(
            t("freight.connection.client_id_placeholder")
        )
        client_id_input.setFixedHeight(INPUT_HEIGHT)

        client_id_label = FieldLabel(form_widget, t("freight.connection.client_id"))
        add_required_indicator(client_id_label)

        client_id_container = QWidget()
        client_id_container_layout = QVBoxLayout(client_id_container)
        client_id_container_layout.setContentsMargins(0, 0, 0, 0)
        client_id_container_layout.setSpacing(0)
        client_id_container_layout.addWidget(client_id_input)
        client_id_error = QLabel()
        client_id_error.setProperty("role", "field-error")
        client_id_error.setVisible(False)
        client_id_error.setWordWrap(True)
        client_id_container_layout.addWidget(client_id_error)

        form_fields.addRow(client_id_label, client_id_container)

        # ── Client Secret ──
        client_secret_input = QLineEdit()
        client_secret_input.setPlaceholderText(
            t("freight.connection.client_secret_placeholder")
        )
        client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        client_secret_input.setFixedHeight(INPUT_HEIGHT)

        client_secret_label = FieldLabel(form_widget, t("freight.connection.client_secret"))
        add_required_indicator(client_secret_label)

        client_secret_container = QWidget()
        client_secret_container_layout = QVBoxLayout(client_secret_container)
        client_secret_container_layout.setContentsMargins(0, 0, 0, 0)
        client_secret_container_layout.setSpacing(0)
        client_secret_container_layout.addWidget(client_secret_input)
        client_secret_error = QLabel()
        client_secret_error.setProperty("role", "field-error")
        client_secret_error.setVisible(False)
        client_secret_error.setWordWrap(True)
        client_secret_container_layout.addWidget(client_secret_error)

        form_fields.addRow(client_secret_label, client_secret_container)

        form_layout.addLayout(form_fields)

        # Button row
        form_btn_row = QHBoxLayout()
        form_btn_row.addStretch()

        cancel_btn = Btn(
            form_widget,
            text=t("common.cancel"),
            variant="ghost",
            size="sm",
            command=lambda c=card: self._on_form_cancel(c),
        )
        connect_btn = Btn(
            form_widget,
            text=t("freight.connection.connect"),
            variant="primary",
            size="sm",
            command=lambda c=card: self._on_form_connect(c),
        )

        form_btn_row.addWidget(cancel_btn)
        form_btn_row.addWidget(connect_btn)
        form_layout.addLayout(form_btn_row)

        # Tab order: Client ID -> Client Secret -> Connect -> Cancel
        QWidget.setTabOrder(client_id_input, client_secret_input)
        QWidget.setTabOrder(client_secret_input, connect_btn)
        QWidget.setTabOrder(connect_btn, cancel_btn)

        connect_btn.setDefault(True)

        card_layout.addWidget(form_widget)

        # Store references for later use
        card._form_widget = form_widget
        card._provider_id = pid
        card._client_id_input = client_id_input
        card._client_id_error = client_id_error
        card._client_secret_input = client_secret_input
        card._client_secret_error = client_secret_error

        return card

    # ── Action handlers ──────────────────────────────────────────────

    def _on_card_connect_clicked(self, card):
        """Show the credential form for the given card."""
        if self._open_form_card is not None and self._open_form_card != card:
            self._collapse_form(self._open_form_card)
        card._form_widget.setVisible(True)
        self._open_form_card = card

    def _on_card_disconnect_clicked(self, provider_id):
        """Handle disconnect action."""
        logger.info("Disconnecting provider: %s", provider_id)

    def _on_card_test_clicked(self, provider_id):
        """Handle test connection action."""
        logger.info("Testing provider: %s", provider_id)

    def _on_form_cancel(self, card):
        """Collapse the credential form."""
        self._collapse_form(card)

    def _collapse_form(self, card):
        """Hide the credential form and clear state."""
        card._form_widget.setVisible(False)
        if self._open_form_card == card:
            self._open_form_card = None

    def _on_form_connect(self, card):
        """Attempt to connect with the entered credentials."""
        client_id = card._client_id_input.text().strip()
        client_secret = card._client_secret_input.text().strip()
        pid = card._provider_id

        # ── Validate ──
        has_errors = False

        if not client_id:
            card._client_id_input.setProperty("validation", "error")
            card._client_id_input.style().unpolish(card._client_id_input)
            card._client_id_input.style().polish(card._client_id_input)
            card._client_id_error.setText(t("common.field_required", default="This field is required"))
            card._client_id_error.setVisible(True)
            has_errors = True
        else:
            card._client_id_input.setProperty("validation", "")
            card._client_id_error.setVisible(False)

        if not client_secret:
            card._client_secret_input.setProperty("validation", "error")
            card._client_secret_input.style().unpolish(card._client_secret_input)
            card._client_secret_input.style().polish(card._client_secret_input)
            card._client_secret_error.setText(t("common.field_required", default="This field is required"))
            card._client_secret_error.setVisible(True)
            has_errors = True
        else:
            card._client_secret_input.setProperty("validation", "")
            card._client_secret_error.setVisible(False)

        if has_errors:
            return

        logger.info("Connecting provider %s with client_id=%s", pid, client_id)

        # Collapse form and reload to reflect updated state
        card._form_widget.setVisible(False)
        self._open_form_card = None
        self._load_providers()

    # ── Event handling ──────────────────────────────────────────────

    def keyPressEvent(self, event):
        """Escape key collapses the open credential form (or dismisses dialog)."""
        if event.key() == Qt.Key_Escape and self._open_form_card is not None:
            self._collapse_form(self._open_form_card)
            event.accept()
        else:
            super().keyPressEvent(event)
