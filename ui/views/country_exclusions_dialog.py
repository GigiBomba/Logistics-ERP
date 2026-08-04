"""Country selection dialog for route planner country exclusions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.country_avoidance import CountryAvoidanceManager
from services.i18n import t
from ui.design_tokens import (
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)
from ui.widgets import StyledCheckBox


class CountryExclusionsDialog(QDialog):
    """Dialog for selecting countries to exclude from route calculation."""

    def __init__(
        self,
        parent: QWidget | None,
        avoidance: CountryAvoidanceManager,
    ):
        super().__init__(parent)
        self.setAccessibleName("Country exclusions")
        self.setAccessibleDescription("Dialog for selecting countries to exclude from route calculation")
        self.avoidance = avoidance
        self._checkboxes: list[StyledCheckBox] = []
        self._build()

    def _build(self) -> None:
        self.setWindowTitle(t("route.exclusions_label"))
        self.setMinimumSize(280, 320)
        self.resize(360, 440)
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_MEDIUM};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(t("route.exclusions_label"))
        header.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 14px; font-weight: 600;"
        )
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(type(scroll).NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ width: 4px; background: transparent; }}
            QScrollBar::handle:vertical {{ background: {COLOR_BORDER_MEDIUM}; border-radius: 2px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)

        countries = self.avoidance.get_all_countries()
        selected = set(self.avoidance.get_selected())
        codes = sorted(countries.items(), key=lambda x: x[1])

        for code, name in codes:
            cb = StyledCheckBox(text=name)
            cb.setAccessibleName(f"Exclude {name}")
            cb.setProperty("country_code", code)
            cb.setChecked(code in selected)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {COLOR_TEXT_SECONDARY};
                    font-size: 12px;
                    spacing: 8px;
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
                QCheckBox:hover {{ color: {COLOR_TEXT_PRIMARY}; background: {COLOR_BG_HOVER}; }}
                QCheckBox::indicator {{
                    width: 16px; height: 16px;
                    border-radius: 4px;
                    border: 1px solid {COLOR_BORDER_MEDIUM};
                    background: {COLOR_BG_OVERLAY};
                }}
                QCheckBox::indicator:checked {{
                    background: {COLOR_ACCENT_PRIMARY};
                    border-color: {COLOR_ACCENT_PRIMARY};
                }}
                QCheckBox::indicator:hover {{ border-color: {COLOR_ACCENT_PRIMARY}; }}
            """)
            cl.addWidget(cb)
            self._checkboxes.append(cb)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        for btn in buttons.buttons():
            btn.setAccessibleName(btn.text())
        buttons.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {COLOR_BG_HOVER};
            }}
        """)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        for cb in self._checkboxes:
            code = cb.property("country_code")
            is_checked = cb.isChecked()
            currently_selected = code in self.avoidance.get_selected()
            if is_checked and not currently_selected:
                self.avoidance.toggle(code)
            elif not is_checked and currently_selected:
                self.avoidance.toggle(code)
        self.accept()
