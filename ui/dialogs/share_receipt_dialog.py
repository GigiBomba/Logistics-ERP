"""Share Receipt dialog — copy file path, save-as, OS open.

A modal dialog that lets the user share a generated receipt PDF via:

* Copying the file path to clipboard
* Saving a copy via QFileDialog
* Opening with the OS default application
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QClipboard, QGuiApplication, QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.design_tokens import (
    BTN_HEIGHT,
    BTN_HEIGHT_SM,
    FADE_MS,
)
from ui.design_tokens import SP as S


class ShareReceiptDialog(QDialog):
    """Modal dialog for sharing a receipt PDF.

    Usage::

        dialog = ShareReceiptDialog(
            parent=self,
            file_path="/path/to/receipt.pdf",
            on_save_as=my_save_callback,
            on_open=my_open_callback,
        )
        dialog.exec()
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        file_path: str = "",
        on_save_as: callable | None = None,
        on_open: callable | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("receipt.share.title", default="Share Receipt"))
        self.setAccessibleName("Share Receipt")
        self.setAccessibleDescription("Dialog for sharing a receipt PDF")
        self.setMinimumSize(460, 300)
        self.setMaximumWidth(520)
        self.setWindowModality(Qt.ApplicationModal)

        self._file_path = file_path
        self._on_save_as_cb = on_save_as
        self._on_open_cb = on_open

        self._build_ui()

        # ── Fade-in effect ─────────────────────────────────────────────
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        # Escape key dismisses (default QDialog behavior)

    def showEvent(self, event: QShowEvent) -> None:
        """Fade in the dialog on show."""
        super().showEvent(event)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        anim.setDuration(FADE_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(S["6"], S["6"], S["6"], S["6"])
        outer.setSpacing(S["4"])

        # ── Title ─────────────────────────────────────────────────
        title_lbl = QLabel(t("receipt.share.title", default="Share Receipt"))
        title_lbl.setProperty("fontRole", "h2")
        outer.addWidget(title_lbl)

        subtitle_lbl = QLabel(
            t(
                "receipt.share.subtitle",
                default="Share this receipt PDF with others.",
            )
        )
        subtitle_lbl.setProperty("fontRole", "base-secondary")
        subtitle_lbl.setWordWrap(True)
        outer.addWidget(subtitle_lbl)

        # ── File path field + Copy button ─────────────────────────
        path_label = QLabel(
            t("receipt.share.file_path_label", default="File path")
        )
        path_label.setProperty("role", "url-label")
        outer.addWidget(path_label)

        path_row = QWidget()
        path_row_layout = QHBoxLayout(path_row)
        path_row_layout.setContentsMargins(0, 0, 0, 0)
        path_row_layout.setSpacing(S["2"])

        self._path_field = QLabel(self._file_path if self._file_path else "-")
        self._path_field.setProperty("role", "share-url-field")
        self._path_field.setWordWrap(True)
        self._path_field.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        self._path_field.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_row_layout.addWidget(self._path_field, 1)

        copy_btn = QPushButton(
            t("receipt.share.copy_path", default="Copy Path")
        )
        copy_btn.setAccessibleName("Copy file path")
        copy_btn.setFixedWidth(80)
        copy_btn.setFixedHeight(BTN_HEIGHT_SM)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setProperty("variant", "sm-accent")
        copy_btn.clicked.connect(self._on_copy_path)
        path_row_layout.addWidget(copy_btn)

        outer.addWidget(path_row)

        # ── Action buttons ────────────────────────────────────────
        actions_row = QWidget()
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(S["2"])

        # Save As
        save_as_btn = QPushButton(
            t("receipt.share.save_as", default="Save As")
        )
        save_as_btn.setAccessibleName("Save receipt as")
        save_as_btn.setFixedHeight(BTN_HEIGHT)
        save_as_btn.setCursor(Qt.PointingHandCursor)
        save_as_btn.setProperty("role", "sm-outline-solid")
        save_as_btn.clicked.connect(self._on_save_as)
        actions_layout.addWidget(save_as_btn)

        # Open
        open_btn = QPushButton(
            t("receipt.share.open", default="Open")
        )
        open_btn.setAccessibleName("Open receipt PDF")
        open_btn.setFixedHeight(BTN_HEIGHT)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setProperty("role", "sm-outline-solid")
        open_btn.clicked.connect(self._on_open)
        actions_layout.addWidget(open_btn)

        outer.addWidget(actions_row)

        # ── Close button ──────────────────────────────────────────
        close_btn = QPushButton(
            t("receipt.share.close", default="Close")
        )
        close_btn.setAccessibleName("Close dialog")
        close_btn.setFixedHeight(BTN_HEIGHT)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setProperty("role", "dialog-outline")
        close_btn.clicked.connect(self.reject)
        outer.addWidget(close_btn)

    # ── Slots ────────────────────────────────────────────────────

    def _on_copy_path(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self._file_path, QClipboard.Mode.Clipboard)
            feedback = t(
                "receipt.share.path_copied", default="Copied!"
            )
        else:
            feedback = t(
                "receipt.share.clipboard_unavailable",
                default="Clipboard unavailable",
            )
        # Brief visual feedback
        self._path_field.setText(feedback)
        # Restore after 2 seconds
        from PySide6.QtCore import QTimer

        QTimer.singleShot(2000, self._restore_path_text)

    def _restore_path_text(self) -> None:
        self._path_field.setText(
            self._file_path if self._file_path else "-"
        )

    def _on_save_as(self) -> None:
        if self._on_save_as_cb:
            path = self._on_save_as_cb(self._file_path)
            if path:
                self._path_field.setText(
                    t(
                        "receipt.share.saved",
                        default="Saved: {path}",
                    ).format(path=path)
                )
                from PySide6.QtCore import QTimer

                QTimer.singleShot(3000, self._restore_path_text)

    def _on_open(self) -> None:
        if self._on_open_cb:
            self._on_open_cb(self._file_path)
        self.accept()
