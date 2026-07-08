"""Tests for the global QSS stylesheet generation."""
from __future__ import annotations

from ui.stylesheet import build_stylesheet


class TestStylesheetGeneration:
    def test_returns_string(self):
        ss = build_stylesheet()
        assert isinstance(ss, str)
        assert len(ss) > 0

    def test_contains_stat_card(self):
        ss = build_stylesheet()
        assert "QFrame#stat-card" in ss

    def test_contains_stat_card_hover(self):
        ss = build_stylesheet()
        assert 'QFrame#stat-card[hovered="true"]' in ss

    def test_contains_filter_checkbox(self):
        ss = build_stylesheet()
        assert 'QCheckBox[role="filter"]' in ss

    def test_contains_filter_input(self):
        ss = build_stylesheet()
        assert 'QLineEdit[role="filter"]' in ss
        assert 'QComboBox[role="filter"]' in ss

    def test_contains_section_header(self):
        ss = build_stylesheet()
        assert 'QLabel[role="section-header"]' in ss

    def test_contains_tab_button(self):
        ss = build_stylesheet()
        assert 'QPushButton[tabRole="tab-button"]' in ss

    def test_contains_tab_active(self):
        ss = build_stylesheet()
        assert 'tabActive=' in ss

    def test_contains_kanban_column(self):
        ss = build_stylesheet()
        assert 'QFrame[role="kanban-column"]' in ss

    def test_contains_kanban_column_header(self):
        ss = build_stylesheet()
        assert 'QWidget[role="kanban-column-header"]' in ss

    def test_contains_kanban_column_title(self):
        ss = build_stylesheet()
        assert 'kanban-column-title' in ss

    def test_contains_kanban_column_count(self):
        ss = build_stylesheet()
        assert 'kanban-column-count' in ss

    def test_contains_kanban_columns_container(self):
        ss = build_stylesheet()
        assert 'kanban-columns-container' in ss

    def test_contains_card_rules(self):
        ss = build_stylesheet()
        assert 'QFrame#card' in ss
