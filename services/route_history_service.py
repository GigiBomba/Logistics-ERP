"""Persistent route history storage.

This module stores successful route calculations in the existing ERP SQLite
database without changing routing behavior. Large geometry payloads are zlib
compressed JSON blobs, while searchable route metadata remains indexed.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import threading
import zlib
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from repositories.route_event_repository import RouteEventRepository
from repositories.route_repository import RouteRepository
from repositories.settings_repository import SettingsRepository
from repositories.truck_route_assignment_repository import TruckRouteAssignmentRepository
from services.route_result_presenter import format_duration_minutes
from utils.logger import get_logger

_logger = logging.getLogger(__name__)


ROUTE_HISTORY_METADATA_VERSION = 1
DEFAULT_RETENTION_DAYS = 365
RETENTION_SETTING_KEY = "route_history_retention_days"
ACTIVE_ROUTE_SETTING_KEY = "current_active_route_id"


@dataclass
class RouteHistoryRecord:
    """DTO used to save and load a route history entry.

    Route History is LIGHTWEIGHT: stores only route geometry, distance,
    duration, selected truck, timestamps, and routing parameters.
    Financial data (costs, profit, invoices) belongs in the trips table.
    """

    stops: list[dict[str, Any]]
    geometry: list[Any] = field(default_factory=list)
    total_distance_km: float | None = None
    duration_min: float | None = None
    truck_id: str | None = None
    truck_label: str | None = None
    truck: dict[str, Any] = field(default_factory=dict)
    profile: str | None = None
    excluded_countries: list[str] = field(default_factory=list)
    countries_traversed: list[str] = field(default_factory=list)
    metadata_version: int = ROUTE_HISTORY_METADATA_VERSION
    # DEPRECATED — these were previously populated from route_persistence
    # but are no longer written. They are kept in the DTO only for backward
    # compat when loading entries that still have them in the DB.
    toll_estimates: dict[str, Any] = field(default_factory=dict)
    fuel_estimates: dict[str, Any] = field(default_factory=dict)
    profit_estimates: dict[str, Any] = field(default_factory=dict)
    route_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteHistoryListItem:
    """Lightweight DTO for history lists that do not need full geometry.

    Shows only route metadata — no financial fields (those belong in trips).
    """

    id: int
    route_fingerprint: str
    created_at: str
    last_calculated_at: str
    calculation_count: int
    total_distance_km: float | None
    duration_min: float | None
    truck_id: str | None
    truck_label: str | None
    profile: str | None
    origin: str
    destination: str
    excluded_countries: list[str]
    countries_traversed: list[str]
    # DEPRECATED — kept for backward compat with list items from old DB.
    saved_cost: float | None = None
    saved_profit: float | None = None
    fuel_liters: float | None = None
    metadata_version: int = ROUTE_HISTORY_METADATA_VERSION
    archived_at: str | None = None


class RouteHistoryService:
    """Save, load, delete, and prune persistent route history records."""

    def __init__(self, db_or_conn: Any, retention_days: int | None = None) -> None:
        self.logger = get_logger("RouteHistoryService")
        db = db_or_conn
        self.db = db
        self._route_repo = RouteRepository(db)
        self._event_repo = RouteEventRepository(db)
        self._assignment_repo = TruckRouteAssignmentRepository(db)
        self._lock = threading.RLock()
        self.retention_days = retention_days

    def save_route(self, record: RouteHistoryRecord) -> int:
        """Insert or update a successful route calculation.

        Duplicate spam is prevented by a deterministic fingerprint. Repeated
        calculations of the same stops/profile/truck/exclusions update the
        existing row and increment ``calculation_count``.
        """
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        normalized = self._normalize_record(record)
        fingerprint = self.build_fingerprint(normalized)
        payload = self._to_db_payload(normalized)

        data = {
            "route_fingerprint": fingerprint,
            "metadata_version": normalized.metadata_version,
            "created_at": now,
            "last_calculated_at": now,
            "calculation_count": 1,
            "stops_json": payload["stops_json"],
            "geometry_compressed": payload["geometry_compressed"],
            "geometry_encoding": "zlib-json",
            "total_distance_km": normalized.total_distance_km,
            "duration_min": normalized.duration_min,
            "truck_id": normalized.truck_id,
            "truck_label": normalized.truck_label,
            "truck_json": payload["truck_json"],
            "profile": normalized.profile,
            "excluded_countries_json": payload["excluded_countries_json"],
            "countries_traversed_json": payload["countries_traversed_json"],
        }

        with self._lock:
            self._route_repo.upsert(data, fingerprint)
            route_id = self._route_repo.get_id_by_fingerprint(fingerprint)
            if route_id is None:
                raise RuntimeError("Upsert failed to produce a route id")

        self.prune_old_routes()
        return route_id

    def load_route(self, route_id: int) -> RouteHistoryRecord | None:
        """Load one route history record including decompressed geometry."""
        cached = _RECENT_ROUTE_CACHE.get(route_id)
        if cached is not None:
            return cached
        row = self._route_repo.get_by_id(route_id)
        record = self._row_to_record(row) if row else None
        if record is not None:
            _RECENT_ROUTE_CACHE.put(route_id, record)
        return record

    def list_routes(self, limit: int = 100, offset: int = 0) -> list[RouteHistoryListItem]:
        """Return recent route history metadata without loading geometry blobs."""
        return self.search_routes(limit=limit, offset=offset)

    def search_routes(
        self,
        search: str = "",
        truck: str = "",
        profile: str = "",
        include_archived: bool = False,
        sort_by: str = "last_calculated_at",
        sort_dir: str = "DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> list[RouteHistoryListItem]:
        """Return paginated route history metadata with simple filters."""
        rows = self._route_repo.search(
            search=search,
            truck=truck,
            profile=profile,
            include_archived=include_archived,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
        return [self._row_to_list_item(row) for row in rows]

    def count_routes(
        self,
        search: str = "",
        truck: str = "",
        profile: str = "",
        include_archived: bool = False,
    ) -> int:
        """Count route history rows matching current filters."""
        return self._route_repo.count_filtered(
            search=search,
            truck=truck,
            profile=profile,
            include_archived=include_archived,
        )

    def delete_route(self, route_id: int) -> bool:
        """Delete one route history record by id."""
        self._route_repo.delete(route_id)
        return True

    def commit_route(self, route_id: int) -> bool:
        """Mark a draft route as committed (user intends to use it operationally)."""
        self._route_repo.commit(route_id)
        self.record_event(route_id, "route_committed")
        return True

    def discard_route(self, route_id: int) -> bool:
        """Soft-discard a draft route (sets is_committed = -1, keeps record)."""
        self._route_repo.discard(route_id)
        self.record_event(route_id, "route_discarded")
        return True

    def archive_route(self, route_id: int) -> bool:
        """Soft-archive a route history row."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        self._route_repo.archive(route_id, archived_at=now)
        self.record_event(route_id, "route_archived", {"archived_at": now})
        return True

    def complete_route(self, route_id: int) -> bool:
        """Mark truck assignment as completed and emit a route_completed event."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        ok = self._assignment_repo.complete(route_id, now)
        self.record_event(route_id, "route_completed", {"completed_at": now})
        return ok

    def set_active_route(self, route_id: int) -> None:
        """Set the central current active route id for ERP-wide sync."""
        with self._lock:
            SettingsRepository(self.db).upsert_setting(
                ACTIVE_ROUTE_SETTING_KEY, str(int(route_id)),
            )
        self.record_event(route_id, "route_updated", {"active": True})

    def get_active_route_id(self) -> int | None:
        """Return the active route id if configured."""
        try:
            value = SettingsRepository(self.db).get_setting_value(ACTIVE_ROUTE_SETTING_KEY)
            return int(value) if value else None
        except Exception:
            return None

    def get_active_route(self) -> RouteHistoryRecord | None:
        """Load the current active route record."""
        route_id = self.get_active_route_id()
        return self.load_route(route_id) if route_id else None

    def assign_route_to_truck(self, route_id: int, truck_id: str, status: str = "assigned", notes: str = "") -> int:
        """Assign a saved route to a truck for dispatch/fleet workflows."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        started_at = now if status == "active" else None
        assignment_id = self._assignment_repo.assign(
            truck_id=str(truck_id),
            route_id=int(route_id),
            status=status,
            assigned_at=now,
            started_at=started_at,
            notes=notes,
        )
        self.record_event(route_id, "route_updated", {"truck_id": str(truck_id), "assignment_status": status})
        if status == "active":
            self.set_active_route(route_id)
        return assignment_id

    def get_truck_routes(self, truck_id: str, status: str | None = None) -> list[dict[str, Any]]:
        """Return assigned, active, or completed route assignments for a truck."""
        return self._assignment_repo.get_by_truck(truck_id, status=status)

    def record_event(self, route_id: int | None, event_type: str, payload: dict[str, Any] | None = None) -> int:
        """Persist and publish a route event."""
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        event_id = self._event_repo.create(
            route_id=route_id,
            event_type=event_type,
            payload_json=self._json(payload or {}),
            created_at=now,
        )
        RouteEventBus.publish(event_type, {"id": event_id, "route_id": route_id, **(payload or {})})
        return event_id

    def update_route(self, route_id: int, record: RouteHistoryRecord) -> bool:
        """Update an existing route history record.

        Loads the existing record to verify it exists, normalizes the
        new data, builds a DB payload, and calls ``RouteRepository.update()``.
        Returns ``True`` on success, ``False`` if the route was not found.
        """
        existing = self.load_route(route_id)
        if not existing:
            return False

        normalized = self._normalize_record(record)
        payload = self._to_db_payload(normalized)
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        data: dict[str, Any] = {
            "stops_json": payload["stops_json"],
            "geometry_compressed": payload["geometry_compressed"],
            "total_distance_km": normalized.total_distance_km,
            "duration_min": normalized.duration_min,
            "truck_id": normalized.truck_id,
            "truck_label": normalized.truck_label,
            "truck_json": payload["truck_json"],
            "profile": normalized.profile,
            "excluded_countries_json": payload["excluded_countries_json"],
            "countries_traversed_json": payload["countries_traversed_json"],
        }

        self._route_repo.update(route_id, data)
        self.record_event(route_id, "route_updated", {"route_id": route_id})
        return True

    def duplicate_route(self, route_id: int) -> int | None:
        """Create a copy of a history route as a new row."""
        record = self.load_route(route_id)
        if not record:
            return None
        record.route_summary = dict(record.route_summary or {})
        record.route_summary["duplicated_from"] = route_id
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        fingerprint = hashlib.sha256(f"{route_id}:{now}".encode()).hexdigest()
        payload = self._to_db_payload(record)
        data = {
            "route_fingerprint": fingerprint,
            "metadata_version": record.metadata_version,
            "created_at": now,
            "last_calculated_at": now,
            "calculation_count": 1,
            "stops_json": payload["stops_json"],
            "geometry_compressed": payload["geometry_compressed"],
            "geometry_encoding": "zlib-json",
            "total_distance_km": record.total_distance_km,
            "duration_min": record.duration_min,
            "truck_id": record.truck_id,
            "truck_label": record.truck_label,
            "truck_json": payload["truck_json"],
            "profile": record.profile,
            "excluded_countries_json": payload["excluded_countries_json"],
            "toll_estimates_json": self._json(record.toll_estimates),
            "fuel_estimates_json": self._json(record.fuel_estimates),
            "profit_estimates_json": self._json(record.profit_estimates),
            "countries_traversed_json": payload["countries_traversed_json"],
            "route_summary_json": self._json(record.route_summary),
        }
        return self._route_repo.create(data)

    def get_statistics(self, include_archived: bool = False) -> dict[str, Any]:
        """Compute route history statistics (route-only) — memory-efficient, no BLOBs."""
        agg = self._route_repo.get_statistics_aggregate(include_archived=include_archived)

        destinations: dict[str, int] = {}
        for row in self._route_repo.get_stops_for_statistics(include_archived=include_archived):
            stops = self._loads(row["stops_json"], [])
            if stops:
                dest = self._stop_label(stops[-1])
                destinations[dest] = destinations.get(dest, 0) + 1

        common_destinations = sorted(destinations.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {
            "route_count": agg["route_count"],
            "total_distance_km": round(float(agg["total_distance"]), 2),
            "most_common_destinations": common_destinations,
        }

    def get_route_analytics(self, include_archived: bool = False) -> dict[str, Any]:
        """Return route analytics (route-only) — memory-efficient, no BLOBs."""
        rows = self._route_repo.get_countries_and_durations(include_archived=include_archived)
        country_frequency: dict[str, int] = {}
        durations = []
        for row in rows:
            countries = self._loads(row.get("countries_traversed_json"), [])
            dur = row.get("duration_min")
            if dur is not None:
                durations.append(float(dur or 0))
            for country in countries:
                cc = str(country).upper()
                country_frequency[cc] = country_frequency.get(cc, 0) + 1
        return {
            "average_trip_duration_min": round(sum(durations) / len(durations), 2) if durations else 0.0,
            "country_frequency": dict(sorted(country_frequency.items(), key=lambda kv: kv[1], reverse=True)),
        }

    def export_route(self, route_id: int, fmt: str = "json") -> Any:
        """Return a JSON, CSV, or PDF-ready export payload for one route."""
        record = self.load_route(route_id)
        if not record:
            return None
        payload = {
            "metadata": {
                "route_id": route_id,
                "metadata_version": record.metadata_version,
                "profile": record.profile,
                "truck": record.truck,
            },
            "route": {
                "origin": self._stop_label(record.stops[0]) if record.stops else "",
                "destination": self._stop_label(record.stops[-1]) if record.stops else "",
                "stops": record.stops,
                "distance_km": record.total_distance_km,
                "duration_min": record.duration_min,
                "countries_traversed": record.countries_traversed,
                "excluded_countries": record.excluded_countries,
            },
            "geometry": record.geometry,
        }
        fmt = fmt.lower()
        if fmt == "json":
            return payload
        if fmt == "pdf":
            return self._pdf_ready_payload(payload)
        if fmt == "csv":
            return self._csv_payload(payload)
        raise ValueError(f"Unsupported export format: {fmt}")

    def export_route_file(self, route_id: int, filepath: str) -> str | None:
        """Export a route history record as a ``.operionroute`` binary file.

        The file can be shared via email, chat, or file transfer, and
        opened in another Operion instance to reproduce the route.

        Parameters
        ----------
        route_id : int
            The route history record id.
        filepath : str
            Destination file path (should end in ``.operionroute``).

        Returns
        -------
        str or None
            The *filepath* on success, ``None`` on failure.
        """
        from services.route_sharing_service import encode_route_file

        record = self.load_route(route_id)
        if not record:
            return None

        # Build stop dicts from the record's stops
        stop_dicts: list[dict[str, Any]] = []
        for i, s in enumerate(record.stops):
            stop_type = "start" if i == 0 else ("destination" if i == len(record.stops) - 1 else "stop")
            stop_dicts.append({
                "lat": s.get("lat"),
                "lon": s.get("lon"),
                "type": stop_type,
            })

        data = encode_route_file(
            stops=stop_dicts,
            profile=record.profile,
            truck_id=record.truck_id,
            truck_label=record.truck_label,
            geometry=record.geometry,
            distance_km=record.total_distance_km,
            duration_min=record.duration_min,
        )

        try:
            with open(filepath, "wb") as f:
                f.write(data)
            return filepath
        except OSError:
            self.logger.exception("Failed to export route file to %s", filepath)
            return None

    def clear_history(self) -> int:
        """Delete all route history rows and return the deleted count."""
        return self._route_repo.clear_all()

    def set_retention_days(self, days: int) -> None:
        """Persist route history retention in days. Use 0 or lower to disable pruning."""
        with self._lock:
            SettingsRepository(self.db).upsert_setting(
                RETENTION_SETTING_KEY, str(int(days)),
            )
        self.retention_days = int(days)

    def get_retention_days(self) -> int:
        """Read configured retention days, defaulting to one year."""
        if self.retention_days is not None:
            return int(self.retention_days)
        try:
            value = SettingsRepository(self.db).get_setting_value(RETENTION_SETTING_KEY)
            if value:
                return int(value)
        except Exception:
            self.logger.exception("Failed to read route history retention setting")
        return DEFAULT_RETENTION_DAYS

    def prune_old_routes(self) -> int:
        """Delete route history older than the configured retention period."""
        days = self.get_retention_days()
        if days <= 0:
            return 0
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds") + "Z"
        return self._route_repo.prune_before(cutoff)

    def run_cleanup(self) -> dict[str, int]:
        """Background cleanup hook for app startup or future scheduler."""
        pruned = self.prune_old_routes()
        orphan_events = self._event_repo.delete_orphans()
        return {"pruned_routes": pruned, "orphan_events": orphan_events}

    def build_fingerprint(self, record: RouteHistoryRecord) -> str:
        """Build a stable duplicate-prevention key for route identity."""
        key = {
            "stops": self._fingerprint_stops(record.stops),
            "profile": record.profile,
            "truck_id": record.truck_id,
            "excluded_countries": sorted([c.upper() for c in record.excluded_countries]),
            "metadata_version": record.metadata_version,
        }
        raw = json.dumps(key, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _normalize_record(self, record: RouteHistoryRecord) -> RouteHistoryRecord:
        data = asdict(record)
        data["excluded_countries"] = sorted({str(c).upper() for c in record.excluded_countries if c})
        data["countries_traversed"] = sorted({str(c).upper() for c in record.countries_traversed if c})
        data["stops"] = self._normalize_stops(record.stops)
        return RouteHistoryRecord(**data)

    def _normalize_stops(self, stops: Iterable[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for idx, stop in enumerate(stops or []):
            if isinstance(stop, dict):
                item = dict(stop)
            elif isinstance(stop, (list, tuple)) and len(stop) >= 2:
                item = {"lat": stop[0], "lon": stop[1]}
            else:
                item = {"value": stop}
            item.setdefault("position", idx)
            normalized.append(item)
        return normalized

    def _fingerprint_stops(self, stops: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        fp_stops = []
        for stop in stops:
            lat = stop.get("lat")
            lon = stop.get("lon")
            fp_stops.append({
                "lat": round(float(lat), 5) if lat is not None else None,
                "lon": round(float(lon), 5) if lon is not None else None,
                "address": (stop.get("address") or "").strip().lower(),
                "type": stop.get("type"),
            })
        return fp_stops

    def _to_db_payload(self, record: RouteHistoryRecord) -> dict[str, Any]:
        return {
            "stops_json": self._json(record.stops),
            "geometry_compressed": self._compress_json(record.geometry),
            "truck_json": self._json(record.truck),
            "excluded_countries_json": self._json(record.excluded_countries),
            "countries_traversed_json": self._json(record.countries_traversed),
        }

    def _row_to_record(self, row: dict[str, Any]) -> RouteHistoryRecord:
        return RouteHistoryRecord(
            stops=self._loads(row["stops_json"], []),
            geometry=self._decompress_json(row["geometry_compressed"]),
            total_distance_km=row["total_distance_km"],
            duration_min=row["duration_min"],
            truck_id=row["truck_id"],
            truck_label=row["truck_label"],
            truck=self._loads(row["truck_json"], {}),
            profile=row["profile"],
            excluded_countries=self._loads(row["excluded_countries_json"], []),
            countries_traversed=self._loads(row["countries_traversed_json"], []),
            metadata_version=row["metadata_version"],
        )

    def _row_to_list_item(self, row: dict[str, Any]) -> RouteHistoryListItem:
        stops = self._loads(row["stops_json"], [])
        return RouteHistoryListItem(
            id=row["id"],
            route_fingerprint=row["route_fingerprint"],
            created_at=row["created_at"],
            last_calculated_at=row["last_calculated_at"],
            calculation_count=row["calculation_count"],
            total_distance_km=row["total_distance_km"],
            duration_min=row["duration_min"],
            truck_id=row["truck_id"],
            truck_label=row["truck_label"],
            profile=row["profile"],
            origin=self._stop_label(stops[0]) if stops else "",
            destination=self._stop_label(stops[-1]) if stops else "",
            excluded_countries=self._loads(row.get("excluded_countries_json"), []),
            countries_traversed=self._loads(row.get("countries_traversed_json"), []),
            metadata_version=row["metadata_version"],
            archived_at=row.get("archived_at"),
        )

    @staticmethod
    def _row_total_cost(
        profit: dict[str, Any],
        fuel: dict[str, Any],
        toll: dict[str, Any],
    ) -> float | None:
        """Trip total cost (fuel + toll), not a 'savings' figure."""
        if profit.get("total_cost") is not None:
            try:
                return round(float(profit["total_cost"]), 2)
            except (TypeError, ValueError):
                pass
        fuel_part = float(fuel.get("fuel_cost") or 0)
        toll_part = float(toll.get("toll_cost") or 0)
        if fuel_part or toll_part:
            return round(fuel_part + toll_part, 2)
        return None

    def _stop_label(self, stop: dict[str, Any]) -> str:
        label = stop.get("address") or stop.get("label") or stop.get("value")
        if label:
            return str(label)
        lat = stop.get("lat")
        lon = stop.get("lon")
        if lat is not None and lon is not None:
            return f"{float(lat):.5f}, {float(lon):.5f}"
        return "Unknown"

    def _compress_json(self, value: Any) -> bytes:
        raw = self._json(value).encode("utf-8")
        return zlib.compress(raw, level=6)

    def _decompress_json(self, value: bytes | None) -> list[Any]:
        if not value:
            return []
        try:
            return json.loads(zlib.decompress(value).decode("utf-8"))
        except Exception:
            self.logger.exception("Failed to decompress route geometry")
            try:
                if isinstance(value, bytes):
                    text = value.decode("utf-8", errors="ignore")
                    recovered = json.loads(text)
                    return recovered if isinstance(recovered, list) else []
            except Exception:
                pass
            return []

    def _pdf_ready_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        route = payload["route"]
        return {
            "title": "Route Report",
            "sections": [
                {"heading": "Route", "rows": [
                    ["Origin", route["origin"]],
                    ["Destination", route["destination"]],
                    ["Distance", route["distance_km"]],
                    ["Duration", format_duration_minutes(route["duration_min"])],
                    ["Profile", payload["metadata"]["profile"]],
                ]},
            ],
        }

    def _csv_payload(self, payload: dict[str, Any]) -> str:
        rows = [
            ["route_id", payload["metadata"]["route_id"]],
            ["origin", payload["route"]["origin"]],
            ["destination", payload["route"]["destination"]],
            ["distance_km", payload["route"]["distance_km"]],
            ["duration", format_duration_minutes(payload["route"]["duration_min"])],
            ["profile", payload["metadata"]["profile"]],
        ]
        return "\n".join(",".join("" if v is None else str(v) for v in row) for row in rows)

    def _json(self, value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)

    def _loads(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except Exception:
            _logger.warning("Failed to parse JSON value: %.200s", value, exc_info=True)
            return default


class _RecentRouteCache:
    def __init__(self, max_size: int = 32) -> None:
        self.max_size = max_size
        self._items: dict[int, RouteHistoryRecord] = {}
        self._order: list[int] = []
        self._lock = threading.RLock()

    def get(self, key: int) -> RouteHistoryRecord | None:
        with self._lock:
            item = self._items.get(key)
            if item is not None and key in self._order:
                self._order.remove(key)
                self._order.append(key)
            return item

    def put(self, key: int, value: RouteHistoryRecord) -> None:
        with self._lock:
            self._items[key] = value
            if key in self._order:
                self._order.remove(key)
            self._order.append(key)
            while len(self._order) > self.max_size:
                old = self._order.pop(0)
                self._items.pop(old, None)


class RouteEventBus:
    _listeners: dict[str, list[Any]] = {}
    _lock = threading.RLock()

    @classmethod
    def subscribe(cls, event_type: str, callback) -> None:
        with cls._lock:
            cls._listeners.setdefault(event_type, []).append(callback)

    @classmethod
    def unsubscribe(cls, event_type: str, callback) -> None:
        with cls._lock:
            callbacks = cls._listeners.get(event_type, [])
            if callback in callbacks:
                callbacks.remove(callback)

    @classmethod
    def publish(cls, event_type: str, payload: dict[str, Any]) -> None:
        with cls._lock:
            callbacks = list(cls._listeners.get(event_type, [])) + list(cls._listeners.get("*", []))
        for callback in callbacks:
            with contextlib.suppress(Exception):
                callback(event_type, payload)


_RECENT_ROUTE_CACHE = _RecentRouteCache()
