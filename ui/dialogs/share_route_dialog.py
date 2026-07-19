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

from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.theme import COLORS, S

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
        self.setMinimumSize(460, 360)
        self.setMaximumWidth(520)
        self.setWindowModality(Qt.ApplicationModal)

        self._share_url = share_url
        self._google_maps_url = google_maps_url
        self._on_export_file_cb = on_export_file
        self._on_share_via_os_cb = on_share_via_os
        self._on_open_in_gmaps_cb = on_open_in_gmaps

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(S["6"], S["6"], S["6"], S["6"])
        outer.setSpacing(S["4"])

        # ── Title ─────────────────────────────────────────────────
        title_lbl = QLabel(t("route.share_title", default="Share Route"))
        title_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 700;"
            f" background: transparent; border: none;"
        )
        outer.addWidget(title_lbl)

        subtitle_lbl = QLabel(
            t("route.share_subtitle", default="Share this route with others so they can load it in Operion.")
        )
        subtitle_lbl.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 12px;"
            f" background: transparent; border: none;"
        )
        subtitle_lbl.setWordWrap(True)
        outer.addWidget(subtitle_lbl)

        # ── Share URL field + Copy button ─────────────────────────
        url_label = QLabel(t("route.share_link_label", default="Share link"))
        url_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        outer.addWidget(url_label)

        url_row = QWidget()
        url_row_layout = QHBoxLayout(url_row)
        url_row_layout.setContentsMargins(0, 0, 0, 0)
        url_row_layout.setSpacing(S["2"])

        self._url_field = QLabel(self._share_url if self._share_url else "-")
        self._url_field.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 11px;"
            f" background: {COLORS['bg_input']}; border: 1px solid {COLORS['border']};"
            f" border-radius: 4px; padding: 6px 8px;"
        )
        self._url_field.setWordWrap(True)
        self._url_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._url_field.setTextInteractionFlags(Qt.TextSelectableByMouse)
        url_row_layout.addWidget(self._url_field, 1)

        copy_btn = QPushButton(
            t("route.copy_link", default="Copy")
        )
        copy_btn.setFixedWidth(64)
        copy_btn.setFixedHeight(30)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_hover']};
            }}
            QPushButton:pressed {{
                background: #4547B0;
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
        export_btn.setFixedHeight(32)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_elevated']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
            }}
        """)
        export_btn.clicked.connect(self._on_export_file)
        actions_layout.addWidget(export_btn)

        # Open in Google Maps
        gmaps_btn = QPushButton(
            t("route.open_in_gmaps", default="Google Maps")
        )
        gmaps_btn.setFixedHeight(32)
        gmaps_btn.setCursor(Qt.PointingHandCursor)
        gmaps_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_elevated']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
            }}
        """)
        gmaps_btn.clicked.connect(self._on_open_gmaps)
        actions_layout.addWidget(gmaps_btn)

        # Export + open folder (Windows Share contract requires winrt)
        share_os_btn = QPushButton(
            t("route.save_and_open", default="Save & Open Folder")
        )
        share_os_btn.setFixedHeight(32)
        share_os_btn.setCursor(Qt.PointingHandCursor)
        share_os_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_elevated']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
            }}
        """)
        share_os_btn.clicked.connect(self._on_share_via_os)
        actions_layout.addWidget(share_os_btn)

        outer.addWidget(actions_row)

        # ── Close button ──────────────────────────────────────────
        close_btn = QPushButton(
            t("common.close", default="Close")
        )
        close_btn.setFixedHeight(32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_elevated']};
                color: {COLORS['text_primary']};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        outer.addWidget(close_btn)

        # Dialog background
        self.setStyleSheet(
            f"QDialog {{ background: {COLORS['bg_surface']}; border-radius: 8px; }}"
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
