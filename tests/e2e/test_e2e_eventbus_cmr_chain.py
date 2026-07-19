"""E2E: EventBus CMR generation chain — auto-CMR on trip status change.

Tests the AutoCMRGenerator subscriber that listens to TRIP_STATUS_CHANGED
events and generates CMR documents when a trip enters 'In Transit'.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from repositories.client_repository import ClientRepository
from repositories.driver_repository import DriverRepository
from repositories.document_repository import DocumentRepository
from repositories.fleet_repository import FleetRepository
from services.document_service import DocumentService
from services.invoicing.cmr_generator import CMRGenerator
from services.operations.alert_manager import AlertManager, AlertType, Severity
from services.operations.cmr_auto_generator import AutoCMRGenerator
from services.operations.event_bus import TRIP_STATUS_CHANGED, EventBus
from services.trip_service import TripService
from tests.test_helpers import make_db

pytestmark = pytest.mark.slow

logging.disable(logging.CRITICAL)


# ── Helpers ───────────────────────────────────────────────────────────────

def _dt(days_offset: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")


def _create_minimal_trip(db, status="Planned", cargo="Test cargo", **extra) -> int:
    svc = TripService(db)
    now = datetime.now().isoformat()
    # Seed a minimal client so FK constraints are satisfied
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, email, is_active, created_at, updated_at) "
        "VALUES (1, 'CMR Chain Client AG', 'cmr@test.com', 1, ?, ?)",
        (now, now),
    )
    db.conn.commit()
    # Seed truck and driver if IDs provided in extra (or default)
    if extra.get("truck_id"):
        db.conn.execute(
            "INSERT OR IGNORE INTO trucks (id, plate_number, manufacturer, model, year, status) "
            "VALUES (?, ?, ?, ?, ?, 'active')",
            (extra["truck_id"], "TR-CMR-001", "MAN", "TGX", 2023),
        )
        db.conn.commit()
    if extra.get("driver_id"):
        db.conn.execute(
            "INSERT OR IGNORE INTO drivers (id, name, license_number, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (extra["driver_id"], "CMR Driver", "LIC-CMR-001", now, now),
        )
        db.conn.commit()
    data = {
        "client_name": "CMR Chain Client AG",
        "client_id": 1,
        "truck_number": "TR-CMR-001",
        "driver_name": "CMR Driver",
        "start_date": _dt(0),
        "end_date": _dt(2),
        "distance_km": 850.0,
        "total_price_eur": 3400.0,
        "currency": "EUR",
        "status": status,
        "created_at": now,
        "cargo_description": cargo,
        "package_count": 24,
        "package_type": "Pallets",
        "gross_weight_kg": 12000.0,
        "loading_country": "DE",
        "delivery_country": "RO",
    }
    data.update(extra)
    return svc.add(data)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestEventBusCMRChain:
    """EventBus CMR generation chain — auto-CMR on trip status change."""

    def test_trip_in_transit_triggers_cmr_generation(self, db):
        """Publish TRIP_STATUS_CHANGED with 'In Transit', verify subscriber fires."""
        trip_id = _create_minimal_trip(db, status="Loading")
        alert_mgr = AlertManager(db)
        prefs = MagicMock()

        generator = AutoCMRGenerator(db=db, prefs=prefs, alert_mgr=alert_mgr)
        subscriber = MagicMock(wraps=generator.on_trip_in_transit)

        eb = EventBus()
        eb.subscribe(TRIP_STATUS_CHANGED, subscriber)

        # Publish In Transit event
        eb.publish(TRIP_STATUS_CHANGED, {
            "trip_id": trip_id,
            "old_status": "Loading",
            "new_status": "In Transit",
        })

        # The subscriber spawns a daemon thread, but we can check it was called
        subscriber.assert_called_once()
        call_args = subscriber.call_args[0][0]
        assert call_args["data"]["new_status"] == "In Transit"
        assert call_args["data"]["trip_id"] == trip_id

    def test_cmr_generation_creates_4_document_copies(self, db):
        """Mock CMRGenerator.generate_all_copies, call AutoCMRGenerator.generate(),
        verify 4 document records in DB."""
        # Seed a company so FK documents.company_id -> companies.id is satisfied
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, is_active, created_at, updated_at) "
            "VALUES (1, 'Test Company', 1, datetime('now'), datetime('now'))"
        )
        db.conn.commit()
        trip_id = _create_minimal_trip(db, status="Loading", driver_id=1, truck_id=1)
        alert_mgr = AlertManager(db)
        prefs = MagicMock()

        # Create temp files for the fake paths so register_existing works
        import tempfile
        _tmpdir = tempfile.mkdtemp()
        try:
            fake_paths = {
                "Sender": os.path.join(_tmpdir, "cmr_sender.pdf"),
                "Consignee": os.path.join(_tmpdir, "cmr_consignee.pdf"),
                "Carrier": os.path.join(_tmpdir, "cmr_carrier.pdf"),
                "Administrative": os.path.join(_tmpdir, "cmr_admin.pdf"),
            }
            # Use unique content per file to avoid hash-based dedup
            for suffix, p in fake_paths.items():
                with open(p, "wb") as _f:
                    _f.write(f"dummy cmr content {suffix}".encode())

            with patch.object(CMRGenerator, "generate_all_copies", return_value=fake_paths):
                generator = AutoCMRGenerator(db=db, prefs=prefs, alert_mgr=alert_mgr)
                # Call generate directly (bypass threading)
                generator.generate(trip_id)

            # Verify 4 document records were created
            doc_repo = DocumentRepository(db)
            docs = doc_repo.get_documents_for_entity("trip", trip_id)
            # tags is stored as JSON string in DB, parse it properly
            def _has_cmr_tag(doc):
                raw = doc.get("tags") or "[]"
                try:
                    tags = json.loads(raw) if isinstance(raw, str) else (raw or [])
                except (json.JSONDecodeError, TypeError):
                    return False
                return any("cmr" in str(t).lower() for t in tags)
            cmr_docs = [d for d in docs if _has_cmr_tag(d)]
            assert len(cmr_docs) == 4
        finally:
            import shutil
            shutil.rmtree(_tmpdir, ignore_errors=True)

    def test_cmr_blocked_without_cargo_data(self, db):
        """Trip without cargo_description, verify no CMR + alert created."""
        trip_id = _create_minimal_trip(db, status="Loading", cargo_description=None,
                                        gross_weight_kg=None)
        alert_mgr = AlertManager(db)
        prefs = MagicMock()

        with patch.object(CMRGenerator, "generate_all_copies") as mock_gen:
            generator = AutoCMRGenerator(db=db, prefs=prefs, alert_mgr=alert_mgr)
            generator.generate(trip_id)

        # CMR generation should NOT be called
        mock_gen.assert_not_called()

        # An alert should have been created
        alerts = alert_mgr.get_active_alerts(limit=50)
        trip_alerts = [a for a in alerts if a.trip_id == str(trip_id)]
        assert len(trip_alerts) >= 1
        assert "CMR blocked" in trip_alerts[0].title

    def test_cmr_skips_if_already_generated(self, db):
        """Generate CMR twice, verify no duplicates."""
        trip_id = _create_minimal_trip(db, status="In Transit")
        alert_mgr = AlertManager(db)
        prefs = MagicMock()

        # Insert existing CMR documents in DB and link them to the trip
        doc_repo = DocumentRepository(db)
        now = datetime.now().isoformat()
        for suffix in ("Sender", "Consignee", "Carrier", "Administrative"):
            doc_id = doc_repo.create(
                doc_number=f"CMR-{trip_id}-{suffix}",
                title=f"CMR - {suffix} COPY",
                category="trips",
                entity_type="trip",
                entity_id=trip_id,
                file_path=f"/tmp/cmr_{suffix.lower()}.pdf",
                file_name=f"cmr_{suffix.lower()}.pdf",
                file_size=1024,
                mime_type="application/pdf",
                file_hash=f"hash_{suffix}",
                tags=json.dumps(["cmr", suffix.lower(), "auto-generated"]),
                description="",
                uploaded_by="system",
                uploaded_at=now,
                updated_at=now,
            )
            # Also create the document link so get_documents_for_entity finds them
            doc_repo.add_link(doc_id, "trip", trip_id, "attached", now)

        # Second generation — should detect existing CMR docs and skip
        with patch.object(CMRGenerator, "generate_all_copies") as mock_gen:
            generator = AutoCMRGenerator(db=db, prefs=prefs, alert_mgr=alert_mgr)
            generator.generate(trip_id)

        # generate_all_copies should NOT be called the second time
        mock_gen.assert_not_called()

    def test_cmr_event_subscriber_only_fires_on_in_transit(self, db):
        """Publish with 'Loading' (no CMR gen), then 'In Transit' (triggers CMR)."""
        trip_id = _create_minimal_trip(db, status="Loading")
        alert_mgr = AlertManager(db)
        prefs = MagicMock()

        generator = AutoCMRGenerator(db=db, prefs=prefs, alert_mgr=alert_mgr)
        # Spy on generate to detect when CMR generation is triggered
        with patch.object(generator, "generate") as mock_generate:
            eb = EventBus()
            subscriber = MagicMock(wraps=generator.on_trip_in_transit)
            eb.subscribe(TRIP_STATUS_CHANGED, subscriber)

            # Publish Loading event — subscriber fires but generate should NOT be called
            eb.publish(TRIP_STATUS_CHANGED, {
                "trip_id": trip_id,
                "old_status": "Planned",
                "new_status": "Loading",
            })
            # The subscriber IS called (it's subscribed to the event),
            # but generate() should not be triggered for non-Transit status
            mock_generate.assert_not_called()

            # Now publish In Transit — should trigger generate
            eb.publish(TRIP_STATUS_CHANGED, {
                "trip_id": trip_id,
                "old_status": "Loading",
                "new_status": "In Transit",
            })
            # generate should have been called now
            mock_generate.assert_called_once_with(trip_id)

    def test_cmr_adr_certificate_check_blocks_generation(self, db):
        """Driver with expired ADR certificate, verify CMR blocked + compliance alert."""
        # Create driver with expired ADR certificate
        driver_repo = DriverRepository(db)
        now = datetime.now().isoformat()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        driver_id = driver_repo.create({
            "name": "ADR Expired Driver",
            "phone": "+40-700-000-002",
            "email": "adr.expired@example.com",
            "license_number": "RO/88888/XYZ",
            "license_category": "CE",
            "license_expiry": _dt(365),
            "medical_expiry": _dt(180),
            "hire_date": _dt(-365),
            "monthly_salary": 3500.0,
            "is_active": 1,
            "adr_certificate": "ADR-2023-001",
            "adr_certificate_expiry": yesterday,
            "created_at": now,
            "updated_at": now,
        })

        # Create trip with ADR info and driver_id
        adr_json = json.dumps([{
            "un_no": "UN1203",
            "adr_class": "3",
            "packing_group": "II",
            "tunnel_code": "E",
            "quantity": 100,
            "net_weight": 1000,
        }])
        trip_id = _create_minimal_trip(
            db, status="Loading",
            driver_id=driver_id,
            adr_info_json=adr_json,
        )

        alert_mgr = AlertManager(db)
        prefs = MagicMock()

        with patch.object(CMRGenerator, "generate_all_copies") as mock_gen:
            generator = AutoCMRGenerator(db=db, prefs=prefs, alert_mgr=alert_mgr)
            generator.generate(trip_id)

        # CMR generation should be blocked
        mock_gen.assert_not_called()

        # A COMPLIANCE_RISK alert should have been created
        alerts = alert_mgr.get_active_alerts(limit=50)
        compliance_alerts = [
            a for a in alerts
            if a.type == AlertType.COMPLIANCE_RISK
            and a.trip_id == str(trip_id)
        ]
        assert len(compliance_alerts) >= 1
        assert "ADR certificate expired" in compliance_alerts[0].title
