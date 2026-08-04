"""Contract tests for ``GET /api/v1/mobile/driver/transports/{id}/route-share``.

Validates the existing ``RouteShareResponse`` schema against the mobile
``RouteShareGeometry`` Dart contract
(``mobile/lib/features/driver/models/route_share_geometry.dart``):

- ``points`` items: ``lat`` / ``lng`` (double, Dart ``num``-coerced)
- ``instructions`` items: ``text_key`` (string), ``distance_meters`` (double),
  ``point_index`` (int)
- ``total_distance_meters`` double, ``total_duration_seconds`` int
- ``generated_at`` ISO-8601 (Dart ``DateTime.parse``), ``ttl_seconds`` int

All JSON keys are snake_case, matching the Dart ``toJson``/``fromJson``
contract exactly.
"""

from datetime import datetime

from backend.schemas.mobile import RouteInstruction, RoutePoint, RouteShareResponse

EXPECTED_KEYS = {
    "transport_id",
    "points",
    "instructions",
    "total_distance_meters",
    "total_duration_seconds",
    "generated_at",
    "ttl_seconds",
}

FULL_PAYLOAD = {
    "transport_id": "7",
    "points": [
        {"lat": 52.5200, "lng": 13.4050},
        {"lat": 48.8566, "lng": 2.3522},
    ],
    "instructions": [
        {"text_key": "Turn right", "distance_meters": 150.5, "point_index": 0},
        {"text_key": "Continue straight", "distance_meters": 800.0, "point_index": 1},
    ],
    "total_distance_meters": 1054500.0,
    "total_duration_seconds": 36000,
    "generated_at": "2026-07-31T10:00:00Z",
    "ttl_seconds": 300,
}


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (matches Dart's ``DateTime.parse``)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class TestRouteShareGeometrySchema:
    """Schema-level round-trip contract for ``RouteShareResponse``."""

    def test_full_payload_round_trips_with_exact_fields(self) -> None:
        model = RouteShareResponse.model_validate(FULL_PAYLOAD)
        data = model.model_dump()
        assert set(data) == EXPECTED_KEYS
        assert data == FULL_PAYLOAD

    def test_transport_id_is_a_string(self) -> None:
        data = RouteShareResponse.model_validate(FULL_PAYLOAD).model_dump()
        assert isinstance(data["transport_id"], str)
        assert data["transport_id"] == "7"

    def test_points_have_lat_lng_as_floats(self) -> None:
        model = RouteShareResponse.model_validate(FULL_PAYLOAD)
        assert len(model.points) == 2
        first = model.points[0]
        assert isinstance(first, RoutePoint)
        assert first.lat == 52.52 and first.lng == 13.405
        assert isinstance(first.lat, float) and isinstance(first.lng, float)

    def test_points_accept_integer_coords_like_dart_num(self) -> None:
        """Dart casts ``lat``/``lng`` via ``(as num).toDouble()`` — integers
        must coerce to floats (Pydantic lax mode)."""
        model = RouteShareResponse.model_validate(
            {"transport_id": "1", "points": [{"lat": 52, "lng": 13}]}
        )
        point = model.points[0]
        assert point.lat == 52.0 and point.lng == 13.0
        assert isinstance(point.lat, float)

    def test_instructions_have_text_key_distance_meters_point_index(self) -> None:
        model = RouteShareResponse.model_validate(FULL_PAYLOAD)
        assert len(model.instructions) == 2
        inst = model.instructions[0]
        assert isinstance(inst, RouteInstruction)
        assert inst.text_key == "Turn right"
        assert isinstance(inst.text_key, str)
        assert inst.distance_meters == 150.5
        assert isinstance(inst.distance_meters, float)
        assert inst.point_index == 0
        assert isinstance(inst.point_index, int)

    def test_numeric_aggregates_have_exact_types(self) -> None:
        data = RouteShareResponse.model_validate(FULL_PAYLOAD).model_dump()
        assert isinstance(data["total_distance_meters"], float)
        assert data["total_distance_meters"] == 1054500.0
        assert isinstance(data["total_duration_seconds"], int)
        assert data["total_duration_seconds"] == 36000
        assert isinstance(data["ttl_seconds"], int)
        assert data["ttl_seconds"] == 300

    def test_generated_at_is_iso8601(self) -> None:
        data = RouteShareResponse.model_validate(FULL_PAYLOAD).model_dump()
        assert data["generated_at"] == "2026-07-31T10:00:00Z"
        parsed = _parse_iso(data["generated_at"])
        assert parsed.year == 2026 and parsed.hour == 10

    def test_unknown_fields_are_ignored_like_dart(self) -> None:
        """The Dart model reads only its known keys — unknown keys are
        silently dropped, never surfacing in the serialized payload."""
        model = RouteShareResponse.model_validate({**FULL_PAYLOAD, "route_direction": "north"})
        assert "route_direction" not in model.model_dump()

    def test_defaults_empty_collections_and_ttl(self) -> None:
        model = RouteShareResponse.model_validate(
            {"transport_id": "9", "total_distance_meters": 0.0,
             "total_duration_seconds": 0, "generated_at": "2026-01-01T00:00:00Z"}
        )
        assert model.points == []
        assert model.instructions == []
        assert model.ttl_seconds == 300
        data = model.model_dump()
        assert data["points"] == [] and data["instructions"] == []
        assert data["ttl_seconds"] == 300
