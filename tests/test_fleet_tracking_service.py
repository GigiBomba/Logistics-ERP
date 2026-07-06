"""Tests for fleet_tracking_service adapters and FleetTrackingService."""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.fleet_tracking_service import (
    BaseTrackingAdapter,
    FleetTrackingService,
    FrotcomAdapter,
    GenericRestAdapter,
    NavixyAdapter,
    TraccarAdapter,
    VehiclePosition,
    WialonAdapter,
)


@pytest.fixture(autouse=True)
def reset_fleet_singleton():
    FleetTrackingService._instance = None
    yield


class TestVehiclePosition:
    def test_defaults(self):
        vp = VehiclePosition()
        assert vp.device_id == ""
        assert vp.latitude == 0.0
        assert vp.status == "offline"
        assert vp.ignition_on is False


class TestWialonAdapter:
    @patch("services.fleet_tracking_service.requests.get")
    def test_login_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"eid": "session123"},
        )
        adapter = WialonAdapter(token="test_token")
        assert adapter._login() is True
        assert adapter._session_id == "session123"

    @patch("services.fleet_tracking_service.requests.get")
    def test_login_failure(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"error": 1},
        )
        adapter = WialonAdapter(token="bad_token")
        assert adapter._login() is False
        assert adapter._session_id is None

    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [
                    {
                        "id": 1001,
                        "nm": "Truck 1",
                        "pos": {"y": 45.0, "x": 24.0, "s": 50, "c": 180, "t": 1700000000},
                        "lmsg": {"p": {"mileage": 50000}},
                    }
                ]
            },
        )
        adapter = WialonAdapter(token="test", host="https://hst-api.wialon.com")
        adapter._session_id = "sid123"

        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].device_id == "1001"
        assert positions[0].name == "Truck 1"
        assert positions[0].latitude == 45.0
        assert positions[0].speed_kmh == 50
        assert positions[0].status == "moving"

    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions_auto_login(self, mock_get):
        mock_responses = [
            MagicMock(status_code=200, json=lambda: {"eid": "sid_auto"}),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "items": [
                        {"id": 1, "nm": "Truck", "pos": {"y": 45.0, "x": 24.0, "s": 0, "c": 0, "t": 0}}
                    ]
                },
            ),
        ]
        mock_get.side_effect = mock_responses
        adapter = WialonAdapter(token="test")
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert mock_get.call_count == 2  # login + search

    @patch("services.fleet_tracking_service.requests.get")
    def test_test_connection(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"eid": "sid"},
        )
        adapter = WialonAdapter(token="test")
        success, msg = adapter.test_connection()
        assert success is True
        assert "vehicle" in msg.lower()


class TestFrotcomAdapter:
    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": "1", "plate": "AB123CD", "latitude": 45.0, "longitude": 24.0, "speed": 60},
            ],
        )
        adapter = FrotcomAdapter(username="u", password="p")
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].name == "AB123CD"
        assert positions[0].status == "moving"

    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions_filters_missing_coords(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {"id": "1", "plate": "AB123CD", "latitude": None, "longitude": None},
                {"id": "2", "plate": "CD456EF", "latitude": 46.0, "longitude": 25.0},
            ],
        )
        adapter = FrotcomAdapter(username="u", password="p")
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].device_id == "2"

    @patch("services.fleet_tracking_service.requests.get")
    def test_test_connection_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"id": 1}, {"id": 2}],
        )
        adapter = FrotcomAdapter(username="u", password="p")
        success, msg = adapter.test_connection()
        assert success is True

    @patch("services.fleet_tracking_service.requests.get")
    def test_test_connection_http_error(self, mock_get):
        mock_get.return_value = MagicMock(status_code=401, text="Unauthorized")
        adapter = FrotcomAdapter(username="u", password="p")
        success, msg = adapter.test_connection()
        assert success is False


class TestTraccarAdapter:
    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    "deviceId": 42,
                    "deviceName": "Truck 42",
                    "latitude": 45.5,
                    "longitude": 23.5,
                    "speed": 30,
                    "course": 90,
                    "fixTime": "2024-01-15T10:30:00Z",
                    "attributes": {"totalDistance": 100000, "ignition": True},
                }
            ],
        )
        adapter = TraccarAdapter(url="http://traccar:8082", email="a@b.com", password="p")
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].device_id == "42"
        assert positions[0].speed_kmh == pytest.approx(30 * 1.852, rel=0.01)
        assert positions[0].ignition_on is True

    @patch("services.fleet_tracking_service.requests.get")
    def test_test_connection(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"id": 1}, {"id": 2}],
        )
        adapter = TraccarAdapter(url="http://t:8082", email="a@b.com", password="p")
        success, msg = adapter.test_connection()
        assert success is True


class TestNavixyAdapter:
    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "list": [
                    {"id": 1, "label": "Tracker1", "lat": 45.0, "lng": 24.0, "speed": 40},
                ]
            },
        )
        adapter = NavixyAdapter(api_key="key123")
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].name == "Tracker1"

    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions_skips_missing_coords(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "list": [
                    {"id": 1, "label": "T1"},
                    {"id": 2, "label": "T2", "lat": 46.0, "lng": 25.0},
                ]
            },
        )
        adapter = NavixyAdapter(api_key="key123")
        positions = adapter.get_positions()
        assert len(positions) == 1

    @patch("services.fleet_tracking_service.requests.get")
    def test_test_connection(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"list": [{"id": 1}]},
        )
        adapter = NavixyAdapter(api_key="key123")
        success, msg = adapter.test_connection()
        assert success is True


class TestGenericRestAdapter:
    def test_resolve_path_nested(self):
        adapter = GenericRestAdapter(url="http://example.com/api")
        data = {"data": {"vehicles": [{"id": 1}]}}
        result = adapter._resolve_path(data, "data.vehicles")
        assert result == [{"id": 1}]

    def test_resolve_path_missing(self):
        adapter = GenericRestAdapter(url="http://example.com/api")
        result = adapter._resolve_path({"a": 1}, "b.c")
        assert result is None

    @patch("services.fleet_tracking_service.requests.get")
    def test_get_positions(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": {"vehicles": [
                {"id": "v1", "name": "Van1", "lat": 45.0, "lng": 24.0, "speed": 20},
            ]}},
        )
        adapter = GenericRestAdapter(
            url="http://api.com/v", positions_path="data.vehicles",
        )
        positions = adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].name == "Van1"

    @patch("services.fleet_tracking_service.requests.get")
    def test_no_url(self, mock_get):
        adapter = GenericRestAdapter(url="")
        positions = adapter.get_positions()
        assert positions == []
        mock_get.assert_not_called()


class TestFleetTrackingService:
    def test_singleton(self):
        fs1 = FleetTrackingService()
        fs2 = FleetTrackingService()
        assert fs1 is fs2

    def test_not_configured_initially(self):
        fs = FleetTrackingService()
        assert fs.is_configured() is False

    def test_test_connection_no_adapter(self):
        fs = FleetTrackingService()
        success, msg = fs.test_connection()
        assert success is False
        assert "No platform configured" in msg

    @patch("services.fleet_tracking_service.FleetTrackingService._create_adapter")
    def test_initialize_creates_adapter(self, mock_create):
        mock_db = MagicMock()
        mock_db.get_setting.return_value = "wialon"
        mock_adapter = MagicMock()
        mock_create.return_value = mock_adapter

        fs = FleetTrackingService()
        fs.initialize(db=mock_db)

        assert fs.is_configured() is True
        mock_create.assert_called_once_with("wialon")

    def test_get_positions_returns_empty_without_adapter(self):
        fs = FleetTrackingService()
        assert fs.get_positions() == []

    @patch("services.fleet_tracking_service.FleetTrackingService._create_adapter")
    def test_get_positions_delegates_to_adapter(self, mock_create):
        mock_adapter = MagicMock()
        mock_adapter.get_positions.return_value = [VehiclePosition(device_id="1")]
        mock_create.return_value = mock_adapter

        fs = FleetTrackingService()
        fs._adapter = mock_adapter
        fs._last_poll = None

        positions = fs.get_positions(force_refresh=True)
        assert len(positions) == 1
        mock_adapter.get_positions.assert_called_once()

    def test_match_to_truck_no_db(self):
        fs = FleetTrackingService()
        result = fs.match_to_truck(VehiclePosition(name="AB123CD"))
        assert result is None

    @patch("repositories.fleet_repository.FleetRepository")
    def test_match_to_truck_by_plate(self, mock_fleet_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_by_plate.return_value = {"id": 42}
        mock_fleet_repo_cls.return_value = mock_repo

        fs = FleetTrackingService()
        fs._db = MagicMock()
        result = fs.match_to_truck(VehiclePosition(name="AB123CD"))
        assert result == 42
        mock_repo.get_by_plate.assert_called_once_with("AB123CD")

    def test_create_adapter_wialon(self):
        mock_db = MagicMock()
        mock_db.get_setting.side_effect = lambda k: {
            "tracking.token": "tok123",
            "tracking.host": "https://hst-api.wialon.com",
        }.get(k, "")
        fs = FleetTrackingService()
        fs._db = mock_db
        adapter = fs._create_adapter("wialon")
        assert isinstance(adapter, WialonAdapter)
        assert adapter.token == "tok123"

    def test_create_adapter_not_configured(self):
        fs = FleetTrackingService()
        assert fs._create_adapter("not configured") is None
        assert fs._create_adapter("") is None
