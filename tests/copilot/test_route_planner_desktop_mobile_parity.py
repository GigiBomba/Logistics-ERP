"""Route Planner — desktop/mobile parity, scripted via the backend test client.

Blueprint §6.2 + §11 (Gate 1 adjudication — D6 IMPLEMENT): the desktop route
planner and the mobile ``route_planner`` feature must consume the SAME route
calculation contract.  No desktop app is needed — this file scripts the
parity through the backend API:

- **Shared input fixture** — the exact multi-stop input the mobile parity
  test uses: ``mobile/test/features/route_planner/test_route_planner_parity.dart``
  feeds ``['Bucharest', 'Ploiești', 'Cluj-Napoca']`` with ``profile='truck'``
  through ``buildRouteRequest``.
- **Scripted desktop side** — ``POST /api/v1/routes/calculate`` via the repo's
  standard ``create_app`` + dependency-override TestClient (mirroring
  ``tests/freight_exchange/test_api_contract.py`` / ``tests/contracts/``).
  GraphHopper and Nominatim are mocked exactly the way the repo's chaos tests
  do (``patch.object(GraphHopperClient, 'route')`` and
  ``patch('services.geocode_nominatim.geocode_place')``) so no live routing
  server is required.
- **Scripted mobile side** — the Dart contract fixture: ``buildRouteRequest``
  output (``{points, profile: 'truck'}``) plus the expected parsed values
  (distance/duration/geometry/instructions) asserted in the Dart test.

The deliverable is a printed diff artifact: the canonical parity lines from
the mobile fixture vs. the same lines derived from the live backend response.
The artifact must show **ZERO differences**.
"""
from __future__ import annotations

import copy
import difflib
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from backend.main import create_app
from tests.test_helpers import InMemoryDB

_ROUTES_CALCULATE_URL = "/api/v1/routes/calculate"

# ────────────────────────────────────────────────────────────────────────────
# Shared input fixture — sourced from the mobile parity test
# (mobile/test/features/route_planner/test_route_planner_parity.dart:56-60).
# ────────────────────────────────────────────────────────────────────────────
POINTS = ["Bucharest", "Ploiești", "Cluj-Napoca"]
PROFILE = "truck"
MOBILE_REQUEST_BODY = {"points": POINTS, "profile": PROFILE}

# Fixed geocoding for the three stops — identical to the geometry points the
# Dart fixture's canned route carries (parity test lines 15-30).
_GEO = {
    "Bucharest": (44.4268, 26.1025),
    "Ploiești": (45.0, 26.5),
    "Cluj-Napoca": (46.7712, 23.6236),
}

# Canned GraphHopper result — the normalized route dict that
# ``GraphHopperClient.route`` returns.  Field values match the Dart fixture's
# ``_cannedRouteResponse`` exactly (distance_km 124.5 / duration_min 96.0 /
# 3 geometry points / 2 instructions).
CANNED_GH_ROUTE: Dict[str, Any] = {
    "distance_km": 124.5,
    "duration_min": 96.0,
    "geometry": [
        (44.4268, 26.1025),
        (45.0, 26.5),
        (46.7712, 23.6236),
    ],
    "instructions": [
        {
            "text": "Turn right",
            "distance_meters": 120,
            "time_seconds": 0.0,
            "sign": 2,
            "interval_start": 0,
            "interval_end": 1,
            "point_index": 0,
        },
        {
            "text": "Keep straight",
            "distance_meters": 250,
            "time_seconds": 0.0,
            "sign": 1,
            "interval_start": 1,
            "interval_end": 2,
            "point_index": 1,
        },
    ],
    "points_count": 3,
    "request_time_s": 0.0,
    "graphhopper_response": {},
    "avoid_countries": [],
    "exclusions_applied": False,
    "routing_method": "GET",
    "exclusion_strategy": None,
}


def _fake_geocode(address: str, *args, **kwargs):
    """Stand-in for ``services.geocode_nominatim.geocode_place``."""
    if address not in _GEO:
        return None
    return _GEO[address]


def _canned_gh_route(*args, **kwargs) -> Dict[str, Any]:
    """Return a fresh copy of the canned GraphHopper route per call.

    ``RouteService.calculate_route`` mutates the dict it receives
    (``res['profile']``, ``res['stops']``, ...) and caches it — a deep copy
    per call keeps every request deterministic.
    """
    return copy.deepcopy(CANNED_GH_ROUTE)


# ────────────────────────────────────────────────────────────────────────────
# Fixtures — standard ``create_app`` + dependency overrides
# (tests/freight_exchange/test_api_contract.py conventions).
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db() -> InMemoryDB:
    """Fresh in-memory SQLite database for each test."""
    return InMemoryDB()


@pytest.fixture
def client(db: InMemoryDB) -> TestClient:
    """TestClient with mocked get_db + require_dispatcher (dispatcher role)."""
    app = create_app()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    async def _mock_dispatcher() -> Dict[str, Any]:
        return {
            "id": 1,
            "email": "dispatcher@test.com",
            "role": "dispatcher",
            "is_admin": False,
            "company_id": 1,
        }

    app.dependency_overrides[require_dispatcher] = _mock_dispatcher

    return TestClient(app)


# ────────────────────────────────────────────────────────────────────────────
# Canonical parity lines — one key=value line per compared field, in a fixed
# order, derived independently from (a) the mobile Dart fixture and (b) the
# live backend response.  The diff between the two must be EMPTY.
# ────────────────────────────────────────────────────────────────────────────


def _fmt_coord(value: float) -> str:
    """Canonical float formatting (strip trailing zeros, no exponent)."""
    return "{:.6f}".format(round(float(value), 6)).rstrip("0").rstrip(".")


def _fmt_geom(point) -> str:
    lat, lng = point
    return f"[{_fmt_coord(lat)}, {_fmt_coord(lng)}]"


def _mobile_expected_lines() -> List[str]:
    """Canonical lines derived from the Dart parity fixture.

    Sources:
      - request body:      test_route_planner_parity.dart:56-60 (buildRouteRequest)
      - distance/duration: test_route_planner_parity.dart:97-100
        (124.5 km → 124500 m; 96 min → 5760 s)
      - geometry:          test_route_planner_parity.dart:102-107
      - instructions:      test_route_planner_parity.dart:109-113
    """
    lines: List[str] = []
    lines.append(f"request.points={tuple(POINTS)!r}")
    lines.append(f"request.profile={PROFILE!r}")
    lines.append("route.distance_km=124.5")
    lines.append("route.distance_meters=124500")
    lines.append(f"route.duration_min={_fmt_coord(96.0)}")
    lines.append("route.duration_seconds=5760")
    lines.append("route.geometry_count=3")
    lines.append(f"route.geometry[0]={_fmt_geom((44.4268, 26.1025))}")
    lines.append(f"route.geometry[-1]={_fmt_geom((46.7712, 23.6236))}")
    lines.append("route.instructions_count=2")
    lines.append(f"route.instructions[0].text={repr('Turn right')}")
    lines.append("route.instructions[0].distance_meters=120")
    lines.append("route.instructions[0].point_index=0")
    return lines


def _backend_actual_lines(request_body: Dict[str, Any], route: Dict[str, Any]) -> List[str]:
    """Canonical lines derived from the live backend response."""
    geometry = route.get("geometry") or []
    instructions = route.get("instructions") or []
    first_inst = instructions[0] if instructions else {}

    lines: List[str] = []
    lines.append(f"request.points={tuple(request_body['points'])!r}")
    lines.append(f"request.profile={request_body['profile']!r}")
    lines.append(f"route.distance_km={_fmt_coord(route['distance_km'])}")
    lines.append(f"route.distance_meters={int(round(float(route['distance_km']) * 1000))}")
    lines.append(f"route.duration_min={_fmt_coord(route['duration_min'])}")
    lines.append(f"route.duration_seconds={int(round(float(route['duration_min']) * 60))}")
    lines.append(f"route.geometry_count={len(geometry)}")
    lines.append(f"route.geometry[0]={_fmt_geom(geometry[0])}")
    lines.append(f"route.geometry[-1]={_fmt_geom(geometry[-1])}")
    lines.append(f"route.instructions_count={len(instructions)}")
    lines.append(f"route.instructions[0].text={first_inst.get('text', '')!r}")
    lines.append(f"route.instructions[0].distance_meters={first_inst.get('distance_meters', 0)}")
    lines.append(f"route.instructions[0].point_index={first_inst.get('point_index', -1)}")
    return lines


def _print_parity_artifact(diff_lines: List[str]) -> None:
    """Print the zero-differences artifact for the session record."""
    print("\n===== ROUTE PLANNER DESKTOP/MOBILE PARITY ARTIFACT =====")
    print("  mobile fixture : test_route_planner_parity.dart (buildRouteRequest + parsed values)")
    print(f"  desktop script : POST {_ROUTES_CALCULATE_URL} (GraphHopper/Nominatim mocked)")
    if diff_lines:
        print("\n".join(diff_lines))
    else:
        print("  diff: <no differences — mobile fixture and backend response agree>")
    print(f"  PARITY_DIFF_LINES={len(diff_lines)}")
    print("============================================================")


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────


class TestRequestParity:
    """The request body the desktop script sends is identical to the mobile
    ``buildRouteRequest`` output."""

    def test_request_body_matches_mobile_build_route_request(self) -> None:
        assert MOBILE_REQUEST_BODY == {"points": POINTS, "profile": "truck"}

    @patch("services.geocode_nominatim.geocode_place", side_effect=_fake_geocode)
    @patch("services.route_service.GraphHopperClient.route", side_effect=_canned_gh_route)
    def test_desktop_posts_identical_request_body(
        self, mock_gh_route, mock_geocode, client: TestClient,
    ) -> None:
        resp = client.post(_ROUTES_CALCULATE_URL, json=MOBILE_REQUEST_BODY)
        assert resp.status_code == 200, f"routes/calculate failed: {resp.text}"
        body = resp.json()
        assert body["status"] == "ok"
        assert set(body.keys()) == {"status", "route"}

        # The route service must have been asked for the geocoded triple
        # (origin → waypoint → destination), truck profile.
        called_with = mock_gh_route.call_args[0][0]
        assert called_with == [
            (44.4268, 26.1025),
            (45.0, 26.5),
            (46.7712, 23.6236),
        ]
        assert mock_gh_route.call_args.kwargs["profile"] == "truck"

    def test_request_body_is_the_mobile_fixture(self) -> None:
        """Guard: this test file and the Dart fixture share one input."""
        assert POINTS == ["Bucharest", "Ploiești", "Cluj-Napoca"]
        assert PROFILE == "truck"


class TestResponseParity:
    """The backend response route matches the mobile fixture's expected parsed
    values EXACTLY (geometry point count, distance_km, duration_min,
    instruction count/content)."""

    @patch("services.geocode_nominatim.geocode_place", side_effect=_fake_geocode)
    @patch("services.route_service.GraphHopperClient.route", side_effect=_canned_gh_route)
    def test_route_matches_mobile_fixture_exactly(
        self, mock_gh_route, mock_geocode, client: TestClient,
    ) -> None:
        resp = client.post(_ROUTES_CALCULATE_URL, json=MOBILE_REQUEST_BODY)
        assert resp.status_code == 200, f"routes/calculate failed: {resp.text}"
        route = resp.json()["route"]

        # distance: 124.5 km == the Dart parse expectation (124500 meters).
        assert route["distance_km"] == 124.5
        assert int(round(route["distance_km"] * 1000)) == 124500

        # duration: 96 min == 5760 seconds (Dart: durationSeconds, 5760).
        assert route["duration_min"] == 96.0
        assert int(round(route["duration_min"] * 60)) == 5760

        # geometry: exactly 3 [lat, lng] pairs, first/last matching the Dart
        # geometry assertions (44.4268/26.1025 and 46.7712/23.6236).
        geometry = route["geometry"]
        assert len(geometry) == 3
        assert [geometry[0][0], geometry[0][1]] == [44.4268, 26.1025]
        assert [geometry[-1][0], geometry[-1][1]] == [46.7712, 23.6236]

        # instructions: exactly 2, first step "Turn right"/120 m/point 0.
        instructions = route["instructions"]
        assert len(instructions) == 2
        assert instructions[0]["text"] == "Turn right"
        assert instructions[0]["distance_meters"] == 120
        assert instructions[0]["point_index"] == 0


class TestParityDiffArtifact:
    """Deliverable: the printed diff between the mobile fixture and the live
    backend response shows ZERO differences."""

    @patch("services.geocode_nominatim.geocode_place", side_effect=_fake_geocode)
    @patch("services.route_service.GraphHopperClient.route", side_effect=_canned_gh_route)
    def test_diff_between_mobile_fixture_and_backend_is_empty(
        self, mock_gh_route, mock_geocode, client: TestClient,
    ) -> None:
        resp = client.post(_ROUTES_CALCULATE_URL, json=MOBILE_REQUEST_BODY)
        assert resp.status_code == 200, f"routes/calculate failed: {resp.text}"

        mobile_lines = _mobile_expected_lines()
        backend_lines = _backend_actual_lines(MOBILE_REQUEST_BODY, resp.json()["route"])

        assert len(mobile_lines) == len(backend_lines), (
            "Canonical line count drifted between fixture and backend — "
            f"mobile={len(mobile_lines)} backend={len(backend_lines)}"
        )

        diff_lines = list(
            difflib.unified_diff(
                mobile_lines,
                backend_lines,
                fromfile="mobile_fixture",
                tofile="backend_response",
                lineterm="",
            )
        )

        _print_parity_artifact(diff_lines)

        # THE artifact: zero differences.
        assert diff_lines == [], (
            "Desktop/mobile parity broken — differences:\n" + "\n".join(diff_lines)
        )
