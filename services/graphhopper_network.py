"""GraphHopper URL and request helpers (network layer only)."""
from __future__ import annotations

import os
import time
from typing import Any, List, Optional, Sequence, Tuple
from urllib.parse import urlparse, urlunparse

# Default GraphHopper instance (LAN)
DEFAULT_GRAPHHOPPER_BASE_URL = "http://192.168.0.93:8989"

MAX_ROUTE_RETRIES = 3
RETRY_BACKOFF_SECONDS = (0.0, 2.0, 4.0)

# Use POST when GET query strings grow large (avoids proxy/parser edge cases on long routes)
POST_DISTANCE_THRESHOLD_KM = 400.0

# Auto-disable CH when points exceed this distance (avoids PointDistanceExceededException)
CH_DISABLE_DISTANCE_THRESHOLD_KM = 800.0


def graphhopper_base_url_from_env(default: str = DEFAULT_GRAPHHOPPER_BASE_URL) -> str:
    return normalize_graphhopper_base_url(os.environ.get("GRAPHHOPPER_URL", default))


def normalize_graphhopper_base_url(url: Any) -> str:
    """Validate and normalize base URL without mutating the host (no replace/format on IP octets)."""
    if url is None:
        raise ValueError("GraphHopper base URL is required")
    if isinstance(url, (int, float)):
        raise TypeError(
            f"GraphHopper base URL must be a string, not {type(url).__name__} "
            "(do not cast IP addresses to numbers)"
        )
    raw = str(url).strip()
    if not raw:
        raise ValueError("Empty GraphHopper base URL")

    if "://" not in raw:
        raw = f"http://{raw}"

    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"GraphHopper URL must use http or https, got: {raw!r}")
    if not parsed.hostname:
        raise ValueError(f"Invalid GraphHopper base URL (missing host): {raw!r}")

    host = parsed.hostname
    port = parsed.port
    if port:
        netloc = f"{host}:{port}"
    else:
        netloc = host

    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        netloc = f"{auth}@{netloc}"

    # Rebuild origin only — path/query must not alter host (no .replace on full URL)
    normalized = urlunparse((parsed.scheme, netloc, "", "", "", "")).rstrip("/")

    # IPv4 literals must retain dot separators (guards against corrupted hosts like 192/68.0.93)
    if host.count(".") == 3 and all(p.isdigit() for p in host.split(".")):
        rebuilt = ".".join(host.split("."))
        if rebuilt != host:
            raise ValueError(f"GraphHopper IPv4 host corrupted during normalization: {raw!r}")

    return normalized


def build_route_endpoint(base_url: str) -> str:
    base = normalize_graphhopper_base_url(base_url)
    return f"{base}/route"


def validate_route_points(points: Sequence[Sequence[float]]) -> List[Tuple[float, float]]:
    """Normalize and validate coordinates before any HTTP call."""
    if not points or len(points) < 2:
        raise ValueError("At least 2 route points required")

    validated: List[Tuple[float, float]] = []
    for i, pt in enumerate(points):
        if not isinstance(pt, (tuple, list)) or len(pt) < 2:
            raise ValueError(f"Malformed point at index {i}: {pt!r}")
        try:
            lat = float(pt[0])
            lon = float(pt[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Malformed point at index {i}: {pt!r}") from exc
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Invalid coordinates at point {i}: ({lat}, {lon})")
        if lat == 0.0 and lon == 0.0:
            raise ValueError(f"Invalid zero coordinates at point {i}")
        validated.append((lat, lon))
    return validated


def should_use_post_routing(
    *,
    has_custom_model: bool,
    point_count: int,
    estimated_distance_km: float,
) -> bool:
    if has_custom_model:
        return True
    if point_count > 2:
        return True
    if estimated_distance_km >= POST_DISTANCE_THRESHOLD_KM:
        return True
    return False


def is_transient_http_status(status_code: int) -> bool:
    return status_code in (408, 429, 500, 502, 503, 504)


def is_retryable_request_error(exc: BaseException) -> bool:
    import requests

    if isinstance(exc, requests.exceptions.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None and not is_transient_http_status(resp.status_code):
            return False
        return resp is not None and is_transient_http_status(resp.status_code)
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    return False


def retry_delay_seconds(attempt_index: int) -> float:
    """attempt_index: 0 = first retry after failure."""
    idx = min(attempt_index, len(RETRY_BACKOFF_SECONDS) - 1)
    return RETRY_BACKOFF_SECONDS[idx]


def format_point_param(lat: float, lon: float) -> str:
    """GraphHopper GET point=lat,lon — invariant formatting (never locale-dependent)."""
    return f"{lat:.7f},{lon:.7f}"
