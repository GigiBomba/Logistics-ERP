"""Tests for backend/schemas/mobile.py — all 19 mobile API schema models."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.mobile import (
    ApprovalActionRequest,
    DeviceRegisterRequest,
    DispatcherAlertResponse,
    DispatcherDriverResponse,
    DispatcherJobResponse,
    DispatcherOverviewResponse,
    DriverMyDayResponse,
    DriverTransportDetailResponse,
    DriverTransportResponse,
    DriverVehicleResponse,
    FleetPositionResponse,
    MobileExpenseCreateRequest,
    MobileExpenseResponse,
    MobileMessageResponse,
    MobileMessageSendRequest,
    StatusUpdateRequest,
    SyncCursorRequest,
    SyncResponse,
    VehicleDocumentResponse,
)


# ── SyncCursorRequest ──────────────────────────────────────────────────────────


class TestSyncCursorRequest:
    """entity_type (required), cursor (required)."""

    def test_valid(self):
        inst = SyncCursorRequest(entity_type="transport", cursor="abc123")
        assert inst.entity_type == "transport"
        assert inst.cursor == "abc123"

    def test_missing_entity_type_raises(self):
        with pytest.raises(ValidationError):
            SyncCursorRequest(cursor="abc123")  # type: ignore[call-arg]

    def test_missing_cursor_raises(self):
        with pytest.raises(ValidationError):
            SyncCursorRequest(entity_type="transport")  # type: ignore[call-arg]

    def test_both_missing_raises(self):
        with pytest.raises(ValidationError):
            SyncCursorRequest()  # type: ignore[call-arg]

    def test_empty_strings_accepted(self):
        inst = SyncCursorRequest(entity_type="", cursor="")
        assert inst.entity_type == ""
        assert inst.cursor == ""

    def test_long_strings(self):
        long_str = "x" * 10000
        inst = SyncCursorRequest(entity_type=long_str, cursor=long_str)
        assert inst.entity_type == long_str
        assert inst.cursor == long_str

    def test_wrong_type_entity_type_raises(self):
        with pytest.raises(ValidationError):
            SyncCursorRequest(entity_type=123, cursor="abc")  # type: ignore[call-arg]

    def test_wrong_type_cursor_raises(self):
        with pytest.raises(ValidationError):
            SyncCursorRequest(entity_type="abc", cursor=456)  # type: ignore[call-arg]


# ── DriverTransportResponse ────────────────────────────────────────────────────


class TestDriverTransportResponse:
    """id (required) — all other fields have defaults; extra="ignore"."""

    def test_valid_minimal(self):
        inst = DriverTransportResponse(id=1)
        assert inst.id == 1
        assert inst.load_info == ""
        assert inst.origin == ""
        assert inst.destination == ""
        assert inst.status == ""
        assert inst.vehicle_plate == ""
        assert inst.scheduled_date is None
        assert inst.last_updated is None

    def test_valid_all_fields(self):
        inst = DriverTransportResponse(
            id=42,
            load_info="Electronics",
            origin="Bucharest",
            destination="Cluj",
            status="in_progress",
            vehicle_plate="B-123-ABC",
            scheduled_date="2025-06-01",
            last_updated="2025-06-01T10:00:00Z",
        )
        assert inst.id == 42
        assert inst.load_info == "Electronics"
        assert inst.last_updated == "2025-06-01T10:00:00Z"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportResponse(id="not_an_int")  # type: ignore[call-arg]

    def test_scheduled_date_none(self):
        inst = DriverTransportResponse(id=1, scheduled_date=None)
        assert inst.scheduled_date is None

    def test_long_strings(self):
        long_str = "x" * 5000
        inst = DriverTransportResponse(id=1, load_info=long_str, origin=long_str)
        assert inst.load_info == long_str
        assert inst.origin == long_str

    def test_extra_field_ignored(self):
        inst = DriverTransportResponse(id=1, unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── DriverTransportDetailResponse ──────────────────────────────────────────────


class TestDriverTransportDetailResponse:
    """id (required) — many optional coords, waypoints list; extra="ignore"."""

    def test_valid_minimal(self):
        inst = DriverTransportDetailResponse(id=1)
        assert inst.id == 1
        assert inst.load_info == ""
        assert inst.waypoints == []
        assert inst.origin_lat is None
        assert inst.dest_lat is None

    def test_valid_all_fields(self):
        inst = DriverTransportDetailResponse(
            id=10,
            load_info="Furniture",
            origin="Bucharest",
            origin_lat=44.4268,
            origin_lng=26.1025,
            destination="Constanta",
            dest_lat=44.1598,
            dest_lng=28.6348,
            waypoints=["Ploiesti", "Focsani"],
            status="delivered",
            assigned_driver_name="Ion Popescu",
            vehicle_plate="B-456-XYZ",
            scheduled_date="2025-06-15",
            delivered_date="2025-06-16",
            last_updated="2025-06-16T18:00:00Z",
        )
        assert inst.origin_lat == 44.4268
        assert inst.dest_lng == 28.6348
        assert inst.waypoints == ["Ploiesti", "Focsani"]
        assert inst.delivered_date == "2025-06-16"
        assert inst.assigned_driver_name == "Ion Popescu"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportDetailResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportDetailResponse(id="bad")  # type: ignore[call-arg]

    def test_coords_as_floats(self):
        inst = DriverTransportDetailResponse(id=1, origin_lat=44.4, origin_lng=26.1)
        assert inst.origin_lat == 44.4
        assert inst.origin_lng == 26.1

    def test_coords_as_integers(self):
        """Pydantic coerces int to float."""
        inst = DriverTransportDetailResponse(id=1, origin_lat=44, origin_lng=26)
        assert isinstance(inst.origin_lat, float)
        assert inst.origin_lat == 44.0

    def test_coords_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportDetailResponse(id=1, origin_lat="bad")  # type: ignore[call-arg]

    def test_waypoints_not_a_list_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportDetailResponse(id=1, waypoints="not_a_list")  # type: ignore[call-arg]

    def test_waypoints_wrong_item_type_raises(self):
        with pytest.raises(ValidationError):
            DriverTransportDetailResponse(id=1, waypoints=[1, 2])  # type: ignore[call-arg]

    def test_empty_waypoints(self):
        inst = DriverTransportDetailResponse(id=1, waypoints=[])
        assert inst.waypoints == []

    def test_extra_field_ignored(self):
        inst = DriverTransportDetailResponse(id=1, extra="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "extra")

    def test_negative_coords(self):
        """No constraint — any float is accepted."""
        inst = DriverTransportDetailResponse(id=1, origin_lat=-45.0)
        assert inst.origin_lat == -45.0


# ── DriverMyDayResponse ────────────────────────────────────────────────────────


class TestDriverMyDayResponse:
    """All fields have defaults; contains nested lists."""

    def test_defaults(self):
        inst = DriverMyDayResponse()
        assert inst.active_transports == 0
        assert inst.next_stop is None
        assert inst.next_stop_time is None
        assert inst.unread_messages == 0
        assert inst.recent_transports == []
        assert inst.recent_messages == []

    def test_all_fields(self):
        rt = DriverTransportResponse(id=1, load_info="Test")
        msg = MobileMessageResponse(id=1, sender_id=2, receiver_id=3)
        inst = DriverMyDayResponse(
            active_transports=3,
            next_stop="Constanta",
            next_stop_time="14:30",
            unread_messages=5,
            recent_transports=[rt],
            recent_messages=[msg],
        )
        assert inst.active_transports == 3
        assert inst.next_stop == "Constanta"
        assert inst.unread_messages == 5
        assert len(inst.recent_transports) == 1
        assert inst.recent_transports[0].load_info == "Test"
        assert inst.recent_messages[0].sender_id == 2

    def test_negative_counts(self):
        """No constraint — any int is accepted."""
        inst = DriverMyDayResponse(active_transports=-5, unread_messages=-1)
        assert inst.active_transports == -5
        assert inst.unread_messages == -1

    def test_wrong_type_active_transports_raises(self):
        with pytest.raises(ValidationError):
            DriverMyDayResponse(active_transports="three")  # type: ignore[call-arg]

    def test_wrong_nested_type_raises(self):
        with pytest.raises(ValidationError):
            DriverMyDayResponse(recent_transports=["not_a_transport"])  # type: ignore[call-arg]

    def test_wrong_nested_message_type_raises(self):
        with pytest.raises(ValidationError):
            DriverMyDayResponse(recent_messages=["not_a_message"])  # type: ignore[call-arg]

    def test_large_counts(self):
        inst = DriverMyDayResponse(active_transports=9999, unread_messages=8888)
        assert inst.active_transports == 9999
        assert inst.unread_messages == 8888


# ── StatusUpdateRequest ────────────────────────────────────────────────────────


class TestStatusUpdateRequest:
    """status (required)."""

    def test_valid(self):
        inst = StatusUpdateRequest(status="delivered")
        assert inst.status == "delivered"

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            StatusUpdateRequest()  # type: ignore[call-arg]

    def test_empty_string(self):
        inst = StatusUpdateRequest(status="")
        assert inst.status == ""

    def test_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            StatusUpdateRequest(status=123)  # type: ignore[call-arg]

    def test_long_string(self):
        long_str = "x" * 5000
        inst = StatusUpdateRequest(status=long_str)
        assert inst.status == long_str


# ── DriverVehicleResponse ──────────────────────────────────────────────────────


class TestDriverVehicleResponse:
    """id (required); documents nested list; extra="ignore"; type field."""

    def test_valid_minimal(self):
        inst = DriverVehicleResponse(id=1)
        assert inst.id == 1
        assert inst.plate == ""
        assert inst.type == ""
        assert inst.brand == ""
        assert inst.model == ""
        assert inst.status == ""
        assert inst.documents == []

    def test_valid_all_fields(self):
        doc = VehicleDocumentResponse(id=10, document_type="ITP")
        inst = DriverVehicleResponse(
            id=5,
            plate="B-789-DEF",
            type="truck",
            brand="Mercedes",
            model="Actros",
            status="active",
            documents=[doc],
        )
        assert inst.plate == "B-789-DEF"
        assert inst.type == "truck"
        assert inst.brand == "Mercedes"
        assert inst.documents[0].document_type == "ITP"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DriverVehicleResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DriverVehicleResponse(id="bad")  # type: ignore[call-arg]

    def test_documents_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DriverVehicleResponse(id=1, documents=["not_a_doc"])  # type: ignore[call-arg]

    def test_documents_none_raises(self):
        """documents is not Optional, so None should raise."""
        with pytest.raises(ValidationError):
            DriverVehicleResponse(id=1, documents=None)  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        inst = DriverVehicleResponse(id=1, unknown=True)  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── VehicleDocumentResponse ────────────────────────────────────────────────────


class TestVehicleDocumentResponse:
    """id (required); is_expiring_soon defaults False; extra="ignore"."""

    def test_valid_minimal(self):
        inst = VehicleDocumentResponse(id=1)
        assert inst.id == 1
        assert inst.document_type == ""
        assert inst.expiry_date is None
        assert inst.is_expiring_soon is False

    def test_valid_all_fields(self):
        inst = VehicleDocumentResponse(
            id=10,
            document_type="ITP",
            expiry_date="2025-12-31",
            is_expiring_soon=True,
        )
        assert inst.document_type == "ITP"
        assert inst.expiry_date == "2025-12-31"
        assert inst.is_expiring_soon is True

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            VehicleDocumentResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            VehicleDocumentResponse(id="bad")  # type: ignore[call-arg]

    def test_is_expiring_soon_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            VehicleDocumentResponse(id=1, is_expiring_soon="not_a_bool")  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        inst = VehicleDocumentResponse(id=1, extra="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "extra")

    def test_empty_document_type(self):
        inst = VehicleDocumentResponse(id=1, document_type="")
        assert inst.document_type == ""


# ── MobileExpenseResponse ──────────────────────────────────────────────────────


class TestMobileExpenseResponse:
    """id (required); amount defaults 0.0; currency defaults EUR; extra="ignore"."""

    def test_valid_minimal(self):
        inst = MobileExpenseResponse(id=1)
        assert inst.id == 1
        assert inst.expense_type == ""
        assert inst.amount == 0.0
        assert inst.currency == "EUR"
        assert inst.date is None
        assert inst.description == ""
        assert inst.receipt_url is None
        assert inst.status == "pending"

    def test_valid_all_fields(self):
        inst = MobileExpenseResponse(
            id=42,
            expense_type="fuel",
            amount=125.50,
            currency="RON",
            date="2025-06-10",
            description="Motorina OMV",
            receipt_url="https://example.com/receipt.pdf",
            status="approved",
        )
        assert inst.amount == 125.50
        assert inst.currency == "RON"
        assert inst.receipt_url == "https://example.com/receipt.pdf"
        assert inst.status == "approved"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            MobileExpenseResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileExpenseResponse(id="bad")  # type: ignore[call-arg]

    def test_amount_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileExpenseResponse(id=1, amount="free")  # type: ignore[call-arg]

    def test_amount_integer_coerced(self):
        """Pydantic coerces int to float."""
        inst = MobileExpenseResponse(id=1, amount=100)
        assert isinstance(inst.amount, float)
        assert inst.amount == 100.0

    def test_negative_amount(self):
        """No constraint — any float accepted."""
        inst = MobileExpenseResponse(id=1, amount=-50.0)
        assert inst.amount == -50.0

    def test_currency_empty_string(self):
        inst = MobileExpenseResponse(id=1, currency="")
        assert inst.currency == ""

    def test_receipt_url_none(self):
        inst = MobileExpenseResponse(id=1, receipt_url=None)
        assert inst.receipt_url is None

    def test_extra_field_ignored(self):
        inst = MobileExpenseResponse(id=1, extra=True)  # type: ignore[call-arg]
        assert not hasattr(inst, "extra")

    def test_status_empty_string(self):
        inst = MobileExpenseResponse(id=1, status="")
        assert inst.status == ""


# ── MobileExpenseCreateRequest ─────────────────────────────────────────────────


class TestMobileExpenseCreateRequest:
    """amount (required); expense_type defaults "other"; currency defaults EUR."""

    def test_valid_minimal(self):
        inst = MobileExpenseCreateRequest(amount=50.0)
        assert inst.amount == 50.0
        assert inst.expense_type == "other"
        assert inst.currency == "EUR"
        assert inst.date is None
        assert inst.description == ""

    def test_valid_all_fields(self):
        inst = MobileExpenseCreateRequest(
            expense_type="fuel",
            amount=200.75,
            currency="USD",
            date="2025-06-15",
            description="Gas station",
        )
        assert inst.expense_type == "fuel"
        assert inst.amount == 200.75
        assert inst.currency == "USD"
        assert inst.description == "Gas station"

    def test_missing_amount_raises(self):
        with pytest.raises(ValidationError):
            MobileExpenseCreateRequest()  # type: ignore[call-arg]

    def test_amount_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileExpenseCreateRequest(amount="fifty")  # type: ignore[call-arg]

    def test_amount_integer_coerced(self):
        inst = MobileExpenseCreateRequest(amount=100)
        assert isinstance(inst.amount, float)
        assert inst.amount == 100.0

    def test_negative_amount(self):
        inst = MobileExpenseCreateRequest(amount=-10.0)
        assert inst.amount == -10.0

    def test_zero_amount(self):
        inst = MobileExpenseCreateRequest(amount=0.0)
        assert inst.amount == 0.0

    def test_empty_expense_type(self):
        inst = MobileExpenseCreateRequest(amount=10.0, expense_type="")
        assert inst.expense_type == ""

    def test_date_none(self):
        inst = MobileExpenseCreateRequest(amount=10.0, date=None)
        assert inst.date is None

    def test_long_description(self):
        long_str = "x" * 5000
        inst = MobileExpenseCreateRequest(amount=10.0, description=long_str)
        assert inst.description == long_str


# ── MobileMessageResponse ──────────────────────────────────────────────────────


class TestMobileMessageResponse:
    """id, sender_id, receiver_id required; rest have defaults; extra="ignore"."""

    def test_valid_minimal(self):
        inst = MobileMessageResponse(id=1, sender_id=10, receiver_id=20)
        assert inst.id == 1
        assert inst.sender_id == 10
        assert inst.receiver_id == 20
        assert inst.sender_name == ""
        assert inst.text == ""
        assert inst.timestamp is None
        assert inst.is_read is False
        assert inst.transport_id is None

    def test_valid_all_fields(self):
        inst = MobileMessageResponse(
            id=99,
            sender_id=10,
            sender_name="Ion",
            receiver_id=20,
            text="Hello!",
            timestamp="2025-06-01T12:00:00Z",
            is_read=True,
            transport_id=42,
        )
        assert inst.sender_name == "Ion"
        assert inst.text == "Hello!"
        assert inst.is_read is True
        assert inst.transport_id == 42

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(sender_id=1, receiver_id=2)  # type: ignore[call-arg]

    def test_missing_sender_id_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(id=1, receiver_id=2)  # type: ignore[call-arg]

    def test_missing_receiver_id_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(id=1, sender_id=2)  # type: ignore[call-arg]

    def test_all_required_missing_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(id="bad", sender_id=1, receiver_id=2)  # type: ignore[call-arg]

    def test_sender_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(id=1, sender_id="bad", receiver_id=2)  # type: ignore[call-arg]

    def test_receiver_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(id=1, sender_id=2, receiver_id="bad")  # type: ignore[call-arg]

    def test_transport_id_none(self):
        inst = MobileMessageResponse(id=1, sender_id=2, receiver_id=3, transport_id=None)
        assert inst.transport_id is None

    def test_is_read_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageResponse(id=1, sender_id=2, receiver_id=3, is_read=123)  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        inst = MobileMessageResponse(id=1, sender_id=2, receiver_id=3, extra="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "extra")

    def test_negative_ids(self):
        """No constraint — any int is accepted."""
        inst = MobileMessageResponse(id=-1, sender_id=-2, receiver_id=-3)
        assert inst.id == -1


# ── MobileMessageSendRequest ───────────────────────────────────────────────────


class TestMobileMessageSendRequest:
    """receiver_id (required), text (required), transport_id optional."""

    def test_valid_minimal(self):
        inst = MobileMessageSendRequest(receiver_id=10, text="Hello")
        assert inst.receiver_id == 10
        assert inst.text == "Hello"
        assert inst.transport_id is None

    def test_valid_all_fields(self):
        inst = MobileMessageSendRequest(receiver_id=10, text="Hello", transport_id=42)
        assert inst.transport_id == 42

    def test_missing_receiver_id_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageSendRequest(text="Hello")  # type: ignore[call-arg]

    def test_missing_text_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageSendRequest(receiver_id=10)  # type: ignore[call-arg]

    def test_both_missing_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageSendRequest()  # type: ignore[call-arg]

    def test_empty_text_accepted(self):
        inst = MobileMessageSendRequest(receiver_id=1, text="")
        assert inst.text == ""

    def test_receiver_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageSendRequest(receiver_id="bad", text="hi")  # type: ignore[call-arg]

    def test_text_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            MobileMessageSendRequest(receiver_id=1, text=123)  # type: ignore[call-arg]

    def test_long_text(self):
        long_str = "x" * 10000
        inst = MobileMessageSendRequest(receiver_id=1, text=long_str)
        assert inst.text == long_str

    def test_negative_receiver_id(self):
        inst = MobileMessageSendRequest(receiver_id=-1, text="hi")
        assert inst.receiver_id == -1


# ── DeviceRegisterRequest ──────────────────────────────────────────────────────


class TestDeviceRegisterRequest:
    """token, platform, device_id required; device_name defaults to ""."""

    def test_valid_minimal(self):
        inst = DeviceRegisterRequest(token="abc", platform="ios", device_id="d1")
        assert inst.token == "abc"
        assert inst.platform == "ios"
        assert inst.device_id == "d1"
        assert inst.device_name == ""

    def test_valid_all_fields(self):
        inst = DeviceRegisterRequest(
            token="token123",
            platform="android",
            device_id="device-001",
            device_name="My Phone",
        )
        assert inst.device_name == "My Phone"

    def test_missing_token_raises(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest(platform="ios", device_id="d1")  # type: ignore[call-arg]

    def test_missing_platform_raises(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest(token="abc", device_id="d1")  # type: ignore[call-arg]

    def test_missing_device_id_raises(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest(token="abc", platform="ios")  # type: ignore[call-arg]

    def test_all_missing_raises(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest()  # type: ignore[call-arg]

    def test_empty_strings_accepted(self):
        inst = DeviceRegisterRequest(token="", platform="", device_id="")
        assert inst.token == ""
        assert inst.platform == ""
        assert inst.device_id == ""

    def test_wrong_type_token_raises(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest(token=123, platform="ios", device_id="d1")  # type: ignore[call-arg]

    def test_wrong_type_platform_raises(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest(token="abc", platform=456, device_id="d1")  # type: ignore[call-arg]

    def test_device_name_none(self):
        """device_name is Optional[str] with default ""; None should be accepted."""
        inst = DeviceRegisterRequest(token="abc", platform="ios", device_id="d1", device_name=None)
        assert inst.device_name is None

    def test_long_strings(self):
        long_str = "x" * 5000
        inst = DeviceRegisterRequest(token=long_str, platform=long_str, device_id=long_str)
        assert inst.token == long_str


# ── DispatcherOverviewResponse ─────────────────────────────────────────────────


class TestDispatcherOverviewResponse:
    """All fields have defaults (int)."""

    def test_defaults(self):
        inst = DispatcherOverviewResponse()
        assert inst.active_jobs == 0
        assert inst.active_drivers == 0
        assert inst.open_alerts == 0
        assert inst.vehicles_on_road == 0

    def test_all_fields(self):
        inst = DispatcherOverviewResponse(
            active_jobs=12, active_drivers=8, open_alerts=3, vehicles_on_road=5
        )
        assert inst.active_jobs == 12
        assert inst.active_drivers == 8
        assert inst.open_alerts == 3
        assert inst.vehicles_on_road == 5

    def test_negative_values(self):
        inst = DispatcherOverviewResponse(
            active_jobs=-1, active_drivers=-2, open_alerts=-3, vehicles_on_road=-4
        )
        assert inst.active_jobs == -1

    def test_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherOverviewResponse(active_jobs="many")  # type: ignore[call-arg]

    def test_large_values(self):
        inst = DispatcherOverviewResponse(
            active_jobs=99999, active_drivers=88888, open_alerts=77777, vehicles_on_road=66666
        )
        assert inst.active_jobs == 99999


# ── FleetPositionResponse ──────────────────────────────────────────────────────


class TestFleetPositionResponse:
    """vehicle_id (required); lat/lng optional; no extra=ignore so extra is kept."""

    def test_valid_minimal(self):
        inst = FleetPositionResponse(vehicle_id=1)
        assert inst.vehicle_id == 1
        assert inst.plate == ""
        assert inst.driver_name == ""
        assert inst.lat is None
        assert inst.lng is None
        assert inst.status == ""
        assert inst.last_update is None

    def test_valid_all_fields(self):
        inst = FleetPositionResponse(
            vehicle_id=5,
            plate="B-007-ABC",
            driver_name="Andrei",
            lat=44.4325,
            lng=26.1039,
            status="moving",
            last_update="2025-06-01T10:30:00Z",
        )
        assert inst.lat == 44.4325
        assert inst.lng == 26.1039
        assert inst.driver_name == "Andrei"
        assert inst.last_update == "2025-06-01T10:30:00Z"

    def test_missing_vehicle_id_raises(self):
        with pytest.raises(ValidationError):
            FleetPositionResponse()  # type: ignore[call-arg]

    def test_vehicle_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            FleetPositionResponse(vehicle_id="bad")  # type: ignore[call-arg]

    def test_lat_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            FleetPositionResponse(vehicle_id=1, lat="bad")  # type: ignore[call-arg]

    def test_lng_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            FleetPositionResponse(vehicle_id=1, lng="bad")  # type: ignore[call-arg]

    def test_lat_integer_coerced(self):
        inst = FleetPositionResponse(vehicle_id=1, lat=44)
        assert inst.lat == 44.0

    def test_negative_coords(self):
        inst = FleetPositionResponse(vehicle_id=1, lat=-33.0, lng=-71.0)
        assert inst.lat == -33.0

    def test_empty_strings(self):
        inst = FleetPositionResponse(vehicle_id=1, plate="", driver_name="", status="")
        assert inst.plate == ""
        assert inst.driver_name == ""

    def test_extra_field_kept(self):
        """No extra=ignore, so unknown fields are kept."""
        inst = FleetPositionResponse(vehicle_id=1, extra_field="kept")  # type: ignore[call-arg]
        # Only assert that no error is raised; the extra field will be accepted
        # because BaseModel by default allows extras (extra="allow" is default).


# ── DispatcherJobResponse ──────────────────────────────────────────────────────


class TestDispatcherJobResponse:
    """id (required); extra="ignore"."""

    def test_valid_minimal(self):
        inst = DispatcherJobResponse(id=1)
        assert inst.id == 1
        assert inst.load_info == ""
        assert inst.driver_name == ""
        assert inst.vehicle_plate == ""
        assert inst.status == ""
        assert inst.origin == ""
        assert inst.destination == ""
        assert inst.last_updated is None

    def test_valid_all_fields(self):
        inst = DispatcherJobResponse(
            id=42,
            load_info="Coal",
            driver_name="Mihai",
            vehicle_plate="B-123-ABC",
            status="in_progress",
            origin="Bucharest",
            destination="Iasi",
            last_updated="2025-06-01T08:00:00Z",
        )
        assert inst.load_info == "Coal"
        assert inst.last_updated == "2025-06-01T08:00:00Z"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DispatcherJobResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherJobResponse(id="bad")  # type: ignore[call-arg]

    def test_long_strings(self):
        long_str = "x" * 5000
        inst = DispatcherJobResponse(id=1, load_info=long_str, origin=long_str)
        assert inst.load_info == long_str

    def test_extra_field_ignored(self):
        inst = DispatcherJobResponse(id=1, unknown=True)  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")


# ── DispatcherDriverResponse ───────────────────────────────────────────────────


class TestDispatcherDriverResponse:
    """id (required); current_transport/current_vehicle optional."""

    def test_valid_minimal(self):
        inst = DispatcherDriverResponse(id=1)
        assert inst.id == 1
        assert inst.name == ""
        assert inst.status == ""
        assert inst.current_transport is None
        assert inst.current_vehicle is None

    def test_valid_all_fields(self):
        inst = DispatcherDriverResponse(
            id=10,
            name="Ion Popescu",
            status="driving",
            current_transport="Transport #42",
            current_vehicle="B-123-ABC",
        )
        assert inst.name == "Ion Popescu"
        assert inst.status == "driving"
        assert inst.current_transport == "Transport #42"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DispatcherDriverResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherDriverResponse(id="bad")  # type: ignore[call-arg]

    def test_name_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherDriverResponse(id=1, name=123)  # type: ignore[call-arg]

    def test_current_transport_none(self):
        inst = DispatcherDriverResponse(id=1, current_transport=None)
        assert inst.current_transport is None

    def test_current_vehicle_none(self):
        inst = DispatcherDriverResponse(id=1, current_vehicle=None)
        assert inst.current_vehicle is None

    def test_empty_strings(self):
        inst = DispatcherDriverResponse(id=1, name="", status="")
        assert inst.name == ""
        assert inst.status == ""

    def test_long_name(self):
        long_str = "x" * 5000
        inst = DispatcherDriverResponse(id=1, name=long_str)
        assert inst.name == long_str


# ── DispatcherAlertResponse ────────────────────────────────────────────────────


class TestDispatcherAlertResponse:
    """id (required); related_entity_id optional int; is_read defaults False."""

    def test_valid_minimal(self):
        inst = DispatcherAlertResponse(id=1)
        assert inst.id == 1
        assert inst.type == ""
        assert inst.title == ""
        assert inst.description == ""
        assert inst.severity == ""
        assert inst.is_read is False
        assert inst.created_at is None
        assert inst.related_entity_id is None
        assert inst.related_entity_type == ""

    def test_valid_all_fields(self):
        inst = DispatcherAlertResponse(
            id=42,
            type="maintenance",
            title="Oil change due",
            description="Vehicle B-123 needs oil change",
            severity="high",
            is_read=True,
            created_at="2025-06-01T10:00:00Z",
            related_entity_id=5,
            related_entity_type="vehicle",
        )
        assert inst.type == "maintenance"
        assert inst.severity == "high"
        assert inst.is_read is True
        assert inst.related_entity_id == 5
        assert inst.related_entity_type == "vehicle"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            DispatcherAlertResponse()  # type: ignore[call-arg]

    def test_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherAlertResponse(id="bad")  # type: ignore[call-arg]

    def test_is_read_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherAlertResponse(id=1, is_read=123)  # type: ignore[call-arg]

    def test_related_entity_id_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            DispatcherAlertResponse(id=1, related_entity_id="bad")  # type: ignore[call-arg]

    def test_related_entity_id_none(self):
        inst = DispatcherAlertResponse(id=1, related_entity_id=None)
        assert inst.related_entity_id is None

    def test_negative_id(self):
        inst = DispatcherAlertResponse(id=-1)
        assert inst.id == -1

    def test_long_strings(self):
        long_str = "x" * 5000
        inst = DispatcherAlertResponse(id=1, title=long_str, description=long_str)
        assert inst.title == long_str
        assert inst.description == long_str


# ── ApprovalActionRequest ──────────────────────────────────────────────────────


class TestApprovalActionRequest:
    """reason optional with default None."""

    def test_default(self):
        inst = ApprovalActionRequest()
        assert inst.reason is None

    def test_with_reason(self):
        inst = ApprovalActionRequest(reason="Approved by dispatcher")
        assert inst.reason == "Approved by dispatcher"

    def test_reason_none(self):
        inst = ApprovalActionRequest(reason=None)
        assert inst.reason is None

    def test_reason_empty_string(self):
        inst = ApprovalActionRequest(reason="")
        assert inst.reason == ""

    def test_reason_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            ApprovalActionRequest(reason=123)  # type: ignore[call-arg]

    def test_long_reason(self):
        long_str = "x" * 10000
        inst = ApprovalActionRequest(reason=long_str)
        assert inst.reason == long_str


# ── SyncResponse ───────────────────────────────────────────────────────────────


class TestSyncResponse:
    """records list of dicts; cursor optional; has_more defaults False."""

    def test_defaults(self):
        inst = SyncResponse()
        assert inst.records == []
        assert inst.cursor is None
        assert inst.has_more is False

    def test_with_records(self):
        inst = SyncResponse(records=[{"id": 1, "name": "test"}], cursor="abc", has_more=True)
        assert inst.records == [{"id": 1, "name": "test"}]
        assert inst.cursor == "abc"
        assert inst.has_more is True

    def test_multiple_records(self):
        inst = SyncResponse(
            records=[{"a": 1}, {"b": 2}, {"c": 3}],
            cursor="xyz",
            has_more=True,
        )
        assert len(inst.records) == 3

    def test_empty_records(self):
        inst = SyncResponse(records=[], cursor=None, has_more=False)
        assert inst.records == []

    def test_records_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            SyncResponse(records="not_a_list")  # type: ignore[call-arg]

    def test_records_item_wrong_type_raises(self):
        """Items must be dicts, not plain strings."""
        with pytest.raises(ValidationError):
            SyncResponse(records=["not_a_dict"])  # type: ignore[call-arg]

    def test_cursor_none(self):
        inst = SyncResponse(cursor=None)
        assert inst.cursor is None

    def test_cursor_empty_string(self):
        inst = SyncResponse(cursor="")
        assert inst.cursor == ""

    def test_has_more_wrong_type_raises(self):
        with pytest.raises(ValidationError):
            SyncResponse(has_more="not_a_bool")  # type: ignore[call-arg]

    def test_large_records_list(self):
        records = [{"idx": i} for i in range(1000)]
        inst = SyncResponse(records=records)
        assert len(inst.records) == 1000


# ── Cross-model edge cases ─────────────────────────────────────────────────────


class TestCrossModelEdgeCases:
    """Tests that exercise interactions between nested models."""

    def test_driver_my_day_with_full_nesting(self):
        """DriverMyDayResponse with both nested list types fully populated."""
        transport = DriverTransportResponse(
            id=1, load_info="Cargo", origin="A", destination="B", status="active"
        )
        message = MobileMessageResponse(
            id=10, sender_id=5, sender_name="Dispatcher", receiver_id=3, text="Go!"
        )
        inst = DriverMyDayResponse(
            active_transports=1,
            recent_transports=[transport],
            recent_messages=[message],
        )
        assert inst.recent_transports[0].origin == "A"
        assert inst.recent_messages[0].text == "Go!"

    def test_driver_vehicle_with_documents(self):
        """DriverVehicleResponse with multiple nested VehicleDocumentResponse."""
        docs = [
            VehicleDocumentResponse(id=1, document_type="ITP", is_expiring_soon=False),
            VehicleDocumentResponse(id=2, document_type="RCA", is_expiring_soon=True),
        ]
        inst = DriverVehicleResponse(id=5, plate="B-123", documents=docs)
        assert len(inst.documents) == 2
        assert inst.documents[0].document_type == "ITP"
        assert inst.documents[1].is_expiring_soon is True

    def test_forward_refs_resolved(self):
        """DriverMyDayResponse and DriverVehicleResponse use forward refs that must be resolved."""
        # model_rebuild() was called at module end; construction should work.
        msg = MobileMessageResponse(id=1, sender_id=2, receiver_id=3)
        day = DriverMyDayResponse(recent_messages=[msg])
        assert len(day.recent_messages) == 1

        doc = VehicleDocumentResponse(id=1)
        vehicle = DriverVehicleResponse(id=1, documents=[doc])
        assert vehicle.documents[0].id == 1

    def test_mobile_expense_create_round_trip(self):
        """Verify that an ExpenseResponse can be constructed from a CreateRequest dict plus id."""
        create = MobileExpenseCreateRequest(amount=100.0, expense_type="fuel")
        resp = MobileExpenseResponse(id=1, **create.model_dump())
        assert resp.id == 1
        assert resp.amount == 100.0
        assert resp.expense_type == "fuel"
        # status gets the default "pending", not anything from create
        assert resp.status == "pending"
