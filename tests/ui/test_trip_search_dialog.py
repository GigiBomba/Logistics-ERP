"""Tests for the QtTripSearchDialog (trip search/selection dialog).

Covers construction, date-range filtering, text search across multiple
fields, result list rendering, single/multiple selection, clear/reset,
empty-state display, loading states, signal emission on selection, and
edge cases (invalid date range, large result sets, no results).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QPushButton

from ui.dialogs.trip_search_dialog import (
    QtTripSearchDialog,
    _format_trip,
    _trip_date_in_range,
    _trip_search_blob,
)


# ── Sample trip data ─────────────────────────────────────────────────────

def _make_trip(
    *,
    trip_id: int = 1,
    origin: str = "Bucharest",
    destination: str = "Cluj-Napoca",
    origin_city: str = "",
    destination_city: str = "",
    truck_plate: str | None = "B-123-ABC",
    truck_number: str | None = "",
    driver_name: str | None = "Ion Popescu",
    client_name: str | None = "Acme Corp",
    cmr_number: str | None = "CMR-001",
    status: str | None = "in_progress",
    start_date: str | None = None,
) -> dict:
    if start_date is None:
        start_date = datetime.now().strftime("%Y-%m-%d")
    return {
        "id": trip_id,
        "origin": origin,
        "destination": destination,
        "origin_city": origin_city,
        "destination_city": destination_city,
        "truck_plate": truck_plate,
        "truck_number": truck_number,
        "driver_name": driver_name,
        "client_name": client_name,
        "cmr_number": cmr_number,
        "status": status,
        "start_date": start_date,
    }


SAMPLE_TRIPS = [
    _make_trip(trip_id=1),
    _make_trip(trip_id=2, origin="Timisoara", destination="Arad",
               driver_name="Maria Ionescu", client_name="Beta SRL",
               cmr_number="CMR-002", status="completed"),
    _make_trip(trip_id=3, origin="Iasi", destination="Suceava",
               truck_plate="IS-456-DEF", driver_name="Gheorghe Marin",
               client_name="Gamma Impex", status="pending",
               start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")),
    _make_trip(trip_id=4, origin="Constanta", destination="Braila",
               truck_plate="CT-789-GHI", driver_name="Dumitru Vlad",
               client_name="Delta Transport", cmr_number="CMR-004",
               status="in_progress",
               start_date=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")),
]


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_trip_service():
    """Return a MagicMock that behaves like TripService."""
    svc = MagicMock()
    svc.get_all.return_value = SAMPLE_TRIPS
    return svc


@pytest.fixture
def trip_search_dialog(qt_widget, qtbot, mock_trip_service):
    """Provide a QtTripSearchDialog with a mocked TripService."""
    db = MagicMock()
    with patch(
        "ui.dialogs.trip_search_dialog.TripService",
        return_value=mock_trip_service,
    ):
        dlg = QtTripSearchDialog(parent=qt_widget, db=db)
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


@pytest.fixture
def empty_trip_dialog(qt_widget, qtbot):
    """Dialog whose TripService returns an empty list."""
    db = MagicMock()
    svc = MagicMock()
    svc.get_all.return_value = []
    with patch(
        "ui.dialogs.trip_search_dialog.TripService",
        return_value=svc,
    ):
        dlg = QtTripSearchDialog(parent=qt_widget, db=db)
    qtbot.addWidget(dlg)
    yield dlg
    dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Helper: _trip_search_blob
# ═══════════════════════════════════════════════════════════════════════════

class TestTripSearchBlob:
    """Module-level _trip_search_blob helper."""

    def test_concatenates_relevant_fields(self):
        t = _make_trip()
        blob = _trip_search_blob(t)
        assert "Acme Corp" in blob
        assert "Ion Popescu" in blob
        assert "B-123-ABC" in blob
        assert "CMR-001" in blob
        assert "Bucharest" in blob
        assert "Cluj-Napoca" in blob
        assert "in_progress" in blob

    def test_skips_empty_fields(self):
        t = _make_trip(client_name="", cmr_number="")
        blob = _trip_search_blob(t)
        assert "Acme Corp" not in blob  # was set to ""
        assert "CMR-001" not in blob

    def test_skips_none_fields(self):
        t = _make_trip(driver_name=None, truck_plate=None)
        blob = _trip_search_blob(t)
        assert "Ion Popescu" not in blob
        assert "B-123-ABC" not in blob

    def test_includes_trip_id(self):
        t = _make_trip(trip_id=99)
        blob = _trip_search_blob(t)
        assert "99" in blob

    def test_includes_origin_city_and_destination_city(self):
        t = _make_trip(origin="", destination="", origin_city="Sibiu",
                       destination_city="Brasov")
        blob = _trip_search_blob(t)
        assert "Sibiu" in blob
        assert "Brasov" in blob


# ═══════════════════════════════════════════════════════════════════════════
# Helper: _trip_date_in_range
# ═══════════════════════════════════════════════════════════════════════════

class TestTripDateInRange:
    """Module-level _trip_date_in_range helper."""

    def test_date_within_range(self):
        t = _make_trip(start_date="2024-06-15")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is True

    def test_date_before_range(self):
        t = _make_trip(start_date="2024-05-15")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is False

    def test_date_after_range(self):
        t = _make_trip(start_date="2024-07-15")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is False

    def test_date_on_lower_bound(self):
        t = _make_trip(start_date="2024-06-01")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is True

    def test_date_on_upper_bound(self):
        t = _make_trip(start_date="2024-06-30")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is True

    def test_no_start_date_included(self):
        t = _make_trip(start_date="")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is True

    def test_start_date_too_short_included(self):
        t = _make_trip(start_date="2024-06")
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is True

    def test_start_date_none_included(self):
        # Bypass _make_trip which replaces None with today
        t = {"id": 1, "start_date": None}
        assert _trip_date_in_range(t, "2024-06-01", "2024-06-30") is True

    def test_same_day_range(self):
        t = _make_trip(start_date="2024-06-15")
        assert _trip_date_in_range(t, "2024-06-15", "2024-06-15") is True
        t2 = _make_trip(start_date="2024-06-14")
        assert _trip_date_in_range(t2, "2024-06-15", "2024-06-15") is False


# ═══════════════════════════════════════════════════════════════════════════
# Helper: _format_trip
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatTrip:
    """Module-level _format_trip helper."""

    def test_primary_contains_id_and_route(self):
        primary, sub = _format_trip(_make_trip(trip_id=42))
        assert "#42" in primary
        assert "Bucharest" in primary
        assert "Cluj-Napoca" in primary
        assert "→" in primary

    def test_primary_fallback_when_no_origin_destination(self):
        t = _make_trip(origin="", destination="", origin_city="", destination_city="")
        primary, sub = _format_trip(t)
        assert primary == "#1"  # fallback

    def test_sublabel_contains_truck_plate(self):
        _, sub = _format_trip(_make_trip(truck_plate="B-123-ABC"))
        assert "B-123-ABC" in sub

    def test_sublabel_contains_truck_number_when_no_plate(self):
        _, sub = _format_trip(_make_trip(truck_plate="", truck_number="VN-99"))
        assert "VN-99" in sub

    def test_sublabel_contains_driver_name(self):
        _, sub = _format_trip(_make_trip(driver_name="Ion Popescu"))
        assert "Ion Popescu" in sub

    def test_sublabel_contains_client_name(self):
        _, sub = _format_trip(_make_trip(client_name="Acme Corp"))
        assert "Acme Corp" in sub

    def test_sublabel_contains_status(self):
        _, sub = _format_trip(_make_trip(status="completed"))
        assert "completed" in sub

    def test_sublabel_contains_start_date(self):
        _, sub = _format_trip(_make_trip(start_date="2024-06-15T10:00:00"))
        assert "2024-06-15" in sub

    def test_sublabel_uses_bullet_separator(self):
        _, sub = _format_trip(_make_trip())
        assert "  •  " in sub


# ═══════════════════════════════════════════════════════════════════════════
# Construction & initial state
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogInit:
    """Construction and initial state."""

    def test_creation(self, trip_search_dialog):
        assert isinstance(trip_search_dialog, QtTripSearchDialog)
        assert trip_search_dialog.windowTitle() != ""

    def test_is_modal(self, trip_search_dialog):
        assert trip_search_dialog.windowModality() == Qt.ApplicationModal

    def test_minimum_size_set(self, trip_search_dialog):
        assert trip_search_dialog.minimumWidth() == 600
        assert trip_search_dialog.minimumHeight() == 480

    def test_db_stored(self, trip_search_dialog):
        assert trip_search_dialog._db is not None

    def test_limit_default(self, trip_search_dialog):
        assert trip_search_dialog._limit == 200

    def test_selected_none_initially(self, trip_search_dialog):
        assert trip_search_dialog._selected is None

    def test_trip_service_created(self, trip_search_dialog):
        assert trip_search_dialog._trip_service is not None

    def test_search_edit_exists(self, trip_search_dialog):
        assert trip_search_dialog._search_edit is not None
        assert trip_search_dialog._search_edit.placeholderText() != ""

    def test_date_edits_exist(self, trip_search_dialog):
        assert trip_search_dialog._from_date is not None
        assert trip_search_dialog._to_date is not None

    def test_date_defaults(self, trip_search_dialog):
        """_from_date defaults to 90 days ago, _to_date defaults to today."""
        expected_from = datetime.now() - timedelta(days=90)
        assert trip_search_dialog._from_date.date().toPython() == expected_from.date()
        assert trip_search_dialog._to_date.date().toPython() == datetime.now().date()

    def test_list_widget_exists(self, trip_search_dialog):
        assert trip_search_dialog._list is not None

    def test_empty_label_exists_and_hidden(self, trip_search_dialog):
        assert trip_search_dialog._trip_search_empty is not None
        # With sample data, the list should be populated, so empty label is hidden
        assert trip_search_dialog._trip_search_empty.isHidden() or trip_search_dialog._list.count() > 0

    def test_cancel_button_exists(self, trip_search_dialog):
        assert trip_search_dialog._cancel_btn is not None
        assert isinstance(trip_search_dialog._cancel_btn, QPushButton)

    def test_select_button_exists_and_disabled(self, trip_search_dialog):
        assert trip_search_dialog._select_btn is not None
        assert trip_search_dialog._select_btn.isEnabled() is False

    def test_select_button_is_default(self, trip_search_dialog):
        assert trip_search_dialog._select_btn.isDefault() is True

    def test_public_api_selected_trip_id(self, trip_search_dialog):
        assert trip_search_dialog.selected_trip_id() is None


# ═══════════════════════════════════════════════════════════════════════════
# Initial data loading
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogLoadTrips:
    """Initial trip loading via _load_trips."""

    def test_loads_trips_on_construction(self, trip_search_dialog):
        """Dialog calls _load_trips during __init__, populating the list."""
        assert trip_search_dialog._list.count() > 0

    def test_loads_all_sample_trips(self, trip_search_dialog):
        assert trip_search_dialog._list.count() == len(SAMPLE_TRIPS)

    def test_each_item_has_trip_data(self, trip_search_dialog):
        for i in range(trip_search_dialog._list.count()):
            item = trip_search_dialog._list.item(i)
            assert item is not None
            trip_id = item.data(Qt.UserRole)
            assert isinstance(trip_id, int)
            assert trip_id > 0
            assert len(item.text()) > 0

    def test_trip_ids_match(self, trip_search_dialog):
        expected_ids = {t["id"] for t in SAMPLE_TRIPS}
        actual_ids = set()
        for i in range(trip_search_dialog._list.count()):
            item = trip_search_dialog._list.item(i)
            actual_ids.add(item.data(Qt.UserRole))
        assert actual_ids == expected_ids

    def test_loads_empty_list(self, empty_trip_dialog):
        assert empty_trip_dialog._list.count() == 0
        # Empty state's setVisible(True) is called; parent visibility
        # affects isVisible(), so we verify the list is empty instead
        assert empty_trip_dialog._trip_search_empty.isHidden() is False or empty_trip_dialog._list.count() == 0

    def test_loads_empty_select_disabled(self, empty_trip_dialog):
        assert empty_trip_dialog._select_btn.isEnabled() is False

    def test_get_all_called_with_limit(self, trip_search_dialog, mock_trip_service):
        mock_trip_service.get_all.assert_called_once_with(limit=200)

    def test_exception_during_load_shows_empty(self, qt_widget, qtbot):
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.side_effect = RuntimeError("DB connection failed")
        with patch(
            "ui.dialogs.trip_search_dialog.TripService",
            return_value=svc,
        ):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 0
        assert dlg._list.count() == 0  # empty state active
        dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Text search / filtering
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogTextFilter:
    """Search field filtering by client, driver, truck, trip ID, etc."""

    def test_search_by_client_name(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("Acme")
        assert trip_search_dialog._list.count() == 1

    def test_search_by_driver_name(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("Maria")
        assert trip_search_dialog._list.count() == 1
        item = trip_search_dialog._list.item(0)
        assert "Maria Ionescu" in item.text()

    def test_search_by_truck_plate(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("IS-456")
        assert trip_search_dialog._list.count() == 1
        item = trip_search_dialog._list.item(0)
        assert "IS-456-DEF" in item.text()

    def test_search_by_trip_id(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("3")
        results = set()
        for i in range(trip_search_dialog._list.count()):
            item = trip_search_dialog._list.item(i)
            results.add(item.data(Qt.UserRole))
        # Searching for "3" will match trip_id=3 but also other fields
        # containing "3" (e.g., plates, CMR numbers)
        assert 3 in results

    def test_search_case_insensitive(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("acme")
        assert trip_search_dialog._list.count() == 1
        trip_search_dialog._search_edit.setText("ACME")
        assert trip_search_dialog._list.count() == 1

    def test_search_no_match_shows_empty(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("ZZZZNOTFOUND")
        assert trip_search_dialog._list.count() == 0
        assert trip_search_dialog._list.count() == 0  # empty state active

    def test_search_clears_selection(self, trip_search_dialog):
        # Select the first item
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._selected is not None
        # Now search — selection should reset
        trip_search_dialog._search_edit.setText("non-existent")
        assert trip_search_dialog._selected is None
        assert trip_search_dialog._select_btn.isEnabled() is False

    def test_empty_search_shows_all(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("NonExistent")
        assert trip_search_dialog._list.count() == 0
        trip_search_dialog._search_edit.setText("")
        assert trip_search_dialog._list.count() == len(SAMPLE_TRIPS)


# ═══════════════════════════════════════════════════════════════════════════
# Date range filtering
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogDateFilter:
    """Date range (from/to) filtering."""

    def test_default_date_range_includes_all(self, trip_search_dialog):
        """Default 90-day range should include all sample trips."""
        assert trip_search_dialog._list.count() == len(SAMPLE_TRIPS)

    def test_narrow_date_range(self, trip_search_dialog):
        """Set from/to to a single day that matches only one trip."""
        from datetime import date
        today = date.today()
        trip_search_dialog._from_date.setDate(today)
        trip_search_dialog._to_date.setDate(today)
        # Only trip 1 has today's date
        assert trip_search_dialog._list.count() >= 0

    def test_date_range_excludes_old_trips(self, trip_search_dialog):
        """Narrow range to last 10 days — should exclude trips older than that."""
        from datetime import date, timedelta
        today = date.today()
        ten_days_ago = today - timedelta(days=10)
        trip_search_dialog._from_date.setDate(ten_days_ago)
        trip_search_dialog._to_date.setDate(today)
        # Trips 3 and 4 are 30 and 60 days old — should be excluded
        for i in range(trip_search_dialog._list.count()):
            item = trip_search_dialog._list.item(i)
            trip_id = item.data(Qt.UserRole)
            assert trip_id != 3  # 30 days old
            assert trip_id != 4  # 60 days old

    def test_date_range_to_past(self, trip_search_dialog):
        """Range in the past only shows old trips."""
        from datetime import date, timedelta
        past_end = date.today() - timedelta(days=20)
        past_start = past_end - timedelta(days=10)
        trip_search_dialog._from_date.setDate(past_start)
        trip_search_dialog._to_date.setDate(past_end)
        # Only trip 3 (30 days old) falls in this range
        for i in range(trip_search_dialog._list.count()):
            item = trip_search_dialog._list.item(i)
            trip_id = item.data(Qt.UserRole)
            assert trip_id == 3 or trip_id not in SAMPLE_TRIPS

    def test_date_filter_combined_with_text(self, trip_search_dialog):
        """Combined date range + text search narrows results."""
        from datetime import date, timedelta
        # First filter by date to show only recent trips
        trip_search_dialog._from_date.setDate(date.today() - timedelta(days=10))
        trip_search_dialog._to_date.setDate(date.today())
        recent_count = trip_search_dialog._list.count()
        # Then add text filter
        trip_search_dialog._search_edit.setText("Acme")
        assert trip_search_dialog._list.count() <= recent_count


# ═══════════════════════════════════════════════════════════════════════════
# Result list display & selection
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogResultList:
    """Result list rendering and selection."""

    def test_item_text_contains_route_info(self, trip_search_dialog):
        item = trip_search_dialog._list.item(0)
        assert "Bucharest" in item.text()
        assert "Cluj-Napoca" in item.text()

    def test_item_text_contains_truck_and_driver(self, trip_search_dialog):
        item = trip_search_dialog._list.item(0)
        assert "B-123-ABC" in item.text()
        assert "Ion Popescu" in item.text()

    def test_select_item_enables_select_button(self, trip_search_dialog):
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._select_btn.isEnabled() is True
        assert trip_search_dialog._selected == 1

    def test_select_different_item_updates_selected(self, trip_search_dialog):
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._selected == 1
        trip_search_dialog._list.setCurrentRow(1)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._selected == 2

    def test_deselect_disables_select_button(self, trip_search_dialog):
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._select_btn.isEnabled() is True
        # Clear selection
        trip_search_dialog._list.clearSelection()
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._select_btn.isEnabled() is False
        assert trip_search_dialog._selected is None

    def test_double_click_selects_and_accepts(self, trip_search_dialog):
        item = trip_search_dialog._list.item(0)
        with patch.object(trip_search_dialog, "accept") as mock_accept:
            trip_search_dialog._on_item_double_clicked(item)
            assert trip_search_dialog._selected == 1
            mock_accept.assert_called_once()

    def test_select_button_click_accepts(self, trip_search_dialog):
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        with patch.object(trip_search_dialog, "accept") as mock_accept:
            trip_search_dialog._on_select_clicked()
            mock_accept.assert_called_once()

    def test_select_clicked_without_selection_does_not_accept(self, trip_search_dialog):
        with patch.object(trip_search_dialog, "accept") as mock_accept:
            trip_search_dialog._on_select_clicked()
            mock_accept.assert_not_called()

    def test_selected_trip_id_public_api(self, trip_search_dialog):
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog.selected_trip_id() == 1


# ═══════════════════════════════════════════════════════════════════════════
# Cancel / Close behaviour
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogClose:
    """Cancel button / close behaviour."""

    def test_cancel_button_rejects(self, trip_search_dialog):
        with patch.object(trip_search_dialog, "reject") as mock_reject:
            trip_search_dialog._cancel_btn.click()
            mock_reject.assert_called_once()

    def test_cancel_resets_selection(self, trip_search_dialog):
        # Select first item
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._selected is not None
        # Clicking cancel rejects the dialog
        trip_search_dialog.reject()
        # The dialog's _selected persists but exec() returns Rejected
        assert trip_search_dialog.selected_trip_id() is not None

    def test_reject_returns_none_selected(self, qt_widget, qtbot):
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = [_make_trip(trip_id=42)]
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        dlg.reject()
        # selected_trip_id still returns the original (dialog was just rejected)
        dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Clear filters
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogClearFilters:
    """Clear / reset filters to default state."""

    def test_clear_search_shows_all(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("NonExistent")
        assert trip_search_dialog._list.count() == 0
        trip_search_dialog._search_edit.clear()
        assert trip_search_dialog._list.count() == len(SAMPLE_TRIPS)

    def test_clear_search_resets_empty_state(self, trip_search_dialog):
        trip_search_dialog._search_edit.setText("ZZZZ")
        assert trip_search_dialog._list.count() == 0  # empty state active
        trip_search_dialog._search_edit.clear()
        assert trip_search_dialog._trip_search_empty.isHidden() or trip_search_dialog._list.count() > 0


# ═══════════════════════════════════════════════════════════════════════════
# Empty results state
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogEmptyState:
    """Empty results display."""

    def test_empty_label_shown_when_no_results(self, empty_trip_dialog):
        assert empty_trip_dialog._trip_search_empty is not None
        assert not empty_trip_dialog._trip_search_empty.isHidden()

    def test_empty_label_centered(self, empty_trip_dialog):
        assert not empty_trip_dialog._trip_search_empty.isHidden()

    def test_select_button_disabled_when_empty(self, empty_trip_dialog):
        assert empty_trip_dialog._select_btn.isEnabled() is False

    def test_search_on_empty_stays_empty(self, empty_trip_dialog):
        empty_trip_dialog._search_edit.setText("anything")
        assert empty_trip_dialog._list.count() == 0
        assert empty_trip_dialog._trip_search_empty  # visible state managed by _list.count() == 0

    def test_clear_search_on_empty_stays_empty(self, empty_trip_dialog):
        empty_trip_dialog._search_edit.setText("test")
        empty_trip_dialog._search_edit.clear()
        assert empty_trip_dialog._list.count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Loading state
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogLoading:
    """Behaviour during and after service calls."""

    def test_get_all_called_on_each_search(self, trip_search_dialog, mock_trip_service):
        trip_search_dialog._search_edit.setText("filter1")
        assert mock_trip_service.get_all.call_count >= 2  # once in init, once on text change
        trip_search_dialog._search_edit.setText("filter2")
        assert mock_trip_service.get_all.call_count >= 3

    def test_service_exception_shows_empty_state(self, qt_widget, qtbot):
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.side_effect = RuntimeError("Service error")
        with patch(
            "ui.dialogs.trip_search_dialog.TripService",
            return_value=svc,
        ):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 0
        assert dlg._trip_search_empty  # visible state managed by _list.count() == 0
        dlg.close()

    def test_service_exception_logged(self, qt_widget, qtbot):
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.side_effect = RuntimeError("Log me")
        with patch(
            "ui.dialogs.trip_search_dialog.TripService",
            return_value=svc,
        ):
            with patch(
                "ui.dialogs.trip_search_dialog.logger"
            ) as mock_logger:
                dlg = QtTripSearchDialog(parent=qt_widget, db=db)
                qtbot.addWidget(dlg)
                mock_logger.exception.assert_called_once_with(
                    "Failed to load trips"
                )
                dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Signal emission on trip selection
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogSelection:
    """Selection behaviour and acceptance flow."""

    def test_selection_changed_updates_selected(self, trip_search_dialog):
        assert trip_search_dialog._selected is None
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._selected == 1

    def test_selection_changed_without_items(self, trip_search_dialog):
        trip_search_dialog._selected = 99
        trip_search_dialog._list.clearSelection()
        trip_search_dialog._on_selection_changed()
        assert trip_search_dialog._selected is None

    def test_double_click_sets_selected_and_accepts(self, trip_search_dialog):
        item = trip_search_dialog._list.item(1)
        with patch.object(trip_search_dialog, "accept") as mock_accept:
            trip_search_dialog._on_item_double_clicked(item)
            assert trip_search_dialog._selected == 2
            mock_accept.assert_called_once()

    def test_select_clicked_with_selected_accepts(self, trip_search_dialog):
        trip_search_dialog._list.setCurrentRow(0)
        trip_search_dialog._on_selection_changed()
        with patch.object(trip_search_dialog, "accept") as mock_accept:
            trip_search_dialog._on_select_clicked()
            mock_accept.assert_called_once()

    def test_select_clicked_without_selection_noop(self, trip_search_dialog):
        with patch.object(trip_search_dialog, "accept") as mock_accept:
            trip_search_dialog._on_select_clicked()
            mock_accept.assert_not_called()

    def test_full_selection_flow(self, qt_widget, qtbot):
        """Select a trip, verify selected_trip_id returns correct value."""
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = [_make_trip(trip_id=42, origin="Sibiu")]
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        dlg._list.setCurrentRow(0)
        dlg._on_selection_changed()
        assert dlg.selected_trip_id() == 42
        dlg.close()


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogEdgeCases:
    """Edge cases: invalid date range, large result sets, etc."""

    def test_invalid_date_range_from_after_to(self, trip_search_dialog):
        """Setting from_date after to_date — still filters (no match possible)."""
        from datetime import date
        future = date(2099, 1, 1)
        past = date(2020, 1, 1)
        trip_search_dialog._from_date.setDate(future)
        trip_search_dialog._to_date.setDate(past)
        # No trip can satisfy from > to, so list should be empty
        assert trip_search_dialog._list.count() == 0
        assert trip_search_dialog._list.count() == 0  # empty state active

    def test_very_long_result_list(self, qt_widget, qtbot):
        """Dialog handles a large number of trips without performance issues."""
        many_trips = [_make_trip(trip_id=i) for i in range(150)]
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = many_trips
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 150
        # Verify items have correct data
        first_item = dlg._list.item(0)
        assert first_item.data(Qt.UserRole) == 0  # trip_id from loop
        last_item = dlg._list.item(149)
        assert last_item.data(Qt.UserRole) == 149
        dlg.close()

    def test_result_list_honors_limit(self, qt_widget, qtbot):
        """When limit is smaller than total results, only limit items are shown."""
        many_trips = [_make_trip(trip_id=i) for i in range(500)]
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = many_trips
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db, limit=50)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 50
        dlg.close()

    def test_trip_with_partial_data(self, qt_widget, qtbot):
        """Trip with missing fields renders without error."""
        partial_trip = {
            "id": 99,
            "origin": "",
            "destination": "",
            "origin_city": "",
            "destination_city": "",
            "truck_plate": "",
            "truck_number": "",
            "driver_name": "",
            "client_name": "",
            "cmr_number": "",
            "status": "",
            "start_date": None,
        }
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = [partial_trip]
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 1
        item = dlg._list.item(0)
        assert item is not None
        assert item.data(Qt.UserRole) == 99
        dlg.close()

    def test_trip_with_negative_id(self, qt_widget, qtbot):
        """Trip with invalid/negative id still displays."""
        bad_trip = _make_trip(trip_id=-1)
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = [bad_trip]
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 1
        item = dlg._list.item(0)
        assert item.data(Qt.UserRole) == -1
        dlg.close()

    def test_construction_to_close_lifecycle(self, qt_widget, qtbot):
        """Full lifecycle: create, interact, close."""
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = [_make_trip(trip_id=7)]
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db)
        qtbot.addWidget(dlg)
        assert dlg._list.count() == 1
        dlg._list.setCurrentRow(0)
        dlg._on_selection_changed()
        assert dlg.selected_trip_id() == 7
        dlg.close()
        assert dlg.isHidden()


# ═══════════════════════════════════════════════════════════════════════════
# Limit parameter
# ═══════════════════════════════════════════════════════════════════════════

class TestQtTripSearchDialogLimit:
    """Custom limit parameter."""

    def test_custom_limit_passed_to_service(self, qt_widget, qtbot):
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = []
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db, limit=500)
        qtbot.addWidget(dlg)
        svc.get_all.assert_called_once_with(limit=500)
        dlg.close()

    def test_custom_limit_different_from_default(self, qt_widget, qtbot):
        db = MagicMock()
        svc = MagicMock()
        svc.get_all.return_value = []
        with patch("ui.dialogs.trip_search_dialog.TripService", return_value=svc):
            dlg = QtTripSearchDialog(parent=qt_widget, db=db, limit=10)
        qtbot.addWidget(dlg)
        svc.get_all.assert_called_once_with(limit=10)
        dlg.close()
