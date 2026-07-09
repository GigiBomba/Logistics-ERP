"""Route sharing service — share URLs, Google Maps export, .operionroute files.

Supports three sharing mechanisms:

1. **Share URL** (``https://operion.app/route?stops=...``)
   — Self-contained, no server needed. Encodes stops, profile, truck in a
   compact query string. Recipient opens the link → Operion loads the route.

2. **Google Maps Directions URL** (``https://www.google.com/maps/dir/...``)
   — Opens the route in Google Maps with turn-by-turn navigation.

3. **``.operionroute`` file** — Binary file (zlib-compressed JSON) that
   preserves the full route state.  Can be emailed, drag-dropped, or
   opened via file association.
"""

from __future__ import annotations

import json
import logging
import zlib
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

SHARE_URL_BASE = "https://operion.app/route"
SHARE_URL_VERSION = 1
OPERIONROUTE_MAGIC = b"OPERIONROUTE"
OPERIONROUTE_VERSION = 1
FILE_EXTENSION = ".operionroute"
FILE_FILTER = "Operion Route (*.operionroute)"

# ── Share URL encode / decode ──────────────────────────────────────────


def build_share_url(
    stops: list[dict[str, Any]],
    profile: str | None = None,
    truck_id: str | None = None,
    truck_label: str | None = None,
) -> str:
    """Build a shareable ``https://operion.app/route?stops=...`` URL.

    Parameters
    ----------
    stops : list[dict]
        Stop dicts with ``lat``, ``lon`` keys (as produced by
        ``normalize_existing_stop`` or ``stops_state``).
    profile : str, optional
        Routing profile key (e.g. ``"fastest"``, ``"shortest"``).
    truck_id : str, optional
        Internal truck database id.
    truck_label : str, optional
        Human-readable truck label (plate number).

    Returns
    -------
    str
        A compact, URL-safe share link.
    """
    coords = _extract_coordinate_pairs(stops)
    if not coords:
        logger.warning("build_share_url called with no coordinate data")
        return SHARE_URL_BASE + "?v=1&stops="

    stops_str = ";".join(f"{lat:.5f},{lng:.5f}" for lat, lng in coords)
    params: dict[str, str] = {
        "v": str(SHARE_URL_VERSION),
        "stops": stops_str,
    }
    if profile:
        params["profile"] = profile
    if truck_id:
        params["truck_id"] = truck_id
    if truck_label:
        params["truck_label"] = truck_label

    return f"{SHARE_URL_BASE}?{urlencode(params)}"


def parse_share_url(url: str) -> dict[str, Any]:
    """Parse a share URL back into route parameters.

    Parameters
    ----------
    url : str
        A share URL of the form
        ``https://operion.app/route?stops=...&profile=...``.

    Returns
    -------
    dict
        Keys: ``stops`` (list of ``(lat, lng)`` tuples), ``profile``
        (str or None), ``truck_id`` (str or None), ``truck_label``
        (str or None).
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    stops: list[tuple[float, float]] = []
    stops_raw = params.get("stops", [None])[0]
    if stops_raw:
        for pair in stops_raw.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            parts = pair.split(",")
            if len(parts) >= 2:
                try:
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
                    stops.append((lat, lng))
                except (TypeError, ValueError):
                    logger.warning("parse_share_url: skipping malformed pair %r", pair)

    return {
        "stops": stops,
        "profile": params.get("profile", [None])[0],
        "truck_id": params.get("truck_id", [None])[0],
        "truck_label": params.get("truck_label", [None])[0],
    }


def is_share_url(url: str) -> bool:
    """Return True if *url* looks like an Operion share URL."""
    return url.strip().startswith(SHARE_URL_BASE) or (
        url.strip().startswith("operion://") and "/route" in url
    )


# ── Google Maps URL builder ────────────────────────────────────────────


def build_google_maps_url(
    origin: tuple[float, float],
    destination: tuple[float, float],
    waypoints: list[tuple[float, float]] | None = None,
    travel_mode: str = "driving",
) -> str:
    """Build a Google Maps Directions URL for turn-by-turn navigation.

    Follows the official Google Maps Directions URL API format:
    ``https://www.google.com/maps/dir/?api=1&origin=LAT,LNG&destination=...``

    Parameters
    ----------
    origin : (float, float)
        Start coordinate ``(lat, lng)``.
    destination : (float, float)
        End coordinate ``(lat, lng)``.
    waypoints : list[(float, float)], optional
        Intermediate stop coordinates.
    travel_mode : str
        One of ``"driving"``, ``"walking"``, ``"bicycling"``, ``"transit"``.

    Returns
    -------
    str
        A Google Maps URL ready to open in the system browser.
    """
    parts = [
        "https://www.google.com/maps/dir/?api=1",
        f"origin={origin[0]:.5f},{origin[1]:.5f}",
        f"destination={destination[0]:.5f},{destination[1]:.5f}",
    ]
    if waypoints:
        wp_str = "%7C".join(f"{lat:.5f},{lng:.5f}" for lat, lng in waypoints)
        parts.append(f"waypoints={wp_str}")
    allowed_modes = {"driving", "walking", "bicycling", "transit"}
    if travel_mode not in allowed_modes:
        travel_mode = "driving"
    parts.append(f"travelmode={travel_mode}")
    return "&".join(parts)


# ── .operionroute file encode / decode ──────────────────────────────


def encode_route_file(
    stops: list[dict[str, Any]],
    profile: str | None = None,
    truck_id: str | None = None,
    truck_label: str | None = None,
    geometry: list[Any] | None = None,
    distance_km: float | None = None,
    duration_min: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> bytes:
    """Serialize route state to a compressed ``.operionroute`` binary blob.

    Format::

        [8-byte magic "OPERIONROUTE"]
        [1-byte version]
        [4-byte payload length (big-endian)]
        [zlib-compressed JSON payload]

    Parameters
    ----------
    stops : list[dict]
        Stop dicts with ``lat``, ``lon`` keys.
    profile : str, optional
    truck_id : str, optional
    truck_label : str, optional
    geometry : list, optional
        Route geometry (list of coordinate pairs).
    distance_km : float, optional
    duration_min : float, optional
    metadata : dict, optional
        Any extra key/value pairs to include.

    Returns
    -------
    bytes
        Binary blob suitable for saving to a ``.operionroute`` file.
    """
    coords = _extract_coordinate_pairs(stops)
    payload: dict[str, Any] = {
        "version": OPERIONROUTE_VERSION,
        "stops": coords,
    }
    if profile:
        payload["profile"] = profile
    if truck_id:
        payload["truck_id"] = truck_id
    if truck_label:
        payload["truck_label"] = truck_label
    if geometry:
        payload["geometry"] = geometry
    if distance_km is not None:
        payload["distance_km"] = distance_km
    if duration_min is not None:
        payload["duration_min"] = duration_min
    if metadata:
        payload["metadata"] = metadata

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    compressed = zlib.compress(raw, level=6)
    length = len(compressed)

    header = OPERIONROUTE_MAGIC + bytes([OPERIONROUTE_VERSION])
    header += length.to_bytes(4, byteorder="big")
    return header + compressed


def decode_route_file(data: bytes) -> dict[str, Any]:
    """Deserialize a ``.operionroute`` binary blob back into route state.

    Parameters
    ----------
    data : bytes
        The binary blob read from a ``.operionroute`` file.

    Returns
    -------
    dict
        Keys: ``stops`` (list of ``(lat, lng)`` tuples), ``profile``,
        ``truck_id``, ``truck_label``, ``geometry``, ``distance_km``,
        ``duration_min``, ``metadata``.
    """
    if not data or len(data) < 17:
        raise ValueError("Invalid .operionroute file: too short")

    magic = data[:13]
    if magic[:12] != OPERIONROUTE_MAGIC or magic[12] != OPERIONROUTE_VERSION:
        raise ValueError("Invalid .operionroute file: bad magic or version")

    payload_len = int.from_bytes(data[13:17], byteorder="big")
    if payload_len <= 0 or payload_len > 100 * 1024 * 1024:
        raise ValueError(f"Invalid .operionroute file: payload length {payload_len} out of range")
    if len(data) < 17 + payload_len:
        raise ValueError(
            f"Truncated .operionroute file: expected {17 + payload_len} bytes, got {len(data)}"
        )
    compressed = data[17:17 + payload_len]

    try:
        raw = zlib.decompress(compressed)
    except zlib.error as exc:
        raise ValueError(f"Invalid .operionroute file: decompression failed ({exc})") from exc

    payload: dict[str, Any] = json.loads(raw.decode("utf-8"))
    stops: list[tuple[float, float]] = []
    for s in payload.get("stops", []):
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            stops.append((float(s[0]), float(s[1])))

    return {
        "stops": stops,
        "profile": payload.get("profile"),
        "truck_id": payload.get("truck_id"),
        "truck_label": payload.get("truck_label"),
        "geometry": payload.get("geometry"),
        "distance_km": payload.get("distance_km"),
        "duration_min": payload.get("duration_min"),
        "metadata": payload.get("metadata"),
    }


# ── Helpers ────────────────────────────────────────────────────────────


def extract_stops_from_route_result(route: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract stop dicts from a route calculation result dict.

    The route result's ``"stops"`` key is a list of ``(lat, lng)`` tuples.
    This wraps each tuple into the stop dict format expected by
    ``build_share_url`` and ``encode_route_file``.
    """
    raw_stops = route.get("stops") or []
    result: list[dict[str, Any]] = []
    for i, s in enumerate(raw_stops):
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            stop_type = "start" if i == 0 else ("destination" if i == len(raw_stops) - 1 else "stop")
            result.append({
                "id": "",
                "type": stop_type,
                "lat": float(s[0]),
                "lon": float(s[1]),
                "address": None,
                "source": "share",
                "resolved": True,
            })
    return result


def extract_stops_from_state(stops_state: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract resolved stops from the planner's ``stops_state`` list.

    Filters out stops that have no lat/lng (unresolved).
    Returns a list of ``{"lat": ..., "lon": ..., "type": ...}`` dicts
    suitable for ``build_share_url``.
    """
    result: list[dict[str, Any]] = []
    for s in stops_state:
        lat = s.get("lat")
        lon = s.get("lon")
        if lat is not None and lon is not None:
            try:
                result.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "type": s.get("type", "stop"),
                })
            except (TypeError, ValueError):
                continue
    return result


def _extract_coordinate_pairs(stops: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Extract ``(lat, lng)`` tuples from a list of stop dicts."""
    coords: list[tuple[float, float]] = []
    for s in stops:
        lat = s.get("lat")
        lon = s.get("lon") if s.get("lon") is not None else s.get("lng")
        if lat is not None and lon is not None:
            try:
                coords.append((float(lat), float(lon)))
            except (TypeError, ValueError):
                continue
    return coords
