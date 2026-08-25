"""Contract tests for ``GET /api/v1/mobile/driver/trip-overview``.

Validates the Python-side response schema against the authoritative mobile
contract (``mobile/lib/features/driver/models/driver_trip_overview.dart``):

- ``transport_id`` is a *string* (never an int)
- ``status`` is one of ``planned | loading | in_transit | delivered | cancelled``
- ``eta`` is ISO-8601
- ``eta_confidence`` is ``live`` or ``stale`` (null = no ETA available)
- when the driver has no current trip the endpoint returns HTTP 200 with
  every field null (NOT 404) — the mobile app renders its empty state.

Uses the repo's standard TestClient + ``create_app`` convention with
dependency overrides (see ``tests/freight_exchange/test_api_contract.py``).
"""
from __future__ import annotations


from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.dependencies import get_db
from backend.dependencies_security import get_current_user
from backend.main import create_app
from backend.schemas.mobile import DriverTripOverviewResponse
from database.db_manager import DatabaseManager

# All mobile endpoints are mounted under /api/v1 (see router.py).
_API_PREFIX = "/api/v1"
_TRIP_OVERVIEW_URL = f"{_API_PREFIX}/mobile/driver/trip-overview"

# ── Contract payloads — snake_case keys per the Dart model ──────────────

EXPECTED_KEYS = {
    "transport_id",
    "load_info",
    "origin",
    "destination",
    "status",
    "status_since",
    "eta",
    "eta_confidence",
}

FULL_PAYLOAD = {
    "transport_id": "42",
    "load_info": "REF-42",
    "origin": "Berlin",
    "destination": "Paris",
    "status": "in_transit",
    "status_since": "2026-07-31T08:00:00Z",
    "eta": "2026-07-31T18:30:00Z",
    "eta_confidence": "live",
}

ALL_NULL_PAYLOAD = {key: None for key in EXPECTED_KEYS}


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (matches Dart's ``DateTime.tryParse``)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _seed_driver_with_trip(db: DatabaseManager) -> None:
    """Seed a driver user linked to a driver record with one active trip."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.conn.execute(
        "INSERT INTO users (email, password_hash, role, company_id, is_active, created_at) "
        "VALUES (?, ?, 'driver', 1, 1, ?)",
        ("driver-contract@test.com", "not-used", now),
    )
    db.conn.execute(
        "INSERT INTO drivers (name, email, user_id, company_id, is_active, created_at, updated_at) "
        "VALUES (?, ?, 1, 1, 1, ?, ?)",
        ("Contract Driver", "driver-contract@test.com", now, now),
    )
    db.conn.execute(
        """INSERT INTO trips (driver_id, company_id, status, cmr_number,
                              place_of_loading, delivery_country, start_date,
                              end_date, created_at)
           VALUES (1, 1, 'In Transit', 'REF-C-1', 'Berlin', 'Paris',
                   ?, ?, ?)""",
        (now, "2026-08-01T18:00:00Z", now),
    )
    db.conn.commit()


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db(tmp_path):
    """Fresh file-backed SQLite database with the full app schema.

    Uses a temporary file rather than ``:memory:``: TestClient executes
    sync endpoints in an anyio worker thread, which gets its own SQLite
    connection — a file DB is visible across all threads.

    Seeds company IDs 0–100 so FK constraints on ``company_id`` columns
    (which reference ``companies(id)``) do not block test inserts.
    """
    db = DatabaseManager(str(tmp_path / "contract.db"))
    for cid in range(0, 101):
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (?, ?, 'starter')",
            (cid, f"Company-{cid}"),
        )
    db.conn.commit()
    yield db
    db.close()


@pytest.fixture
def driver_client(db: DatabaseManager) -> TestClient:
    """TestClient with a mocked driver identity (real endpoint logic runs)."""
    app = create_app()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    async def _mock_driver() -> Dict[str, Any]:
        return {
            "id": 1,
            "email": "driver-contract@test.com",
            "role": "driver",
            "is_admin": False,
            "company_id": 1,
        }

    app.dependency_overrides[get_current_user] = _mock_driver
    return TestClient(app)


# ════════════════════════════════════════════════════════════════════════
# Schema-level contract round-trip
# ════════════════════════════════════════════════════════════════════════


class TestDriverTripOverviewSchema:
    """Schema-level round-trip contract for ``DriverTripOverviewResponse``."""

    def test_full_payload_round_trips_with_exact_fields(self) -> None:
        model = DriverTripOverviewResponse.model_validate(FULL_PAYLOAD)
        data = model.model_dump()
        assert set(data) == EXPECTED_KEYS
        assert data == FULL_PAYLOAD

    def test_transport_id_is_a_string_never_an_int(self) -> None:
        data = DriverTripOverviewResponse.model_validate(FULL_PAYLOAD).model_dump()
        assert isinstance(data["transport_id"], str)
        assert data["transport_id"] == "42"

    def test_eta_is_iso8601(self) -> None:
        data = DriverTripOverviewResponse.model_validate(FULL_PAYLOAD).model_dump()
        assert data["eta"] == "2026-07-31T18:30:00Z"
        parsed = _parse_iso(data["eta"])
        assert parsed.year == 2026 and parsed.hour == 18

    def test_status_since_is_iso8601(self) -> None:
        data = DriverTripOverviewResponse.model_validate(FULL_PAYLOAD).model_dump()
        assert _parse_iso(data["status_since"]).minute == 0

    def test_status_is_enum_constrained(self) -> None:
        for value in ("planned", "loading", "in_transit", "delivered", "cancelled"):
            model = DriverTripOverviewResponse.model_validate({**FULL_PAYLOAD, "status": value})
            assert model.status == value
        with pytest.raises(ValidationError):
            DriverTripOverviewResponse.model_validate({**FULL_PAYLOAD, "status": "in-progress"})

    def test_eta_confidence_is_enum_constrained(self) -> None:
        for value in ("live", "stale"):
            model = DriverTripOverviewResponse.model_validate({**FULL_PAYLOAD, "eta_confidence": value})
            assert model.eta_confidence == value
        # null is allowed — the app falls back to its 'unavailable' value
        assert (
            DriverTripOverviewResponse.model_validate(
                {**FULL_PAYLOAD, "eta_confidence": None}
            ).eta_confidence
            is None
        )
        with pytest.raises(ValidationError):
            DriverTripOverviewResponse.model_validate(
                {**FULL_PAYLOAD, "eta_confidence": "unavailable"}
            )

    def test_all_null_payload_validates(self) -> None:
        model = DriverTripOverviewResponse.model_validate(ALL_NULL_PAYLOAD)
        data = model.model_dump()
        assert set(data) == EXPECTED_KEYS
        assert all(v is None for v in data.values())


# ════════════════════════════════════════════════════════════════════════
# Endpoint behaviour — empty-state contract
# ════════════════════════════════════════════════════════════════════════


class TestDriverTripOverviewEndpoint:
    """Endpoint returns HTTP 200 + all-null body when no trip is current."""

    def test_unauthenticated_request_returns_401(self, db: DatabaseManager) -> None:
        """Without an auth override the real auth dependency runs → 401."""
        app = create_app()

        async def _override_get_db():
            yield db

        app.dependency_overrides[get_db] = _override_get_db
        resp = TestClient(app).get(_TRIP_OVERVIEW_URL)
        assert resp.status_code == 401

    def test_no_driver_record_returns_200_with_all_null_body(
        self, driver_client: TestClient
    ) -> None:
        """Driver with no linked driver record → 200 + all null (NOT 404)."""
        resp = driver_client.get(_TRIP_OVERVIEW_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == EXPECTED_KEYS
        assert all(v is None for v in body.values())

    def test_no_active_trip_returns_200_with_all_null_body(
        self, driver_client: TestClient, db: DatabaseManager
    ) -> None:
        """Driver whose trips are all terminal → 200 + all null."""
        _seed_driver_with_trip(db)
        db.conn.execute("UPDATE trips SET status = 'Delivered' WHERE id = 1")
        db.conn.commit()

        resp = driver_client.get(_TRIP_OVERVIEW_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == EXPECTED_KEYS
        assert all(v is None for v in body.values())

    def test_active_trip_returns_contract_fields(
        self, driver_client: TestClient, db: DatabaseManager
    ) -> None:
        """Driver with an active trip → mapped contract fields (snake_case)."""
        _seed_driver_with_trip(db)

        resp = driver_client.get(_TRIP_OVERVIEW_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == EXPECTED_KEYS
        assert body["transport_id"] == "1"
        assert isinstance(body["transport_id"], str)
        assert body["load_info"] == "REF-C-1"
        assert body["origin"] == "Berlin"
        assert body["destination"] == "Paris"
        assert body["status"] == "in_transit"
        assert _parse_iso(body["status_since"]).tzinfo is not None
        assert body["eta"] == "2026-08-01T18:00:00Z"
        # end_date is a planned ETA → "stale" (truthful; null would hide the ETA)
        assert body["eta_confidence"] == "stale"

    def test_unknown_status_maps_to_null(
        self, driver_client: TestClient, db: DatabaseManager
    ) -> None:
        """DB status values outside the contract enum → ``status: null``."""
        _seed_driver_with_trip(db)
        db.conn.execute("UPDATE trips SET status = 'NonExistentStatus' WHERE id = 1")
        db.conn.commit()

        resp = driver_client.get(_TRIP_OVERVIEW_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] is None
        assert body["transport_id"] == "1"

    def test_driver_cannot_see_other_driver_trip(
        self, db: DatabaseManager
    ) -> None:
        """Driver B must never receive driver A's trip through this endpoint."""
        _seed_driver_with_trip(db)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Driver B — same company, own user/driver/trip records.
        db.conn.execute(
            "INSERT INTO users (email, password_hash, role, company_id, is_active, created_at) "
            "VALUES (?, ?, 'driver', 1, 1, ?)",
            ("driver-b@test.com", "not-used", now),
        )
        db.conn.execute(
            "INSERT INTO drivers (name, email, user_id, company_id, is_active, created_at, updated_at) "
            "VALUES (?, ?, 2, 1, 1, ?, ?)",
            ("Driver B", "driver-b@test.com", now, now),
        )
        db.conn.execute(
            """INSERT INTO trips (driver_id, company_id, status, cmr_number,
                                  place_of_loading, delivery_country, start_date,
                                  end_date, created_at)
               VALUES (2, 1, 'In Transit', 'REF-C-2', 'Madrid', 'Rome',
                       ?, ?, ?)""",
            (now, "2026-08-02T18:00:00Z", now),
        )
        db.conn.commit()

        app = create_app()

        async def _override_get_db():
            yield db

        app.dependency_overrides[get_db] = _override_get_db

        async def _mock_driver_b() -> Dict[str, Any]:
            return {
                "id": 2,
                "email": "driver-b@test.com",
                "role": "driver",
                "is_admin": False,
                "company_id": 1,
            }

        app.dependency_overrides[get_current_user] = _mock_driver_b
        resp = TestClient(app).get(_TRIP_OVERVIEW_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["transport_id"] == "2"
        assert body["load_info"] == "REF-C-2"
        assert body["origin"] == "Madrid"
