"""Fleet tracking service — polls external GPS platforms via adapter pattern."""
from __future__ import annotations

import json
import logging
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests

from services.encryption_service import decrypt_value

logger = logging.getLogger(__name__)

# ── Poll backoff (F5 resilience) ────────────────────────────────────────
# On consecutive empty/failed polls the background loop backs off: base wait
# is the configured poll interval (default 30s), doubled each failure up to
# 10 minutes, plus up to 5s of random jitter to avoid stampeding a
# recovering partner when the fleet comes back online.
POLL_BACKOFF_MAX_SECONDS = 600  # 10 minutes
POLL_JITTER_MAX_SECONDS = 5.0


def _decrypt_tracking_credential(value: Optional[str]) -> str:
    """Decrypt a stored tracking-provider credential read from the settings table.

    Mirrors how ``smtp_password`` is handled by ``PreferencesManager``:
    values are encrypted on write and transparently decrypted on read.

    Backward-compatible fallback: legacy plaintext values (stored before
    encryption existed) and values written while ``OPERION_ENCRYPTION_KEY``
    was unset pass through unchanged — ``decrypt_value`` returns the raw
    value when it does not look like Fernet ciphertext or no key is set.
    """
    if value:
        value = decrypt_value(value)
    return value or ""


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
    driver_id: int = 0       # populated by caller via driver→vehicle mapping


# ── Base adapter ────────────────────────────────────────────────────

class BaseTrackingAdapter:
    def get_positions(self) -> list[VehiclePosition]:
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

    def get_positions(self) -> list[VehiclePosition]:
        if not self._session_id and not self._login():
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
            if resp.status_code != 200:
                logger.warning("Wialon get_positions: HTTP %d", resp.status_code)
                return []
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

    def get_positions(self) -> list[VehiclePosition]:
        try:
            resp = requests.get(
                f"{self.base}vehicles/positions",
                auth=self.auth,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Frotcom get_positions: HTTP %d", resp.status_code)
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

    def get_positions(self) -> list[VehiclePosition]:
        try:
            resp = requests.get(
                f"{self.base}positions",
                auth=self.auth, timeout=10
            )
            if resp.status_code != 200:
                logger.warning("Traccar get_positions: HTTP %d", resp.status_code)
                return []
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

    def get_positions(self) -> list[VehiclePosition]:
        try:
            resp = requests.get(
                f"{self.base}/tracker/list",
                params={"hash": self.api_key},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Navixy get_positions: HTTP %d", resp.status_code)
                return []
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

    def get_positions(self) -> list[VehiclePosition]:
        if not self.url:
            logger.warning("Generic REST adapter: no URL configured")
            return []
        try:
            headers = {}
            if self.auth_header:
                headers["Authorization"] = self.auth_header
            resp = requests.get(self.url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning(
                    "Generic REST get_positions: HTTP %d", resp.status_code,
                )
                return []
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
        self._last_positions: list[VehiclePosition] = []
        self._last_poll: Optional[datetime] = None
        self._poll_interval = 30  # seconds
        self._polling = False
        self._poll_timer = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._db = None
        self._fleet_repo = None
        self._config: dict = {}

    def initialize(self, db=None, api_client=None, config=None):
        """Call on app startup — loads adapter from settings.

        Local mode (``db`` provided): reads the ``tracking.*`` settings from
        the settings table exactly as before (unchanged behaviour).

        Remote mode (``db is None``): when ``api_client`` (or an explicit
        ``config`` dict) is provided, reads the tracking config from the API
        and configures the adapter without touching a local database.  If no
        platform/tokens are present, ``is_configured()`` stays ``False`` so
        callers see the graceful "not configured" state.
        """
        self._db = db
        if db:
            platform = db.get_setting("tracking.platform") or ""
            self._adapter = self._create_adapter(platform)
            if self._adapter:
                logger.info("Fleet tracking initialized: %s", platform)
            else:
                logger.debug("Fleet tracking not configured")
            return
        if api_client is None and config is None:
            logger.warning("FleetTrackingService initialized without DB or API client")
            return
        if config is None:
            config = self._fetch_remote_config(api_client)
        self._config = config if isinstance(config, dict) else {}
        try:
            interval = int(self._config.get("interval_seconds", 30) or 30)
            if interval >= 5:
                self._poll_interval = interval
        except (TypeError, ValueError):
            pass
        self._adapter = self._create_adapter_from_config(self._config)
        if self._adapter:
            logger.info(
                "Fleet tracking initialized (remote): %s",
                self._config.get("platform", ""),
            )
        else:
            logger.debug("Fleet tracking not configured")

    def _fetch_remote_config(self, api_client) -> dict:
        """Read the tracking config dict from the API client (remote mode)."""
        try:
            from client.remote_tracking_config import RemoteTrackingConfig
            config = RemoteTrackingConfig(api_client).get_config()
        except Exception as e:
            logger.warning("Failed to load remote tracking config: %s", e)
            return {}
        return config if isinstance(config, dict) else {}

    # ------------------------------------------------------------------
    # Background polling
    # ------------------------------------------------------------------

    def start_polling(self, interval_seconds: int = 30) -> None:
        """Start background GPS polling in a daemon thread.

        Polls the configured tracking adapter every *interval_seconds*
        and updates the internal position cache.  The polling loop
        respects a ``threading.Event`` for clean shutdown via
        :meth:`stop_polling`.

        Args:
            interval_seconds: Seconds between polls (default 30).
        """
        if self._polling:
            logger.warning("Polling already running")
            return
        self._poll_interval = interval_seconds
        self._polling = True
        self._stop_event.clear()

        def _poll_loop():
            logger.info(
                "Background polling started (interval=%ds)", self._poll_interval,
            )
            consecutive_failures = 0
            while not self._stop_event.is_set():
                positions = self.get_positions(force_refresh=True)
                if positions:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                wait = self._compute_poll_wait(
                    self._poll_interval, consecutive_failures,
                )
                # ``_stop_event.wait`` stays interruptible by ``stop_polling``.
                self._stop_event.wait(wait)

        self._poll_thread = threading.Thread(target=_poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self, timeout: Optional[float] = None) -> None:
        """Stop background GPS polling and wait for the thread to finish.

        Args:
            timeout: Optional seconds to wait for the poll thread to exit.
                     ``None`` means wait indefinitely.
        """
        self._polling = False
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=timeout)
            self._poll_thread = None
        logger.info("Background polling stopped")

    @staticmethod
    def _compute_poll_wait(interval_seconds: float, consecutive_failures: int) -> float:
        """Exponential backoff + jitter for the background polling loop.

        Base wait is the configured poll interval (default 30s); it doubles
        on every consecutive empty/failed poll up to ``POLL_BACKOFF_MAX_SECONDS``
        (10 minutes) and a ``random.uniform(0, POLL_JITTER_MAX_SECONDS)``
        jitter is added so a recovering partner is not stampeded by all
        tenants polling simultaneously.  A success resets to the base
        interval (``consecutive_failures=0``).
        """
        if consecutive_failures <= 0:
            return interval_seconds
        backoff = min(
            interval_seconds * (2 ** (consecutive_failures - 1)),
            POLL_BACKOFF_MAX_SECONDS,
        )
        return backoff + random.uniform(0, POLL_JITTER_MAX_SECONDS)

    def _create_adapter(self, platform: str) -> Optional[BaseTrackingAdapter]:
        if not platform or platform.lower() == "not configured":
            return None
        p = platform.lower()
        if not self._db:
            return None
        db = self._db
        if "wialon" in p or "gps-trace" in p or "gurtam" in p:
            return WialonAdapter(
                token=_decrypt_tracking_credential(db.get_setting("tracking.token")),
                host=db.get_setting("tracking.host") or "https://hst-api.wialon.com",
            )
        elif "frotcom" in p:
            return FrotcomAdapter(
                username=_decrypt_tracking_credential(db.get_setting("tracking.username")),
                password=_decrypt_tracking_credential(db.get_setting("tracking.password")),
                account=_decrypt_tracking_credential(db.get_setting("tracking.account")),
            )
        elif "traccar" in p:
            return TraccarAdapter(
                url=db.get_setting("tracking.host") or "",
                email=_decrypt_tracking_credential(db.get_setting("tracking.username")),
                password=_decrypt_tracking_credential(db.get_setting("tracking.password")),
            )
        elif "navixy" in p:
            return NavixyAdapter(
                api_key=_decrypt_tracking_credential(db.get_setting("tracking.token")),
                host=db.get_setting("tracking.host") or "https://api.eu.navixy.com/v2",
            )
        elif "generic" in p or "rest" in p:
            return GenericRestAdapter(
                url=db.get_setting("tracking.host") or "",
                auth_header=_decrypt_tracking_credential(db.get_setting("tracking.token")),
                positions_path=db.get_setting("tracking.positions_path") or "data.vehicles",
                lat_field=db.get_setting("tracking.lat_field") or "lat",
                lng_field=db.get_setting("tracking.lng_field") or "lng",
                id_field=db.get_setting("tracking.id_field") or "id",
            )
        return None

    def _create_adapter_from_config(self, config) -> Optional[BaseTrackingAdapter]:
        """Build the tracking adapter from an API tracking-config dict.

        Mirrors :meth:`_create_adapter` but reads from a config dict (remote
        mode) instead of the local DB settings table.  Credentials returned by
        the API are already decrypted; ``_decrypt_tracking_credential`` is
        still applied defensively so legacy/encrypted values pass through
        unchanged either way.
        """
        if not isinstance(config, dict):
            return None
        platform = (config.get("platform") or "").strip()
        if not platform or platform.lower() == "not configured":
            return None
        tokens = config.get("tokens") or {}
        if not isinstance(tokens, dict):
            tokens = {}
        p = platform.lower()

        def tok(key: str, default: str = "") -> str:
            return _decrypt_tracking_credential(tokens.get(key) or default)

        if "wialon" in p or "gps-trace" in p or "gurtam" in p:
            return WialonAdapter(
                token=tok("token"),
                host=tokens.get("host") or "https://hst-api.wialon.com",
            )
        elif "frotcom" in p:
            return FrotcomAdapter(
                username=tok("username"),
                password=tok("password"),
                account=tok("account"),
            )
        elif "traccar" in p:
            return TraccarAdapter(
                url=tokens.get("host") or "",
                email=tok("username"),
                password=tok("password"),
            )
        elif "navixy" in p:
            return NavixyAdapter(
                api_key=tok("token"),
                host=tokens.get("host") or "https://api.eu.navixy.com/v2",
            )
        elif "generic" in p or "rest" in p:
            return GenericRestAdapter(
                url=tokens.get("host") or "",
                auth_header=tok("token"),
                positions_path=tokens.get("positions_path") or "data.vehicles",
                lat_field=tokens.get("lat_field") or "lat",
                lng_field=tokens.get("lng_field") or "lng",
                id_field=tokens.get("id_field") or "id",
            )
        return None

    def get_positions(self, force_refresh: bool = False, driver_id: int | None = None) -> list[VehiclePosition]:
        """Return cached (or freshly polled) vehicle positions.

        When ``driver_id`` is provided, positions are filtered to only
        include the vehicle assigned to that driver (driver scoping for
        the mobile app).  The driver's vehicle is determined by looking
        up the driver → truck assignment in the database.
        """
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
                with self._lock:
                    self._last_positions = self._adapter.get_positions()
                    self._last_poll = now
            except Exception as e:
                logger.error("Tracking poll failed: %s", e)
        with self._lock:
            positions = list(self._last_positions)

        # ── Driver scoping: filter to only the driver's assigned vehicle ──
        if driver_id is not None and self._db:
            try:
                from repositories.driver_repository import DriverRepository
                driver_repo = DriverRepository(self._db)
                driver = driver_repo.get_by_id(driver_id)
                if driver and driver.get("truck_id"):
                    from repositories.fleet_repository import FleetRepository
                    fleet_repo = FleetRepository(self._db)
                    truck = fleet_repo.get_by_id(driver["truck_id"])
                    if truck:
                        # Match by plate number (position.name is the vehicle plate/name)
                        truck_plate = truck.get("plate_number", "").lower()
                        if truck_plate:
                            positions = [p for p in positions if p.name.lower() == truck_plate]
                        else:
                            # Fallback: match by device_id if no plate
                            tracking_id = truck.get("tracking_device_id", "")
                            if tracking_id:
                                positions = [p for p in positions if p.device_id == tracking_id]
                            else:
                                positions = []  # Can't match — return nothing
                    else:
                        positions = []  # Truck not found — return nothing
                else:
                    positions = []  # Driver has no truck assigned — return nothing
            except Exception as e:
                logger.warning("Driver scoping lookup failed: %s — returning unfiltered", e)

        return positions

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
            if self._fleet_repo is None:
                from repositories.fleet_repository import FleetRepository
                self._fleet_repo = FleetRepository(self._db)
            truck = self._fleet_repo.get_by_plate(position.name)
            if truck:
                return truck.get("id")
            truck = self._fleet_repo.get_by_tracking_device_id(position.device_id)
            if truck:
                return truck.get("id")
        except Exception as e:
            logger.debug("match_to_truck failed: %s", e)
        return None

# Global singleton
fleet_tracking_service = FleetTrackingService()
