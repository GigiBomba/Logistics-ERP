"""Export REAL desktop invoice line-item calculations to shared/test_vectors.

Feeds a representative set of ``InvoiceLineItem`` inputs through the actual
desktop calculation — ``InvoiceService._calculate_line_items`` in
``services/invoicing/service.py`` — and records the exact returned per-line
values plus the three aggregate floats (subtotal_net, total_vat, total_gross).

The REAL code wins over the documented blueprint formula (§4.5).  Differences
observed in the real implementation (service.py lines 66–112):

  - ``gross_value = round(qty * price, 2)`` is rounded BEFORE discounting
    (blueprint computes from the unrounded ``lineTotal``).
  - ``qty = li.quantity or 1.0`` — a zero/None quantity becomes 1.0.
  - ``discount_amt`` is capped at ``gross_value``.
  - Python's ``round()`` (banker's rounding) is used at every step.
  - Pre-set ``taxable_amount`` / ``vat_amount`` / ``line_total`` fields
    override the computed values when not None.

Inputs are recorded exactly as fed; ``discount_amount=0.0`` lets the service
derive the discount from ``discount_percent`` (reproducible from the
documented formula inputs).

Run:  python scripts/export_invoice_test_vectors.py
Writes: shared/test_vectors/invoice_calculations.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure the project root is on sys.path so repo modules are importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.invoice_models import InvoiceLineItem
from services.invoicing.service import InvoiceService

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shared",
    "test_vectors",
    "invoice_calculations.json",
)

# (description, quantity, unit_price, discount_percent, discount_amount, vat_rate)
# discount_amount=0.0 → the service derives it from discount_percent (real derivation).
_VECTORS = [
    ("Standard 19% VAT, no discount", 3, 123.45, 0, 0.0, 19),
    ("Standard 19% VAT, 5% discount", 1, 1000.00, 5, 0.0, 19),
    ("0% VAT (intra-community)", 7, 45.67, 0, 0.0, 0),
    ("9% reduced VAT", 2, 99.99, 0, 0.0, 9),
    ("5% reduced VAT", 4, 19.99, 0, 0.0, 5),
    ("EDGE: 100% discount", 5, 50.00, 100, 0.0, 19),
    ("EDGE: zero quantity", 0, 100.00, 0, 0.0, 19),
    ("EDGE: half-up candidate (qty*price=0.015)", 3, 0.005, 0, 0.0, 19),
    ("EDGE: discount lands on .xx5 (19.99 * 50%)", 1, 19.99, 50, 0.0, 19),
    ("Fractional quantity", 0.5, 250.00, 0, 0.0, 19),
    ("Fractional quantity with discount", 0.5, 250.00, 20, 0.0, 19),
    ("Large line", 7, 1000.00, 5, 0.0, 19),
    ("0% VAT with 50% discount", 3, 10.00, 50, 0.0, 0),
    ("Explicit discount_amount override (no percent)", 4, 25.00, 0, 25.0, 19),
    ("Explicit discount_amount with percent ignored", 2, 50.00, 10, 10.0, 19),
    ("9% VAT with 20% discount", 7, 12.34, 20, 0.0, 9),
    ("Tiny unit price", 1, 0.01, 0, 0.0, 19),
    ("Large unit price", 1, 1234.56, 5, 0.0, 19),
    ("Fractional price", 0.5, 19.99, 0, 0.0, 19),
    ("Multi-unit price with discount", 3, 19.99, 5, 0.0, 19),
    ("0% VAT, no discount", 1, 10.00, 0, 0.0, 0),
    ("50% discount", 1, 100.00, 50, 0.0, 19),
    ("5% VAT on decimal unit price", 5, 7.50, 0, 0.0, 5),
    ("20% discount on decimal price", 1, 7.77, 20, 0.0, 19),
    ("9% VAT with 5% discount", 4, 25.00, 5, 0.0, 9),
    ("Low price, multiple units", 2, 0.33, 0, 0.0, 19),
    ("EDGE: 100% discount on decimal price", 1, 123.45, 100, 0.0, 19),
    ("EDGE: discount_amount capped at gross", 1, 100.00, 0, 500.0, 19),
    ("20% discount, 7 units", 7, 3.50, 20, 0.0, 19),
]


def _build_service() -> InvoiceService:
    """Build InvoiceService with minimal dummy deps.

    Mirrors the existing unit-test pattern (``tests/test_invoice_service_unit.py``
    uses ``InvoiceService(db_mock, prefs=None)`` with a ``MagicMock`` db).
    ``_calculate_line_items`` itself never touches db/repositories/generator —
    only ``InvoiceLineItem`` models — so a ``MagicMock`` db is sufficient.
    """
    return InvoiceService(MagicMock(), prefs=None)


def main() -> None:
    svc = _build_service()
    vectors: list[dict[str, object]] = []
    for desc, qty, price, disc_pct, disc_amt, vat_rate in _VECTORS:
        item = InvoiceLineItem(
            description=desc,
            quantity=qty,
            unit_of_measure="buc",
            unit_price=price,
            discount_percent=disc_pct,
            discount_amount=disc_amt,
            vat_rate=vat_rate,
        )
        calculated, subtotal_net, total_vat, total_gross = svc._calculate_line_items(
            [item]
        )
        vectors.append(
            {
                "input": {
                    "description": desc,
                    "quantity": qty,
                    "unit_of_measure": "buc",
                    "unit_price": price,
                    "discount_percent": disc_pct,
                    "discount_amount": disc_amt,
                    "vat_rate": vat_rate,
                },
                "expected": {
                    "lines": [li.model_dump() for li in calculated],
                    "subtotal_net": subtotal_net,
                    "total_vat": total_vat,
                    "total_gross": total_gross,
                },
            }
        )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(vectors, fh, indent=2)
        fh.write("\n")

    print(f"Wrote {len(vectors)} invoice test vectors to {OUT_PATH}")


if __name__ == "__main__":
    main()
