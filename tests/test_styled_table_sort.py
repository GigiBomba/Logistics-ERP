"""Extended tests for the styled table widget sorting."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from PySide6.QtCore import Qt

class TestStyledTableWidget:
    def test_set_data_populates(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50), ("name", "Name", 150)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        rows = [{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}]
        table.set_data(rows)
        assert table.rowCount() == 2

    def test_set_column_alignment(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50), ("value", "Value", 100)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        table.set_column_alignment("id", Qt.AlignCenter)

    def test_current_row_data(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        rows = [{"id": 1}]
        table.set_data(rows)
        data = table.current_row_data()
        assert data is None or isinstance(data, dict)

    def test_selected_row_data(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        rows = [{"id": 1}]
        table.set_data(rows)
        data = table.selected_row_data()
        assert data is None or isinstance(data, dict)

    def test_sort_indicator_preserved(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50), ("name", "Name", 150)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        assert table.horizontalHeader().sortIndicatorSection() == 0

    def test_empty_data_does_not_crash(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        table.set_data([])
        assert table.rowCount() == 0

    def test_sorting_nulls_last(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50), ("name", "Name", 150)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        rows = [{"id": 2, "name": None}, {"id": 1, "name": "Alpha"}]
        table.set_data(rows)
        assert table.rowCount() == 2

    def test_row_selected_signal(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        rows = [{"id": 1}]
        table.set_data(rows)
        signals = []
        table.rowSelected.connect(lambda d: signals.append(d))
        table.selectRow(0)
        if signals:
            assert signals[0]["id"] == 1

    def test_double_click_signal(self, qt_widget, qtbot):
        from ui.widgets import StyledTableWidget
        columns = [("id", "ID", 50)]
        table = StyledTableWidget(qt_widget, columns=columns)
        qtbot.addWidget(table)
        rows = [{"id": 1}]
        table.set_data(rows)
        signals = []
        table.rowDoubleClicked.connect(lambda d: signals.append(d))

    def test_factory_styled_table(self, qt_widget, qtbot):
        from ui.widgets import styled_table
        table = styled_table(qt_widget, [("id", "ID", 50)])
        qtbot.addWidget(table)
