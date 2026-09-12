"""Shared date-parsing helpers for trip scheduling and invoicing.

The trip conflict service and the invoice service each carried their own
private ``_parse_date`` implementation; this module is the single shared
home for that logic so both keep identical parsing semantics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def parse_trip_date(date_str) -> Optional[datetime]:
    """Parse a trip date/datetime in ISO-8601 or DD/MM/YYYY form.

    Production ``start_date`` / ``end_date`` values are ISO-8601
    (``YYYY-MM-DD``, sometimes with a time component) while older
    records and some dialogs still pass ``DD/MM/YYYY``.  ISO formats are
    tried first (full string, so time components are kept); the legacy
    ``DD/MM/YYYY`` branch keeps the original slice-[:10] behaviour so
    trailing time text is tolerated.  Unparseable input returns ``None``.
    """
    if not date_str:
        return None
    raw = str(date_str).strip()
    if not raw:
        return None
    iso_with_t = raw[:-1] if raw.endswith("Z") else raw
    for candidate, fmt in (
        (iso_with_t, "%Y-%m-%dT%H:%M:%S"),
        (raw, "%Y-%m-%d %H:%M:%S"),
        (raw, "%Y-%m-%d %H:%M"),
        (raw, "%Y-%m-%d"),
        (raw[:10], "%d/%m/%Y"),
    ):
        try:
            return datetime.strptime(candidate, fmt)
        except (ValueError, TypeError):
            continue
    return None