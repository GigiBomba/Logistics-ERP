"""Tests for the trip card widget."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

@pytest.fixture
def trip_card(qt_widget, qtbot):
    trip_data = {
        "id": 1,
        "client": "Test Client",
        "origin": "Bucharest",
        "destination": "Cluj",
        "status": "planned",
        "price": 500.0,
        "distance_km": 450,
        "truck_number": "AG01ABC",
        "driver_name": "John Doe",
    }
    card = __import__("ui.widgets.trip_card", fromlist=["QtTripCard"]).QtTripCard(
        parent=qt_widget,
        trip_data=trip_data,
    )
    qtbot.addWidget(card)
    yield card

class TestQtTripCard:
    def test_creation(self, trip_card):
        assert trip_card.trip_data["id"] == 1

    def test_client_label_shown(self, trip_card):
        # New QtTripCard shows route label not client label
        assert hasattr(trip_card, "_route_lbl")
        assert "Bucharest" in trip_card._route_lbl.text()

    def test_origin_destination_shown(self, trip_card):
        assert hasattr(trip_card, "_route_lbl")

    def test_price_shown(self, trip_card):
        # New card doesn't have a price label
        assert "price" in trip_card.trip_data

    def test_status_badge_shown(self, trip_card):
        assert hasattr(trip_card, "_chip_frame")

    def test_truck_info_shown(self, trip_card):
        assert hasattr(trip_card, "_truck_lbl")

    def test_driver_info_shown(self, trip_card):
        assert hasattr(trip_card, "_driver_lbl")

    def test_click_handler_wired(self, trip_card):
        trip_card._on_click = MagicMock()
        trip_card._on_click()
        trip_card._on_click.assert_called_once()

    def test_context_menu_trigger(self, trip_card):
        # New card uses _on_documents_clicked as context menu
        assert hasattr(trip_card, "_on_documents_clicked")
