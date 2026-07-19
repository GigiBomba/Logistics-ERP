"""Tests for TachoStatusModel — table model, formatting, status logic."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QModelIndex, Qt


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def model(qt_widget, qtbot):
    """Create an empty TachoStatusModel."""
    from ui.models.tacho_status_model import TachoStatusModel
    m = TachoStatusModel(qt_widget)
    yield m
    m.deleteLater()


@pytest.fixture
def populated_model(model):
    """Model with sample tacho data rows."""
    model._rows = [
        {
            "truck_id": 1,
            "plate_number": "AG01ABC",
            "imported_at": "2026-06-01 10:30:00",
            "calibration_date": "2025-01-15",
            "calibration_expiry": "2026-01-15",
        },
        {
            "truck_id": 2,
            "plate_number": "AG02XYZ",
            "imported_at": "2026-05-20 08:00:00",
            "calibration_date": "2024-06-01",
            "calibration_expiry": "2025-06-01",
        },
        {
            "truck_id": 3,
            "plate_number": "AG03DEF",
            "imported_at": None,
            "calibration_date": None,
            "calibration_expiry": None,
        },
    ]
    # Reset the model after directly manipulating _rows
    model.beginResetModel()
    model.endResetModel()
    return model


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    """Model creates empty."""

    def test_creation(self, model):
        assert model is not None

    def test_empty_row_count(self, model):
        assert model.rowCount() == 0

    def test_column_count(self, model):
        assert model.columnCount() == 5

    def test_headers_defined(self):
        from ui.models.tacho_status_model import TachoStatusModel
        assert len(TachoStatusModel._HEADERS) == 5


# =========================================================================
# rowCount / columnCount
# =========================================================================


class TestRowColumnCount:
    """Row/column counts reflect data."""

    def test_row_count_after_populate(self, populated_model):
        assert populated_model.rowCount() == 3

    def test_column_count_constant(self, populated_model):
        assert populated_model.columnCount() == 5


# =========================================================================
# headerData
# =========================================================================


class TestHeaderData:
    """Header labels and widths."""

    def test_header_returns_string(self, populated_model):
        h = populated_model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_header_out_of_range_returns_none(self, populated_model):
        assert populated_model.headerData(99, Qt.Horizontal, Qt.DisplayRole) is None

    def test_header_vertical_returns_none(self, populated_model):
        assert populated_model.headerData(0, Qt.Vertical, Qt.DisplayRole) is None

    def test_header_wrong_role_returns_none(self, populated_model):
        assert populated_model.headerData(0, Qt.Horizontal, Qt.DecorationRole) is None

    def test_header_width_valid(self, populated_model):
        assert populated_model.header_width(0) == 120

    def test_header_width_invalid(self, populated_model):
        assert populated_model.header_width(99) == 80


# =========================================================================
# data()
# =========================================================================


class TestData:
    """Data access via model index."""

    def test_invalid_index(self, populated_model):
        idx = QModelIndex()
        assert populated_model.data(idx) is None

    def test_out_of_range_row(self, populated_model):
        idx = populated_model.index(999, 0)
        assert populated_model.data(idx) is None

    def test_plate_display(self, populated_model):
        idx = populated_model.index(0, populated_model.COL_PLATE)
        assert populated_model.data(idx, Qt.DisplayRole) == "AG01ABC"

    def test_plate_display_missing(self, populated_model):
        row = populated_model._rows[2]
        row["plate_number"] = None
        idx = populated_model.index(2, populated_model.COL_PLATE)
        assert populated_model.data(idx, Qt.DisplayRole) == "\u2014"

    def test_last_import_display(self, populated_model):
        idx = populated_model.index(0, populated_model.COL_LAST_IMPORT)
        assert populated_model.data(idx, Qt.DisplayRole) == "2026-06-01"

    def test_last_import_missing(self, populated_model):
        idx = populated_model.index(2, populated_model.COL_LAST_IMPORT)
        assert populated_model.data(idx, Qt.DisplayRole) == "\u2014"

    def test_calibration_date_display(self, populated_model):
        idx = populated_model.index(0, populated_model.COL_CALIBRATION_DATE)
        assert populated_model.data(idx, Qt.DisplayRole) == "2025-01-15"

    def test_calibration_date_missing(self, populated_model):
        idx = populated_model.index(2, populated_model.COL_CALIBRATION_DATE)
        assert populated_model.data(idx, Qt.DisplayRole) == "\u2014"

    def test_expiry_display(self, populated_model):
        idx = populated_model.index(0, populated_model.COL_EXPIRY)
        assert populated_model.data(idx, Qt.DisplayRole) == "2026-01-15"

    def test_expiry_missing(self, populated_model):
        idx = populated_model.index(2, populated_model.COL_EXPIRY)
        assert populated_model.data(idx, Qt.DisplayRole) == "\u2014"

    def test_user_role_returns_row_dict(self, populated_model):
        idx = populated_model.index(0, 0)
        data = populated_model.data(idx, Qt.UserRole)
        assert isinstance(data, dict)
        assert data["truck_id"] == 1

    def test_other_role_returns_none(self, populated_model):
        idx = populated_model.index(0, 0)
        assert populated_model.data(idx, Qt.ToolTipRole) is None

    def test_unknown_column_returns_empty_string(self, populated_model):
        """COL_STATUS (4) is the last column; there's no default fallback
        for unknown columns in _format_cell, so we test it returns ''."""
        row = populated_model._rows[0]
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell(row, 99)
        assert result == ""


# =========================================================================
# _days_remaining
# =========================================================================


class TestDaysRemaining:
    """Days-remaining calculation."""

    def test_expiry_in_future(self):
        from ui.models.tacho_status_model import TachoStatusModel
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        days = TachoStatusModel._days_remaining({"calibration_expiry": future})
        assert days is not None
        assert 25 <= days <= 35  # approximate

    def test_expiry_in_past(self):
        from ui.models.tacho_status_model import TachoStatusModel
        past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        days = TachoStatusModel._days_remaining({"calibration_expiry": past})
        assert days is not None
        assert days < 0

    def test_expiry_today(self):
        from ui.models.tacho_status_model import TachoStatusModel
        today = datetime.now().strftime("%Y-%m-%d")
        days = TachoStatusModel._days_remaining({"calibration_expiry": today})
        assert days is not None
        # Can be 0 or -1 depending on time of day
        assert days <= 0

    def test_no_expiry(self):
        from ui.models.tacho_status_model import TachoStatusModel
        days = TachoStatusModel._days_remaining({})
        assert days is None

    def test_none_expiry(self):
        from ui.models.tacho_status_model import TachoStatusModel
        days = TachoStatusModel._days_remaining({"calibration_expiry": None})
        assert days is None

    def test_invalid_expiry_string(self):
        from ui.models.tacho_status_model import TachoStatusModel
        days = TachoStatusModel._days_remaining({"calibration_expiry": "not-a-date"})
        assert days is None

    def test_empty_expiry_string(self):
        from ui.models.tacho_status_model import TachoStatusModel
        days = TachoStatusModel._days_remaining({"calibration_expiry": ""})
        assert days is None

    def test_expiry_with_time_component(self):
        from ui.models.tacho_status_model import TachoStatusModel
        future = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d 12:00:00")
        days = TachoStatusModel._days_remaining({"calibration_expiry": future})
        assert days is not None
        assert 0 <= days <= 5


# =========================================================================
# _status_label
# =========================================================================


class TestStatusLabel:
    """Status label text for each range."""

    def test_no_data(self):
        from ui.models.tacho_status_model import TachoStatusModel
        label = TachoStatusModel._status_label({})
        assert label == "No data"

    def test_expired(self):
        from ui.models.tacho_status_model import TachoStatusModel
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": past})
        assert label == "Expired"

    def test_expired_long_ago(self):
        from ui.models.tacho_status_model import TachoStatusModel
        past = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": past})
        assert label == "Expired"

    def test_within_7_days(self):
        from ui.models.tacho_status_model import TachoStatusModel
        soon = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": soon})
        # Can be 2d or 3d depending on time of day
        assert label.endswith("d")
        days_val = int(label.rstrip("d"))
        assert 1 <= days_val <= 7

    def test_within_7_days_edge(self):
        from ui.models.tacho_status_model import TachoStatusModel
        edge = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": edge})
        assert label.endswith("d")
        days_val = int(label.rstrip("d"))
        assert 0 <= days_val <= 7

    def test_within_30_days(self):
        from ui.models.tacho_status_model import TachoStatusModel
        soon = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": soon})
        assert label.endswith("d")
        days_val = int(label.rstrip("d"))
        assert 8 <= days_val <= 30

    def test_within_30_days_edge(self):
        from ui.models.tacho_status_model import TachoStatusModel
        edge = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": edge})
        assert label == "Valid" or (label.endswith("d") and int(label.rstrip("d")) <= 30)

    def test_valid(self):
        from ui.models.tacho_status_model import TachoStatusModel
        far = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": far})
        assert label == "Valid"

    def test_valid_out_of_range(self):
        from ui.models.tacho_status_model import TachoStatusModel
        # 60 days out → clearly valid (well beyond the 30-day threshold)
        far = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        label = TachoStatusModel._status_label({"calibration_expiry": far})
        assert label == "Valid"


# =========================================================================
# refresh()
# =========================================================================


class TestRefresh:
    """Data refresh through repository."""

    def test_refresh_populates_rows(self, qt_widget, qtbot):
        mock_repo = MagicMock()
        mock_repo.get_tacho_status_data.return_value = [
            {"truck_id": 10, "plate_number": "AG10ZZZ"},
        ]
        from ui.models.tacho_status_model import TachoStatusModel
        m = TachoStatusModel(qt_widget)
        with patch("ui.models.tacho_status_model.TachoVehicleDataRepository", return_value=mock_repo):
            m.refresh(db=MagicMock())
        assert m.rowCount() == 1
        assert m._rows[0]["truck_id"] == 10

    def test_refresh_with_empty_data(self, qt_widget, qtbot):
        mock_repo = MagicMock()
        mock_repo.get_tacho_status_data.return_value = []
        from ui.models.tacho_status_model import TachoStatusModel
        m = TachoStatusModel(qt_widget)
        with patch("ui.models.tacho_status_model.TachoVehicleDataRepository", return_value=mock_repo):
            m.refresh(db=MagicMock())
        assert m.rowCount() == 0

    def test_refresh_with_none_data(self, qt_widget, qtbot):
        mock_repo = MagicMock()
        mock_repo.get_tacho_status_data.return_value = None
        from ui.models.tacho_status_model import TachoStatusModel
        m = TachoStatusModel(qt_widget)
        with patch("ui.models.tacho_status_model.TachoVehicleDataRepository", return_value=mock_repo):
            m.refresh(db=MagicMock())
        assert m.rowCount() == 0  # None → empty list

    def test_refresh_raises_on_none_db(self, qt_widget, qtbot):
        from ui.models.tacho_status_model import TachoStatusModel
        m = TachoStatusModel(qt_widget)
        with pytest.raises(RuntimeError, match="requires local database"):
            m.refresh(db=None)

    def test_refresh_handles_repo_exception(self, qt_widget, qtbot):
        mock_repo = MagicMock()
        mock_repo.get_tacho_status_data.side_effect = RuntimeError("repo fail")
        from ui.models.tacho_status_model import TachoStatusModel
        m = TachoStatusModel(qt_widget)
        with patch("ui.models.tacho_status_model.TachoVehicleDataRepository", return_value=mock_repo):
            m.refresh(db=MagicMock())
        assert m.rowCount() == 0  # Falls back to empty list

    def test_refresh_emits_model_reset(self, qt_widget, qtbot):
        mock_repo = MagicMock()
        mock_repo.get_tacho_status_data.return_value = [{"truck_id": 1}]
        from ui.models.tacho_status_model import TachoStatusModel
        m = TachoStatusModel(qt_widget)
        with patch("ui.models.tacho_status_model.TachoVehicleDataRepository", return_value=mock_repo):
            with patch.object(m, "beginResetModel") as begin, patch.object(m, "endResetModel") as end:
                m.refresh(db=MagicMock())
                begin.assert_called_once()
                end.assert_called_once()


# =========================================================================
# truck_id_at
# =========================================================================


class TestTruckIdAt:
    """Lookup truck_id by row index."""

    def test_valid_row(self, populated_model):
        assert populated_model.truck_id_at(0) == 1
        assert populated_model.truck_id_at(1) == 2

    def test_negative_row(self, populated_model):
        assert populated_model.truck_id_at(-1) is None

    def test_out_of_range_row(self, populated_model):
        assert populated_model.truck_id_at(999) is None

    def test_empty_model(self, model):
        assert model.truck_id_at(0) is None

    def test_row_without_truck_id(self, populated_model):
        populated_model._rows[0] = {}
        assert populated_model.truck_id_at(0) is None


# =========================================================================
# _format_cell edge cases
# =========================================================================


class TestFormatCell:
    """Static formatting helper."""

    def test_plate_with_full_data(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"plate_number": "AB123CD"}, 0)
        assert result == "AB123CD"

    def test_plate_none(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"plate_number": None}, 0)
        assert result == "\u2014"

    def test_plate_missing_key(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({}, 0)
        assert result == "\u2014"

    def test_imported_at_datetime(self):
        from ui.models.tacho_status_model import TachoStatusModel
        from datetime import datetime
        result = TachoStatusModel._format_cell({"imported_at": datetime(2026, 6, 15, 14, 30)}, 1)
        assert result == "2026-06-15"

    def test_imported_at_none(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"imported_at": None}, 1)
        assert result == "\u2014"

    def test_calibration_date_string(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"calibration_date": "2025-03-10"}, 2)
        assert result == "2025-03-10"

    def test_calibration_date_none(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"calibration_date": None}, 2)
        assert result == "\u2014"

    def test_expiry_string(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"calibration_expiry": "2025-03-10"}, 3)
        assert result == "2025-03-10"

    def test_expiry_none(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({"calibration_expiry": None}, 3)
        assert result == "\u2014"

    def test_status_column_delegates(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({}, 4)
        # No data → No data status
        assert result == "No data"

    def test_unexpected_column(self):
        from ui.models.tacho_status_model import TachoStatusModel
        result = TachoStatusModel._format_cell({}, 99)
        assert result == ""


# =========================================================================
# Data transformation — ensure all column constants are consistent
# =========================================================================


class TestDataConsistency:
    """Column indices and header arrays are consistent."""

    def test_column_constants_in_range(self):
        from ui.models.tacho_status_model import TachoStatusModel
        assert TachoStatusModel.COL_PLATE == 0
        assert TachoStatusModel.COL_LAST_IMPORT == 1
        assert TachoStatusModel.COL_CALIBRATION_DATE == 2
        assert TachoStatusModel.COL_EXPIRY == 3
        assert TachoStatusModel.COL_STATUS == 4

    def test_headers_match_column_count(self):
        from ui.models.tacho_status_model import TachoStatusModel
        assert len(TachoStatusModel._HEADERS) == 5


# =========================================================================
# Edge cases — empty model
# =========================================================================


class TestEmptyModel:
    """All methods work on an empty model."""

    def test_row_count_zero(self, model):
        assert model.rowCount() == 0

    def test_data_returns_none(self, model):
        idx = model.index(0, 0)
        assert model.data(idx) is None

    def test_truck_id_at_none(self, model):
        assert model.truck_id_at(0) is None

    def test_header_data_still_works(self, model):
        h = model.headerData(0, Qt.Horizontal, Qt.DisplayRole)
        assert isinstance(h, str)
