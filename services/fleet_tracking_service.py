"""Fleet tracking service — polls external GPS platforms via adapter pattern."""
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class VehiclePosition:
    """Standardized position object — same format regardless of platform."""
    device_id: str = ""
    name: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    speed_kmh: float = 0.0
    heading: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "offline"  # 'moving' | 'stopped' | 'idle' | 'offline'
    address: str = ""
    odometer_km: float = 0.0
    ignition_on: bool = False


# ── Base adapter ────────────────────────────────────────────────────

class BaseTrackingAdapter:
    def get_positions(self) -> List[VehiclePosition]:
        raise NotImplementedError

    def test_connection(self) -> tuple:
        """Returns (success: bool, message: str)"""
        raise NotImplementedError


# ── Wialon / GPS-Trace adapter ──────────────────────────────────────

class WialonAdapter(BaseTrackingAdapter):
    """Wialon Hosting / GPS-Trace API (Gurtam)."""

    def __init__(self, token: str,
                 host: str = "https://hst-api.wialon.com"):
        self.token = token
        self.host = host.rstrip("/")
        self._session_id = None

    def _login(self) -> bool:
        try:
            resp = requests.get(
                f"{self.host}/wialon/ajax.html",
                params={
                    "svc": "token/login",
                    "params": json.dumps({"token": self.token}),
                },
                timeout=10,
            )
            data = resp.json()
            if "eid" in data:
                self._session_id = data["eid"]
                return True
            return False
        except Exception as e:
            logger.warning("Wialon login failed: %s", e)
            return False

    def get_positions(self) -> List[VehiclePosition]:
        if not self._session_id:
            if not self._login():
                return []
        try:
            resp = requests.get(
                f"{self.host}/wialon/ajax.html",
                params={
                    "svc": "core/search_items",
                    "params": json.dumps({
                        "spec": {
                            "itemsType": "avl_unit",
                            "propName": "sys_name",
                            "propValueMask": "*",
                            "sortType": "sys_name",
                        },
                        "force": 1,
                        "flags": 1025,  # base + last message
                        "from": 0,
                        "to": 0,
                    }),
                    "sid": self._session_id,
                },
                timeout=10,
            )
            data = resp.json()
            if "error" in data:
                self._session_id = None
                return []

            positions = []
            for item in data.get("items", []):
                pos = item.get("pos", {})
                if not pos:
                    continue
                lm = item.get("lmsg", {})
                speed = pos.get("s", 0) or 0
                status = "moving" if speed > 3 else "stopped"
                ts = pos.get("t", 0)
                try:
                    timestamp = datetime.utcfromtimestamp(ts) if ts else datetime.utcnow()
                except Exception:
                    timestamp = datetime.utcnow()
                positions.append(VehiclePosition(
                    device_id=str(item.get("id", "")),
                    name=item.get("nm", "Unknown"),
                    latitude=pos.get("y", 0.0),
                    longitude=pos.get("x", 0.0),
                    speed_kmh=float(speed),
                    heading=pos.get("c", 0.0) or 0.0,
                    timestamp=timestamp,
                    status=status,
                    address=pos.get("a", ""),
                    odometer_km=float(
                        lm.get("p", {}).get("mileage", 0) or 0
                    ) / 1000.0,
                    ignition_on=(speed > 0),
                ))
            return positions
        except Exception as e:
            logger.error("Wialon get_positions failed: %s", e)
            return []

    def test_connection(self) -> tuple:
        try:
            ok = self._login()
            if ok:
                pos = self.get_positions()
                return True, f"Connected — {len(pos)} vehicle(s) found"
            return False, "Login failed — check your token"
        except Exception as e:
            return False, f"Connection error: {e}"


# ── Frotcom adapter ─────────────────────────────────────────────────

class FrotcomAdapter(BaseTrackingAdapter):
    """Frotcom Fleet Management API."""

    def __init__(self, username: str, password: str,
                 account: str = ""):
        self.base = "https://api.frotcom.com/api/"
        self.auth = (username, password)
        self.account = account

    def get_positions(self) -> List[VehiclePosition]:
        try:
            resp = requests.get(
                f"{self.base}vehicles/positions",
                auth=self.auth,
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            vehicles = resp.json()
            if isinstance(vehicles, dict):
                vehicles = vehicles.get("vehicles", [])
            positions = []
            for v in vehicles:
                lat = v.get("latitude") or v.get("lat")
                lng = v.get("longitude") or v.get("lng")
                if not lat or not lng:
                    continue
                speed = float(v.get("speed", 0) or 0)
                positions.append(VehiclePosition(
                    device_id=str(v.get("id", "")),
                    name=v.get("plate", v.get("name", "Unknown")),
                    latitude=float(lat),
                    longitude=float(lng),
                    speed_kmh=speed,
                    heading=float(v.get("heading", 0) or 0),
                    timestamp=datetime.utcnow(),
                    status="moving" if speed > 3 else "stopped",
                    address=v.get("address", ""),
                    odometer_km=float(v.get("mileage", 0) or 0),
                    ignition_on=v.get("ignitionOn", speed > 0),
                ))
            return positions
        except Exception as e:
            logger.error("Frotcom API error: %s", e)
            return []

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f"{self.base}vehicles",
                auth=self.auth, timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                count = len(data) if isinstance(data, list) else len(
                    data.get("vehicles", [])
                )
                return True, f"Connected — {count} vehicle(s)"
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, str(e)


# ── Traccar adapter ─────────────────────────────────────────────────

class TraccarAdapter(BaseTrackingAdapter):
    def __init__(self, url: str, email: str, password: str):
        self.base = url.rstrip("/") + "/api/"
        self.auth = (email, password)

    def get_positions(self) -> List[VehiclePosition]:
        try:
            resp = requests.get(
                f"{self.base}positions",
                auth=self.auth, timeout=10
            )
            positions = []
            for p in resp.json():
                speed = float(p.get("speed", 0) or 0) * 1.852
                fix_time = p.get("fixTime", "")
                try:
                    timestamp = datetime.fromisoformat(
                        fix_time.replace("Z", "+00:00")
                    )
                except Exception:
                    timestamp = datetime.utcnow()
                positions.append(VehiclePosition(
                    device_id=str(p.get("deviceId", "")),
                    name=p.get("deviceName", str(p.get("deviceId", ""))),
                    latitude=float(p.get("latitude", 0)),
                    longitude=float(p.get("longitude", 0)),
                    speed_kmh=speed,
                    heading=float(p.get("course", 0) or 0),
                    timestamp=timestamp,
                    status="moving" if speed > 3 else "stopped",
                    address=p.get("address", ""),
                    odometer_km=float(
                        p.get("attributes", {}).get("totalDistance", 0)
                    ) / 1000.0,
                    ignition_on=p.get("attributes", {}).get(
                        "ignition", speed > 0
                    ),
                ))
            return positions
        except Exception as e:
            logger.error("Traccar error: %s", e)
            return []

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f"{self.base}devices",
                auth=self.auth, timeout=10
            )
            if resp.status_code == 200:
                return True, f"Connected — {len(resp.json())} device(s)"
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)


# ── Navixy adapter ──────────────────────────────────────────────────

class NavixyAdapter(BaseTrackingAdapter):
    def __init__(self, api_key: str,
                 host: str = "https://api.eu.navixy.com/v2"):
        self.api_key = api_key
        self.base = host.rstrip("/")

    def get_positions(self) -> List[VehiclePosition]:
        try:
            resp = requests.get(
                f"{self.base}/tracker/list",
                params={"hash": self.api_key},
                timeout=10,
            )
            data = resp.json()
            trackers = data.get("list", []) if isinstance(data, dict) else []
            positions = []
            for t in trackers:
                lat = t.get("lat")
                lng = t.get("lng")
                if lat is None or lng is None:
                    continue
                speed = float(t.get("speed", 0) or 0)
                positions.append(VehiclePosition(
                    device_id=str(t.get("id", "")),
                    name=t.get("label", t.get("name", "Unknown")),
                    latitude=float(lat),
                    longitude=float(lng),
                    speed_kmh=speed,
                    heading=float(t.get("heading", 0) or 0),
                    timestamp=datetime.utcnow(),
                    status="moving" if speed > 3 else "stopped",
                    address=t.get("address", ""),
                    odometer_km=float(t.get("mileage", 0) or 0),
                    ignition_on=t.get("ignition", speed > 0),
                ))
            return positions
        except Exception as e:
            logger.error("Navixy error: %s", e)
            return []

    def test_connection(self) -> tuple:
        try:
            resp = requests.get(
                f"{self.base}/tracker/list",
                params={"hash": self.api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("list", [])) if isinstance(data, dict) else 0
                return True, f"Connected — {count} tracker(s)"
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, str(e)


# ── Generic REST adapter ───────────────────────────────────────────

class GenericRestAdapter(BaseTrackingAdapter):
    def __init__(self, url: str, auth_header: str = "",
                 positions_path: str = "data.vehicles",
                 lat_field: str = "lat",
                 lng_field: str = "lng",
                 id_field: str = "id"):
        self.url = url
        self.auth_header = auth_header
        self.positions_path = positions_path
        self.lat_field = lat_field
        self.lng_field = lng_field
        self.id_field = id_field

    def _resolve_path(self, data: dict, path: str):
        parts = path.split(".")
        v = data
        for p in parts:
            if isinstance(v, dict):
                v = v.get(p)
            else:
                return None
        return v

    def get_positions(self) -> List[VehiclePosition]:
        if not self.url:
            logger.warning("Generic REST adapter: no URL configured")
            return []
        try:
            headers = {}
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            resp = requests.get(self.url, headers=headers, timeout=10)
            data = resp.json()
            vehicles = self._resolve_path(data, self.positions_path)
            if vehicles is None:
                vehicles = data if isinstance(data, list) else []
            positions = []
            for v in vehicles:
                lat = v.get(self.lat_field)
                lng = v.get(self.lng_field)
                if lat is None or lng is None:
                    continue
                speed = float(v.get("speed", 0) or 0)
                positions.append(VehiclePosition(
                    device_id=str(v.get(self.id_field, "")),
                    name=v.get("name", v.get("plate", "Unknown")),
                    latitude=float(lat),
                    longitude=float(lng),
                    speed_kmh=speed,
                    heading=float(v.get("heading", 0) or 0),
                    timestamp=datetime.utcnow(),
                    status="moving" if speed > 3 else "stopped",
                    address=v.get("address", ""),
                    odometer_km=float(v.get("mileage", 0) or 0),
                    ignition_on=v.get("ignition", speed > 0),
                ))
            return positions
        except Exception as e:
            logger.error("Generic REST adapter error: %s", e)
            return []

    def test_connection(self) -> tuple:
        try:
            headers = {}
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            resp = requests.get(self.url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                vehicles = self._resolve_path(data, self.positions_path)
                if vehicles is None:
                    vehicles = data if isinstance(data, list) else []
                return True, f"Connected — {len(vehicles)} vehicle(s)"
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, str(e)


# ── Fleet Tracking Service ──────────────────────────────────────────

class FleetTrackingService:
    """Singleton-style service that manages the active tracking adapter."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._adapter: Optional[BaseTrackingAdapter] = None
        self._last_positions: List[VehiclePosition] = []
        self._last_poll: Optional[datetime] = None
        self._poll_interval = 30  # seconds
        self._polling = False
        self._poll_timer = None
        self._db = None

    def initialize(self, db=None):
        """Call on app startup — loads adapter from settings."""
        self._db = db
        if not db:
            logger.warning("FleetTrackingService initialized without DB")
            return
        platform = db.get_setting("tracking.platform") or ""
        self._adapter = self._create_adapter(platform)
        if self._adapter:
            logger.info("Fleet tracking initialized: %s", platform)
        else:
            logger.debug("Fleet tracking not configured")

    def _create_adapter(self, platform: str) -> Optional[BaseTrackingAdapter]:
        if not platform or platform.lower() == "not configured":
            return None
        p = platform.lower()
        if not self._db:
            return None
        db = self._db
        if "wialon" in p or "gps-trace" in p or "gurtam" in p:
            return WialonAdapter(
                token=db.get_setting("tracking.token") or "",
                host=db.get_setting("tracking.host") or "https://hst-api.wialon.com",
            )
        elif "frotcom" in p:
            return FrotcomAdapter(
                username=db.get_setting("tracking.username") or "",
                password=db.get_setting("tracking.password") or "",
                account=db.get_setting("tracking.account") or "",
            )
        elif "traccar" in p:
            return TraccarAdapter(
                url=db.get_setting("tracking.host") or "",
                email=db.get_setting("tracking.username") or "",
                password=db.get_setting("tracking.password") or "",
            )
        elif "navixy" in p:
            return NavixyAdapter(
                api_key=db.get_setting("tracking.token") or "",
                host=db.get_setting("tracking.host") or "https://api.eu.navixy.com/v2",
            )
        elif "generic" in p or "rest" in p:
            return GenericRestAdapter(
                url=db.get_setting("tracking.host") or "",
                auth_header=db.get_setting("tracking.token") or "",
                positions_path=db.get_setting("tracking.positions_path") or "data.vehicles",
                lat_field=db.get_setting("tracking.lat_field") or "lat",
                lng_field=db.get_setting("tracking.lng_field") or "lng",
                id_field=db.get_setting("tracking.id_field") or "id",
            )
        return None

    def get_positions(self, force_refresh: bool = False) -> List[VehiclePosition]:
        if not self._adapter:
            return []
        now = datetime.utcnow()
        needs_refresh = (
            force_refresh
            or not self._last_poll
            or (now - self._last_poll).total_seconds() > self._poll_interval
        )
        if needs_refresh:
            try:
                self._last_positions = self._adapter.get_positions()
                self._last_poll = now
            except Exception as e:
                logger.error("Tracking poll failed: %s", e)
        return self._last_positions

    def test_connection(self) -> tuple:
        if not self._adapter:
            return False, "No platform configured"
        return self._adapter.test_connection()

    def is_configured(self) -> bool:
        return self._adapter is not None

    def match_to_truck(self, position: VehiclePosition) -> Optional[int]:
        """Try to match a VehiclePosition to a truck in the database."""
        if not self._db:
            return None
        try:
            from repositories.fleet_repository import FleetRepository
            fleet_repo = FleetRepository(self._db)
            truck = fleet_repo.get_by_plate(position.name)
            if truck:
                return truck.get("id")
            truck = fleet_repo.get_by_tracking_device_id(position.device_id)
            if truck:
                return truck.get("id")
        except Exception as e:
            logger.debug("match_to_truck failed: %s", e)
        return None

    def start_polling(self, callback=None):
        """Start background polling every poll_interval seconds."""
        self._polling = True
        self._poll(callback)

    def stop_polling(self):
        self._polling = False
        if self._poll_timer:
            self._poll_timer.cancel()
            self._poll_timer = None

    def _poll(self, callback):
        if not self._polling:
            return
        try:
            positions = self.get_positions(force_refresh=True)
            if callback:
                callback(positions)
        except Exception as e:
            logger.warning("Tracking poll callback error: %s", e)
        self._poll_timer = threading.Timer(self._poll_interval, self._poll, args=(callback,))
        self._poll_timer.daemon = True
        self._poll_timer.start()


# Global singleton
fleet_tracking_service = FleetTrackingService()
