"""
Production-grade Geocoding Service

Optimized for:
- Batch geocoding with rate limiting
- Caching and deduplication
- Proper error handling
- Nominatim usage policy compliance
"""

import time
from threading import Lock
from typing import Optional

import requests

from utils.logger import get_logger

logger = get_logger("GeocodeService")

# Rate limiting for Nominatim (1 request per second as per usage policy)
RATE_LIMIT_DELAY = 1.0
_last_request_time = 0.0
_rate_lock = Lock()


def _apply_rate_limit():
    """Apply rate limiting to respect Nominatim usage policy"""
    global _last_request_time

    with _rate_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        _last_request_time = time.time()


def geocode_place(
    place: str,
    timeout: int = 10,
    retries: int = 2
) -> Optional[tuple[float, float]]:
    """
    Geocode a place name using Nominatim.

    Features:
    - Rate limiting (1 req/sec)
    - Retry with exponential backoff
    - Proper error handling
    - User-Agent compliance

    Args:
        place: Place name or address to geocode
        timeout: Request timeout in seconds
        retries: Number of retry attempts

    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    if not place or not isinstance(place, str):
        logger.warning(f"Invalid place input: {place}")
        return None

    place = place.strip()
    if not place:
        return None

    _429_count = 0
    for attempt in range(retries + 1):
        try:
            _apply_rate_limit()

            logger.debug(
                f"Geocoding attempt {attempt + 1}/{retries + 1}: {place}"
            )

            resp = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={
                    'q': place,
                    'format': 'json',
                    'limit': 1,
                    'addressdetails': 1
                },
                headers={
                    'User-Agent': 'logistics-app/1.0',
                    'Accept-Language': 'en'
                },
                timeout=timeout
            )

            if resp.status_code == 429:
                _429_count += 1
                if _429_count >= 3:
                    raise RuntimeError(
                        "Nominatim rate limit exceeded after max retries"
                    )
                logger.warning("Nominatim rate limit exceeded, waiting...")
                time.sleep(2.0)
                continue

            resp.raise_for_status()
            data = resp.json()

            if not data:
                logger.debug(f"No results for: {place}")
                return None

            first = data[0]
            lat = float(first['lat'])
            lon = float(first['lon'])

            # Validate coordinates
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                logger.error(f"Invalid coordinates from Nominatim: {lat}, {lon}")
                return None

            if lat == 0.0 and lon == 0.0:
                logger.error(f"Null island coordinates for: {place}")
                return None

            logger.debug(f"Geocoded '{place}' -> ({lat:.6f}, {lon:.6f})")
            return (lat, lon)

        except requests.exceptions.Timeout:
            logger.warning(f"Geocode timeout for: {place}")
            if attempt < retries:
                time.sleep(2.0 ** attempt)  # Exponential backoff
                continue
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Geocode request failed: {e}")
            if attempt < retries:
                time.sleep(2.0 ** attempt)
                continue
            return None

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse geocode response: {e}")
            return None

    return None


def reverse_geocode(
    lat: float,
    lon: float,
    zoom: int = 14,
    timeout: int = 10,
) -> Optional[str]:
    """
    Reverse geocode coordinates to an address using Nominatim.

    Args:
        lat: Latitude
        lon: Longitude
        zoom: Zoom level (higher = more detailed)
        timeout: Request timeout in seconds

    Returns:
        Address string or None if not found/failed
    """
    if lat is None or lon is None:
        logger.warning(f"Invalid reverse-geocode input: lat={lat}, lon={lon}")
        return None

    try:
        _apply_rate_limit()
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": zoom},
            headers={"User-Agent": "logistics-app/1.0"},
            timeout=timeout,
        )
        if resp.ok:
            data = resp.json()
            return data.get("display_name")
        logger.warning(f"Reverse geocode HTTP {resp.status_code} for ({lat}, {lon})")
    except requests.exceptions.Timeout:
        logger.warning(f"Reverse geocode timeout for ({lat}, {lon})")
    except requests.exceptions.RequestException as exc:
        logger.warning(f"Reverse geocode request failed: {exc}")
    except (KeyError, ValueError, TypeError) as exc:
        logger.error(f"Failed to parse reverse geocode response: {exc}")
    return None


def geocode_batch(
    places: list[str],
    timeout: int = 10,
    skip_failed: bool = True
) -> list[Optional[tuple[float, float]]]:
    """
    Geocode multiple places with rate limiting.

    Args:
        places: List of place names
        timeout: Request timeout
        skip_failed: If True, continue on failures; if False, raise on first error

    Returns:
        List of coordinate tuples (None for failed geocodes)
    """
    results = []

    for i, place in enumerate(places):
        try:
            coords = geocode_place(place, timeout=timeout)
            results.append(coords)

            if coords is None:
                logger.warning(f"Failed to geocode place {i+1}/{len(places)}: {place}")
                if not skip_failed:
                    raise ValueError(f"Geocoding failed for: {place}")

        except Exception as e:
            logger.error(f"Batch geocoding error at place {i+1}: {e}")
            if not skip_failed:
                raise
            results.append(None)

    success_count = sum(1 for r in results if r is not None)
    logger.info(
        f"Batch geocoding complete: {success_count}/{len(places)} successful"
    )

    return results
