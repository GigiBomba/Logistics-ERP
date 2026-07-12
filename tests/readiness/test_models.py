"""Comprehensive tests for ALL Pydantic models — valid creation, invalid rejection,
validation messages, extra field rejection, defaults, serialization, and type aliases."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# common
# ---------------------------------------------------------------------------
from models.common import (
    PaginationParams,
    PaginatedResponse,
    SuccessResponse,
    ErrorDetail,
    ErrorResponse,
    UndoToken,
    ServiceResult,
    OperationLog,
)

# trip
from models.trip_models import TripStop, TripCreate, TripUpdate, TripResult

# route
from models.route_models import RouteStop, RouteCalculateRequest, RouteResult

# dispatch
from models.dispatch_models import (
    DispatchCreate,
    DispatchAssign,
    DispatchCancel,
    DispatchResult,
    UnassignedTrip,
    AvailableTruck,
    DispatchBoardResult,
)

# vehicle
from models.vehicle_models import (
    VehicleCreate,
    VehicleUpdate,
    VehicleSearchRequest,
    VehicleHealthScore,
    VehicleResult,
)

# client
from models.client_models import ClientContact, ClientCreate, ClientUpdate, ClientResult

# invoice
from models.invoice_models import InvoiceLineItem, InvoiceCreate, InvoiceUpdate, InvoiceFinalizeRequest, InvoiceResult

# receipt
from models.receipt_models import ReceiptLineItem, ReceiptCreate, ReceiptResult

# payment
from models.payment_models import PaymentProfileCreate, PaymentBatchRequest, PaymentProfileResult, PaymentBatchResult

# proforma
from models.proforma_models import ProformaCreate, ProformaResult

# document
from models.document_models import DocumentUpload, DocumentResult

# ocr
from models.ocr_models import OcrProcessRequest, ExtractedFields, MatchedTrip, OcrResult

# analytics
from models.analytics_models import AnalyticsRequest, RevenueReport, OverdueReport, KpiDashboard

# export
from models.export_models import ExportRequest, ExportResult

# cmr
from models.cmr_models import CmrGenerateRequest, CmrResult

# cost
from models.cost_models import CostEstimateRequest, CostBreakdown, CostEstimateResult

# driver
from models.driver_models import DriverCreate, DriverUpdate, DriverHoursCheck, DriverResult, DriverHoursResult, TruckAssignment

# tacho
from models.tacho_models import TachoImportRequest, DriverActivity, VehicleActivity, TachoImportResult, DriverHoursAnalysis, FleetTachoSummary

# calculator
from models.calculator_models import CalculationRequest, TripCalculationResult

# automail
from models.automail_models import EmailTemplateCreate, SendReminderRequest, SendReminderResult

# -- Type aliases (ServiceResult wrappers) ----------------------------------
from models.trip_models import TripCreateResult, TripListResult
from models.route_models import RouteCalculationResult
from models.dispatch_models import DispatchCreateResult, DispatchBoardResult_Typed
from models.vehicle_models import VehicleCreateResult, VehicleSearchResult
from models.client_models import ClientCreateResult, ClientListResult
from models.invoice_models import InvoiceCreateResult, InvoiceListResult
from models.receipt_models import ReceiptCreateResult
from models.payment_models import PaymentBatchCreateResult
from models.proforma_models import ProformaCreateResult
from models.document_models import DocumentUploadResult, DocumentListResult
from models.ocr_models import OcrProcessResult
from models.analytics_models import AnalyticsReportResult
from models.export_models import ExportOperationResult
from models.cmr_models import CmrGenerateResult
from models.cost_models import CostEstimateOperationResult
from models.driver_models import DriverCreateResult, DriverHoursCheckResult
from models.tacho_models import TachoImportOperationResult, TachoAnalysisResult, TachoFleetSummaryResult
from models.calculator_models import CalculationOperationResult
from models.automail_models import AutomailSendResult


# ===================================================================
#  HELPER: assert common serialisation invariants
# ===================================================================
def _check_serialization(model_instance):
    d = model_instance.model_dump()
    assert isinstance(d, dict)
    j = model_instance.model_dump_json()
    assert isinstance(j, str)
    parsed = json.loads(j)
    assert isinstance(parsed, dict)
    # round-trip through json should preserve primitive equality
    for k, v in d.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            assert json.loads(model_instance.model_dump_json()).get(k) == v


# ===================================================================
#  COMMON MODELS
# ===================================================================

class TestPaginationParams:
    def test_valid_defaults(self):
        p = PaginationParams()
        assert p.page == 1
        assert p.per_page == 20

    def test_valid_explicit(self):
        p = PaginationParams(page=3, per_page=50)
        assert p.page == 3
        assert p.per_page == 50

    # Note: PaginationParams has no ge/le constraints on page/per_page,
    # so negative values are accepted at the model level.
    def test_negative_page_accepted(self):
        p = PaginationParams(page=-1)
        assert p.page == -1

    def test_zero_per_page_accepted(self):
        p = PaginationParams(per_page=0)
        assert p.per_page == 0

    def test_serialization(self):
        _check_serialization(PaginationParams(page=2, per_page=10))


class TestPaginatedResponse:
    def test_valid(self):
        pr = PaginatedResponse(items=[1, 2, 3], total=3, page=1, per_page=10, total_pages=1)
        assert pr.items == [1, 2, 3]
        assert pr.total == 3

    def test_empty_items(self):
        pr = PaginatedResponse(items=[], total=0, page=1, per_page=10, total_pages=0)
        assert pr.items == []

    def test_serialization(self):
        _check_serialization(PaginatedResponse(items=["a"], total=1, page=1, per_page=10, total_pages=1))


class TestSuccessResponse:
    def test_valid_defaults(self):
        sr = SuccessResponse()
        assert sr.success is True
        assert sr.message is None

    def test_valid_explicit(self):
        sr = SuccessResponse(success=True, message="OK")
        assert sr.message == "OK"

    def test_serialization(self):
        _check_serialization(SuccessResponse(message="done"))


class TestErrorDetail:
    def test_valid_minimal(self):
        ed = ErrorDetail(message="Not found", code="ERR_001")
        assert ed.field is None

    def test_valid_full(self):
        ed = ErrorDetail(field="email", message="Invalid email", code="ERR_002")
        assert ed.field == "email"

    def test_serialization(self):
        _check_serialization(ErrorDetail(message="err", code="E1"))


class TestErrorResponse:
    def test_valid(self):
        er = ErrorResponse(
            errors=[ErrorDetail(message="err", code="E1")],
            message="Something went wrong",
        )
        assert er.success is False
        assert len(er.errors) == 1

    def test_serialization(self):
        _check_serialization(ErrorResponse(errors=[], message="fail"))


class TestUndoToken:
    def test_valid(self):
        ut = UndoToken(operation_id="abc-123", operation_type="trip_create")
        assert ut.can_undo is True
        assert ut.undo_description == ""

    def test_valid_full(self):
        ut = UndoToken(operation_id="x", operation_type="y", can_undo=False, undo_description="undo create")
        assert ut.can_undo is False

    def test_serialization(self):
        _check_serialization(UndoToken(operation_id="id", operation_type="type"))


class TestOperationLog:
    def test_valid(self):
        now = datetime.now()
        ol = OperationLog(operation="create_trip", duration_ms=150.5, success=True, timestamp=now)
        assert ol.operation == "create_trip"
        assert ol.error is None

    def test_valid_with_error(self):
        ol = OperationLog(operation="fail", duration_ms=0.0, success=False, error="timeout", timestamp=datetime.now())
        assert ol.error == "timeout"

    def test_serialization(self):
        _check_serialization(OperationLog(operation="op", duration_ms=1.0, success=True, timestamp=datetime.now()))


# ===================================================================
#  TRIP MODELS
# ===================================================================

class TestTripStop:
    def test_valid_minimal(self):
        ts = TripStop(address="Berlin HQ", sequence=1)
        assert ts.address == "Berlin HQ"
        assert ts.sequence == 1
        assert ts.type == "pickup"

    def test_valid_full(self):
        now = datetime.now()
        ts = TripStop(
            address="Depot", lat=52.0, lon=13.0, sequence=2,
            arrival=now, departure=now, type="delivery",
        )
        assert ts.lat == 52.0

    def test_defaults(self):
        ts = TripStop(address="A", sequence=0)
        assert ts.lat is None
        assert ts.lon is None
        assert ts.arrival is None
        assert ts.departure is None
        assert ts.type == "pickup"

    def test_serialization(self):
        _check_serialization(TripStop(address="Addr", sequence=5))


class TestTripCreate:
    def test_valid_minimal(self):
        tc = TripCreate(client_id=1, start_date=date(2024, 1, 1))
        assert tc.client_id == 1
        assert tc.price_eur == 0.0
        assert tc.currency == "EUR"
        assert tc.status == "Planned"
        assert tc.stops == []

    def test_valid_full(self):
        tc = TripCreate(
            client_id=1, route_id=10, truck_id=5, driver_id=3,
            reference="REF-001", start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 5), price_eur=1500.0,
            distance_km=1200.0, stops=[TripStop(address="A", sequence=1)],
            notes="Express", truck_plate="AB123CD", driver_name="John",
            client_name="Acme", status="Confirmed",
        )
        assert tc.price_eur == 1500.0
        assert len(tc.stops) == 1

    def test_defaults(self):
        tc = TripCreate(client_id=99, start_date=date(2024, 1, 1))
        assert tc.reference == ""
        assert tc.notes == ""
        assert tc.truck_plate == ""
        assert tc.driver_name == ""
        assert tc.client_name == ""

    def test_price_negative_raises(self):
        with pytest.raises(ValidationError, match="Price cannot be negative"):
            TripCreate(client_id=1, start_date=date.today(), price_eur=-10.0)

    def test_distance_zero_raises(self):
        with pytest.raises(ValidationError, match="Distance must be positive"):
            TripCreate(client_id=1, start_date=date.today(), distance_km=0.0)

    def test_distance_negative_raises(self):
        with pytest.raises(ValidationError, match="Distance must be positive"):
            TripCreate(client_id=1, start_date=date.today(), distance_km=-5.0)

    def test_distance_none_allowed(self):
        tc = TripCreate(client_id=1, start_date=date.today(), distance_km=None)
        assert tc.distance_km is None

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            TripCreate(client_id=1, start_date=date.today(), price_eur=-1)
        msgs = " ".join(e["msg"] for e in exc.value.errors())
        assert "Price cannot be negative" in msgs

    def test_serialization(self):
        _check_serialization(TripCreate(client_id=1, start_date=date(2024, 1, 1)))


class TestTripUpdate:
    def test_valid_empty(self):
        tu = TripUpdate()
        # all fields optional
        assert tu.client_id is None

    def test_valid_partial(self):
        tu = TripUpdate(price_eur=2000.0, status="Completed")
        assert tu.price_eur == 2000.0

    def test_serialization(self):
        _check_serialization(TripUpdate(notes="updated"))


class TestTripResult:
    @staticmethod
    def _minimal_kwargs(**overrides):
        kwargs = dict(
            id=1, client_id=1, client_name="Acme", reference="R1",
            start_date=date(2024, 1, 1), price_eur=1000.0,
            currency="EUR", status="Planned",
        )
        kwargs.update(overrides)
        return kwargs

    def test_valid_minimal(self):
        tr = TripResult(**self._minimal_kwargs())
        assert tr.id == 1

    def test_valid_full(self):
        tr = TripResult(**self._minimal_kwargs(distance_km=500.0, notes="ok", profit=200.0))
        assert tr.distance_km == 500.0

    def test_serialization(self):
        _check_serialization(TripResult(**self._minimal_kwargs()))


# ===================================================================
#  ROUTE MODELS
# ===================================================================

class TestRouteStop:
    def test_valid_minimal(self):
        rs = RouteStop(address="Berlin")
        assert rs.sequence == 0
        assert rs.type == "waypoint"

    def test_valid_full(self):
        rs = RouteStop(address="Hamburg", lat=53.0, lon=10.0, sequence=1, type="end")
        assert rs.lat == 53.0

    def test_serialization(self):
        _check_serialization(RouteStop(address="A"))


class TestRouteCalculateRequest:
    def test_valid_two_stops(self):
        req = RouteCalculateRequest(stops=[RouteStop(address="A"), RouteStop(address="B")])
        assert len(req.stops) == 2

    def test_valid_many_stops(self):
        stops = [RouteStop(address=f"S{i}") for i in range(5)]
        req = RouteCalculateRequest(stops=stops)
        assert req.optimize is True

    def test_defaults(self):
        req = RouteCalculateRequest(stops=[RouteStop(address="A"), RouteStop(address="B")])
        assert req.vehicle_profile == "truck"
        assert req.avoid_tolls is False
        assert req.return_geometry is True
        assert req.country_exclusions == []

    def test_one_stop_raises(self):
        with pytest.raises(ValidationError, match="at least 2 stops"):
            RouteCalculateRequest(stops=[RouteStop(address="Only")])

    def test_zero_stops_raises(self):
        with pytest.raises(ValidationError, match="at least 2 stops"):
            RouteCalculateRequest(stops=[])

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            RouteCalculateRequest(stops=[])
        assert "at least 2 stops" in str(exc.value)

    def test_serialization(self):
        _check_serialization(RouteCalculateRequest(stops=[RouteStop(address="A"), RouteStop(address="B")]))


class TestRouteResult:
    def test_valid_minimal(self):
        rr = RouteResult(distance_km=100.0, duration_minutes=60.0)
        assert rr.toll_cost_eur == 0.0

    def test_valid_full(self):
        rr = RouteResult(distance_km=250.0, duration_minutes=150.0, polyline="abc",
                         toll_cost_eur=5.0, fuel_cost_eur=50.0, total_cost_eur=55.0)
        assert rr.polyline == "abc"

    def test_serialization(self):
        _check_serialization(RouteResult(distance_km=10.0, duration_minutes=5.0))


# ===================================================================
#  DISPATCH MODELS
# ===================================================================

class TestDispatchCreate:
    def test_valid_minimal(self):
        dc = DispatchCreate(trip_id=1)
        assert dc.trip_id == 1
        assert dc.priority == 0

    def test_valid_full(self):
        dc = DispatchCreate(trip_id=1, truck_id=5, driver_id=3, priority=2)
        assert dc.truck_id == 5

    def test_serialization(self):
        _check_serialization(DispatchCreate(trip_id=1))


class TestDispatchAssign:
    def test_valid(self):
        da = DispatchAssign(dispatch_id=10, truck_id=5, driver_id=3)
        assert da.dispatch_id == 10

    def test_serialization(self):
        _check_serialization(DispatchAssign(dispatch_id=1, truck_id=2, driver_id=3))


class TestDispatchCancel:
    def test_valid(self):
        dc = DispatchCancel(dispatch_id=1)
        assert dc.reason == ""

    def test_valid_with_reason(self):
        dc = DispatchCancel(dispatch_id=1, reason="No driver available")
        assert dc.reason == "No driver available"

    def test_serialization(self):
        _check_serialization(DispatchCancel(dispatch_id=1, reason="cancel"))


class TestDispatchResult:
    def test_valid(self):
        now = datetime.now()
        dr = DispatchResult(id=1, trip_id=1, status="assigned", priority=0, created_at=now)
        assert dr.truck_plate == ""

    def test_serialization(self):
        _check_serialization(DispatchResult(id=1, trip_id=1, status="ok", priority=0, created_at=datetime.now()))


class TestUnassignedTrip:
    def test_valid(self):
        ut = UnassignedTrip(trip_id=1, reference="R1", client_name="Acme", pickup="Berlin", delivery="Hamburg", distance_km=300.0)
        assert ut.priority == 0

    def test_serialization(self):
        _check_serialization(UnassignedTrip(trip_id=1, reference="R", client_name="C", pickup="P", delivery="D", distance_km=10.0))


class TestAvailableTruck:
    def test_valid(self):
        at = AvailableTruck(truck_id=1, plate="AB123CD")
        assert at.location == ""

    def test_serialization(self):
        _check_serialization(AvailableTruck(truck_id=1, plate="PL"))


class TestDispatchBoardResult:
    def test_valid(self):
        dbr = DispatchBoardResult(assigned=[], unassigned=[], available_trucks=[])
        assert dbr.assigned == []

    def test_serialization(self):
        _check_serialization(DispatchBoardResult(assigned=[], unassigned=[], available_trucks=[]))


# ===================================================================
#  VEHICLE MODELS
# ===================================================================

class TestVehicleCreate:
    def test_valid_minimal(self):
        vc = VehicleCreate(plate="AB123CD")
        assert vc.plate == "AB123CD"
        assert vc.brand == ""
        assert vc.fuel_type == "diesel"

    def test_valid_full(self):
        vc = VehicleCreate(plate="xy-123-zz", brand="Volvo", model="FH", year=2021,
                           vin="YV12345", max_weight_kg=18000, fuel_type="diesel",
                           consumption_l_per_100km=30.0)
        assert vc.plate == "XY-123-ZZ"

    def test_defaults(self):
        vc = VehicleCreate(plate="AB123CD")
        assert vc.status == "active"
        assert vc.year is None
        assert vc.max_weight_kg is None

    def test_empty_plate_raises(self):
        with pytest.raises(ValidationError, match="Plate number is required"):
            VehicleCreate(plate="")

    def test_blank_plate_raises(self):
        with pytest.raises(ValidationError, match="Plate number is required"):
            VehicleCreate(plate="   ")

    def test_whitespace_only_plate_raises(self):
        with pytest.raises(ValidationError):
            VehicleCreate(plate="\t\n")

    def test_plate_normalized_upper(self):
        vc = VehicleCreate(plate="  ab-123-cd  ")
        assert vc.plate == "AB-123-CD"

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            VehicleCreate(plate="")
        assert "Plate number is required" in str(exc.value)

    def test_serialization(self):
        _check_serialization(VehicleCreate(plate="PLATE1"))


class TestVehicleUpdate:
    def test_valid_empty(self):
        vu = VehicleUpdate()
        assert vu.plate is None

    def test_valid_partial(self):
        vu = VehicleUpdate(plate="NEW123", brand="Updated")
        assert vu.plate == "NEW123"

    def test_serialization(self):
        _check_serialization(VehicleUpdate(status="inactive"))


class TestVehicleSearchRequest:
    def test_valid_defaults(self):
        vs = VehicleSearchRequest()
        assert vs.query == ""
        assert vs.page == 1
        assert vs.per_page == 20

    def test_valid_full(self):
        from datetime import datetime
        vs = VehicleSearchRequest(query="volvo", status="active", min_capacity_kg=10000, fuel_type="diesel")
        assert vs.min_capacity_kg == 10000

    def test_serialization(self):
        _check_serialization(VehicleSearchRequest(query="test"))


class TestVehicleHealthScore:
    def test_valid(self):
        vh = VehicleHealthScore(vehicle_id=1, plate="AB123CD", overall_score=85.0,
                                insurance_status="valid", technical_inspection_status="valid",
                                tachograph_status="valid", maintenance_alerts=0)
        assert vh.overall_score == 85.0

    def test_serialization(self):
        _check_serialization(VehicleHealthScore(
            vehicle_id=1, plate="P", overall_score=50.0,
            insurance_status="ok", technical_inspection_status="ok",
            tachograph_status="ok", maintenance_alerts=0,
        ))


class TestVehicleResult:
    def test_valid(self):
        vr = VehicleResult(id=1, plate="P1", brand="V", model="M", fuel_type="diesel", status="active")
        assert vr.vin == ""

    def test_serialization(self):
        _check_serialization(VehicleResult(id=1, plate="P", brand="B", model="M", fuel_type="diesel", status="ok"))


# ===================================================================
#  CLIENT MODELS
# ===================================================================

class TestClientContact:
    def test_valid_minimal(self):
        cc = ClientContact(name="John")
        assert cc.email == ""
        assert cc.phone == ""

    def test_valid_full(self):
        cc = ClientContact(name="Jane", email="j@j.com", phone="+401", position="Manager")
        assert cc.email == "j@j.com"

    def test_serialization(self):
        _check_serialization(ClientContact(name="Contact"))


class TestClientCreate:
    def test_valid_minimal(self):
        cc = ClientCreate(name="Acme Corp")
        assert cc.name == "Acme Corp"
        assert cc.contacts == []

    def test_valid_full(self):
        cc = ClientCreate(name="Beta", company_code="RO123", vat_number="VAT123",
                          address="Str 1", city="Bucharest", country="RO",
                          email="b@b.com", phone="+40", notes="note",
                          contacts=[ClientContact(name="C1")])
        assert len(cc.contacts) == 1

    def test_defaults(self):
        cc = ClientCreate(name="X")
        assert cc.company_code == ""
        assert cc.vat_number == ""
        assert cc.address == ""

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError, match="Client name is required"):
            ClientCreate(name="")

    def test_blank_name_raises(self):
        with pytest.raises(ValidationError, match="Client name is required"):
            ClientCreate(name="   ")

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            ClientCreate(name="")
        assert "Client name is required" in str(exc.value)

    def test_serialization(self):
        _check_serialization(ClientCreate(name="Valid Client"))


class TestClientUpdate:
    def test_valid_empty(self):
        cu = ClientUpdate()
        assert cu.name is None

    def test_valid_partial(self):
        cu = ClientUpdate(name="New Name", email="new@new.com")
        assert cu.email == "new@new.com"

    def test_serialization(self):
        _check_serialization(ClientUpdate(name="Changed"))


class TestClientResult:
    def test_valid(self):
        cr = ClientResult(id=1, name="Acme", company_code="", vat_number="", address="",
                          city="", country="", email="", phone="", notes="")
        assert cr.trip_count == 0

    def test_serialization(self):
        _check_serialization(ClientResult(id=1, name="N", company_code="", vat_number="",
                                          address="", city="", country="", email="", phone="", notes=""))


# ===================================================================
#  INVOICE MODELS
# ===================================================================

class TestInvoiceLineItem:
    def test_valid_minimal(self):
        il = InvoiceLineItem(description="Service", unit_price=100.0)
        assert il.quantity == 1.0
        assert il.vat_rate == 19.0

    def test_valid_full(self):
        il = InvoiceLineItem(description="Transport", quantity=2.0, unit_price=500.0,
                             vat_rate=9.0, total_net=1000.0, total_vat=90.0, total_gross=1090.0)
        assert il.total_net == 1000.0

    def test_serialization(self):
        _check_serialization(InvoiceLineItem(description="D", unit_price=10.0))


class TestInvoiceCreate:
    def test_valid(self):
        ic = InvoiceCreate(client_id=1, invoice_date=date(2024, 1, 1), due_date=date(2024, 2, 1))
        assert ic.currency == "EUR"

    def test_same_date_allowed(self):
        ic = InvoiceCreate(client_id=1, invoice_date=date(2024, 1, 1), due_date=date(2024, 1, 1))
        assert ic.due_date == ic.invoice_date

    def test_due_before_invoice_raises(self):
        with pytest.raises(ValidationError, match="Due date must be on or after invoice date"):
            InvoiceCreate(client_id=1, invoice_date=date(2024, 6, 1), due_date=date(2024, 5, 31))

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            InvoiceCreate(client_id=1, invoice_date=date(2024, 6, 1), due_date=date(2024, 5, 1))
        assert "Due date must be on or after invoice date" in str(exc.value)

    def test_serialization(self):
        _check_serialization(InvoiceCreate(client_id=1, invoice_date=date.today(), due_date=date.today()))


class TestInvoiceUpdate:
    def test_valid_empty(self):
        iu = InvoiceUpdate()
        assert iu.client_id is None

    def test_valid_partial(self):
        iu = InvoiceUpdate(client_id=2, status="finalized")
        assert iu.status == "finalized"

    def test_serialization(self):
        _check_serialization(InvoiceUpdate(notes="updated"))


class TestInvoiceFinalizeRequest:
    def test_valid_minimal(self):
        fr = InvoiceFinalizeRequest(invoice_id=1)
        assert fr.send_email is False
        assert fr.email_recipient == ""

    def test_valid_with_email(self):
        fr = InvoiceFinalizeRequest(invoice_id=1, send_email=True, email_recipient="test@test.com")
        assert fr.send_email is True

    def test_serialization(self):
        _check_serialization(InvoiceFinalizeRequest(invoice_id=1))


class TestInvoiceResult:
    def test_valid(self):
        ir = InvoiceResult(id=1, invoice_number="INV-001", client_id=1, client_name="Acme",
                           invoice_date=date.today(), due_date=date.today(), currency="EUR",
                           subtotal_net=1000.0, total_vat=190.0, total_gross=1190.0,
                           status="draft", notes="")
        assert ir.trip_reference == ""

    def test_serialization(self):
        _check_serialization(InvoiceResult(id=1, invoice_number="I1", client_id=1, client_name="C",
                                           invoice_date=date.today(), due_date=date.today(),
                                           currency="EUR", subtotal_net=0.0, total_vat=0.0,
                                           total_gross=0.0, status="draft", notes=""))


# ===================================================================
#  RECEIPT MODELS
# ===================================================================

class TestReceiptLineItem:
    def test_valid_minimal(self):
        rl = ReceiptLineItem(description="Fuel", amount=150.0)
        assert rl.quantity == 1.0

    def test_valid_full(self):
        rl = ReceiptLineItem(description="Toll", amount=50.0, quantity=2.0)
        assert rl.quantity == 2.0

    def test_serialization(self):
        _check_serialization(ReceiptLineItem(description="D", amount=10.0))


class TestReceiptCreate:
    def test_valid_minimal(self):
        rc = ReceiptCreate(client_id=1, receipt_date=date.today())
        assert rc.currency == "EUR"
        assert rc.items == []

    def test_valid_full(self):
        rc = ReceiptCreate(client_id=1, trip_id=10, invoice_id=5, vehicle_id=3,
                           receipt_date=date.today(), currency="RON",
                           items=[ReceiptLineItem(description="Fuel", amount=200.0)],
                           total_amount=200.0, notes="paid")
        assert len(rc.items) == 1

    def test_serialization(self):
        _check_serialization(ReceiptCreate(client_id=1, receipt_date=date.today()))


# ===================================================================
#  PAYMENT MODELS
# ===================================================================

class TestPaymentProfileCreate:
    def test_valid_minimal(self):
        pp = PaymentProfileCreate(name="Main account")
        assert pp.currency == "EUR"
        assert pp.is_default is False

    def test_valid_full(self):
        pp = PaymentProfileCreate(name="Secondary", bank_name="BCR", iban="RO123", swift="SWIFTBIC",
                                  currency="RON", is_default=True)
        assert pp.is_default is True

    def test_serialization(self):
        _check_serialization(PaymentProfileCreate(name="P"))


class TestPaymentBatchRequest:
    def test_valid_empty(self):
        pb = PaymentBatchRequest(profile_id=1)
        assert pb.invoice_ids == []
        assert pb.driver_ids == []

    def test_valid_full(self):
        pb = PaymentBatchRequest(profile_id=1, invoice_ids=[1, 2, 3], driver_ids=[4, 5])
        assert len(pb.invoice_ids) == 3

    def test_serialization(self):
        _check_serialization(PaymentBatchRequest(profile_id=1))


class TestPaymentProfileResult:
    def test_valid(self):
        pr = PaymentProfileResult(id=1, name="P", bank_name="B", iban="I", swift="S", currency="EUR", is_default=False)
        assert pr.name == "P"

    def test_serialization(self):
        _check_serialization(PaymentProfileResult(id=1, name="P", bank_name="B", iban="I", swift="S", currency="EUR", is_default=False))


class TestPaymentBatchResult:
    def test_valid(self):
        now = datetime.now()
        pbr = PaymentBatchResult(batch_id=1, file_path="/tmp/x.csv", row_count=10, total_amount=5000.0, currency="EUR", generated_at=now)
        assert pbr.row_count == 10

    def test_serialization(self):
        _check_serialization(PaymentBatchResult(batch_id=1, file_path="f", row_count=0, total_amount=0.0, currency="EUR", generated_at=datetime.now()))


# ===================================================================
#  PROFORMA MODELS
# ===================================================================

class TestProformaCreate:
    def test_valid_minimal(self):
        pc = ProformaCreate(client_id=1, issue_date=date.today(), valid_until=date(2024, 2, 1))
        assert pc.currency == "EUR"

    def test_valid_full(self):
        pc = ProformaCreate(client_id=1, trip_id=5, issue_date=date.today(),
                            valid_until=date(2024, 3, 1), currency="RON",
                            items=[{"desc": "Transport", "amount": 1000}], notes="note")
        assert len(pc.items) == 1

    def test_serialization(self):
        _check_serialization(ProformaCreate(client_id=1, issue_date=date.today(), valid_until=date(2024, 2, 1)))


class TestProformaResult:
    def test_valid(self):
        pr = ProformaResult(id=1, proforma_number="PF-001", client_id=1, client_name="Acme",
                            issue_date=date.today(), valid_until=date.today(), currency="EUR",
                            total_amount=1000.0, status="draft")
        assert pr.notes == ""

    def test_serialization(self):
        _check_serialization(ProformaResult(id=1, proforma_number="P", client_id=1, client_name="C",
                                            issue_date=date.today(), valid_until=date.today(),
                                            currency="EUR", total_amount=0.0, status="draft"))


# ===================================================================
#  DOCUMENT MODELS
# ===================================================================

class TestDocumentUpload:
    def test_valid_minimal(self):
        du = DocumentUpload(source_path="/tmp/doc.pdf")
        assert du.title == "doc"  # derived from filename
        assert du.category == ""

    def test_valid_explicit_title(self):
        du = DocumentUpload(source_path="/tmp/doc.pdf", title="My Document")
        assert du.title == "My Document"

    def test_valid_full(self):
        du = DocumentUpload(source_path="/tmp/inv.pdf", title="Invoice", category="invoice",
                            entity_type="trip", entity_id=42, description="desc", tags=["urgent"])
        assert du.entity_id == 42
        assert du.tags == ["urgent"]

    def test_title_defaults_from_source_path(self):
        du = DocumentUpload(source_path="C:\\Users\\test\\document.pdf")
        assert du.title == "document"

    def test_title_empty_without_source_path_ok(self):
        # source_path is required, title is derived from it if empty
        du = DocumentUpload(source_path="/tmp/first.pdf")
        assert du.title == "first"

    def test_serialization(self):
        _check_serialization(DocumentUpload(source_path="/tmp/x.pdf"))


class TestDocumentResult:
    def test_valid(self):
        dr = DocumentResult(id=1, title="Doc", category="invoice", entity_type="trip",
                            filename="doc.pdf", file_size=1024, mime_type="application/pdf")
        assert dr.tags == []
        assert dr.ocr_processed is False

    def test_serialization(self):
        _check_serialization(DocumentResult(id=1, title="T", category="C", entity_type="E",
                                            filename="F", file_size=0, mime_type="M"))


# ===================================================================
#  OCR MODELS
# ===================================================================

class TestOcrProcessRequest:
    def test_valid_minimal(self):
        ocr = OcrProcessRequest(document_id=1)
        assert ocr.language == "auto"
        assert ocr.extract_fields is True

    def test_valid_explicit(self):
        ocr = OcrProcessRequest(document_id=5, language="ro", extract_fields=False, match_to_trips=False)
        assert ocr.language == "ro"

    def test_serialization(self):
        _check_serialization(OcrProcessRequest(document_id=1))


class TestExtractedFields:
    def test_valid_defaults(self):
        ef = ExtractedFields()
        assert ef.raw_text == ""
        assert ef.confidence == 0.0
        assert ef.additional_fields == {}

    def test_valid_full(self):
        ef = ExtractedFields(document_number="INV-001", amount=1500.0, currency="EUR", confidence=0.95)
        assert ef.amount == 1500.0

    def test_serialization(self):
        _check_serialization(ExtractedFields())


class TestMatchedTrip:
    def test_valid(self):
        mt = MatchedTrip(trip_id=1, trip_reference="REF-001", confidence=0.87)
        assert mt.match_reason == ""

    def test_serialization(self):
        _check_serialization(MatchedTrip(trip_id=1, trip_reference="R", confidence=0.5))


class TestOcrResult:
    def test_valid(self):
        ocr_result = OcrResult(document_id=1, success=True)
        assert ocr_result.matched_trips == []
        assert ocr_result.error_message == ""

    def test_serialization(self):
        _check_serialization(OcrResult(document_id=1, success=False))


# ===================================================================
#  ANALYTICS MODELS
# ===================================================================

class TestAnalyticsRequest:
    def test_valid_defaults(self):
        ar = AnalyticsRequest()
        assert ar.group_by == "month"
        assert ar.start_date is None

    def test_valid_full(self):
        ar = AnalyticsRequest(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
                              client_id=5, group_by="quarter")
        assert ar.client_id == 5

    def test_serialization(self):
        _check_serialization(AnalyticsRequest())


class TestRevenueReport:
    def test_valid(self):
        rr = RevenueReport(total_revenue=100000, total_cost=70000, total_profit=30000,
                           margin_pct=30.0, trip_count=50, invoice_count=40, average_trip_revenue=2000.0)
        assert rr.currency == "EUR"

    def test_serialization(self):
        _check_serialization(RevenueReport(total_revenue=0, total_cost=0, total_profit=0,
                                           margin_pct=0, trip_count=0, invoice_count=0, average_trip_revenue=0))


class TestOverdueReport:
    def test_valid(self):
        oa = OverdueReport(total_overdue=5000.0, overdue_count=3, average_days_late=15.0)
        assert oa.items == []

    def test_serialization(self):
        _check_serialization(OverdueReport(total_overdue=0, overdue_count=0, average_days_late=0))


class TestKpiDashboard:
    def test_valid(self):
        rev = RevenueReport(total_revenue=0, total_cost=0, total_profit=0, margin_pct=0,
                            trip_count=0, invoice_count=0, average_trip_revenue=0)
        overdue = OverdueReport(total_overdue=0, overdue_count=0, average_days_late=0)
        kpi = KpiDashboard(revenue=rev, overdue=overdue, active_trips=10, active_vehicles=5,
                           total_distance_km=5000.0, total_fuel_liters=1500.0,
                           period=(date(2024, 1, 1), date(2024, 12, 31)), generated_at=date.today())
        assert kpi.active_trips == 10

    def test_serialization(self):
        rev = RevenueReport(total_revenue=0, total_cost=0, total_profit=0, margin_pct=0,
                            trip_count=0, invoice_count=0, average_trip_revenue=0)
        overdue = OverdueReport(total_overdue=0, overdue_count=0, average_days_late=0)
        _check_serialization(KpiDashboard(revenue=rev, overdue=overdue, active_trips=0, active_vehicles=0,
                                          total_distance_km=0, total_fuel_liters=0,
                                          period=(date.today(), date.today()), generated_at=date.today()))


# ===================================================================
#  EXPORT MODELS
# ===================================================================

class TestExportRequest:
    def test_valid_defaults(self):
        er = ExportRequest(entity_type="trip")
        assert er.format == "pdf"
        assert er.template == "default"
        assert er.language == "ro"

    def test_valid_explicit(self):
        er = ExportRequest(format="excel", entity_type="invoice", entity_id=5,
                           template="standard", filename="report", include_logo=False, language="en")
        assert er.format == "excel"

    def test_valid_csv(self):
        er = ExportRequest(format="csv", entity_type="analytics")
        assert er.format == "csv"

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            ExportRequest(format="docx", entity_type="trip")

    def test_serialization(self):
        _check_serialization(ExportRequest(entity_type="trip"))


class TestExportResult:
    def test_valid(self):
        now = datetime.now()
        er = ExportResult(file_path="/tmp/out.pdf", format="pdf", entity_type="trip", file_size=1024, generated_at=now)
        assert er.file_size == 1024

    def test_serialization(self):
        _check_serialization(ExportResult(file_path="f", format="pdf", entity_type="t", file_size=0, generated_at=datetime.now()))


# ===================================================================
#  CMR MODELS
# ===================================================================

class TestCmrGenerateRequest:
    def test_valid_minimal(self):
        cmr = CmrGenerateRequest(trip_id=1)
        assert cmr.language == "ro"
        assert cmr.copies == 3
        assert cmr.include_stamps is True

    def test_valid_full(self):
        cmr = CmrGenerateRequest(trip_id=1, language="en", copies=5, include_stamps=False,
                                 sender_name="Sender", sender_address="Addr", carrier_name="Carrier",
                                 carrier_license="LIC", remarks="Urgent")
        assert cmr.copies == 5

    def test_serialization(self):
        _check_serialization(CmrGenerateRequest(trip_id=1))


class TestCmrResult:
    def test_valid(self):
        now = datetime.now()
        cmr = CmrResult(cmr_number="CMR-001", trip_id=1, file_path="/tmp/cmr.pdf", copies=3, generated_at=now)
        assert cmr.cmr_data == {}

    def test_serialization(self):
        _check_serialization(CmrResult(cmr_number="C", trip_id=1, file_path="f", copies=1, generated_at=datetime.now()))


# ===================================================================
#  COST MODELS
# ===================================================================

class TestCostEstimateRequest:
    def test_valid_minimal(self):
        cer = CostEstimateRequest(distance_km=500.0)
        assert cer.fuel_type == "diesel"
        assert cer.currency == "EUR"

    def test_valid_full(self):
        cer = CostEstimateRequest(distance_km=1000.0, truck_id=5, fuel_type="gasoline",
                                  consumption_l_per_100km=30.0, fuel_price_per_liter=1.5,
                                  toll_cost_eur=50.0, driver_daily_rate=200.0, days=2.0,
                                  extra_costs={"parking": 20.0}, currency="RON")
        assert cer.driver_daily_rate == 200.0

    def test_defaults(self):
        cer = CostEstimateRequest(distance_km=100.0)
        assert cer.toll_cost_eur == 0.0
        assert cer.driver_daily_rate == 0.0
        assert cer.days == 1.0
        assert cer.extra_costs == {}

    def test_distance_zero_raises(self):
        with pytest.raises(ValidationError, match="Distance must be positive"):
            CostEstimateRequest(distance_km=0.0)

    def test_distance_negative_raises(self):
        with pytest.raises(ValidationError, match="Distance must be positive"):
            CostEstimateRequest(distance_km=-10.0)

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            CostEstimateRequest(distance_km=0.0)
        assert "Distance must be positive" in str(exc.value)

    def test_serialization(self):
        _check_serialization(CostEstimateRequest(distance_km=100.0))


class TestCostBreakdown:
    def test_valid(self):
        cb = CostBreakdown(fuel_cost=500.0, toll_cost=50.0, driver_cost=200.0,
                           total_cost=750.0, cost_per_km=1.5, currency="EUR")
        assert cb.extra_costs == {}

    def test_serialization(self):
        _check_serialization(CostBreakdown(fuel_cost=0, toll_cost=0, driver_cost=0, total_cost=0, cost_per_km=0, currency="EUR"))


class TestCostEstimateResult:
    def test_valid(self):
        cb = CostBreakdown(fuel_cost=0, toll_cost=0, driver_cost=0, total_cost=0, cost_per_km=0, currency="EUR")
        cer = CostEstimateResult(distance_km=500.0, days=1.0, breakdown=cb)
        assert cer.truck_info == ""

    def test_serialization(self):
        cb = CostBreakdown(fuel_cost=0, toll_cost=0, driver_cost=0, total_cost=0, cost_per_km=0, currency="EUR")
        _check_serialization(CostEstimateResult(distance_km=100.0, days=1.0, breakdown=cb))


# ===================================================================
#  DRIVER MODELS
# ===================================================================

class TestDriverCreate:
    def test_valid_minimal(self):
        dc = DriverCreate(name="John Doe")
        assert dc.email == ""
        assert dc.hours_worked == 0.0
        assert dc.max_hours_per_day == 9.0

    def test_valid_full(self):
        dc = DriverCreate(name="Jane", email="j@j.com", phone="+401", license_number="LIC123",
                          license_expiry=date(2025, 1, 1), hours_worked=40.0, max_hours_per_day=10.0, status="active")
        assert dc.license_number == "LIC123"

    def test_defaults(self):
        dc = DriverCreate(name="Driver")
        assert dc.status == "active"
        assert dc.max_hours_per_day == 9.0

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError, match="Driver name is required"):
            DriverCreate(name="")

    def test_blank_name_raises(self):
        with pytest.raises(ValidationError, match="Driver name is required"):
            DriverCreate(name="   ")

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            DriverCreate(name="")
        assert "Driver name is required" in str(exc.value)

    def test_serialization(self):
        _check_serialization(DriverCreate(name="Valid Driver"))


class TestDriverUpdate:
    def test_valid_empty(self):
        du = DriverUpdate()
        assert du.name is None

    def test_valid_partial(self):
        du = DriverUpdate(name="Updated", status="inactive")
        assert du.status == "inactive"

    def test_serialization(self):
        _check_serialization(DriverUpdate(name="Changed"))


class TestDriverHoursCheck:
    def test_valid_minimal(self):
        dhc = DriverHoursCheck(driver_id=1, check_date=date.today())
        assert dhc.planned_hours == 0.0

    def test_valid_full(self):
        dhc = DriverHoursCheck(driver_id=1, check_date=date.today(), planned_hours=8.0)
        assert dhc.planned_hours == 8.0

    def test_serialization(self):
        _check_serialization(DriverHoursCheck(driver_id=1, check_date=date.today()))


class TestDriverResult:
    def test_valid(self):
        dr = DriverResult(id=1, name="John", email="j@j.com", phone="+40",
                          license_number="L123", hours_worked=0.0, max_hours_per_day=9.0, status="active")
        assert dr.current_truck_plate == ""

    def test_serialization(self):
        _check_serialization(DriverResult(id=1, name="N", email="e@e.com", phone="P",
                                          license_number="L", hours_worked=0, max_hours_per_day=9, status="ok"))


class TestDriverHoursResult:
    def test_valid(self):
        dhr = DriverHoursResult(driver_id=1, driver_name="John", hours_worked_today=4.0,
                                hours_worked_week=20.0, max_hours_per_day=9.0,
                                available_hours_today=5.0, is_compliant=True)
        assert dhr.warnings == []

    def test_serialization(self):
        _check_serialization(DriverHoursResult(driver_id=1, driver_name="N", hours_worked_today=0,
                                                hours_worked_week=0, max_hours_per_day=9,
                                                available_hours_today=9, is_compliant=True))


class TestTruckAssignment:
    def test_valid(self):
        ta = TruckAssignment(driver_id=1, truck_id=5)
        assert ta.assigned_at is None

    def test_serialization(self):
        _check_serialization(TruckAssignment(driver_id=1, truck_id=1))


# ===================================================================
#  TACHO MODELS
# ===================================================================

class TestTachoImportRequest:
    def test_valid_minimal(self):
        tir = TachoImportRequest(file_path="/tmp/data.ddd")
        assert tir.file_type == "ddd"
        assert tir.driver_id is None

    def test_valid_full(self):
        tir = TachoImportRequest(file_path="/tmp/data.c1b", file_type="c1b", driver_id=1, vehicle_id=5)
        assert tir.file_type == "c1b"

    def test_empty_path_raises(self):
        with pytest.raises(ValidationError, match="File path is required"):
            TachoImportRequest(file_path="")

    def test_blank_path_raises(self):
        with pytest.raises(ValidationError, match="File path is required"):
            TachoImportRequest(file_path="   ")

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            TachoImportRequest(file_path="")
        assert "File path is required" in str(exc.value)

    def test_serialization(self):
        _check_serialization(TachoImportRequest(file_path="/tmp/data.ddd"))


class TestDriverActivity:
    def test_valid(self):
        da = DriverActivity(date=date.today(), activity_type="driving",
                            start_time=datetime.now(), end_time=datetime.now(), duration_minutes=480.0)
        assert da.driver_name == ""

    def test_serialization(self):
        _check_serialization(DriverActivity(date=date.today(), activity_type="rest",
                                            start_time=datetime.now(), end_time=datetime.now(),
                                            duration_minutes=60.0))


class TestVehicleActivity:
    def test_valid(self):
        va = VehicleActivity(plate="AB123CD", date=date.today(),
                             odometer_start=10000.0, odometer_end=10500.0, distance_km=500.0)
        assert va.vehicle_id is None

    def test_serialization(self):
        _check_serialization(VehicleActivity(plate="P", date=date.today(),
                                             odometer_start=0, odometer_end=0, distance_km=0))


class TestTachoImportResult:
    def test_valid(self):
        tir = TachoImportResult(import_id=1, file_path="/tmp/data.ddd", file_type="ddd", status="success")
        assert tir.errors == []
        assert tir.warnings == []

    def test_serialization(self):
        _check_serialization(TachoImportResult(import_id=1, file_path="f", file_type="ddd", status="ok"))


class TestDriverHoursAnalysis:
    def test_valid(self):
        dha = DriverHoursAnalysis(driver_name="John", date=date.today(), total_driving_hours=8.0,
                                  total_rest_hours=2.0, total_work_hours=10.0, is_compliant=True)
        assert dha.violations == []

    def test_serialization(self):
        _check_serialization(DriverHoursAnalysis(driver_name="N", date=date.today(),
                                                  total_driving_hours=0, total_rest_hours=0,
                                                  total_work_hours=0, is_compliant=True))


class TestFleetTachoSummary:
    def test_valid(self):
        fts = FleetTachoSummary(plate="AB123CD", date=date.today(), total_distance_km=500.0,
                                total_driving_hours=8.0, average_speed=62.5, max_speed=90.0, driver_count=1)
        assert fts.average_speed == 62.5

    def test_serialization(self):
        _check_serialization(FleetTachoSummary(plate="P", date=date.today(), total_distance_km=0,
                                                total_driving_hours=0, average_speed=0, max_speed=0, driver_count=0))


# ===================================================================
#  CALCULATOR MODELS
# ===================================================================

class TestCalculationRequest:
    def test_valid_minimal(self):
        cr = CalculationRequest(km=500.0, price_eur=1000.0, fuel_price=1.5, consum_litri=30.0)
        assert cr.days == 1.0
        assert cr.sal_in == 0.0
        assert cr.taxa_in == 0.0

    def test_valid_full(self):
        cr = CalculationRequest(km=1200.0, price_eur=2000.0, fuel_price=1.6, consum_litri=32.0,
                                days=3.0, extra_in=100.0, sal_in=300.0, taxa_in=50.0,
                                fuel_cost_override=500.0)
        assert cr.extra_in == 100.0

    def test_km_zero_raises(self):
        with pytest.raises(ValidationError, match="Distance .* must be positive"):
            CalculationRequest(km=0.0, price_eur=100.0, fuel_price=1.5, consum_litri=30.0)

    def test_km_negative_raises(self):
        with pytest.raises(ValidationError, match="Distance .* must be positive"):
            CalculationRequest(km=-10.0, price_eur=100.0, fuel_price=1.5, consum_litri=30.0)

    def test_price_negative_raises(self):
        with pytest.raises(ValidationError, match="Price cannot be negative"):
            CalculationRequest(km=100.0, price_eur=-50.0, fuel_price=1.5, consum_litri=30.0)

    def test_fuel_price_zero_raises(self):
        with pytest.raises(ValidationError, match="Fuel price must be positive"):
            CalculationRequest(km=100.0, price_eur=100.0, fuel_price=0.0, consum_litri=30.0)

    def test_fuel_price_negative_raises(self):
        with pytest.raises(ValidationError, match="Fuel price must be positive"):
            CalculationRequest(km=100.0, price_eur=100.0, fuel_price=-1.0, consum_litri=30.0)

    def test_days_zero_raises(self):
        with pytest.raises(ValidationError, match="Days must be positive"):
            CalculationRequest(km=100.0, price_eur=100.0, fuel_price=1.5, consum_litri=30.0, days=0.0)

    def test_consumption_zero_raises(self):
        with pytest.raises(ValidationError, match="Consumption must be positive"):
            CalculationRequest(km=100.0, price_eur=100.0, fuel_price=1.5, consum_litri=0.0)

    def test_multiple_validation_errors(self):
        with pytest.raises(ValidationError) as exc:
            CalculationRequest(km=0.0, price_eur=-1.0, fuel_price=0.0, consum_litri=0.0)
        # Should report multiple errors
        assert len(exc.value.errors()) >= 4

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            CalculationRequest(km=100.0, price_eur=100.0, fuel_price=1.5, consum_litri=0.0)
        assert "Consumption must be positive" in str(exc.value)

    def test_serialization(self):
        _check_serialization(CalculationRequest(km=100.0, price_eur=100.0, fuel_price=1.5, consum_litri=30.0))


class TestTripCalculationResult:
    def test_valid(self):
        tcr = TripCalculationResult(
            km=500.0, price_eur=1000.0, fuel_price=1.5, days=1.0, consum_litri=30.0,
            total_income=1000.0, fuel_consumed_liters=150.0, fuel_cost=225.0,
            net_profit=775.0, profit_per_km=1.55, margin_percent=77.5, cost_per_km=0.45,
        )
        assert tcr.currency == "EUR"
        assert tcr.extra_in == 0.0

    def test_serialization(self):
        _check_serialization(TripCalculationResult(
            km=100, price_eur=100, fuel_price=1.5, days=1, consum_litri=30,
            total_income=100, fuel_consumed_liters=30, fuel_cost=45,
            net_profit=55, profit_per_km=0.55, margin_percent=55, cost_per_km=0.45,
        ))


# ===================================================================
#  AUTOMAIL MODELS
# ===================================================================

class TestEmailTemplateCreate:
    def test_valid_minimal(self):
        etc = EmailTemplateCreate(name="Reminder", subject="Payment Reminder", body_html="<p>Please pay</p>")
        assert etc.language == "ro"
        assert etc.type == "reminder"

    def test_valid_full(self):
        etc = EmailTemplateCreate(name="Invoice", subject="Invoice", body_html="<p>Invoice</p>",
                                  language="en", type="invoice")
        assert etc.type == "invoice"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError, match="Template name is required"):
            EmailTemplateCreate(name="", subject="S", body_html="B")

    def test_blank_name_raises(self):
        with pytest.raises(ValidationError, match="Template name is required"):
            EmailTemplateCreate(name="   ", subject="S", body_html="B")

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            EmailTemplateCreate(name="", subject="S", body_html="B")
        assert "Template name is required" in str(exc.value)

    def test_serialization(self):
        _check_serialization(EmailTemplateCreate(name="T", subject="S", body_html="<p>B</p>"))


class TestSendReminderRequest:
    def test_valid(self):
        srr = SendReminderRequest(template_id=1, client_id=2, recipient_email="client@test.com")
        assert srr.attachments == []

    def test_valid_full(self):
        srr = SendReminderRequest(template_id=1, client_id=2, invoice_id=5, trip_id=10,
                                  recipient_email="client@example.com", attachments=[1, 2])
        assert len(srr.attachments) == 2

    def test_invalid_email_no_at(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            SendReminderRequest(template_id=1, client_id=2, recipient_email="invalid")

    def test_invalid_email_no_domain(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            SendReminderRequest(template_id=1, client_id=2, recipient_email="user@")

    def test_invalid_email_no_dot(self):
        with pytest.raises(ValidationError, match="Invalid email address"):
            SendReminderRequest(template_id=1, client_id=2, recipient_email="user@domain")

    def test_validation_messages(self):
        with pytest.raises(ValidationError) as exc:
            SendReminderRequest(template_id=1, client_id=2, recipient_email="bad")
        assert "Invalid email address" in str(exc.value)

    def test_serialization(self):
        _check_serialization(SendReminderRequest(template_id=1, client_id=2, recipient_email="a@b.com"))


class TestSendReminderResult:
    def test_valid(self):
        now = datetime.now()
        srr = SendReminderResult(email_id=1, sent_to="a@b.com", template_name="Reminder",
                                 sent_at=now, success=True)
        assert srr.error_message == ""

    def test_serialization(self):
        _check_serialization(SendReminderResult(email_id=1, sent_to="a@b.com", template_name="T",
                                                sent_at=datetime.now(), success=True))


# ===================================================================
#  EXTRA FIELDS — models with extra="forbid" should reject unknown fields
#  NOTE: Currently none of the models use extra="forbid" or model_config.
#        This test confirms that behaviour (no model rejects extras by default).
# ===================================================================

class TestExtraFields:
    """Verify that models either reject or accept extra fields as configured.

    Pydantic v2 by default ignores extra fields unless extra="forbid" is set.
    Currently (July 2026) none of the existing models set extra="forbid",
    so extras are silently ignored. When a model is later configured with
    extra="forbid", this test will fail and remind the author to add a
    dedicated test for that model.
    """

    # Representative sample of models — test that unknown fields are NOT rejected
    # (change to with pytest.raises when a model gains extra="forbid")
    SAMPLE_MODELS = [
        ("TripCreate", lambda: TripCreate(client_id=1, start_date=date(2024, 1, 1))),
        ("VehicleCreate", lambda: VehicleCreate(plate="AB123CD")),
        ("ClientCreate", lambda: ClientCreate(name="Test")),
        ("InvoiceCreate", lambda: InvoiceCreate(client_id=1, invoice_date=date.today(), due_date=date.today())),
        ("DriverCreate", lambda: DriverCreate(name="Test")),
        ("DispatchCreate", lambda: DispatchCreate(trip_id=1)),
        ("CalculationRequest", lambda: CalculationRequest(km=100, price_eur=100, fuel_price=1.5, consum_litri=30)),
        ("ExportRequest", lambda: ExportRequest(entity_type="trip")),
    ]

    @pytest.mark.parametrize("model_name, factory", SAMPLE_MODELS, ids=[m[0] for m in SAMPLE_MODELS])
    def test_unknown_fields_are_accepted_by_default(self, model_name, factory):
        """All models currently accept extra fields silently (ignore)."""
        instance = factory()
        # Attempting to construct with an unknown field should not raise
        try:
            instance.__class__(**{**instance.model_dump(), "unknown_field": "xyz"})
        except ValidationError:
            pytest.fail(f"{model_name} rejected an unknown field — "
                        f"if extra='forbid' was added, update this test accordingly.")


# ===================================================================
#  TYPE ALIASES (ServiceResult wrappers)
# ===================================================================

class TestServiceResultWrappers:
    """Verify that ServiceResult[T] type aliases construct and serialize correctly."""

    @pytest.mark.parametrize("alias_name, factory", [
        ("TripCreateResult", lambda: TripCreateResult(success=True, data=TripResult(id=1, client_id=1, client_name="C", reference="R", start_date=date.today(), price_eur=0, currency="EUR", status="P"))),
        ("TripListResult", lambda: TripListResult(success=True, data=[])),
        ("RouteCalculationResult", lambda: RouteCalculationResult(success=True, data=RouteResult(distance_km=10, duration_minutes=5))),
        ("DispatchCreateResult", lambda: DispatchCreateResult(success=True, data=DispatchResult(id=1, trip_id=1, status="s", priority=0, created_at=datetime.now()))),
        ("DispatchBoardResult_Typed", lambda: DispatchBoardResult_Typed(success=True, data=DispatchBoardResult(assigned=[], unassigned=[], available_trucks=[]))),
        ("VehicleCreateResult", lambda: VehicleCreateResult(success=True, data=VehicleResult(id=1, plate="P", brand="B", model="M", fuel_type="d", status="a"))),
        ("VehicleSearchResult", lambda: VehicleSearchResult(success=True, data=[])),
        ("ClientCreateResult", lambda: ClientCreateResult(success=True, data=ClientResult(id=1, name="N", company_code="", vat_number="", address="", city="", country="", email="", phone="", notes=""))),
        ("ClientListResult", lambda: ClientListResult(success=True, data=[])),
        ("InvoiceCreateResult", lambda: InvoiceCreateResult(success=True, data=InvoiceResult(id=1, invoice_number="I", client_id=1, client_name="C", invoice_date=date.today(), due_date=date.today(), currency="EUR", subtotal_net=0, total_vat=0, total_gross=0, status="d", notes=""))),
        ("InvoiceListResult", lambda: InvoiceListResult(success=True, data=[])),
        ("ReceiptCreateResult", lambda: ReceiptCreateResult(success=True, data=ReceiptResult(id=1, receipt_number="R", client_id=1, client_name="C", receipt_date=date.today(), currency="EUR", items=[], total_amount=0))),
        ("ProformaCreateResult", lambda: ProformaCreateResult(success=True, data=ProformaResult(id=1, proforma_number="P", client_id=1, client_name="C", issue_date=date.today(), valid_until=date.today(), currency="EUR", total_amount=0, status="d"))),
        ("PaymentBatchCreateResult", lambda: PaymentBatchCreateResult(success=True, data=PaymentBatchResult(batch_id=1, file_path="f", row_count=0, total_amount=0, currency="EUR", generated_at=datetime.now()))),
        ("DocumentUploadResult", lambda: DocumentUploadResult(success=True, data=DocumentResult(id=1, title="T", category="C", entity_type="E", filename="F", file_size=0, mime_type="M"))),
        ("DocumentListResult", lambda: DocumentListResult(success=True, data=[])),
        ("OcrProcessResult", lambda: OcrProcessResult(success=True, data=OcrResult(document_id=1, success=True))),
        ("AnalyticsReportResult", lambda: AnalyticsReportResult(success=True, data=KpiDashboard(
            revenue=RevenueReport(total_revenue=0, total_cost=0, total_profit=0, margin_pct=0, trip_count=0, invoice_count=0, average_trip_revenue=0),
            overdue=OverdueReport(total_overdue=0, overdue_count=0, average_days_late=0),
            active_trips=0, active_vehicles=0, total_distance_km=0, total_fuel_liters=0,
            period=(date.today(), date.today()), generated_at=date.today(),
        ))),
        ("ExportOperationResult", lambda: ExportOperationResult(success=True, data=ExportResult(file_path="f", format="pdf", entity_type="t", file_size=0, generated_at=datetime.now()))),
        ("CmrGenerateResult", lambda: CmrGenerateResult(success=True, data=CmrResult(cmr_number="C", trip_id=1, file_path="f", copies=1, generated_at=datetime.now()))),
        ("CostEstimateOperationResult", lambda: CostEstimateOperationResult(success=True, data=CostEstimateResult(
            distance_km=100, days=1,
            breakdown=CostBreakdown(fuel_cost=0, toll_cost=0, driver_cost=0, total_cost=0, cost_per_km=0, currency="EUR"),
        ))),
        ("DriverCreateResult", lambda: DriverCreateResult(success=True, data=DriverResult(id=1, name="N", email="e@e.com", phone="P", license_number="L", hours_worked=0, max_hours_per_day=9, status="a"))),
        ("DriverHoursCheckResult", lambda: DriverHoursCheckResult(success=True, data=DriverHoursResult(driver_id=1, driver_name="N", hours_worked_today=0, hours_worked_week=0, max_hours_per_day=9, available_hours_today=9, is_compliant=True))),
        ("CalculationOperationResult", lambda: CalculationOperationResult(success=True, data=TripCalculationResult(
            km=100, price_eur=100, fuel_price=1.5, days=1, consum_litri=30,
            total_income=100, fuel_consumed_liters=30, fuel_cost=45,
            net_profit=55, profit_per_km=0.55, margin_percent=55, cost_per_km=0.45,
        ))),
        ("AutomailSendResult", lambda: AutomailSendResult(success=True, data=SendReminderResult(email_id=1, sent_to="a@b.com", template_name="T", sent_at=datetime.now(), success=True))),
        ("TachoImportOperationResult", lambda: TachoImportOperationResult(success=True, data=TachoImportResult(import_id=1, file_path="f", file_type="ddd", status="ok"))),
        ("TachoAnalysisResult", lambda: TachoAnalysisResult(success=True, data=DriverHoursAnalysis(driver_name="N", date=date.today(), total_driving_hours=0, total_rest_hours=0, total_work_hours=0, is_compliant=True))),
        ("TachoFleetSummaryResult", lambda: TachoFleetSummaryResult(success=True, data=[FleetTachoSummary(plate="P", date=date.today(), total_distance_km=0, total_driving_hours=0, average_speed=0, max_speed=0, driver_count=0)])),
    ])
    def test_alias_construct_and_serialize(self, alias_name, factory):
        result = factory()
        assert result.success is True
        assert result.errors == []
        assert result.undo_token is None
        # Serialization round-trip
        d = result.model_dump()
        assert isinstance(d, dict)
        j = result.model_dump_json()
        assert isinstance(j, str)
        parsed = json.loads(j)
        assert parsed["success"] is True

    def test_alias_error_case(self):
        """ServiceResult with success=False and errors."""
        sr = TripCreateResult(
            success=False,
            errors=[ErrorDetail(field="price", message="Negative", code="VAL_001")],
        )
        assert sr.data is None
        assert len(sr.errors) == 1
        assert sr.errors[0].field == "price"

    def test_alias_undo_token(self):
        """ServiceResult with undo_token."""
        ut = UndoToken(operation_id="123", operation_type="create", undo_description="undo")
        sr = DriverCreateResult(
            success=True,
            data=DriverResult(id=1, name="N", email="e@e.com", phone="P", license_number="L",
                              hours_worked=0, max_hours_per_day=9, status="a"),
            undo_token=ut,
        )
        assert sr.undo_token is not None
        assert sr.undo_token.operation_id == "123"
        # Serialization should include undo_token
        parsed = json.loads(sr.model_dump_json())
        assert parsed["undo_token"]["operation_id"] == "123"
