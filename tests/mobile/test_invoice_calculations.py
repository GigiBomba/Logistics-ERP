"""§13.3 backend calc cross-check — REAL desktop calculator vs committed vectors.

Loads ``shared/test_vectors/invoice_calculations.json`` (generated in Phase 0
from the REAL ``InvoiceService._calculate_line_items``) and asserts the REAL
calculator reproduces every expected value.  This guards drift of the
generator itself (the vectors are the cross-repo parity contract with the
mobile app's ``calculateInvoiceLines``).

Also end-to-end: POST /mobile/invoices for two vector entries and assert the
persisted totals byte-match (plain float equality) the vector expectations.
"""
from __future__ import annotations

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

BASE = "/api/v1/mobile/invoices"


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
        assert line.quantity == exp_line["quantity"]
        assert line.unit_of_measure == exp_line["unit_of_measure"]
        assert line.unit_price == exp_line["unit_price"]
        assert line.discount_percent == exp_line["discount_percent"]
        assert line.discount_amount == exp_line["discount_amount"]
        assert line.taxable_amount == exp_line["taxable_amount"]
        assert line.vat_rate == exp_line["vat_rate"]
        assert line.total_net == exp_line["total_net"]
        assert line.vat_amount == exp_line["vat_amount"]
        assert line.line_total == exp_line["line_total"]
        assert subtotal_net == expected["subtotal_net"]
        assert total_vat == expected["total_vat"]
        assert total_gross == expected["total_gross"]

    def test_multi_line_aggregation(self):
        """Sums across lines use the sequential left-to-right rounding."""
        items = [InvoiceLineItem(**_vector_input(i)) for i in (0, 1, 2)]
        _calc, subtotal_net, total_vat, total_gross = _real_calc(items)
        assert subtotal_net == round(370.35 + 950.0 + 319.69, 2)
        assert total_vat == round(70.37 + 180.5 + 0.0, 2)
        assert total_gross == round(440.72 + 1130.5 + 319.69, 2)


class TestCalcEndToEnd:
    """POST /mobile/invoices must persist byte-identical totals via the API."""

    def _create(self, manager_client, client_id, line_items):
        return manager_client.post(BASE, json={"client_id": client_id, "line_items": line_items})

    def test_vector_0_end_to_end(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._create(manager_client, finance_seed["client_a"], [_vector_input(0)])
        assert resp.status_code == 201, resp.text
        body = resp.json()
        exp = _vector_expected(0)
        assert body["subtotal_net"] == exp["subtotal_net"]
        assert body["total_vat"] == exp["total_vat"]
        assert body["total_gross"] == exp["total_gross"]
        assert body["total_amount"] == exp["total_gross"]
        assert body["line_items"][0]["taxable_amount"] == exp["lines"][0]["taxable_amount"]
        assert body["line_items"][0]["vat_amount"] == exp["lines"][0]["vat_amount"]
        assert body["line_items"][0]["line_total"] == exp["lines"][0]["line_total"]
        # Persisted row matches the response exactly.
        row = dict(real_db.execute(
            "SELECT subtotal_net, total_vat, total_gross, total_amount FROM invoices WHERE id = ?",
            (body["id"],),
        ).fetchone())
        assert row["subtotal_net"] == exp["subtotal_net"]
        assert row["total_vat"] == exp["total_vat"]
        assert row["total_gross"] == exp["total_gross"]

    def test_vector_1_end_to_end(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._create(manager_client, finance_seed["client_a"], [_vector_input(1)])
        assert resp.status_code == 201, resp.text
        body = resp.json()
        exp = _vector_expected(1)
        assert body["subtotal_net"] == exp["subtotal_net"]
        assert body["total_vat"] == exp["total_vat"]
        assert body["total_gross"] == exp["total_gross"]
        assert body["total_amount"] == exp["total_gross"]
