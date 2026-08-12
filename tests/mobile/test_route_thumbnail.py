"""Route-history map thumbnail endpoint tests (§2 row 16) — real DB.

Covers: 200 + PNG magic bytes + 320×180 image + polyline pixels present;
company isolation 404; missing route 404; NULL geometry 404; undecodable
garbage geometry 404; soft-deleted route 404; single-point degenerate
geometry renders a valid PNG; dispatcher role allowed; the route LIST
endpoint remains intact.
"""
from __future__ import annotations

import io
import json
import zlib
from uuid import uuid4

from PIL import Image

BASE = "/api/v1/mobile/history"


def _seed_route(db, *, company_id: int = 1, name: str | None = None,
                geometry=None, geometry_blob=None, deleted_at=None) -> int:
    """Insert a route_history_v2 row with the REAL zlib-json geometry blob.

    Mirrors the writer contract: ``zlib.compress(json.dumps([(lat, lon), ...]))``
    where JSON arrays are ``[lat, lon]`` (lat first, lon second).
    """
    name = name or f"THUMB-{uuid4().hex[:8]}"
    if geometry_blob is None:
        if geometry is None:
            geometry_blob = None
        else:
            geometry_blob = zlib.compress(json.dumps(geometry).encode())
    created = "2026-07-01T10:00:00"
    stops_json = json.dumps([
        {"lat": 48.8566, "lon": 2.3522, "address": "Paris"},
        {"lat": 44.4268, "lon": 26.1025, "address": "Bucharest"},
    ])
    cur = db.execute(
        "INSERT INTO route_history_v2 (route_fingerprint, metadata_version, created_at, "
        "last_calculated_at, calculation_count, stops_json, geometry_compressed, "
        "geometry_encoding, total_distance_km, duration_min, truck_id, truck_label, "
        "profile, excluded_countries_json, countries_traversed_json, is_committed, "
        "company_id, deleted_at) "
        "VALUES (?, 1, ?, ?, 1, ?, ?, 'zlib-json', 1870.0, 1200.0, 'TRUCK-1', "
        "'Scania R500', 'truck', '[]', '[]', 1, ?, ?)",
        (name, created, created, stops_json, geometry_blob, company_id, deleted_at),
    )
    db.conn.commit()
    return cur.lastrowid


def _sample_route_geometry():
    """A realistic lat/lon polyline (Bucharest → Vienna, simplified)."""
    return [
        (44.4268, 26.1025),
        (45.1, 25.0),
        (46.5, 24.0),
        (47.5, 20.5),
        (48.2082, 16.3738),
    ]


def _is_line_pixel(pixel) -> bool:
    """Blue-dominant pixel (polyline colour, not frame/background)."""
    r, g, b = pixel
    return b > 160 and (b - r) > 50 and r < 130


def _interior_line_pixel_count(img: Image.Image) -> int:
    """Count blue polyline pixels away from the frame border."""
    w, h = img.size
    interior = img.crop((12, 12, w - 12, h - 12))
    pixels = (
        interior.get_flattened_data()
        if hasattr(interior, "get_flattened_data")
        else interior.getdata()
    )
    return sum(1 for p in pixels if _is_line_pixel(p))


class TestRouteThumbnail:
    def test_returns_png_with_expected_size_and_polyline(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, geometry=_sample_route_geometry())

        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG")

        img = Image.open(io.BytesIO(resp.content))
        assert img.size == (320, 180)
        # Not a uniform image (frame + polyline on light background).
        assert len(img.getcolors(maxcolors=1_000_000)) > 1
        # The polyline itself is present as interior blue pixels.
        assert _interior_line_pixel_count(img) > 0

    def test_dispatcher_allowed(self, mobile_app, real_db, dispatcher_client):
        _seed_route(real_db, geometry=_sample_route_geometry())
        resp = dispatcher_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 200

    def test_cross_company_404(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, company_id=2, geometry=_sample_route_geometry())
        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 404

    def test_missing_route_404(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.get(f"{BASE}/routes/9999/thumbnail")
        assert resp.status_code == 404

    def test_null_geometry_404(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, geometry=None)
        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 404

    def test_undecodable_geometry_404(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, geometry_blob=b"\x00\x01\x02\x03not-zlib")
        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 404

    def test_empty_geometry_list_404(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, geometry=[])
        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 404

    def test_soft_deleted_route_404(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, geometry=_sample_route_geometry(),
                    deleted_at="2026-08-01T00:00:00")
        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 404

    def test_single_point_geometry_renders_valid_png(self, mobile_app, real_db, mobile_client):
        _seed_route(real_db, geometry=[(44.4268, 26.1025)])
        resp = mobile_client.get(f"{BASE}/routes/1/thumbnail")
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")
        img = Image.open(io.BytesIO(resp.content))
        assert img.size == (320, 180)
        # Degenerate input still draws a visible dot (blue interior pixels).
        assert _interior_line_pixel_count(img) > 0

    def test_route_list_still_intact(self, mobile_app, real_db, mobile_client):
        route_id = _seed_route(real_db, name="THUMB-LIST", geometry=_sample_route_geometry())
        resp = mobile_client.get(f"{BASE}/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == route_id
        assert data["items"][0]["name"] == "THUMB-LIST"
