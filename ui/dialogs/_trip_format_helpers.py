"""Shared trip-row formatting helpers for the trip dialogs.

Extracted from ``ui/dialogs/trip_search_dialog.py`` and
``ui/dialogs/trip_picker_dialog.py`` (previously two near-duplicate
``_format_trip`` helpers).  The two callers differ in two edge-case
behaviours — a truck-number fallback and which date field is shown — so
the single function is parameterized and each dialog binds its own
variant via ``functools.partial`` (see the module-level ``_format_trip``
in each dialog module).  Rendered rows stay byte-identical.
"""

from __future__ import annotations

from typing import Any


def _format_trip(
    t: dict[str, Any],
    *,
    include_truck_number: bool = False,
    date_key: str = "start_date",
    date_slice: int | None = 10,
) -> tuple:
    """Return ``(primary_label, sublabel)`` for a trip row.

    Parameters
    ----------
    include_truck_number:
        Fall back to ``truck_number`` when ``truck_plate`` is empty
        (used by the search dialog; the picker only shows ``truck_plate``).
    date_key:
        Trip field appended as the trailing date (``start_date`` for the
        search dialog, ``departure_date`` for the picker).
    date_slice:
        How many characters of the date to keep (``None`` keeps the full
        value).  The search dialog shows ``YYYY-MM-DD`` (first 10 chars).
    """
    tid = t.get("id", "?")
    origin = t.get("origin") or t.get("origin_city") or ""
    destination = t.get("destination") or t.get("destination_city") or ""
    primary = f"#{tid}  {origin} → {destination}" if origin and destination else f"#{tid}"
    sub_bits: list[str] = []
    plate = t.get("truck_plate")
    if not plate and include_truck_number:
        plate = t.get("truck_number")
    if plate:
        sub_bits.append(str(plate))
    if t.get("driver_name"):
        sub_bits.append(str(t["driver_name"]))
    if t.get("client_name"):
        sub_bits.append(str(t["client_name"]))
    if t.get("status"):
        sub_bits.append(str(t["status"]))
    date_val = t.get(date_key)
    if date_val:
        date_str = str(date_val)
        if date_slice is not None:
            date_str = date_str[:date_slice]
        sub_bits.append(date_str)
    return primary, "  •  ".join(sub_bits)