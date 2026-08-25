"""Verify the document/export color tokenization produces identical output.

Generates a sample dispatch-board PDF via ExportService.generate_dispatch_board_pdf
covering all 5 statuses, then checks the PDF content streams contain the expected
status colors. reportlab compresses content streams (FlateDecode) and formats
colors as "%.4g" floats, so we decompress each stream and match that format.

The token values are byte-identical to the original hex, so this confirms the
refactor is a pure token consolidation with no visual change.

Usage:
    python tools/verify_doc_colors.py
"""
from __future__ import annotations

import base64
import os
import re
import sys
import tempfile
import zlib

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from services.export_service import ExportService

# Status color -> RGB (0..1) as reportlab would write it (%.4g floats).
STATUS_RGB = {
    "Planned":    (28 / 255, 25 / 255, 23 / 255),   # #1c1917
    "Loading":    (52 / 255, 26 / 255, 0 / 255),    # #341a00
    "In Transit": (15 / 255, 31 / 255, 74 / 255),   # #0f1f4a
    "Delivered":  (5 / 255, 46 / 255, 22 / 255),    # #052e16
    "Cancelled":  (26 / 255, 26 / 255, 32 / 255),   # #1A1A20
}


def _fmt(v: float) -> str:
    """reportlab writes colors as %.6f, then strips the leading zero and
    trailing zeros (e.g. 0.125490 -> .12549, 0 -> 0)."""
    s = f"{v:.6f}"
    if s == "0.000000":
        return "0"
    s = s.lstrip("0")
    s = s.rstrip("0")
    if s.endswith("."):
        s = s[:-1]
    return s


def _content_streams(data: bytes) -> list[bytes]:
    """Extract and decode all PDF content streams.

    reportlab writes content streams with ``/Filter [ /ASCII85Decode
    /FlateDecode ]`` and terminates them with ``~>endstream`` (no newline).
    """
    streams = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.DOTALL):
        raw = m.group(1).strip()
        try:
            decoded = base64.a85decode(raw, adobe=True)
            streams.append(zlib.decompress(decoded))
        except Exception:
            try:
                streams.append(zlib.decompress(raw))
            except Exception:
                streams.append(raw)
    return streams


def main() -> int:
    svc = ExportService()
    card_data = []
    for i, st in enumerate(STATUS_RGB):
        card_data.append({
            "trip_id": f"T-{i}",
            "status": st,
            "truck_plate": f"AB-0{i}-XYZ",
            "driver_name": f"Driver {i}",
            "origin": "Bucharest",
            "destination": "Cluj",
            "departure_date": "2026-08-24",
            "eta": "2026-08-25",
            "alerts_count": 0,
        })

    out = os.path.join(tempfile.gettempdir(), f"dispatch_audit_{os.getpid()}.pdf")
    result = svc.generate_dispatch_board_pdf(card_data, out)
    print(f"PDF generated: {result}")
    print(f"Size: {os.path.getsize(out)} bytes")

    with open(out, "rb") as fh:
        data = fh.read()
    streams = _content_streams(data)
    print(f"Content streams found: {len(streams)}")

    all_ok = True
    for status, (r, g, b) in STATUS_RGB.items():
        needle = f"{_fmt(r)} {_fmt(g)} {_fmt(b)}".encode()
        found = any(needle in s for s in streams)
        print(f"  {status}: {'FOUND' if found else 'MISSING'} ({needle.decode()})")
        if not found:
            all_ok = False

    print(f"\nDoc color verification: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
