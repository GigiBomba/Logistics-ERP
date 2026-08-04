"""Component-level QSS selector and property tests.

Verifies that Qt dynamic-property selectors (e.g. ``[variant="secondary"]``,
``[role="card"]``, ``[validation="error"]``) exist in the generated stylesheet
and that setting those properties on real widgets followed by unpolish/polish
preserves the property value.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
)

from ui.theme_engine import QtTheme
from ui.stylesheet import build_stylesheet


# ── Test helpers ──────────────────────────────────────────────────────────


def _qss() -> str:
    """Shortcut to the cached QSS string."""
    return QtTheme.qss()


def _polished(widget) -> None:
    """Unpolish and re-polish *widget* so that Qt re-evaluates its QSS."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


# ══════════════════════════════════════════════════════════════════════════
# 1. QPushButton variants
# ══════════════════════════════════════════════════════════════════════════


class TestPushButtonVariants:
    """QPushButton variant selectors and property persistence."""

    def test_primary_button_selector(self, qapp) -> None:
        """Base QPushButton selector is present in the applied stylesheet."""
        assert "QPushButton" in qapp.styleSheet()

    def test_secondary_button_variant(self, qapp) -> None:
        """Variant selector exists and property persists after polish."""
        assert '[variant="secondary"]' in _qss()
        btn = QPushButton()
        btn.setProperty("variant", "secondary")
        _polished(btn)
        assert btn.property("variant") == "secondary"

    def test_danger_button_variant(self, qapp) -> None:
        """Variant selector exists and property persists after polish."""
        assert '[variant="danger"]' in _qss()
        btn = QPushButton()
        btn.setProperty("variant", "danger")
        _polished(btn)
        assert btn.property("variant") == "danger"

    def test_ghost_button_variant(self, qapp) -> None:
        """Variant selector exists and property persists after polish."""
        assert '[variant="ghost"]' in _qss()
        btn = QPushButton()
        btn.setProperty("variant", "ghost")
        _polished(btn)
        assert btn.property("variant") == "ghost"

    def test_success_button_variant(self, qapp) -> None:
        """Variant selector exists and property persists after polish."""
        assert '[variant="success"]' in _qss()
        btn = QPushButton()
        btn.setProperty("variant", "success")
        _polished(btn)
        assert btn.property("variant") == "success"


# ══════════════════════════════════════════════════════════════════════════
# 2. QLineEdit validation states
# ══════════════════════════════════════════════════════════════════════════


class TestLineEditValidation:
    """Validation-state selectors and property persistence."""

    def test_validation_selectors_exist(self) -> None:
        """Both error and success validation selectors appear in the QSS."""
        qss = _qss()
        assert '[validation="error"]' in qss
        assert '[validation="success"]' in qss

    def test_set_error_validation_property(self, qapp) -> None:
        """Setting validation='error' persists after polish."""
        le = QLineEdit()
        le.setProperty("validation", "error")
        _polished(le)
        assert le.property("validation") == "error"

    def test_set_success_validation_property(self, qapp) -> None:
        """Setting validation='success' persists after polish."""
        le = QLineEdit()
        le.setProperty("validation", "success")
        _polished(le)
        assert le.property("validation") == "success"


# ══════════════════════════════════════════════════════════════════════════
# 3. QFrame role selectors
# ══════════════════════════════════════════════════════════════════════════


class TestFrameRoles:
    """QFrame role selectors and property persistence."""

    def test_card_role_selector(self) -> None:
        """The [role="card"] selector is present in the QSS."""
        assert '[role="card"]' in _qss()

    def test_card_role_property(self, qapp) -> None:
        """Setting role='card' persists after polish."""
        frame = QFrame()
        frame.setProperty("role", "card")
        _polished(frame)
        assert frame.property("role") == "card"

    def test_card_elevated_role_property(self, qapp) -> None:
        """Setting role='card-elevated' persists after polish."""
        frame = QFrame()
        frame.setProperty("role", "card-elevated")
        _polished(frame)
        assert frame.property("role") == "card-elevated"

    def test_divider_role_property(self, qapp) -> None:
        """Setting role='divider' persists after polish."""
        frame = QFrame()
        frame.setProperty("role", "divider")
        _polished(frame)
        assert frame.property("role") == "divider"

    def test_input_role_property(self, qapp) -> None:
        """Setting role='input' persists after polish."""
        frame = QFrame()
        frame.setProperty("role", "input")
        _polished(frame)
        assert frame.property("role") == "input"

    def test_kpi_card_role_property(self, qapp) -> None:
        """Setting role='kpi-card' persists after polish."""
        frame = QFrame()
        frame.setProperty("role", "kpi-card")
        _polished(frame)
        assert frame.property("role") == "kpi-card"


# ══════════════════════════════════════════════════════════════════════════
# 4. QLabel font-role selectors
# ══════════════════════════════════════════════════════════════════════════


class TestLabelFontRoles:
    """QLabel fontRole selectors and property persistence."""

    def test_label_font_role_selectors_exist(self) -> None:
        """All major fontRole value selectors appear in the QSS."""
        qss = _qss()
        for role in ("h1", "h2", "h3", "hero", "mono", "muted"):
            assert f'[fontRole="{role}"]' in qss, (
                f"Missing fontRole selector for '{role}'"
            )

    def test_set_h1_font_role(self, qapp) -> None:
        """Setting fontRole='h1' persists after polish."""
        lbl = QLabel()
        lbl.setProperty("fontRole", "h1")
        _polished(lbl)
        assert lbl.property("fontRole") == "h1"

    def test_set_mono_font_role(self, qapp) -> None:
        """Setting fontRole='mono' persists after polish."""
        lbl = QLabel()
        lbl.setProperty("fontRole", "mono")
        _polished(lbl)
        assert lbl.property("fontRole") == "mono"

    def test_set_muted_font_role(self, qapp) -> None:
        """Setting fontRole='muted' persists after polish."""
        lbl = QLabel()
        lbl.setProperty("fontRole", "muted")
        _polished(lbl)
        assert lbl.property("fontRole") == "muted"

    def test_set_hero_font_role(self, qapp) -> None:
        """Setting fontRole='hero' persists after polish."""
        lbl = QLabel()
        lbl.setProperty("fontRole", "hero")
        _polished(lbl)
        assert lbl.property("fontRole") == "hero"


# ══════════════════════════════════════════════════════════════════════════
# 5. QTableWidget styles
# ══════════════════════════════════════════════════════════════════════════


class TestTableWidgetStyles:
    """QTableWidget and QHeaderView selectors, alternating rows."""

    def test_table_selectors_exist(self) -> None:
        """QTableWidget and QHeaderView::section selectors are present."""
        qss = _qss()
        assert "QTableWidget" in qss
        assert "QHeaderView::section" in qss

    def test_alternating_row_colors(self, qapp) -> None:
        """Alternating row colours can be enabled on a QTableWidget."""
        table = QTableWidget(2, 2)
        table.setAlternatingRowColors(True)
        assert table.alternatingRowColors() is True


# ══════════════════════════════════════════════════════════════════════════
# 6. QScrollBar styles
# ══════════════════════════════════════════════════════════════════════════


class TestScrollBarStyles:
    """QScrollBar selectors and handle styling."""

    def test_scrollbar_selectors_exist(self) -> None:
        """Vertical, horizontal and handle selectors are present."""
        qss = _qss()
        assert "QScrollBar:vertical" in qss
        assert "QScrollBar:horizontal" in qss
        assert "QScrollBar::handle:vertical" in qss

    def test_scrollbar_handle_has_background(self) -> None:
        """The vertical-handle block includes a 'background' declaration."""
        qss = _qss()
        idx = qss.index("QScrollBar::handle:vertical")
        block = qss[idx:].split("}")[0]
        assert "background" in block, (
            "QScrollBar::handle:vertical block missing background property"
        )


# ══════════════════════════════════════════════════════════════════════════
# 7. Filter and tab-button styles (build_stylesheet additions)
# ══════════════════════════════════════════════════════════════════════════


class TestFilterAndTabStyles:
    """Selectors added by the build_stylesheet() wrapper."""

    def test_filter_checkbox_selector(self) -> None:
        """QCheckBox[role='filter'] is present in build_stylesheet()."""
        ss = build_stylesheet()
        assert 'QCheckBox[role="filter"]' in ss

    def test_filter_input_selector(self) -> None:
        """QLineEdit[role='filter'] is present in build_stylesheet()."""
        ss = build_stylesheet()
        assert 'QLineEdit[role="filter"]' in ss

    def test_tab_button_active_selector(self) -> None:
        """Tab-button active selector is present in build_stylesheet()."""
        ss = build_stylesheet()
        assert 'QPushButton[tabRole="tab-button"][tabActive="true"]' in ss
