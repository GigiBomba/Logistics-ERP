"""Share Route dialog — share URL, QR code, file export, Google Maps, OS share.

A modal dialog that lets the user share a calculated route via:

* Copying a share link to clipboard
* Exporting a ``.operionroute`` file
* Opening in Google Maps for navigation
* OS-level share sheet (Windows Share contract)
* QR code (when the ``qrcode`` package is installed)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QClipboard, QGuiApplication, QPixmap, QShowEvent
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
    COLOR_ACCENT_HOVER, COLOR_ACCENT_PRIMARY, COLOR_BG_ELEVATED, COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_WHITE,
    FADE_MS, FONT_SIZE_BASE, FONT_SIZE_LG, FONT_SIZE_SM, FONT_WEIGHT_BOLD, FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG, RADIUS_SM, SPACE_1, SPACE_2, SPACE_3, BTN_HEIGHT, BTN_HEIGHT_SM,
)
from ui.design_tokens import SP as S

logger = logging.getLogger(__name__)


def _try_import_qrcode():
    """Attempt to import ``qrcode``; return the module or None."""
    try:
        import qrcode as _qr

        return _qr
    except ImportError:
        return None


class ShareRouteDialog(QDialog):
    """Modal dialog for sharing a route via URL, file, QR, or Google Maps.

    Usage::

        dialog = ShareRouteDialog(
            parent=self,
            share_url="https://operion.app/route?stops=...",
            google_maps_url="https://www.google.com/maps/dir/?api=1&...",
            on_export_file=my_export_callback,
            on_share_via_os=my_share_callback,
        )
        dialog.exec()
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        share_url: str = "",
        google_maps_url: str = "",
        on_export_file: callable | None = None,
        on_share_via_os: callable | None = None,
        on_open_in_gmaps: callable | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("route.share_title", default="Share Route"))
        self.setAccessibleName("Share Route")
        self.setAccessibleDescription("Dialog for sharing a route via link, file, or maps")
        self.setMinimumSize(460, 360)
        self.setMaximumWidth(520)
        self.setWindowModality(Qt.ApplicationModal)

        self._share_url = share_url
        self._google_maps_url = google_maps_url
        self._on_export_file_cb = on_export_file
        self._on_share_via_os_cb = on_share_via_os
        self._on_open_in_gmaps_cb = on_open_in_gmaps

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
        title_lbl = QLabel(t("route.share_title", default="Share Route"))
        title_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_LG}px; font-weight: {FONT_WEIGHT_BOLD};"
            f" background: transparent; border: none;"
        )
        outer.addWidget(title_lbl)

        subtitle_lbl = QLabel(
            t("route.share_subtitle", default="Share this route with others so they can load it in Operion.")
        )
        subtitle_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_BASE}px;"
            f" background: transparent; border: none;"
        )
        subtitle_lbl.setWordWrap(True)
        outer.addWidget(subtitle_lbl)

        # ── Share URL field + Copy button ─────────────────────────
        url_label = QLabel(t("route.share_link_label", default="Share link"))
        url_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
            f" background: transparent; border: none;"
        )
        outer.addWidget(url_label)

        url_row = QWidget()
        url_row_layout = QHBoxLayout(url_row)
        url_row_layout.setContentsMargins(0, 0, 0, 0)
        url_row_layout.setSpacing(S["2"])

        self._url_field = QLabel(self._share_url if self._share_url else "-")
        self._url_field.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_SM}px;"
            f" background: {COLOR_BG_OVERLAY}; border: 1px solid {COLOR_BORDER_MEDIUM};"
            f" border-radius: {RADIUS_SM}px; padding: {SPACE_1}px {SPACE_2}px;"
        )
        self._url_field.setWordWrap(True)
        self._url_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._url_field.setTextInteractionFlags(Qt.TextSelectableByMouse)
        url_row_layout.addWidget(self._url_field, 1)

        copy_btn = QPushButton(
            t("route.copy_link", default="Copy")
        )
        copy_btn.setAccessibleName("Copy link")
        copy_btn.setFixedWidth(64)
        copy_btn.setFixedHeight(BTN_HEIGHT_SM)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_ACCENT_PRIMARY};
                color: {COLOR_TEXT_WHITE};
                border: none;
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_SEMIBOLD};
            }}
            QPushButton:hover {{
                background: {COLOR_ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background: {COLOR_ACCENT_HOVER};
            }}
        """)
        copy_btn.clicked.connect(self._on_copy_link)
        url_row_layout.addWidget(copy_btn)

        outer.addWidget(url_row)

        # ── QR code ───────────────────────────────────────────────
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setStyleSheet("background: transparent; border: none;")
        self._qr_label.setFixedHeight(120)
        self._qr_label.hide()
        outer.addWidget(self._qr_label)

        self._generate_qr()

        # ── Action buttons ────────────────────────────────────────
        actions_row = QWidget()
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(S["2"])

        # Export File
        export_btn = QPushButton(
            t("route.export_file", default="Export File")
        )
        export_btn.setAccessibleName("Export route file")
        export_btn.setFixedHeight(BTN_HEIGHT)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_SEMIBOLD};
                padding: 0 {SPACE_3}px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        export_btn.clicked.connect(self._on_export_file)
        actions_layout.addWidget(export_btn)

        # Open in Google Maps
        gmaps_btn = QPushButton(
            t("route.open_in_gmaps", default="Google Maps")
        )
        gmaps_btn.setAccessibleName("Open in Google Maps")
        gmaps_btn.setFixedHeight(BTN_HEIGHT)
        gmaps_btn.setCursor(Qt.PointingHandCursor)
        gmaps_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_SEMIBOLD};
                padding: 0 {SPACE_3}px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        gmaps_btn.clicked.connect(self._on_open_gmaps)
        actions_layout.addWidget(gmaps_btn)

        # Export + open folder (Windows Share contract requires winrt)
        share_os_btn = QPushButton(
            t("route.save_and_open", default="Save & Open Folder")
        )
        share_os_btn.setAccessibleName("Save and open folder")
        share_os_btn.setFixedHeight(BTN_HEIGHT)
        share_os_btn.setCursor(Qt.PointingHandCursor)
        share_os_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
                font-weight: {FONT_WEIGHT_SEMIBOLD};
                padding: 0 {SPACE_3}px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        share_os_btn.clicked.connect(self._on_share_via_os)
        actions_layout.addWidget(share_os_btn)

        outer.addWidget(actions_row)

        # ── Close button ──────────────────────────────────────────
        close_btn = QPushButton(
            t("common.close", default="Close")
        )
        close_btn.setAccessibleName("Close dialog")
        close_btn.setFixedHeight(BTN_HEIGHT)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_TEXT_SECONDARY};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: {RADIUS_SM}px;
                font-size: {FONT_SIZE_SM}px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        outer.addWidget(close_btn)

        # Dialog background
        self.setStyleSheet(
            f"QDialog {{ background: {COLOR_BG_ELEVATED}; border-radius: {RADIUS_LG}px; }}"
        )

    # ── Slots ────────────────────────────────────────────────────

    def _on_copy_link(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self._share_url, QClipboard.Mode.Clipboard)
            feedback = t("route.link_copied", default="Copied!")
        else:
            feedback = t("route.clipboard_unavailable", default="Clipboard unavailable")
        # Brief visual feedback — change button text temporarily
        self._url_field.setText(feedback)
        # Restore after 2 seconds
        from PySide6.QtCore import QTimer

        QTimer.singleShot(2000, self._restore_url_text)

    def _restore_url_text(self) -> None:
        self._url_field.setText(self._share_url if self._share_url else "-")

    def _on_export_file(self) -> None:
        if self._on_export_file_cb:
            path = self._on_export_file_cb()
            if path:
                self._url_field.setText(
                    t("route.export_success_file", default="Saved: {path}").format(path=path)
                )
                from PySide6.QtCore import QTimer

                QTimer.singleShot(3000, self._restore_url_text)

    def _on_open_gmaps(self) -> None:
        if self._on_open_in_gmaps_cb:
            self._on_open_in_gmaps_cb()
        self.accept()

    def _on_share_via_os(self) -> None:
        if self._on_share_via_os_cb:
            self._on_share_via_os_cb()
        self.accept()

    # ── QR code generation ──────────────────────────────────────

    def _generate_qr(self) -> None:
        qr = _try_import_qrcode()
        if qr is None or not self._share_url:
            self._qr_label.hide()
            return

        try:
            img = qr.make(self._share_url, box_size=4, border=1)
            # Convert PIL Image to QPixmap
            from PIL.ImageQt import ImageQt

            qimage = ImageQt(img)
            pixmap = QPixmap.fromImage(qimage)
            self._qr_label.setPixmap(pixmap)
            self._qr_label.show()
        except Exception:
            logger.debug("QR generation failed (Pillow ImageQt not available?)", exc_info=True)
            self._qr_label.hide()
