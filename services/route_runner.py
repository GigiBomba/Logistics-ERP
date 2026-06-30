# services/route_runner.py
# Production-grade route orchestrator with long-distance optimizations

import threading
import time
from typing import Any, Callable, Optional

from services.geocode_nominatim import geocode_place
from services.route_service import RouteService

class RouteRunner:
    """
    Production route runner with clean threading architecture.

    Features:
    - Single worker thread (no nested threads)
    - Thread-safe callbacks
    - Request cancellation support
    - Progress tracking
    - Comprehensive error handling
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._current_thread: Optional[threading.Thread] = None
        self._cancel_flag = threading.Event()
        self.logger = None

        try:
            from utils.logger import get_logger
            self.logger = get_logger("RouteRunner")
        except Exception:
            pass

    def _log(self, level: str, message: str, **kwargs):
        if self.logger:
            getattr(self.logger, level)(message, **kwargs)

    def _safe_invoke(self, cb: Optional[Callable[[Any], None]], data: Any):
        """Invoke the callback from the worker thread.

        GUI code must NOT touch widgets directly from here — instead the
        caller should marshal back to the GUI thread (e.g. via a Qt
        ``Signal``).  ``QTimer.singleShot(0, ...)`` from a worker thread
        does NOT marshal; Qt creates the timer in the calling thread.
        """
        if not cb:
            return
        try:
            cb(data)
        except Exception as exc:
            self._log('exception', 'Callback invocation failed: %s', exc)

    def cancel(self):
        """Cancel current route calculation"""
        with self._lock:
            self._cancel_flag.set()
            self._log("info", "Route calculation cancelled by user")

    def _is_cancelled(self) -> bool:
        return self._cancel_flag.is_set()

    def _reset_cancel_flag(self):
        self._cancel_flag.clear()

    def _resolve_stops(
        self,
        stops_state: list[dict],
        geocode_cache: Optional[object] = None
    ) -> list[tuple]:
        """Resolve all stops to coordinates with validation and intelligent chunking for long routes"""
        resolved = []

        for i, stop in enumerate(stops_state):
            if self._is_cancelled():
                raise InterruptedError("Route calculation cancelled")

            # Check if already resolved
            if stop.get("resolved") and stop.get("lat") and stop.get("lon"):
                try:
                    lat = float(stop["lat"])
                    lon = float(stop["lon"])

                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        raise ValueError(f"Invalid coordinates at stop {i}")

                    if lat == 0.0 and lon == 0.0:
                        raise ValueError(f"Zero coordinates at stop {i}")

                    resolved.append((lat, lon))
                    self._log("debug", f"Stop {i}: using pre-resolved coords ({lat:.4f}, {lon:.4f})")
                    continue
                except (KeyError, TypeError, ValueError) as e:
                    self._log("warning", f"Stop {i}: invalid resolved coords - {e}")
                    stop["resolved"] = False

            # Geocode address (use cache if provided)
            address = stop.get("address", "").strip()
            if not address:
                raise ValueError(f"Stop {i} has no address or coordinates")

            # check caches first
            cached = None
            try:
                if geocode_cache is not None:
                    cached = geocode_cache.get(address)
            except Exception:
                cached = None

            if cached:
                lat, lon = cached
                resolved.append((lat, lon))
                self._log("debug", f"Stop {i}: geocode cache hit for '{address}' -> ({lat:.4f},{lon:.4f})")
                continue

            self._log("debug", f"Stop {i}: geocoding '{address}'")
            try:
                coords = geocode_place(address, timeout=15)
                if not coords:
                    raise ValueError("Geocoding service returned no results")
                lat, lon = coords
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("Invalid geocode result coordinates")
                if lat == 0.0 and lon == 0.0:
                    raise ValueError("Geocoding returned zero coordinates")

                # store in provided cache if available (best-effort)
                try:
                    if geocode_cache is not None:
                        geocode_cache.set(address, (lat, lon))
                except Exception:
                    pass

                resolved.append((lat, lon))
                self._log("debug", f"Stop {i}: geocoded successfully to ({lat:.4f}, {lon:.4f})")
                # small throttle to avoid hammering geocode service on many unique addresses
                time.sleep(0.05)
            except Exception as e:
                self._log("error", f"Stop {i}: failed to geocode '{address}' - {e}")
                raise ValueError(f"Cannot resolve stop {i} '{address}': {e}") from e

        if len(resolved) < 2:
            raise ValueError(f"At least 2 valid stops required (got {len(resolved)})")

        # Deduplicate consecutive identical points
        deduplicated = [resolved[0]]
        for i in range(1, len(resolved)):
            if resolved[i] != resolved[i-1]:
                deduplicated.append(resolved[i])

        if len(deduplicated) < 2:
            raise ValueError("At least 2 unique stops required after deduplication")

        # OPTIMIZED: Calculate total distance to determine if route needs optimization
        total_distance = self._calculate_distance(deduplicated)
        self._log("info", f"Resolved {len(deduplicated)} stops, estimated distance: {total_distance:.0f}km")

        return deduplicated

    def _calculate_distance(self, points: list[tuple]) -> float:
        """Calculate total distance between points using Haversine formula (delegates to shared impl)."""
        from services.route_service import GraphHopperClient
        total_distance = 0.0
        for i in range(len(points) - 1):
            total_distance += GraphHopperClient._haversine_distance(
                points[i][0], points[i][1], points[i + 1][0], points[i + 1][1],
            )
        return total_distance

    def run_route_async(
        self,
        route_service,
        stops_state: list[dict],
        truck,
        profile: str,
        callback,
        geocode_cache: Optional[object] = None,
        avoid_countries: Optional[list[str]] = None
    ):
        """
        Calculate route asynchronously with proper threading and long-distance optimizations.

        Args:
            route_service: RouteService instance
            stops_state: List of stop dictionaries
            truck: Truck configuration dict
            profile: GraphHopper profile name
            callback: Function to call with result or error
        """
        def task():
            start_time = time.time()
            total_attempts = 0

            self._log("info", f"Starting route calculation: {len(stops_state)} stops, profile={profile}")
            if avoid_countries:
                self._log("info", f"[RouteRunner] Excluding countries: {avoid_countries}")

            try:
                # Phase 1: Resolve all stops to coordinates
                self._log("info", "Phase 1: Resolving stops to coordinates...")

                resolved_points = self._resolve_stops(stops_state, geocode_cache=geocode_cache)

                if self._is_cancelled():
                    raise InterruptedError("Route calculation cancelled")

                self._log("info", f"Phase 1 complete: {len(resolved_points)} unique points")

                # Phase 2: Calculate route (retries handled by GraphHopperClient)
                self._log("info", "Phase 2: Calculating route...")
                total_attempts = 1

                result = route_service.calculate_route(
                    stops=resolved_points,
                    profile=profile,
                    truck=truck,
                    avoid_countries=avoid_countries,
                    stops_are_coordinates=True,
                )

                if self._is_cancelled():
                    raise InterruptedError("Route calculation cancelled")

                elapsed = time.time() - start_time

                if result and len(result) > 0:
                    route = result[0]
                    distance = route.get("distance_km", 0)
                    self._log(
                        "info",
                        f"Route calculated successfully: {distance:.1f} km, "
                        f"{route.get('duration_min', 0):.1f} min in {elapsed:.2f}s",
                    )
                    if callback:
                        self._safe_invoke(callback, result)
                    return

                last_error = "Route calculation returned no results"
                self._log("error", last_error)
                if callback:
                    self._safe_invoke(callback, {"error": last_error, "type": "no_result"})

            except InterruptedError as e:
                self._log("warning", f"Route calculation cancelled: {e}")
                if callback:
                    self._safe_invoke(callback, {"error": "Route calculation cancelled", "cancelled": True})

            except ValueError as e:
                self._log("error", f"Validation error: {e}")
                if callback:
                    self._safe_invoke(callback, {"error": str(e), "type": "validation"})

            except Exception as e:
                self._log("exception", f"Route calculation failed: {e}")
                if callback:
                    self._safe_invoke(callback, {"error": str(e), "type": "calculation", "attempts": total_attempts})

        # Create single worker thread
        with self._lock:
            if self._current_thread and self._current_thread.is_alive():
                self._log("warning", "Previous route calculation still running, cancelling...")
                self._cancel_flag.set()
                self._current_thread.join(timeout=5.0)
                if self._current_thread.is_alive():
                    self._log("warning", "Previous thread did not stop in time, starting new calculation anyway")

            self._reset_cancel_flag()
            self._current_thread = threading.Thread(
                target=task,
                daemon=True,
                name="RouteRunner-LongDistance-Worker"
            )
            self._current_thread.start()
            self._log("debug", "Started optimized route calculation worker thread")


# Backward compatibility wrapper — uses a cached singleton runner
_RUNNER_INSTANCE = RouteRunner()

def run_route_async(
    route_service: RouteService,
    stops_state: list[dict],
    truck: Optional[dict],
    profile: str,
    callback: Optional[Callable[[dict], None]],
    geocode_cache: Optional[object] = None,
    avoid_countries: Optional[list[str]] = None
):
    """Legacy compatibility function — delegates to cached RouteRunner singleton."""
    _RUNNER_INSTANCE.run_route_async(
        route_service=route_service,
        stops_state=stops_state,
        truck=truck,
        profile=profile,
        callback=callback,
        avoid_countries=avoid_countries,
        geocode_cache=geocode_cache
    )
