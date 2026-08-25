from __future__ import annotations

# services/route_decoder.py
# Polyline decoder for GraphHopper route geometry


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """
    Decode Google's Encoded Polyline Algorithm.

    GraphHopper returns route geometry as an encoded polyline string.
    This function decodes it into a list of (lat, lon) tuples.

    Args:
        encoded: Encoded polyline string
        precision: Decimal precision (default 5 for GraphHopper)

    Returns:
        List of (latitude, longitude) tuples
    """
    if not encoded:
        return []

    coordinates = []
    index = 0
    lat = 0
    lng = 0

    try:
        while index < len(encoded):
            # Decode latitude
            shift = 0
            result = 0

            while True:
                if index >= len(encoded):
                    raise ValueError(f"Truncated polyline at position {index} (while decoding latitude)")
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5

                if byte < 0x20:
                    break

            # Convert to signed
            dlat = ~(result >> 1) if result & 1 else result >> 1
            lat += dlat

            # Decode longitude
            shift = 0
            result = 0

            while True:
                if index >= len(encoded):
                    raise ValueError(f"Truncated polyline at position {index} (while decoding longitude)")
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5

                if byte < 0x20:
                    break

            # Convert to signed
            dlng = ~(result >> 1) if result & 1 else result >> 1
            lng += dlng

            # Convert to actual coordinates
            latitude = lat / (10 ** precision)
            longitude = lng / (10 ** precision)

            coordinates.append((latitude, longitude))
    except (IndexError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid encoded polyline string at position {index}: {exc}") from exc

    return coordinates
