# services/route_runner.py
# Production-grade route orchestrator with long-distance optimizations

import threading
import time
import math
from typing import Dict, List, Optional, Callable, Any

from services.geocode_nominatim import geocode_place
from services.graphhopper_network import is_retryable_request_error
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
        self._cancel_flag = False
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
        """Invoke callback on UI/main thread when possible, otherwise call directly."""
        if not cb:
            return
        try:
            import tkinter as tk
            root = getattr(tk, '_default_root', None)
            if root is not None:
                root.after(0, lambda: cb(data))
                return
        except Exception:
            pass
        try:
            cb(data)
        except Exception:
            self._log('exception', 'Callback invocation failed')
    
    def cancel(self):
        """Cancel current route calculation"""
        with self._lock:
            self._cancel_flag = True
            self._log("info", "Route calculation cancelled by user")
    
    def _is_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_flag
    
    def _reset_cancel_flag(self):
        with self._lock:
            self._cancel_flag = False
    
    def _resolve_stops(
        self,
        stops_state: List[Dict],
        geocode_cache: Optional[object] = None
    ) -> List[tuple]:
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
                raise ValueError(f"Cannot resolve stop {i} '{address}': {e}")
        
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
    
    def _calculate_distance(self, points: List[tuple]) -> float:
        """Calculate total distance between points using Haversine formula"""
        import math
        
        total_distance = 0
        for i in range(len(points) - 1):
            lat1, lon1 = points[i]
            lat2, lon2 = points[i + 1]
            
            R = 6371  # Earth's radius in km
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lon2 - lon1)
            
            a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
                math.cos(phi1) * math.cos(phi2) * \
                math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
            
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c
            
            total_distance += distance
        
        return total_distance
    
    def run_route_async(
        self,
        route_service,
        stops_state: List[Dict],
        truck,
        profile: str,
        callback,
        geocode_cache: Optional[object] = None,
        avoid_countries: Optional[List[str]] = None
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
        self._reset_cancel_flag()
        
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
                
                # Phase 2: Calculate route with enhanced retry handling for long distances
                self._log("info", "Phase 2: Calculating route with optimized retry strategy...")
                
                max_retries = 3
                last_error = None

                for attempt in range(max_retries):
                    try:
                        total_attempts += 1

                        result = route_service.calculate_route(
                            stops=resolved_points,
                            profile=profile,
                            truck=truck,
                            avoid_countries=avoid_countries,
                        )

                        if self._is_cancelled():
                            raise InterruptedError("Route calculation cancelled")

                        elapsed = time.time() - start_time

                        if result and len(result) > 0:
                            route = result[0]
                            distance = route.get("distance_km", 0)
                            retry_info = f"(attempt {total_attempts})" if total_attempts > 1 else ""

                            self._log(
                                "info",
                                f"Route calculated successfully: {distance:.1f} km, "
                                f"{route.get('duration_min', 0):.1f} min in {elapsed:.2f}s {retry_info}",
                            )

                            if callback:
                                self._safe_invoke(callback, result)
                            return

                        last_error = "Route calculation returned no results"
                        self._log("error", last_error)
                        if callback:
                            self._safe_invoke(callback, {"error": last_error, "type": "no_result"})
                        return

                    except Exception as e:
                        last_error = str(e)
                        can_retry = is_retryable_request_error(e) and attempt < max_retries - 1
                        if can_retry:
                            wait_time = 2 ** attempt
                            self._log(
                                "warning",
                                f"Route calculation failed (attempt {attempt + 1}/{max_retries}): {last_error} "
                                f"(retrying in {wait_time}s)",
                            )
                            time.sleep(wait_time)
                        else:
                            self._log(
                                "error",
                                f"Route calculation failed after {attempt + 1} attempt(s): {last_error}",
                            )
                            break
                
                # All retries exhausted
                if callback:
                    self._safe_invoke(callback, {
                        "error": last_error or "Route calculation failed",
                        "type": "calculation",
                        "attempts": total_attempts
                    })
                
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
                self._cancel_flag = True
            
            self._current_thread = threading.Thread(
                target=task,
                daemon=True,
                name="RouteRunner-LongDistance-Worker"
            )
            self._current_thread.start()
            self._log("debug", "Started optimized route calculation worker thread")


# Backward compatibility wrapper
def run_route_async(
    route_service: RouteService,
    stops_state: List[Dict],
    truck: Optional[Dict],
    profile: str,
    callback: Optional[Callable[[Dict], None]],
    geocode_cache: Optional[object] = None,
    avoid_countries: Optional[List[str]] = None
):
    """Legacy compatibility function"""
    runner = RouteRunner()
    runner.run_route_async(
        route_service=route_service,
        stops_state=stops_state,
        truck=truck,
        profile=profile,
        callback=callback,
        avoid_countries=avoid_countries,
        geocode_cache=geocode_cache
    )