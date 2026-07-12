"""Base mixin providing common document editor functionality.

Shared across Invoice, Receipt, and Proforma editors.  Provides patterns for:

- Company config loading and event-bus refresh
- i18n lifecycle callbacks
- Common UI helpers (card creation, canvas labels, signal-safe text setting)
- Draft save/load dialog helpers
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from services.invoicing.config_manager import load_company_config
from services.operations.event_bus import SETTINGS_UPDATED
from ui.components import Btn, Card
from ui.theme import COLORS

_logger = logging.getLogger(__name__)


class BaseDocumentEditor:
    """Mixin that provides shared document-editor helpers.

    Intended to be used alongside ``BaseView`` (or any ``QWidget`` subclass).
    Your editor should inherit from this *before* any other mixin that might
    also define the same methods::

        class QtMyEditor(BaseView, BaseDocumentEditor, SomeOtherMixin):
            ...
    """

    # ── Company config ──────────────────────────────────────────────────────

    def _load_company_config(self) -> None:
        """Load company config and apply to editor state variables.

        Override ``_apply_company_config()`` to map the raw config dict
        to your editor-specific attributes.  Editors that need more control
        may override this method entirely.
        """
        conf = load_company_config()
        self._apply_company_config(conf)
        if hasattr(self, "_update_canvas_labels"):
            self._update_canvas_labels()

    def _apply_company_config(self, conf: dict) -> None:
        """Map raw config keys → editor state attributes.

        Default implementation handles the common invoice/proforma fields.
        Override when your editor stores data under different attribute names
        or needs extra processing (e.g. formatting CUI/phone for display).
        """
        self._company_name = conf.get("company_name", "")
        self._company_cui = conf.get("cui", "")
        self._company_reg = conf.get("reg_number", "")
        self._company_address = conf.get("address", "")
        self._company_phone = conf.get("phone", "")
        self._company_email = conf.get("email", "")

        # Branding paths
        logo = conf.get("logo_path", "")
        if logo:
            self._logo_path = logo
        sig = conf.get("signature_path", "")
        if sig:
            self._signature_path = sig
        stamp = conf.get("stamp_path", "")
        if stamp:
            self._stamp_path = stamp

        # Company color
        color = conf.get("company_color", COLORS["accent"])
        if color:
            self._company_color = color

    def _on_settings_updated(self, ev: Any) -> None:
        """React to ``SETTINGS_UPDATED`` events — refresh company config."""
        data = ev.get("data", {}) if isinstance(ev, dict) else {}
        if data.get("key") == "company_config":
            QTimer.singleShot(0, self._load_company_config)

    # ── Event-bus subscription helper ───────────────────────────────────────

    def _subscribe_company_config_updates(self) -> None:
        """Subscribe to ``SETTINGS_UPDATED`` for automatic config refresh.

        Call this once from ``__init__`` after the UI is built::

            self._subscribe_company_config_updates()
        """
        self._subscribe(SETTINGS_UPDATED, self._on_settings_updated)

    # ── i18n ────────────────────────────────────────────────────────────────

    def _on_language_changed(self, _lang: str) -> None:
        """Refresh UI text when the application language changes."""
        self._retranslate_ui()

    def _setup_i18n(self) -> None:
        """Register the language-change callback.

        Equivalent to the common pattern::

            self._language_callback = self._on_language_changed
            self._register_i18n(self._language_callback)

        Call once from ``__init__``.
        """
        self._language_callback = self._on_language_changed
        self._register_i18n(self._language_callback)

    # ── Common UI helpers ───────────────────────────────────────────────────

    def _make_card(self) -> QFrame:
        """Return a ``Card`` frame suitable for a form section."""
        return Card()

    def _make_canvas_label(
        self, parent: QWidget, text: str, bold: bool = False
    ) -> QLabel:
        """Return a ``QLabel`` styled for use in the preview/canvas area."""
        lbl = QLabel(text, parent)
        lbl.setProperty("fontRole", "body-bold" if bold else "body")
        return lbl

    def _set_text(self, edit: QWidget, text: str) -> None:
        """Update a ``QLineEdit`` without re-entering ``textChanged``."""
        if edit is None:
            return
        edit.blockSignals(True)
        edit.setText(text)
        edit.blockSignals(False)

    def _set_plain_text(self, edit: QWidget, text: str) -> None:
        """Update a ``QPlainTextEdit`` without re-entering its signal."""
        if edit is None:
            return
        edit.blockSignals(True)
        edit.setPlainText(text)
        edit.blockSignals(False)

    # ── Export JSON helper ──────────────────────────────────────────────────

    def _export_as_json(
        self,
        collect_fn: Callable[[], dict],
        prefix: str = "document",
        title_key: str = "",
        default_name: str = "",
    ) -> None:
        """Export editor data as a JSON file.

        Parameters
        ----------
        collect_fn:
            Function that returns the data dict to export.
        prefix:
            Fallback filename prefix (used when ``default_name`` is empty).
        title_key:
            Translation key for the dialog title.  Falls back to the
            translation of ``f"{prefix}.export_json"``.
        default_name:
            Explicit default filename.  Generated from prefix + number if
            omitted.
        """
        from utils.editor_toolkit import export_editor_data

        data = collect_fn()
        fn = default_name or f"{prefix}_{data.get(f'{prefix}_number', 'draft')}.json"
        title = t(title_key) if title_key else t(f"{prefix}_editor.export_json")
        export_editor_data(self, data, title, fn)

    # ── Draft helpers ───────────────────────────────────────────────────────

    def _save_draft_via_service(
        self,
        service: Any,
        collect_fn: Callable[[], dict],
        title_key: str = "",
        saved_key: str = "",
        failed_key: str = "",
    ) -> None:
        """Save a draft through a service object.

        Parameters
        ----------
        service:
            Object with ``save_draft(data, name) -> bool``.
        collect_fn:
            Returns the data dict to persist.
        title_key / saved_key / failed_key:
            Translation keys for the input dialog and messages.
        """
        _t = t(title_key) if title_key else t("common.save_draft")
        name, ok = QInputDialog.getText(self, _t, _t)
        if not ok or not name:
            return

        data = collect_fn()
        if service.save_draft(data, name):
            msg_key = saved_key or f"{title_key}.saved"
            QMessageBox.information(
                self,
                t(msg_key),
                t(msg_key + "_msg", str()).format(name=name),
            )
        else:
            err_key = failed_key or "common.error"
            QMessageBox.warning(self, t(err_key), t("common.draft_save_failed"))

    def _load_draft_via_dialog(
        self,
        service: Any,
        restore_fn: Callable[[dict], None],
        title_key: str = "",
        load_key: str = "",
        no_drafts_key: str = "",
    ) -> None:
        """Show a draft-selection dialog and restore the chosen draft.

        Parameters
        ----------
        service:
            Object with ``list_drafts() -> list[str]`` and
            ``load_draft(name) -> dict | None``.
        restore_fn:
            Called with the loaded draft dict to restore form state.
        title_key / load_key / no_drafts_key:
            Translation keys.  Falls back to sensible defaults.
        """
        drafts = service.list_drafts()
        if not drafts:
            msg_key = no_drafts_key or f"{title_key}.no_drafts"
            QMessageBox.information(self, t(msg_key), t(msg_key))
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(t(title_key) if title_key else t("common.load_draft"))
        dlg.setMinimumSize(300, 400)
        dlg_layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        for name in drafts:
            list_widget.addItem(name)
        dlg_layout.addWidget(list_widget)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        load_btn = Btn(btn_row, t(load_key) if load_key else t("common.load"), variant="primary")
        cancel_btn = Btn(btn_row, t("common.cancel"), variant="ghost")

        def do_load() -> None:
            selected = list_widget.currentItem()
            if selected:
                draft = service.load_draft(selected.text())
                if draft:
                    restore_fn(draft)
            dlg.accept()

        load_btn.clicked.connect(do_load)
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        dlg_layout.addWidget(btn_row)

        dlg.exec_()

    # ── Branding file-browse helper ─────────────────────────────────────────

    def _browse_branding_file(
        self,
        field_name: str,
        title: str = "",
        file_filter: str = "",
    ) -> str | None:
        """Open a file picker and return the selected path.

        Sets ``self._<field_name>_path`` and updates the corresponding
        ``self._<field_name>_entry`` widget if it exists.

        Returns the path, or ``None`` if cancelled.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            title or t("common.select_file"),
            "",
            file_filter or "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*.*)",
        )
        if not path:
            return None

        setattr(self, f"_{field_name}_path", path)
        entry = getattr(self, f"_{field_name}_entry", None)
        if entry is not None:
            entry.setText(path)
        return path
