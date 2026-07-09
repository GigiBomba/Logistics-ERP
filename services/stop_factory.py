import threading
import uuid
from typing import Optional

import requests

from config import Config
from services.geocode_nominatim import geocode_place

NOMINATIM_REVERSE_URL = f"{Config.NOMINATIM_URL}/reverse"


def _new_id() -> str:
    return uuid.uuid4().hex


def normalize_existing_stop(data: dict) -> dict:
    """Normalize an existing stop-like dict or tuple into the unified stop model."""
    # Accept tuples (lat, lon)
    if isinstance(data, (list, tuple)) and len(data) >= 2:
        lat = float(data[0])
        lon = float(data[1])
        return {
            'id': _new_id(),
            'type': 'stop',
            'lat': lat,
            'lon': lon,
            'address': None,
            'source': 'map_click',
            'resolved': True
        }

    if not isinstance(data, dict):
        # fallback empty start
        return {
            'id': _new_id(),
            'type': 'stop',
            'lat': None,
            'lon': None,
            'address': None,
            'source': 'manual',
            'resolved': False
        }

    # Build normalized dict
    sid = data.get('id') or _new_id()
    stype = data.get('type') or data.get('kind') or 'stop'
    lat = data.get('lat') if 'lat' in data else (data.get('coords')[0] if data.get('coords') else None)
    lon = data.get('lon') if 'lon' in data else (data.get('coords')[1] if data.get('coords') else None)
    address = data.get('address') if 'address' in data else (data.get('addr') if 'addr' in data else None)
    source = data.get('source') or ('map_click' if lat and lon and address is None else 'manual')
    resolved = bool(lat is not None and lon is not None)

    return {
        'id': sid,
        'type': stype,
        'lat': float(lat) if lat is not None else None,
        'lon': float(lon) if lon is not None else None,
        'address': address,
        'source': source,
        'resolved': resolved
    }


def create_stop_from_map_click(lat: float, lon: float, reverse_callback: Optional[callable] = None) -> dict:
    """Create a normalized stop object from map click coordinates.
    If reverse_callback provided, it will be called asynchronously as reverse_callback(stop_id, address)
    """
    stop = {
        'id': _new_id(),
        'type': 'stop',
        'lat': float(lat),
        'lon': float(lon),
        'address': None,
        'source': 'map_click',
        'resolved': True
    }

    if reverse_callback:
        # Do reverse geocoding in background.
        # Daemon thread lifecycle: created per map click, runs ~2-6s, terminates
        # naturally after the HTTP request completes. Daemon flag ensures the
        # thread does not block app shutdown if it is still in-flight.
        def rev_task(sid, lt, ln):
            try:
                params = {'lat': lt, 'lon': ln, 'format': 'json'}
                headers = {'User-Agent': 'logistics-app'}
                r = requests.get(NOMINATIM_REVERSE_URL, params=params, headers=headers, timeout=6)
                r.raise_for_status()
                data = r.json()
                addr = data.get('display_name')
                # ⚠️ THREAD-SAFETY WARNING: reverse_callback runs in a daemon thread.
                # If the callback touches Qt widgets (or any GUI primitives), this will
                # violate thread affinity and may cause segfaults or undefined behaviour.
                # Marshal to the GUI thread instead, e.g. via QMetaObject.invokeMethod,
                # QTimer.singleShot(0, ...) from the main thread, or root.after(0, ...).
                reverse_callback(sid, addr)
            except Exception:
                reverse_callback(sid, None)
        threading.Thread(target=rev_task, args=(stop['id'], stop['lat'], stop['lon']), daemon=True).start()

    return stop


def create_stop_from_address(address: str) -> dict:
    """Geocode an address and return a normalized stop object. Uses services.geocode_nominatim.geocode_place.
    If geocoding fails, returned stop will have resolved=False and lat/lon None.
    """
    try:
        coords = geocode_place(address)
        if coords:
            lat, lon = coords
            return {
                'id': _new_id(),
                'type': 'stop',
                'lat': float(lat),
                'lon': float(lon),
                'address': address,
                'source': 'geocode',
                'resolved': True
            }
        else:
            return {
                'id': _new_id(),
                'type': 'stop',
                'lat': None,
                'lon': None,
                'address': address,
                'source': 'geocode',
                'resolved': False
            }
    except Exception:
        return {
            'id': _new_id(),
            'type': 'stop',
            'lat': None,
            'lon': None,
            'address': address,
            'source': 'geocode',
            'resolved': False
        }

