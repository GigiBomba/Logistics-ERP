"""Routing layer: GraphHopper client, caching, geocoding integration and segmentation.

This module provides:
- GraphHopperClient: low-level HTTP client for GH with diagnostics and retries
- RouteCache / GeocodeCache: simple in-memory caches
- RouteService: orchestration of geocoding, routing, segmentation and async execution

The implementation focuses on clarity, type annotations and maintainability.
"""

import contextlib
import hashlib
import math
import threading
import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Config
from services.calculator import TripCalculator
from services.constraint_engine import TruckConstraintEngine
from services.country_exclusion import CountryExclusionEngine
from services.geocode_nominatim import geocode_place
from services.graphhopper_network import (
    MAX_ROUTE_RETRIES,
    build_route_endpoint,
    format_point_param,
    graphhopper_base_url_from_env,
    is_retryable_request_error,
    is_transient_http_status,
    normalize_graphhopper_base_url,
    retry_delay_seconds,
    should_use_post_routing,
    validate_route_points,
)
from utils.logger import get_logger

GRAPHHOPPER_PROFILES: dict[str, str] = Config.GRAPHHOPPER_PROFILES


class RouteCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        from collections import OrderedDict
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        # Per-key locks for cache-stampede prevention
        self._compute_locks: dict[str, threading.Lock] = {}

    def _make_key(self, points: list[tuple[float, float]], profile: str, exclusions: Optional[list[str]] = None) -> str:
        points_str = ",".join(f"{lat:.6f},{lon:.6f}" for lat, lon in points)
        excl_str = "" if not exclusions else ",".join(sorted([c.upper() for c in exclusions]))
        key = f"{profile}:{points_str}:excl={excl_str}"
        return hashlib.md5(key.encode()).hexdigest()

    def _get_compute_lock(self, key: str) -> threading.Lock:
        with self._lock:
            if key not in self._compute_locks:
                self._compute_locks[key] = threading.Lock()
            return self._compute_locks[key]

    def get(self, points: list[tuple[float, float]], profile: str, exclusions: Optional[list[str]] = None) -> Optional[dict[str, Any]]:
        key = self._make_key(points, profile, exclusions)
        with self._lock:
            if key in self._cache:
                if time.time() - self._timestamps[key] < self.ttl_seconds:
                    self._cache.move_to_end(key)
                    return self._cache[key]
                del self._cache[key]
                del self._timestamps[key]
        return None

    def set(self, points: list[tuple[float, float]], profile: str, result: dict[str, Any], exclusions: Optional[list[str]] = None) -> None:
        key = self._make_key(points, profile, exclusions)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    oldest_key, _ = self._cache.popitem(last=False)
                    del self._timestamps[oldest_key]
            self._cache[key] = result
            self._timestamps[key] = time.time()

    def get_or_compute(
        self,
        points: list[tuple[float, float]],
        profile: str,
        compute_fn,
        exclusions: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Atomically check cache and compute if missing — prevents cache stampede."""
        key = self._make_key(points, profile, exclusions)
        # Fast check under main lock
        with self._lock:
            if key in self._cache:
                if time.time() - self._timestamps[key] < self.ttl_seconds:
                    self._cache.move_to_end(key)
                    return self._cache[key]
                del self._cache[key]
                del self._timestamps[key]
        # Per-key lock prevents concurrent computation of the same route
        per_key_lock = self._get_compute_lock(key)
        with per_key_lock:
            # Double-check — another thread may have stored while we waited
            with self._lock:
                if key in self._cache:
                    if time.time() - self._timestamps[key] < self.ttl_seconds:
                        self._cache.move_to_end(key)
                        return self._cache[key]
                    del self._cache[key]
                    del self._timestamps[key]
            result = compute_fn()
            self.set(points, profile, result, exclusions)
            return result


class GeocodeCache:
    def __init__(self, max_size: int = 2000, ttl_seconds: int = 604800) -> None:
        self._cache: dict[str, tuple[float, float]] = {}
        self._timestamps: dict[str, float] = {}
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def _is_expired(self, address: str) -> bool:
        ts = self._timestamps.get(address)
        return ts is not None and (time.time() - ts) > self.ttl_seconds

    def get(self, address: str) -> Optional[tuple[float, float]]:
        with self._lock:
            if address in self._cache and self._is_expired(address):
                del self._cache[address]
                del self._timestamps[address]
                return None
            return self._cache.get(address)

    def set(self, address: str, coords: tuple[float, float]) -> None:
        with self._lock:
            if self._is_expired(address):
                del self._cache[address]
                del self._timestamps[address]
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                del self._timestamps[oldest_key]
            self._cache[address] = coords
            self._timestamps[address] = time.time()


class GraphHopperClient:
    """Thin GraphHopper HTTP client with retry and diagnostics."""

    def __init__(
        self,
        base_url: str = "",
        timeout: int = 300,
    ) -> None:
        if not base_url:
            base_url = getattr(Config, 'GRAPHHOPPER_URL', 'https://maps.operionerp.xyz')
        self.base_url = normalize_graphhopper_base_url(base_url)
        self._route_endpoint = build_route_endpoint(self.base_url)
        self.timeout = timeout
        self.logger = get_logger("GraphHopperClient")
        self.debug_logger = get_logger("route_debug")

        self.session = requests.Session()
        # Application-level retries only (avoid urllib3 × manual retry storms)
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=Retry(total=0), pool_block=False)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({"Connection": "keep-alive", "Accept": "application/json"})

    @staticmethod
    def _validate_coordinates(lat: float, lon: float) -> bool:
        try:
            lat = float(lat)
            lon = float(lon)
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # Internal-only keys (not sent to GraphHopper query/body)
    _INTERNAL_PARAM_KEYS = frozenset({
        "avoid_countries",
        "country_penalty",
        "_custom_model",
        "_exclusion_strategy",
        "_exclusion_requested",
        "_exclusion_skipped",
        "_meta",
        "_segment_depth",
    })

    def _split_routing_params(self, params: Optional[dict[str, Any]]) -> tuple[dict[str, Any], Optional[dict[str, Any]], dict[str, Any]]:
        """Split truck/query params, custom_model JSON, and diagnostic metadata."""
        if not params:
            return {}, None, {}
        gh_params: dict[str, Any] = {}
        meta: dict[str, Any] = {}
        custom_model = params.get("_custom_model")
        for key, value in params.items():
            if key in self._INTERNAL_PARAM_KEYS:
                if key.startswith("_exclusion") or key == "avoid_countries" or key == "_meta" or key == "_segment_depth":
                    meta[key] = value
                continue
            gh_params[key] = value
        return gh_params, custom_model if isinstance(custom_model, dict) else None, meta

    def _route_post(
        self,
        points: list[tuple[float, float]],
        profile: str,
        gh_params: dict[str, Any],
        custom_model: Optional[dict[str, Any]],
        actual_timeout: int,
        meta: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """POST /route — custom_model exclusions or long / multi-point routes."""
        body: dict[str, Any] = {
            "profile": profile,
            "points": [[float(lon), float(lat)] for lat, lon in points],
            "points_encoded": False,
            "instructions": False,
            "calc_points": True,
        }
        if custom_model is not None:
            body["ch.disable"] = True
            body["custom_model"] = custom_model
        for key, value in gh_params.items():
            if key == "ch.disable":
                body["ch.disable"] = value in (True, "true", "True", "1", 1)
            else:
                body[key] = value
        applied = (meta or {}).get("avoid_countries") or gh_params.get("avoid_countries")
        if custom_model is not None:
            self.debug_logger.info(f"[GraphHopper] POST route exclusions applied={applied}")
        self.debug_logger.info(
            f"[GraphHopper] POST {self._route_endpoint} profile={profile} points={len(points)} "
            f"ch.disable={body.get('ch.disable', False)}"
        )
        return self.session.post(
            self._route_endpoint,
            json=body,
            timeout=actual_timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def _log_request_debug(
        self,
        *,
        use_post: bool,
        profile: str,
        points: list[tuple[float, float]],
        query_params: dict[str, Any],
        meta: dict[str, Any],
        segment_depth: int = 0,
    ) -> None:
        coord_count = len(points) * 2
        line = (
            f"[GH] method={'POST' if use_post else 'GET'} "
            f"points={len(points)} coords={coord_count} "
            f"profile={profile} depth={segment_depth} "
            f"est_km={sum(self._haversine_distance(points[i][0], points[i][1], points[i+1][0], points[i+1][1]) for i in range(len(points)-1)):.1f} "
            f"endpoint={self._route_endpoint}"
        )
        if meta:
            line += f" meta={meta}"
        self.debug_logger.info(line)
        if use_post:
            self.debug_logger.info(
                f"REQUEST POST {self._route_endpoint} profile={profile} points={len(points)} "
                f"strategy={meta.get('_exclusion_strategy', 'post')}"
            )
            return
        try:
            prep = requests.Request("GET", self._route_endpoint, params=query_params).prepare()
            self.debug_logger.info(f"REQUEST URL: {prep.url}")
        except requests.exceptions.InvalidURL as exc:
            raise ValueError(
                f"Invalid GraphHopper request URL (base={self.base_url!r}): {exc}"
            ) from exc

    @staticmethod
    def _parse_geometry(path: dict) -> list[tuple[float, float]]:
        """Extract geometry from a GraphHopper response path."""
        raw_points = path.get("points")
        if not raw_points:
            return []

        geometry: list[tuple[float, float]] = []

        if isinstance(raw_points, str):
            try:
                from services.route_decoder import decode_polyline
                decoded = decode_polyline(raw_points)
                geometry = [(lat, lon) for lat, lon in decoded]
            except Exception:
                try:
                    snapped = decode_polyline(path.get("snapped_waypoints", ""))
                    geometry = [(lat, lon) for lat, lon in snapped]
                except Exception:
                    geometry = []
        elif isinstance(raw_points, dict) and "coordinates" in raw_points:
            coords = raw_points["coordinates"]
            geometry = [(coord[1], coord[0]) for coord in coords]
        elif isinstance(raw_points, list) and raw_points:
            first = raw_points[0]
            if isinstance(first, (list, tuple)) and len(first) == 2:
                geometry = [(p[1], p[0]) for p in raw_points]
            else:
                geometry = [(lat, lon) for lat, lon in raw_points]

        return geometry

    @staticmethod
    def _build_route_result(path: dict, points: list, elapsed: float,
                            avoid, use_post: bool, meta: dict,
                            data: dict) -> dict:
        """Build a normalized route result dict from GraphHopper response."""
        geometry = GraphHopperClient._parse_geometry(path)
        if not geometry:
            geometry = [(lat, lon) for lat, lon in points]

        distance_km = path.get("distance", 0) / 1000.0
        duration_min = path.get("time", 0) / 60000.0

        return {
            "distance_km": distance_km,
            "duration_min": duration_min,
            "geometry": geometry,
            "points_count": len(points),
            "request_time_s": elapsed,
            "graphhopper_response": data,
            "avoid_countries": avoid or [],
            "exclusions_applied": bool(use_post and avoid),
            "routing_method": "POST" if use_post else "GET",
            "exclusion_strategy": meta.get("_exclusion_strategy"),
        }

    def route(self, points: list[tuple[float, float]], profile: str = "truck", params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        gh_params, custom_model, meta = self._split_routing_params(params)
        avoid = meta.get("avoid_countries") or gh_params.get("avoid_countries")
        points = validate_route_points(points)
        start_time = time.time()

        total_distance_km = 0.0
        for i in range(len(points) - 1):
            total_distance_km += self._haversine_distance(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

        use_post = should_use_post_routing(
            has_custom_model=custom_model is not None,
            point_count=len(points),
            estimated_distance_km=total_distance_km,
        )

        dynamic_timeout = max(120, int(120 + (total_distance_km / 100) * 8))
        if use_post:
            dynamic_timeout = max(dynamic_timeout, 180)
        actual_timeout = min(dynamic_timeout, self.timeout)

        query_params: dict[str, Any] = {
            "profile": profile,
            "point": [format_point_param(lat, lon) for lat, lon in points],
            "points_encoded": "false",
            "instructions": "false",
            "calc_points": "true",
            "type": "json",
        }
        query_params.update(gh_params)

        if avoid:
            self.debug_logger.info(f"[GraphHopper] Avoid countries (diagnostic): {avoid}")
        # Extract segment depth from nested meta
        _segment_depth = 0
        _nested_meta = meta.get("_meta", {})
        if isinstance(_nested_meta, dict):
            _segment_depth = _nested_meta.get("_segment_depth", 0)
        self._log_request_debug(
            use_post=use_post,
            profile=profile,
            points=points,
            query_params=query_params,
            meta=meta,
            segment_depth=_segment_depth,
        )

        self.logger.info(
            f"Route request profile={profile} points={len(points)} est_distance_km={total_distance_km:.1f} "
            f"method={'POST' if use_post else 'GET'} endpoint={self._route_endpoint}"
        )

        max_attempts = MAX_ROUTE_RETRIES
        last_error: Optional[str] = None
        for attempt in range(max_attempts):
            if attempt > 0:
                time.sleep(retry_delay_seconds(attempt - 1))
            try:
                if use_post:
                    resp = self._route_post(
                        points, profile, gh_params, custom_model, actual_timeout, meta=meta
                    )
                else:
                    resp = self.session.get(
                        self._route_endpoint,
                        params=query_params,
                        timeout=actual_timeout,
                        headers={"Accept": "application/json"},
                    )
                elapsed = time.time() - start_time
                self.debug_logger.info(f"RESPONSE status={resp.status_code} time_s={elapsed:.2f} attempt={attempt}")
                try:
                    body = resp.text
                    if len(body) > 20000:
                        body = body[:20000] + "... (truncated)"
                    self.debug_logger.info(f"RESPONSE BODY: {body}")
                except Exception:
                    pass

                if is_transient_http_status(resp.status_code):
                    last_error = f"HTTP {resp.status_code}"
                    if attempt < max_attempts - 1:
                        continue
                    resp.raise_for_status()

                if resp.status_code >= 400:
                    gh_message = ""
                    try:
                        error_data = resp.json()
                        if isinstance(error_data, dict):
                            gh_message = error_data.get("message", "") or error_data.get("error", "")
                    except Exception:
                        gh_message = resp.text[:2000] if resp.text else ""

                    if gh_message:
                        self.debug_logger.error(
                            f"GraphHopper HTTP {resp.status_code}: {gh_message}"
                        )
                        # Auto-retry with ch.disable for CH distance errors
                        gh_lower = gh_message.lower()
                        if ("pointdistanceexceeded" in gh_lower or "too far" in gh_lower) and attempt < max_attempts - 1:
                            self.logger.info(
                                f"CH distance error (HTTP {resp.status_code}), retrying with ch.disable=true"
                            )
                            gh_params["ch.disable"] = True
                            if not use_post:
                                query_params["ch.disable"] = "true"
                            self.debug_logger.info(
                                f"[GraphHopper] Retry attempt {attempt+2} with ch.disable=true"
                            )
                            continue
                        raise ValueError(
                            f"GraphHopper error (HTTP {resp.status_code}): {gh_message}"
                        )
                    resp.raise_for_status()

                data = resp.json()
                if "paths" not in data or not data["paths"]:
                    gh_err = data.get("message") if isinstance(data, dict) else None
                    self.debug_logger.error(f"GraphHopper payload: {data}")
                    raise ValueError(gh_err or "No route found")

                path = data["paths"][0]
                result = self._build_route_result(
                    path, points, elapsed, avoid, use_post, meta, data
                )
                if use_post:
                    self.debug_logger.info(
                        f"[GraphHopper] Route success with exclusions applied={avoid} "
                        f"distance_km={result['distance_km']:.1f}"
                    )
                self.logger.info(
                    f"Route success {result['distance_km']:.1f}km time_s={elapsed:.2f}"
                )
                return result

            except requests.exceptions.HTTPError as e:
                if is_retryable_request_error(e) and attempt < max_attempts - 1:
                    last_error = str(e)
                    self.logger.warning(f"HTTP retry attempt {attempt + 1}: {e}")
                    continue
                raise
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = str(e)
                self.logger.warning(f"Transient error attempt {attempt + 1}: {e}")
                if attempt >= max_attempts - 1:
                    raise
            except requests.exceptions.InvalidURL as e:
                raise ValueError(
                    f"Invalid GraphHopper URL (check base URL {self.base_url!r}): {e}"
                ) from e
            except Exception as e:
                if is_retryable_request_error(e) and attempt < max_attempts - 1:
                    last_error = str(e)
                    self.logger.warning(f"Route retry attempt {attempt + 1}: {e}")
                    continue
                raise

        raise RuntimeError(f"Route failed after {max_attempts} attempts: {last_error}")


class RouteService:
    # ── Static helpers (no instance required) ─────────────────────────────

    @staticmethod
    def parse_route_stops(stops_json: str) -> tuple[str, str]:
        """Parse route stops JSON and return (origin, destination) address strings.

        Args:
            stops_json: Raw JSON string from the route repository.

        Returns:
            A 2-tuple ``(origin_address, destination_address)``. Either may be
            an empty string if the data cannot be parsed or has fewer than 2 stops.
        """
        import json
        if not stops_json:
            return ("", "")
        try:
            stops = json.loads(stops_json)
            if not isinstance(stops, list) or len(stops) < 2:
                return ("", "")
            origin = stops[0].get("address", "")
            destination = stops[-1].get("address", "")
            return origin, destination
        except (json.JSONDecodeError, TypeError, IndexError):
            return ("", "")

    def __init__(self, db: Any = None, graphhopper_url: Optional[str] = None, timeout: int = 300) -> None:
        self.db = db
        self.logger = get_logger("RouteService")
        self.debug_logger = get_logger("route_debug")
        self.calculator = TripCalculator()
        self.constraint_engine = TruckConstraintEngine()
        self.country_exclusion = CountryExclusionEngine()
        gh_url = graphhopper_url if graphhopper_url is not None else graphhopper_base_url_from_env()
        self.client = GraphHopperClient(base_url=gh_url, timeout=timeout)
        self._geocode_cache = GeocodeCache(max_size=2000)
        self._route_cache = RouteCache(max_size=1000, ttl_seconds=3600)

        # segmentation defaults
        self.segment_distance_threshold_km = 800.0
        self.min_segment_distance_km = 350.0
        self.max_segmentation_depth = 2
        self.max_segment_count = 4

    def _geocode_address(self, address: str) -> tuple[float, float]:
        if not address or not address.strip():
            raise ValueError("Empty address")
        address = address.strip()
        cached = self._geocode_cache.get(address)
        if cached:
            return cached
        start = time.time()
        coords = geocode_place(address, timeout=15)
        took = time.time() - start
        self.debug_logger.info(f"geocode: address={address} time_s={took:.2f}")
        if not coords:
            raise ValueError(f"Could not geocode address: {address}")
        lat, lon = coords
        if not GraphHopperClient._validate_coordinates(lat, lon):
            raise ValueError(f"Invalid geocode result for {address}: ({lat}, {lon})")
        self._geocode_cache.set(address, coords)
        return coords

    def _resolve_stops(self, addresses: list[Any]) -> list[tuple[float, float]]:
        resolved: list[tuple[float, float]] = []
        failed: list[str] = []
        for i, addr in enumerate(addresses):
            try:
                if isinstance(addr, (tuple, list)) and len(addr) >= 2:
                    lat, lon = float(addr[0]), float(addr[1])
                    if GraphHopperClient._validate_coordinates(lat, lon):
                        resolved.append((lat, lon))
                        continue
                    failed.append(f"Point {i}: invalid coordinates ({lat},{lon})")
                    continue
                start = time.time()
                coords = self._geocode_address(str(addr))
                self.debug_logger.info(f"geocode_point index={i} address={addr} time_s={time.time()-start:.2f}")
                resolved.append(coords)
            except Exception as e:
                failed.append(f"Point {i} ({addr}): {e}")

        if failed:
            raise ValueError("Geocoding failed:\n" + "\n".join(failed))

        if len(resolved) < 2:
            raise ValueError("At least 2 valid stops required")

        # dedupe consecutive
        cleaned: list[tuple[float, float]] = [resolved[0]]
        for i in range(1, len(resolved)):
            if resolved[i] != resolved[i - 1]:
                cleaned.append(resolved[i])
        if len(cleaned) < 2:
            raise ValueError("At least 2 unique stops required after deduplication")
        return cleaned

    @staticmethod
    def _validate_segment(segment: list[tuple[float, float]], context: str = "") -> None:
        """Validate segment points before making a GraphHopper request.

        Raises ValueError if the segment is invalid.
        """
        if not segment:
            raise ValueError(f"Empty segment {context}")
        if len(segment) < 2:
            raise ValueError(f"Segment {context} has only {len(segment)} point(s), need at least 2")
        for i, pt in enumerate(segment):
            if pt is None:
                raise ValueError(f"Segment {context} has None point at index {i}")
            if not isinstance(pt, (tuple, list)) or len(pt) < 2:
                raise ValueError(f"Segment {context} has malformed point at index {i}: {pt!r}")
            lat, lon = pt[0], pt[1]
            if lat is None or lon is None:
                raise ValueError(f"Segment {context} has None coordinate at index {i}")
            try:
                lat_f, lon_f = float(lat), float(lon)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Segment {context} has non-numeric coordinate at index {i}: ({lat}, {lon})") from exc

            if math.isnan(lat_f) or math.isnan(lon_f):
                raise ValueError(f"Segment {context} has NaN coordinate at index {i}")
            if math.isinf(lat_f) or math.isinf(lon_f):
                raise ValueError(f"Segment {context} has Inf coordinate at index {i}")
            if not (-90.0 <= lat_f <= 90.0):
                raise ValueError(f"Segment {context}: invalid latitude at index {i}: {lat_f}")
            if not (-180.0 <= lon_f <= 180.0):
                raise ValueError(f"Segment {context}: invalid longitude at index {i}: {lon_f}")
        for i in range(1, len(segment)):
            if segment[i] == segment[i - 1]:
                raise ValueError(f"Segment {context}: duplicate consecutive point at index {i}: {segment[i]}")

    def _merge_segment_results(self, parts: list[dict[str, Any]], resolved_stops: list[tuple[float, float]]) -> dict[str, Any]:
        merged: dict[str, Any] = {"distance_km": 0.0, "duration_min": 0.0, "geometry": [], "graphhopper_response_parts": []}
        for seg in parts:
            merged["distance_km"] += seg.get("distance_km", 0.0)
            merged["duration_min"] += seg.get("duration_min", 0.0)
            geom = seg.get("geometry") or []
            if not merged["geometry"]:
                merged["geometry"].extend(geom)
            else:
                if geom:
                    if len(merged["geometry"]) > 0 and len(geom) > 0 and merged["geometry"][-1] == geom[0]:
                        merged["geometry"].extend(geom[1:])
                    else:
                        merged["geometry"].extend(geom)
            merged["graphhopper_response_parts"].append(seg.get("graphhopper_response"))
        merged["points_count"] = len(resolved_stops)
        return merged

    @staticmethod
    def _segment_midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
        """Return a geographic midpoint for two coordinates."""
        lat1 = math.radians(a[0])
        lon1 = math.radians(a[1])
        lat2 = math.radians(b[0])
        lon2 = math.radians(b[1])

        dlon = lon2 - lon1
        bx = math.cos(lat2) * math.cos(dlon)
        by = math.cos(lat2) * math.sin(dlon)
        lat3 = math.atan2(
            math.sin(lat1) + math.sin(lat2),
            math.sqrt((math.cos(lat1) + bx) ** 2 + by ** 2),
        )
        lon3 = lon1 + math.atan2(by, math.cos(lat1) + bx)
        return math.degrees(lat3), math.degrees(lon3)

    @staticmethod
    def _is_segmentation_worthy_error(exc: BaseException) -> bool:
        msg = str(exc).lower()
        keywords = (
            "pointdistanceexceededexception",
            "no route",
            "no paths",
            "no path found",
            "invalid route",
            "search exceeded",
            "timeout",
            "too far",
            "bad request",
        )
        if any(k in msg for k in keywords):
            return True
        return is_retryable_request_error(exc)

    def _should_split_segment(self, *, distance_km: float, depth: int, exc: BaseException, segments_total: int) -> bool:
        if depth >= self.max_segmentation_depth:
            self.debug_logger.info("[Segmentation] Max depth reached, aborting safely")
            return False
        if distance_km < self.min_segment_distance_km:
            return False
        if segments_total >= self.max_segment_count:
            self.debug_logger.info("[Segmentation] Max segment count reached, aborting safely")
            return False
        if distance_km < self.segment_distance_threshold_km and not self._is_segmentation_worthy_error(exc):
            return False
        return self._is_segmentation_worthy_error(exc)

    def _should_segment_route(self, *, distance_km: float, exc: BaseException) -> bool:
        if distance_km < self.min_segment_distance_km:
            return False
        return distance_km >= self.segment_distance_threshold_km and self._is_segmentation_worthy_error(exc)

    def _route_pair_recursive(
        self,
        a: tuple[float, float],
        b: tuple[float, float],
        profile: str,
        gh_params: dict[str, Any],
        depth: int,
        resolved_stops: list[tuple[float, float]],
        segment_state: Optional[dict[str, int]] = None,
    ) -> dict[str, Any]:
        if depth > self.max_segmentation_depth:
            self.debug_logger.info("[Segmentation] Max depth reached, aborting safely")
            raise RuntimeError(f"Max segmentation depth exceeded for {a}->{b}")

        if segment_state is None:
            segment_state = {"segments_total": 1}

        pair = [a, b]
        self._validate_segment(pair, context=f"depth={depth}")

        exclusions = None
        try:
            exclusions = gh_params.get('avoid_countries') if gh_params and 'avoid_countries' in gh_params else None
        except Exception:
            exclusions = None

        cached = self._route_cache.get(pair, profile, exclusions=exclusions)
        if cached:
            self.debug_logger.info(f"cache hit for {a}->{b}")
            return cached

        dist_km = GraphHopperClient._haversine_distance(a[0], a[1], b[0], b[1])
        self.debug_logger.info(f"[Segmentation] depth={depth} dist={dist_km:.1f}km segments={segment_state.get('segments_total')} request={a[:2]}->{b[:2]}")

        # Proactive splitting: if a single pair exceeds the threshold
        # with excluded countries, split it without even trying the direct
        # route (it will be ~60-120s and produce massive geometry anyway).
        segs = segment_state.get("segments_total", 1)
        if (exclusions
            and dist_km >= self.segment_distance_threshold_km
            and depth < self.max_segmentation_depth
            and segs < self.max_segment_count):
            self.debug_logger.info(
                "[Segmentation] Proactive pair split: %.0fkm with %d exclusions at depth %d — using midpoint",
                dist_km, len(exclusions or []), depth,
            )
            mid = self._segment_midpoint(a, b)
            self._validate_segment([a, mid, b], context=f"proactive midpoint depth={depth}")
            segment_state["segments_total"] = segs + 1
            left = self._route_pair_recursive(a, mid, profile, gh_params, depth + 1, resolved_stops, segment_state=segment_state)
            right = self._route_pair_recursive(mid, b, profile, gh_params, depth + 1, resolved_stops, segment_state=segment_state)
            merged = self._merge_segment_results([left, right], resolved_stops)
            # NOTE: not caching merged result here — individual segments are cached,
            # and caching under the parent key without depth info would cause ambiguity
            return merged

        try:
            # Tag meta with segment depth for request logging
            seg_params = dict(gh_params)
            seg_meta = seg_params.get("_meta", {})
            seg_meta = dict(seg_meta) if isinstance(seg_meta, dict) else {}
            seg_meta["_segment_depth"] = depth
            seg_params["_meta"] = seg_meta

            res = self.client.route(pair, profile=profile, params=seg_params)
            with contextlib.suppress(Exception):
                self._route_cache.set(pair, profile, res, exclusions=exclusions)
            return res
        except Exception as exc:
            self.debug_logger.warning(f"Direct segment error {a}->{b}: {exc}")
            if not self._should_split_segment(
                distance_km=dist_km,
                depth=depth,
                exc=exc,
                segments_total=segment_state.get("segments_total", 1),
            ):
                raise

        self.debug_logger.info(f"[Segmentation] depth={depth} splitting {a[:2]}->{b[:2]} (dist={dist_km:.1f}km)")

        mid = self._segment_midpoint(a, b)
        self._validate_segment([a, mid, b], context=f"midpoint depth={depth}")

        segment_state["segments_total"] = segment_state.get("segments_total", 1) + 1
        self.debug_logger.info(f"[Segmentation] Created 2 segments (total={segment_state['segments_total']})")
        left = self._route_pair_recursive(a, mid, profile, gh_params, depth + 1, resolved_stops, segment_state=segment_state)
        right = self._route_pair_recursive(mid, b, profile, gh_params, depth + 1, resolved_stops, segment_state=segment_state)
        merged = self._merge_segment_results([left, right], resolved_stops)
        # NOTE: not caching merged result here — individual segments are cached,
        # and caching under the parent key without depth info would cause ambiguity
        return merged

    def calculate_route(self, stops: list[Any], profile: str = "truck", truck: Optional[dict[str, Any]] = None, use_cache: bool = True, avoid_countries: Optional[list[str]] = None, stops_are_coordinates: bool = False) -> dict[str, Any]:
        start = time.time()
        if stops_are_coordinates:
            resolved_stops = validate_route_points(stops)
        else:
            resolved_stops = self._resolve_stops(stops)
        if use_cache:
            cached = self._route_cache.get(resolved_stops, profile, exclusions=avoid_countries)
            if cached:
                cached["cached"] = True
                return cached

        gh_params: dict[str, Any] = {}
        if truck:
            try:
                gh_params = self.constraint_engine.build_params(truck, profile)
            except Exception:
                self.logger.warning("Failed to build truck params", exc_info=True)

        exclusion_plan = self.country_exclusion.prepare(avoid_countries, resolved_stops)
        gh_params = self.country_exclusion.merge_into_params(gh_params, exclusion_plan)

        est_km = sum(
            GraphHopperClient._haversine_distance(
                resolved_stops[i][0], resolved_stops[i][1],
                resolved_stops[i + 1][0], resolved_stops[i + 1][1],
            )
            for i in range(len(resolved_stops) - 1)
        )

        self.debug_logger.info(
            f"[Segmentation] Route distance estimate: {est_km:.1f} km "
            f"stops={len(resolved_stops)} ch.disable={gh_params.get('ch.disable', False)}"
        )

        # Proactive segmentation: for long routes with excluded countries,
        # multi-stop POST routes are extremely slow (60-120s) and produce
        # massive geometries (15K+ points). Split into pair segments upfront.
        has_exclusions = bool(avoid_countries) and len(avoid_countries or []) > 0
        should_segment = (
            has_exclusions
            and est_km >= self.segment_distance_threshold_km
            and est_km >= self.min_segment_distance_km
        )

        if should_segment:
            self.debug_logger.info(
                "[Segmentation] Proactive segmentation: %d excluded countries, %.0fkm — splitting into pairs",
                len(avoid_countries or []), est_km,
            )
            parts: list[dict[str, Any]] = []
            pair_count = len(resolved_stops) - 1
            for i in range(pair_count):
                a = resolved_stops[i]
                b = resolved_stops[i + 1]
                seg = self._route_pair_recursive(a, b, profile, gh_params, depth=0, resolved_stops=resolved_stops)
                parts.append(seg)
            if not parts:
                raise RuntimeError("Segmentation produced no valid segments")
            res = self._merge_segment_results(parts, resolved_stops)
        else:
            self.debug_logger.info("[Segmentation] Attempting direct route first...")
            try:
                res = self.client.route(resolved_stops, profile=profile, params=gh_params)
            except Exception as direct_exc:
                self.debug_logger.warning(f"Direct multi-stop failed: {direct_exc}")
                if not self._should_segment_route(distance_km=est_km, exc=direct_exc):
                    raise
                self.debug_logger.info("[Segmentation] Direct route failed, splitting into pairs...")
                parts: list[dict[str, Any]] = []
                pair_count = len(resolved_stops) - 1
                for i in range(pair_count):
                    a = resolved_stops[i]
                    b = resolved_stops[i + 1]
                    seg = self._route_pair_recursive(a, b, profile, gh_params, depth=0, resolved_stops=resolved_stops)
                    parts.append(seg)
                if not parts:
                    raise RuntimeError("Segmentation produced no valid segments") from None
                res = self._merge_segment_results(parts, resolved_stops)

        try:
            from services.country_borders import countries_from_points
            geom_points = res.get('geometry', [])

            # Downsample geometry to max 500 pts before country detection
            # (avoids O(n×m) ray-casting on massive routes like 1800km/18k pts)
            MAX_COUNTRY_SAMPLE_PTS = 500
            if len(geom_points) > MAX_COUNTRY_SAMPLE_PTS:
                step = max(1, len(geom_points) // MAX_COUNTRY_SAMPLE_PTS)
                sampled_geom = [geom_points[i] for i in range(0, len(geom_points), step)]
                if geom_points and sampled_geom and sampled_geom[-1] != geom_points[-1]:
                    sampled_geom.append(geom_points[-1])
                all_pts = [(float(lat), float(lon)) for lat, lon in resolved_stops] + sampled_geom
            else:
                all_pts = [(float(lat), float(lon)) for lat, lon in resolved_stops] + geom_points

            countries = countries_from_points(all_pts)
            res['detected_countries'] = countries
        except Exception:
            self.logger.warning("Country detection failed", exc_info=True)
            countries = []

        exclusions = exclusion_plan.requested
        res['excluded_countries_requested'] = exclusions
        res['excluded_countries_applied'] = exclusion_plan.applied
        res['excluded_countries_skipped'] = exclusion_plan.skipped_at_stops
        res['exclusion_strategy'] = exclusion_plan.strategy
        if exclusion_plan.active:
            res['routing_method'] = 'POST'
            res['exclusions_applied'] = True

        applied_set = set(exclusion_plan.applied)
        if applied_set and any(c in applied_set for c in countries):
            self.debug_logger.warning(
                f"[RouteService] Route may still cross blocked countries after pathfinding: "
                f"detected={countries} applied_exclusions={list(applied_set)}"
            )
            res['exclusion_warning'] = (
                'Route geometry may still touch excluded regions (border sampling / bbox overlap).'
            )
        elif exclusion_plan.active:
            self.debug_logger.info(
                f"[RouteService] Exclusions active; detected countries={countries} "
                f"applied={exclusion_plan.applied}"
            )

        res["profile"] = profile
        # set truck id safely
        try:
            res["truck_id"] = TruckConstraintEngine._get_truck_value(truck, "id") if truck else None
        except Exception:
            self.logger.warning("Failed to extract truck_id via constraint engine", exc_info=True)
            try:
                res["truck_id"] = truck["id"] if truck and "id" in truck else None
            except Exception:
                self.logger.warning("Failed to extract truck_id direct", exc_info=True)
                res["truck_id"] = None

        res["stops"] = [(lat, lon) for lat, lon in resolved_stops]
        res["cached"] = False
        if use_cache:
            try:
                self._route_cache.set(resolved_stops, profile, res, exclusions=avoid_countries)
            except Exception:
                self.logger.warning("Failed to update route cache", exc_info=True)

        self.debug_logger.info(f"calculate_route_end total_s={time.time()-start:.2f} distance_km={res.get('distance_km')}")
        return res

    def calculate_route_async(
        self,
        stops: list[Any],
        callback,
        profile: str = "truck",
        truck: Optional[dict[str, Any]] = None,
        use_cache: bool = True,
        avoid_countries: Optional[list[str]] = None,
        stops_are_coordinates: bool = False,
    ) -> threading.Thread:
        """Calculate a route in a background thread.

        Args:
            stops: Address strings or coordinate tuples.
            callback: Callable that receives the route result dict when
                      calculation completes.
            profile: Routing profile (default ``"truck"``).
            truck: Optional truck data for constraint-engine params.
            use_cache: Whether to check / update the route cache.
            avoid_countries: Optional list of country codes to exclude.
            stops_are_coordinates: If True, *stops* are (lat, lon) tuples.

        Returns:
            The background ``threading.Thread`` (daemon) for optional join.
        """
        def _run():
            try:
                result = self.calculate_route(
                    stops=stops,
                    profile=profile,
                    truck=truck,
                    use_cache=use_cache,
                    avoid_countries=avoid_countries,
                    stops_are_coordinates=stops_are_coordinates,
                )
                callback(result)
            except Exception as e:
                self.logger.error("Async route calculation failed: %s", e, exc_info=True)
                callback({
                    "success": False,
                    "error": str(e),
                    "distance_km": 0.0,
                    "duration_min": 0.0,
                    "geometry": [],
                })

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread


