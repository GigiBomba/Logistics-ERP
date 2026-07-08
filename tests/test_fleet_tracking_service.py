"""Tests for FleetTrackingService and associated tracking adapters.

Covers:
  - Singleton behavior (fresh after conftest reset)
  - WialonAdapter, FrotcomAdapter, TraccarAdapter, NavixyAdapter,
    GenericRestAdapter — get_positions and test_connection
  - FleetTrackingService — initialize, get_positions, test_connection,
    is_configured, match_to_truck
  - Mocked external HTTP calls via responses or unittest.mock
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests

from services.fleet_tracking_service import (
    BaseTrackingAdapter,
    FleetTrackingService,
    FrotcomAdapter,
    GenericRestAdapter,
    NavixyAdapter,
    TraccarAdapter,
    VehiclePosition,
    WialonAdapter,
    fleet_tracking_service,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset FleetTrackingService singleton before each test.

    The conftest reset_singletons fixture does this, but we make it
    explicit here for clarity.
    """
    FleetTrackingService._instance = None
    yield
    FleetTrackingService._instance = None


@pytest.fixture
def mock_db():
    """An in-memory Database-like object with a get_setting method."""
    db = MagicMock()
    db.get_setting.return_value = ""
    return db


@pytest.fixture
def service():
    return FleetTrackingService()


@pytest.fixture
def sample_position():
    return VehiclePosition(
        device_id="DEV-001",
        name="Truck-1",
        latitude=44.436,
        longitude=26.103,
        speed_kmh=65.0,
        heading=180.0,
        timestamp=datetime.utcnow(),
        status="moving",
        address="Bucharest, Romania",
        odometer_km=123456.7,
        ignition_on=True,
    )


# ── VehiclePosition dataclass ───────────────────────────────────────

class TestVehiclePosition:
    def test_defaults(self):
        pos = VehiclePosition()
        assert pos.device_id == ""
        assert pos.latitude == 0.0
        assert pos.longitude == 0.0
        assert pos.status == "offline"
        assert pos.ignition_on is False

    def test_custom_values(self, sample_position):
        assert sample_position.device_id == "DEV-001"
        assert sample_position.name == "Truck-1"
        assert sample_position.speed_kmh == 65.0


# ── Singleton behavior ──────────────────────────────────────────────

class TestSingleton:
    def test_same_instance(self):
        s1 = FleetTrackingService()
        s2 = FleetTrackingService()
        assert s1 is s2

    def test_initialized_once(self):
        s = FleetTrackingService()
        assert s._initialized is True
        assert s._adapter is None
        assert s._last_positions == []

    def test_reset_between_tests(self, reset_singleton):
        s1 = FleetTrackingService()
        s1._adapter = "something"
        # After reset_singleton, a new instance should be created
        FleetTrackingService._instance = None
        s2 = FleetTrackingService()
        assert s2._adapter is None


# ── FleetTrackingService — initialize ──────────────────────────────

class TestInitialize:
    def test_initialize_with_none_db(self, service):
        service.initialize(db=None)
        assert service._db is None

    def test_initialize_no_platform(self, service, mock_db):
        mock_db.get_setting.return_value = ""
        service.initialize(mock_db)
        assert service._adapter is None

    def test_initialize_not_configured(self, service, mock_db):
        mock_db.get_setting.return_value = "not configured"
        service.initialize(mock_db)
        assert service._adapter is None

    def test_initialize_wialon(self, service, mock_db):
        def get_setting(key):
            settings = {
                "tracking.platform": "wialon",
                "tracking.token": "test-token",
                "tracking.host": "https://hst-api.wialon.com",
            }
            return settings.get(key, "")
        mock_db.get_setting.side_effect = get_setting
        service.initialize(mock_db)
        assert isinstance(service._adapter, WialonAdapter)
        assert service.is_configured() is True

    def test_initialize_frotcom(self, service, mock_db):
        def get_setting(key):
            settings = {
                "tracking.platform": "frotcom",
                "tracking.username": "user",
                "tracking.password": "pass",
                "tracking.account": "acc",
            }
            return settings.get(key, "")
        mock_db.get_setting.side_effect = get_setting
        service.initialize(mock_db)
        assert isinstance(service._adapter, FrotcomAdapter)

    def test_initialize_traccar(self, service, mock_db):
        def get_setting(key):
            settings = {
                "tracking.platform": "traccar",
                "tracking.host": "http://traccar:8082",
                "tracking.username": "admin",
                "tracking.password": "admin",
            }
            return settings.get(key, "")
        mock_db.get_setting.side_effect = get_setting
        service.initialize(mock_db)
        assert isinstance(service._adapter, TraccarAdapter)

    def test_initialize_navixy(self, service, mock_db):
        def get_setting(key):
            settings = {
                "tracking.platform": "navixy",
                "tracking.token": "api-key-123",
                "tracking.host": "https://api.eu.navixy.com/v2",
            }
            return settings.get(key, "")
        mock_db.get_setting.side_effect = get_setting
        service.initialize(mock_db)
        assert isinstance(service._adapter, NavixyAdapter)

    def test_initialize_generic_rest(self, service, mock_db):
        def get_setting(key):
            settings = {
                "tracking.platform": "generic rest",
                "tracking.host": "http://example.com/api",
                "tracking.token": "Bearer xyz",
                "tracking.positions_path": "data.vehicles",
                "tracking.lat_field": "latitude",
                "tracking.lng_field": "longitude",
            }
            return settings.get(key, "")
        mock_db.get_setting.side_effect = get_setting
        service.initialize(mock_db)
        assert isinstance(service._adapter, GenericRestAdapter)


# ── FleetTrackingService — get_positions ───────────────────────────

class TestGetPositions:
    def test_no_adapter_returns_empty(self, service):
        assert service.get_positions() == []

    def test_calls_adapter_on_first_poll(self, service, sample_position):
        adapter = MagicMock(spec=BaseTrackingAdapter)
        adapter.get_positions.return_value = [sample_position]
        service._adapter = adapter

        result = service.get_positions()
        assert result == [sample_position]
        adapter.get_positions.assert_called_once()

    def test_uses_cache_within_interval(self, service, sample_position):
        adapter = MagicMock(spec=BaseTrackingAdapter)
        adapter.get_positions.return_value = [sample_position]
        service._adapter = adapter

        service.get_positions(force_refresh=False)
        service.get_positions(force_refresh=False)
        # Second call should NOT call adapter again (cached)
        adapter.get_positions.assert_called_once()

    def test_force_refresh_ignores_cache(self, service, sample_position):
        adapter = MagicMock(spec=BaseTrackingAdapter)
        adapter.get_positions.return_value = [sample_position]
        service._adapter = adapter

        service.get_positions(force_refresh=False)
        service.get_positions(force_refresh=True)
        assert adapter.get_positions.call_count == 2

    def test_cache_expires_after_interval(self, service, sample_position):
        adapter = MagicMock(spec=BaseTrackingAdapter)
        adapter.get_positions.return_value = [sample_position]
        service._adapter = adapter
        service._poll_interval = 0.001  # very short interval

        service.get_positions(force_refresh=False)
        service._last_poll = datetime.utcnow() - timedelta(seconds=10)
        service.get_positions(force_refresh=False)
        assert adapter.get_positions.call_count == 2

    def test_adapter_exception_returns_cached(self, service, sample_position):
        adapter = MagicMock(spec=BaseTrackingAdapter)
        adapter.get_positions.side_effect = [sample_position, RuntimeError("boom")]
        service._adapter = adapter

        result1 = service.get_positions(force_refresh=True)
        assert result1 == [sample_position]

        # Force another call; adapter raises but we return cached
        result2 = service.get_positions(force_refresh=True)
        assert result2 == [sample_position]


# ── FleetTrackingService — test_connection ─────────────────────────

class TestTestConnection:
    def test_no_adapter_returns_false(self, service):
        success, msg = service.test_connection()
        assert success is False
        assert "No platform" in msg

    def test_delegates_to_adapter(self, service):
        adapter = MagicMock(spec=BaseTrackingAdapter)
        adapter.test_connection.return_value = (True, "Connected — 5 vehicle(s)")
        service._adapter = adapter

        success, msg = service.test_connection()
        assert success is True
        assert "5 vehicle(s)" in msg


# ── FleetTrackingService — match_to_truck ──────────────────────────

class TestMatchToTruck:
    def test_no_db_returns_none(self, service, sample_position):
        assert service.match_to_truck(sample_position) is None

    def test_matches_by_plate(self, service, sample_position):
        db = MagicMock()
        service._db = db
        service._fleet_repo = MagicMock()
        service._fleet_repo.get_by_plate.return_value = {"id": 42}
        service._fleet_repo.get_by_tracking_device_id.return_value = None

        result = service.match_to_truck(sample_position)
        assert result == 42
        service._fleet_repo.get_by_plate.assert_called_with("Truck-1")

    def test_matches_by_device_id(self, service, sample_position):
        db = MagicMock()
        service._db = db
        service._fleet_repo = MagicMock()
        service._fleet_repo.get_by_plate.return_value = None
        service._fleet_repo.get_by_tracking_device_id.return_value = {"id": 99}

        result = service.match_to_truck(sample_position)
        assert result == 99
        service._fleet_repo.get_by_tracking_device_id.assert_called_with("DEV-001")


# ── WialonAdapter ──────────────────────────────────────────────────

class TestWialonAdapter:
    def test_get_positions_no_session_logs_in(self):
        adapter = WialonAdapter(token="test-token")
        with patch.object(adapter, "_login", return_value=True), \
             patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"items": []}
            result = adapter.get_positions()
        assert result == []

    def test_get_positions_login_fails_returns_empty(self):
        adapter = WialonAdapter(token="bad-token")
        with patch.object(adapter, "_login", return_value=False):
            result = adapter.get_positions()
        assert result == []

    def test_get_positions_parses_items(self):
        adapter = WialonAdapter(token="test-token")
        adapter._session_id = "sess-123"
        mock_response = {
            "items": [
                {
                    "id": 1001,
                    "nm": "Truck-1",
                    "pos": {"y": 44.4, "x": 26.1, "s": 50, "c": 90, "t": 1700000000, "a": "Addr"},
                    "lmsg": {"p": {"mileage": 123456789}},
                }
            ]
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].device_id == "1001"
        assert positions[0].name == "Truck-1"
        assert positions[0].latitude == 44.4
        assert positions[0].status == "moving"

    def test_test_connection_success(self):
        adapter = WialonAdapter(token="test-token")
        with patch.object(adapter, "_login", return_value=True), \
             patch.object(adapter, "get_positions", return_value=[VehiclePosition()]):
            success, msg = adapter.test_connection()
        assert success is True
        assert "vehicle(s)" in msg

    def test_test_connection_failure(self):
        adapter = WialonAdapter(token="bad-token")
        with patch.object(adapter, "_login", return_value=False):
            success, msg = adapter.test_connection()
        assert success is False


# ── FrotcomAdapter ─────────────────────────────────────────────────

class TestFrotcomAdapter:
    def test_get_positions_parses_vehicles(self):
        adapter = FrotcomAdapter(username="u", password="p")
        mock_response = [
            {"id": 1, "plate": "TRUCK-1", "latitude": 44.4, "longitude": 26.1, "speed": 60},
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_response
            positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].name == "TRUCK-1"

    def test_get_positions_non_200_returns_empty(self):
        adapter = FrotcomAdapter(username="u", password="p")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 401
            result = adapter.get_positions()
        assert result == []

    def test_test_connection_success(self):
        adapter = FrotcomAdapter(username="u", password="p")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = [{"id": 1}]
            success, msg = adapter.test_connection()
        assert success is True

    def test_test_connection_failure(self):
        adapter = FrotcomAdapter(username="u", password="p")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 403
            success, msg = adapter.test_connection()
        assert success is False


# ── TraccarAdapter ─────────────────────────────────────────────────

class TestTraccarAdapter:
    def test_get_positions_parses(self):
        adapter = TraccarAdapter(url="http://traccar:8082", email="a@b.com", password="p")
        mock_response = [
            {
                "deviceId": 2001,
                "deviceName": "Truck-A",
                "latitude": 45.0,
                "longitude": 25.0,
                "speed": 30.0,
                "course": 180,
                "fixTime": "2025-01-01T12:00:00Z",
                "attributes": {"totalDistance": 50000, "ignition": True},
            }
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].name == "Truck-A"
        # speed should be converted from knots to km/h (30 * 1.852)
        assert positions[0].speed_kmh == pytest.approx(55.56, rel=0.01)

    def test_get_positions_returns_empty_on_error(self):
        adapter = TraccarAdapter(url="http://invalid", email="a@b.com", password="p")
        with patch("requests.get", side_effect=RuntimeError("Connection failed")):
            result = adapter.get_positions()
        assert result == []


# ── NavixyAdapter ──────────────────────────────────────────────────

class TestNavixyAdapter:
    def test_get_positions_parses(self):
        adapter = NavixyAdapter(api_key="key-123")
        mock_response = {
            "list": [
                {"id": 3001, "label": "Truck-B", "lat": 46.0, "lng": 24.0, "speed": 40},
            ]
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].name == "Truck-B"

    def test_get_positions_empty_on_error(self):
        adapter = NavixyAdapter(api_key="bad-key")
        with patch("requests.get", side_effect=RuntimeError("API error")):
            result = adapter.get_positions()
        assert result == []


# ── GenericRestAdapter ─────────────────────────────────────────────

class TestGenericRestAdapter:
    def test_get_positions_no_url_returns_empty(self):
        adapter = GenericRestAdapter(url="")
        assert adapter.get_positions() == []

    def test_get_positions_parses_flattened(self):
        adapter = GenericRestAdapter(
            url="http://example.com/api",
            positions_path="data.vehicles",
            lat_field="lat",
            lng_field="lng",
            id_field="id",
        )
        mock_data = {
            "data": {
                "vehicles": [
                    {"id": "V1", "lat": 44.0, "lng": 25.0, "speed": 55, "name": "Van-1"},
                ]
            }
        }
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = mock_data
            positions = adapter.get_positions()

        assert len(positions) == 1
        assert positions[0].name == "Van-1"

    def test_get_positions_uses_auth_header(self):
        adapter = GenericRestAdapter(
            url="http://example.com/api",
            auth_header="Bearer token123",
        )
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = []
            adapter.get_positions()
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer token123"

    def test_test_connection_success(self):
        adapter = GenericRestAdapter(url="http://example.com/api")
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = []
            success, msg = adapter.test_connection()
        assert success is True


# ── BaseTrackingAdapter (abstract) ─────────────────────────────────

class TestBaseAdapter:
    def test_get_positions_not_implemented(self):
        adapter = BaseTrackingAdapter()
        with pytest.raises(NotImplementedError):
            adapter.get_positions()

    def test_test_connection_not_implemented(self):
        adapter = BaseTrackingAdapter()
        with pytest.raises(NotImplementedError):
            adapter.test_connection()
