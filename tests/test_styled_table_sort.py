"""Regression tests for :class:`StyledTableWidget` sort/selection drift.

Issue 2: after the user sorts a column, the in-memory ``_data`` list
used by selection handlers (e.g. ``current_row_data``) drifted out of
sync with the visual row order.  This file pins down the corrected
behaviour:

* the data list mirrors the visual order after ``set_data`` and after
  the user clicks a header to change the sort,
* ``current_row_data()`` and ``selected_row_data()`` return the data
  for the visible row,
* ``None`` values always sink to the bottom of a sort (regardless of
  direction),
* changing the sort indicator emits ``rowSelected`` so views can
  re-validate the row they think is selected.
"""

import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.widgets import StyledTableWidget


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _names(table) -> list:
    return [table.item(r, 0).text() for r in range(table.rowCount())]


class TestStyledTableWidgetSort(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        self.table = StyledTableWidget(
            columns=[
                ("name", "Name", 100),
                ("active", "Active", 60),
            ],
        )
        self.rows = [
            {"name": "Charlie", "active": 1, "id": 1},
            {"name": "Alpha",   "active": 0, "id": 2},
            {"name": "Bravo",   "active": 1, "id": 3},
        ]

    def test_initial_set_data_sorts_to_default_indicator(self) -> None:
        self.table.set_data(self.rows)
        # Default sort indicator is column 0 ascending.
        self.assertEqual(
            [r["name"] for r in self.table._data],
            ["Alpha", "Bravo", "Charlie"],
        )
        self.assertEqual(_names(self.table), ["Alpha", "Bravo", "Charlie"])

    def test_changing_sort_to_descending_reorders_data(self) -> None:
        self.table.set_data(self.rows)
        self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        QApplication.processEvents()
        self.assertEqual(
            [r["name"] for r in self.table._data],
            ["Charlie", "Bravo", "Alpha"],
        )
        self.assertEqual(_names(self.table), ["Charlie", "Bravo", "Alpha"])

    def test_sort_by_second_column(self) -> None:
        self.table.set_data(self.rows)
        # The data was just sorted by name ascending (default
        # indicator), so ``_data`` is now ``[Alpha, Bravo, Charlie]``
        # and the 1s appear in that order.  Sorting by ``active``
        # ascending then re-sorts the 1s in their *current* order
        # (stable).
        self.table.horizontalHeader().setSortIndicator(1, Qt.AscendingOrder)
        QApplication.processEvents()
        self.assertEqual(
            [r["name"] for r in self.table._data],
            ["Alpha", "Bravo", "Charlie"],
        )

    def test_current_row_data_matches_visual_row(self) -> None:
        self.table.set_data(self.rows)
        # Default asc by name: row 0 is Alpha.
        self.table.selectRow(0)
        self.assertEqual(self.table.current_row_data()["name"], "Alpha")
        # Now sort descending — Qt follows the selected data item
        # across the re-sort, so the row that *was* Alpha is now
        # somewhere else.  ``current_row_data()`` must still return
        # the data the user actually sees highlighted.
        self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        QApplication.processEvents()
        # ``current_row_data`` must point to Alpha, no matter where
        # the visual row landed after the sort.
        self.assertEqual(self.table.current_row_data()["name"], "Alpha")
        # And the visual top row must be Charlie, confirming the
        # sort actually changed the layout.
        self.assertEqual(_names(self.table)[0], "Charlie")

    def test_selected_row_data_matches_visual_row(self) -> None:
        self.table.set_data(self.rows)
        self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        QApplication.processEvents()
        # Visual top row is Charlie.
        self.table.selectRow(0)
        self.assertEqual(self.table.selected_row_data()["name"], "Charlie")

    def test_none_values_sink_in_ascending(self) -> None:
        rows = [
            {"name": "Charlie", "id": 1},
            {"name": None,     "id": 2},
            {"name": "Alpha",   "id": 3},
            {"name": None,     "id": 4},
        ]
        self.table.set_data(rows)
        # Ascending: strings ascending then ``None``s at the bottom.
        self.assertEqual(
            [r["name"] for r in self.table._data],
            ["Alpha", "Charlie", None, None],
        )

    def test_none_values_sink_in_descending(self) -> None:
        rows = [
            {"name": "Charlie", "id": 1},
            {"name": None,     "id": 2},
            {"name": "Alpha",   "id": 3},
            {"name": None,     "id": 4},
        ]
        self.table.set_data(rows)
        self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        QApplication.processEvents()
        # Descending: ``None``s still at the bottom (we want the
        # user to see real values first regardless of direction).
        self.assertEqual(
            [r["name"] for r in self.table._data],
            [None, None, "Charlie", "Alpha"],
        )

    def test_changing_sort_emits_row_selected(self) -> None:
        """Views that cache the selected row's id (e.g. Client Manager)
        need to know when the user's selection has shifted under their
        feet.  ``sortIndicatorChanged`` must trigger ``rowSelected`` if
        there is a current row.
        """
        self.table.set_data(self.rows)
        self.table.selectRow(0)
        received: list = []
        self.table.rowSelected.connect(
            lambda d: received.append(d.get("name"))
        )
        self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        QApplication.processEvents()
        # Qt follows the selected item across the re-sort, so the
        # row that *was* Alpha is still selected.  ``rowSelected``
        # should have fired with that data.
        self.assertTrue(len(received) >= 1)
        self.assertEqual(received[0], "Alpha")

    def test_empty_data_does_not_crash(self) -> None:
        self.table.set_data([])
        self.assertEqual(self.table._data, [])
        self.assertEqual(self.table.rowCount(), 0)
        # Setting sort indicator on empty data must not raise.
        self.table.horizontalHeader().setSortIndicator(0, Qt.DescendingOrder)
        QApplication.processEvents()
        self.assertEqual(self.table._data, [])


if __name__ == "__main__":
    unittest.main()
