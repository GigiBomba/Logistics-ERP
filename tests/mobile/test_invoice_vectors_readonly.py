"""§13.3 backend calc cross-check — REAL desktop calculator vs committed vectors.

Read-only pure-compute subset of ``test_invoice_calculations.py``: the vector
cross-check needs NO database at all (it exercises ``InvoiceService`` against
``shared/test_vectors/invoice_calculations.json`` directly), so it lives here
without ``real_db`` / ``finance_seed`` and runs without the file-backed SQLite
setup cost.

The end-to-end POST /mobile/invoices tests stay in
``test_invoice_calculations.py`` (they need a real DB).
"""
from __future__ import annotations

import functools
import json
import os

import pytest

from models.invoice_models import InvoiceLineItem

VECTORS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "shared",
    "test_vectors",
    "invoice_calculations.json",
)


@functools.lru_cache(maxsize=1)
def _load_vectors() -> list[dict]:
    with open(VECTORS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _real_calc(items):
    from services.invoicing.service import InvoiceService

    return InvoiceService(None)._calculate_line_items(items)


def _vector_input(i: int) -> dict:
    return dict(_load_vectors()[i]["input"])


def _vector_expected(i: int) -> dict:
    return _load_vectors()[i]["expected"]


class TestCalcCrossCheck:
    """Every committed vector must be reproduced by the REAL calculator."""

    def test_vector_count(self):
        assert len(_load_vectors()) == 29, "vector fixture count drift"

    @pytest.mark.parametrize("index", range(29))
    def test_vector_reproduced(self, index):
        vector = _load_vectors()[index]
        item = InvoiceLineItem(**vector["input"])
        calc_items, subtotal_net, total_vat, total_gross = _real_calc([item])

        expected = vector["expected"]
        exp_line = expected["lines"][0]
        line = calc_items[0]
        # Plain float equality — the vectors were generated from THIS code path,
        # so any drift (rounding changes, coalescing changes) fails loudly.
        # Decimal fields require explicit normalization (Decimal == float does
        # exact-binary comparison and rejects numerically identical values).
        assert float(line.quantity) == exp_line["quantity"]
        assert line.unit_of_measure == exp_line["unit_of_measure"]
        assert float(line.unit_price) == exp_line["unit_price"]
        assert float(line.discount_percent) == exp_line["discount_percent"]
        assert float(line.discount_amount) == exp_line["discount_amount"]
        assert float(line.taxable_amount) == exp_line["taxable_amount"]
        assert float(line.vat_rate) == exp_line["vat_rate"]
        # total_net stays None end-to-end (nullable, both sides None by contract).
        assert line.total_net == exp_line["total_net"]
        assert float(line.vat_amount) == exp_line["vat_amount"]
        assert float(line.line_total) == exp_line["line_total"]
        assert float(subtotal_net) == expected["subtotal_net"]
        assert float(total_vat) == expected["total_vat"]
        assert float(total_gross) == expected["total_gross"]