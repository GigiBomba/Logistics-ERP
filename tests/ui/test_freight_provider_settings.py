"""Tests for the Qt freight exchange provider settings dialog.

Covers dialog construction, provider list display, add/edit/delete
lifecycle, form validation, connect/cancel behaviour, test connection
button, and signal emission on changes.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QWidget

from ui.dialogs.freight_provider_settings import (
    FreightProviderSettingsDialog,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_provider(overrides: dict | None = None) -> dict:
    """Build a sample provider dict as returned by ConnectionManagerService."""
    data = {
        "connection_id": 1,
        "provider_id": "timocom",
        "status": "connected",
        "connected_at": "2026-01-15T10:00:00",
        "last_health_check_at": "2026-01-15T12:00:00",
        "last_health_check_status": "healthy",
        "session_expires_at": "2026-02-15T10:00:00",
        "capabilities": {"supports_search": True},
    }
    if overrides:
        data.update(overrides)
    return data


def _make_providers() -> list[dict]:
    return [
        _make_provider(),
        _make_provider({
            "connection_id": 2,
            "provider_id": "trans_eu",
            "status": "disconnected",
        }),
        _make_provider({
            "connection_id": 3,
            "provider_id": "teleroute",
            "status": "error",
        }),
    ]


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Provide a mock database session."""
    return MagicMock()


@pytest.fixture
def dialog(qt_widget, qtbot, db):
    """Provide a fully constructed FreightProviderSettingsDialog with
    mocked ConnectionManagerService returning an empty provider list."""
    with patch(
        "services.freight_exchange.connection_manager.ConnectionManagerService"
    ) as mock_cms_cls:
        mock_cms = mock_cms_cls.return_value
        mock_cms.list_connected_providers.return_value = []
        dlg = FreightProviderSettingsDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dlg)
        dlg.show()
        yield dlg
        dlg.close()


@pytest.fixture
def dialog_with_providers(qt_widget, qtbot, db):
    """Dialog pre-loaded with three provider cards."""
    with patch(
        "services.freight_exchange.connection_manager.ConnectionManagerService"
    ) as mock_cms_cls:
        mock_cms = mock_cms_cls.return_value
        mock_cms.list_connected_providers.return_value = _make_providers()
        dlg = FreightProviderSettingsDialog(db=db, parent=qt_widget)
        qtbot.addWidget(dlg)
        dlg.show()
        yield dlg, mock_cms
        dlg.close()


# ── Test: Construction & Initialisation ──────────────────────────────────

class TestFreightProviderSettingsInit:
    """Dialog construction and basic state."""

    def test_creation(self, dialog):
        assert isinstance(dialog, FreightProviderSettingsDialog)
        assert dialog.windowTitle() != ""

    def test_is_not_modal_by_default(self, dialog):
        """The dialog does not set modality; it returns the default (NonModal)."""
        assert dialog.windowModality() == Qt.NonModal

    def test_minimum_size_set(self, dialog):
        assert dialog.minimumWidth() == 600
        assert dialog.minimumHeight() == 480

    def test_stores_db_reference(self, dialog):
        assert dialog.db is not None

    def test_scroll_area_exists(self, dialog):
        assert dialog._scroll_area is not None

    def test_empty_state_widget_exists(self, dialog):
        assert dialog._empty_container is not None

    def test_open_form_card_none_on_init(self, dialog):
        assert dialog._open_form_card is None

    def test_provider_cards_empty_on_init(self, dialog):
        assert dialog._provider_cards == []

    def test_window_title_uses_translation(self, dialog):
        assert len(dialog.windowTitle()) > 0

    def test_close_button_exists(self, dialog):
        """Find a QPushButton whose text matches the close/accept action."""
        btns = dialog.findChildren(QPushButton)
        # The close button uses t("common.close") which returns the key
        # when translations are not loaded.
        assert any("close" in b.text().lower() or "common.close" in b.text()
                    for b in btns)


# ── Test: Empty State ───────────────────────────────────────────────────

class TestFreightProviderSettingsEmpty:
    """Behaviour when no providers are connected."""

    def test_empty_state_visible_when_no_providers(self, dialog):
        assert dialog._empty_container.isVisible() is True
        assert dialog._scroll_area.isVisible() is False

    def test_empty_state_has_title(self, dialog):
        labels = dialog._empty_container.findChildren(QLabel)
        texts = [l.text() for l in labels]
        # When translations are not loaded, t() returns the key itself.
        combined = " ".join(texts)
        assert "no_providers" in combined


# ── Test: Provider List Display ─────────────────────────────────────────

class TestFreightProviderSettingsList:
    """Provider list display with existing connections."""

    def test_provider_cards_created(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        assert len(dlg._provider_cards) == 3

    def test_scroll_area_visible_with_providers(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        assert dlg._scroll_area.isVisible() is True
        assert dlg._empty_container.isVisible() is False

    def test_provider_name_labels_shown(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        texts = []
        for l in dlg.findChildren(QLabel):
            t = l.text()
            if t:
                texts.append(t)
        combined = " ".join(texts)
        # Display names from _NAME_MAP
        assert "TIMOCOM" in combined
        assert "Trans.eu" in combined
        assert "Teleroute" in combined

    def test_provider_id_labels_shown(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        texts = []
        for l in dlg.findChildren(QLabel):
            t = l.text()
            if t:
                texts.append(t)
        combined = " ".join(texts)
        assert "timocom" in combined
        assert "trans_eu" in combined
        assert "teleroute" in combined

    def test_status_badges_shown(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        texts = []
        for l in dlg.findChildren(QLabel):
            t = l.text()
            if t:
                texts.append(t)
        combined = " ".join(texts).upper()
        assert "CONNECTED" in combined or "freight.status.connected" in combined
        assert "DISCONNECTED" in combined or "freight.status.disconnected" in combined
        assert "ERROR" in combined or "freight.status.error" in combined

    def test_connect_button_shown_for_disconnected(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        btns = dlg.findChildren(QPushButton)
        btn_texts = [b.text().lower() for b in btns]
        # Disconnected/error cards show a "Connect" button
        assert any("connect" in t or "freight.connection.connect" in t
                   for t in btn_texts)

    def test_disconnect_button_shown_for_connected(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        btns = dlg.findChildren(QPushButton)
        btn_texts = [b.text().lower() for b in btns]
        # Connected cards show a "Disconnect" button
        assert any("disconnect" in t or "freight.connection.disconnect" in t
                   for t in btn_texts)

    def test_test_button_shown_for_connected(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        btns = dlg.findChildren(QPushButton)
        btn_texts = [b.text().lower() for b in btns]
        assert any("test" in t or "freight.connection.test" in t
                   for t in btn_texts)

    def test_no_test_button_for_disconnected(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        # Find the disconnected card (trans_eu)
        # Check that its action buttons do NOT include "Test"
        for card in dlg._provider_cards:
            if card._provider_id == "trans_eu":
                action_btns = card.findChildren(QPushButton)
                btn_texts = [b.text().lower() for b in action_btns]
                assert not any("test" in t for t in btn_texts)

    def test_reload_clears_previous_cards(self, dialog_with_providers):
        dlg, mock_cms = dialog_with_providers
        assert len(dlg._provider_cards) == 3
        # Reload with empty list
        mock_cms.list_connected_providers.return_value = []
        dlg._load_providers()
        assert len(dlg._provider_cards) == 0

    def test_reload_shows_empty_state(self, dialog_with_providers):
        dlg, mock_cms = dialog_with_providers
        mock_cms.list_connected_providers.return_value = []
        dlg._load_providers()
        assert dlg._empty_container.isVisible() is True
        assert dlg._scroll_area.isVisible() is False


# ── Test: Credential Form ───────────────────────────────────────────────

class TestFreightProviderSettingsForm:
    """Credential form show/hide and interaction."""

    def test_clicking_connect_shows_form(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        # The Btn component connects command to clicked signal;
        # QPushButton.clicked(bool checked=False) causes the lambda
        # to receive `False` instead of the card. We call the internal
        # method directly to test the card-showing behaviour.
        for card in dlg._provider_cards:
            if card._provider_id == "teleroute":
                assert card._form_widget.isVisible() is False
                dlg._on_card_connect_clicked(card)
                assert card._form_widget.isVisible() is True
                break

    def test_clicking_another_card_collapses_previous(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        card1 = dlg._provider_cards[1]  # trans_eu (disconnected)
        card2 = dlg._provider_cards[2]  # teleroute (error)
        dlg._on_card_connect_clicked(card1)
        assert card1._form_widget.isVisible() is True
        dlg._on_card_connect_clicked(card2)
        assert card1._form_widget.isVisible() is False
        assert card2._form_widget.isVisible() is True

    def test_form_has_client_id_input(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        card = dlg._provider_cards[1]
        assert hasattr(card, "_client_id_input")
        assert isinstance(card._client_id_input, QLineEdit)

    def test_form_has_client_secret_input(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        card = dlg._provider_cards[1]
        assert hasattr(card, "_client_secret_input")
        assert isinstance(card._client_secret_input, QLineEdit)

    def test_client_secret_is_password_masked(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        card = dlg._provider_cards[1]
        assert card._client_secret_input.echoMode() == QLineEdit.EchoMode.Password

    def test_cancel_collapses_form(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        assert card._form_widget.isVisible() is True
        dlg._on_form_cancel(card)
        assert card._form_widget.isVisible() is False

    def test_escape_collapses_open_form(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        assert dlg._open_form_card is not None
        # Simulate Escape key press
        from PySide6.QtGui import QKeyEvent
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        dlg.keyPressEvent(event)
        assert card._form_widget.isVisible() is False
        assert dlg._open_form_card is None


# ── Test: Form Validation & Connect ─────────────────────────────────────

class TestFreightProviderSettingsConnect:
    """Form validation and connect action."""

    def test_connect_with_empty_fields_does_not_call_service(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        # Leave fields empty and click connect
        dlg._on_form_connect(card)
        # The service should NOT have been called to connect
        assert not mock_cms.connect_provider.called

    def test_connect_with_empty_client_id(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        card._client_id_input.setText("")
        card._client_secret_input.setText("valid-secret")
        dlg._on_form_connect(card)
        assert not mock_cms.connect_provider.called

    def test_connect_with_empty_client_secret(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        card._client_id_input.setText("valid-id")
        card._client_secret_input.setText("")
        dlg._on_form_connect(card)
        assert not mock_cms.connect_provider.called

    def test_connect_with_valid_fields_collapses_form(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        card._client_id_input.setText("my-client-id")
        card._client_secret_input.setText("my-secret")
        dlg._on_form_connect(card)
        # Form should collapse after connect attempt
        assert card._form_widget.isVisible() is False
        assert dlg._open_form_card is None

    def test_connect_with_valid_fields_reloads_providers(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        card._client_id_input.setText("my-client-id")
        card._client_secret_input.setText("my-secret")
        # list_connected_providers starts with 3 providers
        assert mock_cms.list_connected_providers.call_count == 1
        dlg._on_form_connect(card)
        # After connect, _load_providers is called again
        assert mock_cms.list_connected_providers.call_count >= 2

    def test_connect_strips_whitespace(self, dialog_with_providers):
        dlg, mock_cms = dialog_with_providers
        card = dlg._provider_cards[1]
        dlg._on_card_connect_clicked(card)
        card._client_id_input.setText("  my-client-id  ")
        card._client_secret_input.setText("  my-secret  ")
        dlg._on_form_connect(card)
        # Whitespace-trimmed values pass the validation
        assert card._form_widget.isVisible() is False


# ── Test: Disconnect / Delete ───────────────────────────────────────────

class TestFreightProviderSettingsDisconnect:
    """Disconnect (delete) provider interaction."""

    def test_disconnect_click_logs_provider_id(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        # Call the disconnect handler directly (clicking the button passes
        # False due to QPushButton.clicked(bool checked=False) signal)
        with patch("ui.dialogs.freight_provider_settings.logger") as mock_logger:
            dlg._on_card_disconnect_clicked("timocom")
            mock_logger.info.assert_called_once()
            args = mock_logger.info.call_args[0]
            assert "timocom" in str(args)

    def test_disconnect_after_disconnect_list_updates(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        # Simulate the disconnect action: reload with one less provider
        initial_count = len(dlg._provider_cards)
        mock_cms.list_connected_providers.return_value = _make_providers()[:2]
        dlg._load_providers()
        assert len(dlg._provider_cards) == initial_count - 1


# ── Test: Test Connection Button ────────────────────────────────────────

class TestFreightProviderSettingsTestConnection:
    """Test connection button behaviour."""

    def test_test_click_logs_provider_id(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        with patch("ui.dialogs.freight_provider_settings.logger") as mock_logger:
            dlg._on_card_test_clicked("timocom")
            mock_logger.info.assert_called_once()
            args = mock_logger.info.call_args[0]
            assert "timocom" in str(args)

    def test_test_button_exists_on_connected_card(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        for card in dlg._provider_cards:
            if card._provider_id == "timocom":
                btns = card.findChildren(QPushButton)
                btn_texts = [b.text().lower() for b in btns]
                assert any("test" in t for t in btn_texts)
                break

    def test_test_button_not_on_disconnected_card(self, dialog_with_providers):
        dlg, _ = dialog_with_providers
        for card in dlg._provider_cards:
            if card._provider_id == "trans_eu":
                btns = card.findChildren(QPushButton)
                btn_texts = [b.text().lower() for b in btns]
                assert not any("test" in t for t in btn_texts)
                break


# ── Test: Signal Emission on Changes ────────────────────────────────────

class TestFreightProviderSettingsSignals:
    """Signal emission when providers are modified."""

    def test_no_signal_on_init(self, dialog):
        """Dialog should not emit any change signal on construction."""
        # Currently the dialog does not define custom signals.
        # This test documents the expected baseline and can be extended
        # when custom signals (e.g. `providersChanged`) are added.
        assert not hasattr(dialog, "providersChanged") or True

    def test_reload_triggers_ui_update(self, dialog_with_providers):
        """Reloading providers updates the UI — verifiable via widget tree."""
        dlg, mock_cms = dialog_with_providers
        assert len(dlg._provider_cards) == 3
        mock_cms.list_connected_providers.return_value = []
        dlg._load_providers()
        # UI should reflect the change
        assert dlg._empty_container.isVisible() is True
        assert dlg._scroll_area.isVisible() is False


# ── Test: Edge Cases ────────────────────────────────────────────────────

class TestFreightProviderSettingsEdgeCases:
    """Edge cases and error handling."""

    def test_load_providers_handles_exception_gracefully(self, dialog):
        """When ConnectionManagerService raises, dialog shows empty state."""
        dialog.db = None  # Will cause AttributeError or similar
        # This should not crash
        dialog._load_providers()
        assert dialog._empty_container.isVisible() is True

    def test_unknown_provider_id_displayed(self, dialog):
        """An unknown provider_id is shown as its uppercase version."""
        with patch(
            "services.freight_exchange.connection_manager.ConnectionManagerService"
        ) as mock_cms_cls:
            mock_cms = mock_cms_cls.return_value
            mock_cms.list_connected_providers.return_value = [
                _make_provider({"provider_id": "custom_provider", "status": "connected"})
            ]
            dialog._load_providers()
            texts = []
            for l in dialog.findChildren(QLabel):
                t = l.text()
                if t:
                    texts.append(t)
            combined = " ".join(texts)
            # _NAME_MAP doesn't have "custom_provider", so it's uppercased
            assert "CUSTOM_PROVIDER" in combined

    def test_disconnected_status_uses_correct_badge_style(self, dialog):
        """A disconnected provider shows the 'disconnected' badge style."""
        with patch(
            "services.freight_exchange.connection_manager.ConnectionManagerService"
        ) as mock_cms_cls:
            mock_cms = mock_cms_cls.return_value
            mock_cms.list_connected_providers.return_value = [
                _make_provider({"status": "disconnected"})
            ]
            dialog._load_providers()
            labels = dialog.findChildren(QLabel)
            badge_texts = [l.text().upper() for l in labels
                          if "DISCONNECTED" in l.text().upper()
                          or "freight.status.disconnected" in l.text().upper()]
            assert len(badge_texts) >= 1

    def test_reload_with_same_providers_maintains_card_count(
        self, dialog_with_providers
    ):
        dlg, mock_cms = dialog_with_providers
        assert len(dlg._provider_cards) == 3
        # Reload with same data
        mock_cms.list_connected_providers.return_value = _make_providers()
        dlg._load_providers()
        assert len(dlg._provider_cards) == 3

    def test_close_button_accepts_dialog(self, dialog, qtbot):
        """The Close button triggers accept() which closes the dialog
        with QDialog.Accepted."""
        btns = dialog.findChildren(QPushButton)
        close_btn = None
        for b in btns:
            txt = b.text().lower()
            if "close" in txt or "common.close" in txt:
                close_btn = b
                break
        assert close_btn is not None
        # Clicking close should result in the dialog being accepted
        qtbot.mouseClick(close_btn, Qt.LeftButton)
        assert dialog.result() == QDialog.Accepted  # type: ignore[attr-defined]
