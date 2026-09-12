"""financial/fixtures.py — known-value financial trip builder + pure invariant checkers.

Stage B / P2-U1: one source of truth for the F1-F10 financial invariants that
``test_financial_invariants.py`` asserts across modules (analytics, invoices,
payments).  Two kinds of helpers live here:

* ``make_known_financial_trip`` — seeds the canonical 450 km / EUR 1350 trip
  (the ``KNOWN_VALUES`` profile from ``..fixtures.workflow_data``) through the
  ``WorkflowEnvironment`` service layer and additionally links it to a fresh
  ``route_history_v2`` row with route hints (``place_of_loading`` /
  ``delivery_country``) so the trip is visible to route-profitability
  analytics exactly like ``TestRouteProfitConsistency`` seeds it.

* ``check_f*`` — *pure* invariant checkers.  They take plain dicts (or the
  Pydantic result models / raw DB rows the services return) and return a
  ``(ok, discrepancy)`` tuple.  ``discrepancy`` is ``None`` when ``ok`` and a
  dict ``{"field", "expected", "actual", "message"}`` otherwise.

Rounding / equality conventions mirror ``test_financial_invariants.py``:
values are converted with ``Decimal(str(value))``, expected amounts are
quantized to 0.01 with ``ROUND_HALF_UP`` and compared with a ``< 0.01``
tolerance (the same threshold the tests use after float normalisation).

The checkers cover the subset of invariants a fixture module can verify from
in-memory data alone:

    F1  route profit consistency (per-km route economics vs trip economics)
    F2  invoice total_gross == trip total_price_eur
    F3  amount_paid + amount_remaining == invoice total
    F4  VAT consistency — per line item vat = net × rate, and the invoice
        subtotal / vat / gross totals follow
    F10 cost breakdown sums — net_profit == total - (fuel+toll+salary+extra)

(F5-F9 need cross-module state — currencies, audit logs, numbering series,
receipt creation — so they stay in the test files, not in pure checkers.)
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..fixtures.workflow_data import KNOWN_VALUES

__all__ = [
    "make_known_financial_trip",
    "check_f1_route_profit",
    "check_f2_invoice_total",
    "check_f3_payment_balance",
    "check_f4_vat",
    "check_f10_cost_sum",
]


# ═════════════════════════════════════════════════════════════════════════
# Decimal helpers — mirror test_financial_invariants.py rounding conventions
# ═════════════════════════════════════════════════════════════════════════

_CENT = Decimal("0.01")
_TOL = Decimal("0.01")  # abs() threshold used across the financial tests


def _dec(value: Any) -> Decimal:
    """Convert a stored value to a Decimal via ``str`` (float-exact, as in the tests)."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any) -> Decimal:
    """Round to 2dp with ROUND_HALF_UP — the monetary rounding the tests encode."""
    return _dec(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a dict, a mapping-like (sqlite3.Row) or a model (attribute)."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    try:
        return obj[name]  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return getattr(obj, name, default)


def _close_enough(a: Decimal, b: Decimal) -> bool:
    """Test-convention comparison: |a - b| < 0.01."""
    return abs(a - b) < _TOL


def _discrepancy(field: str, message: str,
                 expected: Any = None, actual: Any = None) -> dict[str, Any]:
    """Build the ``discrepancy`` half of a checker result."""
    return {
        "field": field,
        "expected": expected,
        "actual": actual,
        "message": message,
    }


def _trip_total(trip: Any) -> Any:
    """Trip total: DB column ``total_price_eur``, falling back to ``price_eur``."""
    value = _field(trip, "total_price_eur", None)
    if value is None:
        value = _field(trip, "price_eur", None)
    return value


def _invoice_total(invoice: Any) -> Any:
    """Invoice total: ``total_gross``, falling back to ``total_amount``."""
    value = _field(invoice, "total_gross", None)
    if value is None:
        value = _field(invoice, "total_amount", None)
    return value


# ═════════════════════════════════════════════════════════════════════════
# Trip seeding — canonical 450 km / EUR 1350 profile
# ═════════════════════════════════════════════════════════════════════════

def make_known_financial_trip(workflow_env: Any, client_id: int) -> dict[str, Any]:
    """Seed the canonical 450 km financial trip and return its row + ids.

    Creates the trip through ``workflow_env.create_trip`` so it goes through
    the real service layer (events, audit, column mapping), using the exact
    ``KNOWN_VALUES`` economics::

        distance 450 km, price 1350 €, fuel 135 €, toll 45 €,
        salary 275 €, extra 25 €, net_profit 870 €,
        rate_per_km 3.00, gross_per_km 1.93, currency EUR, status Delivered

    Then, exactly like ``TestRouteProfitConsistency``, it links the trip to a
    fresh ``route_history_v2`` row (``total_distance_km`` = the known 450 km)
    and stamps the route hints ``place_of_loading='Depot'``,
    ``loading_country='RO'``, ``delivery_country='HU'`` so the trip is
    aggregated by ``get_route_profitability`` under a deterministic label.

    Returns a dict with ``client_id``, ``trip_id``, ``route_history_id``,
    ``route_fingerprint``, the raw ``trip`` row (as returned by
    ``workflow_env.get_trip``) and the ``economics`` values used.
    """
    distance_km = float(KNOWN_VALUES["distance_km"])
    trip_id = workflow_env.create_trip(
        client_id=client_id,
        distance_km=distance_km,
        price_eur=float(KNOWN_VALUES["price_eur"]),
        status="Delivered",
        fuel_cost=float(KNOWN_VALUES["fuel_cost"]),
        toll_cost=float(KNOWN_VALUES["toll_cost"]),
        salary_cost=float(KNOWN_VALUES["salary_cost"]),
        extra_costs=float(KNOWN_VALUES["extra_costs"]),
        net_profit=float(KNOWN_VALUES["net_profit"]),
        rate_per_km=float(KNOWN_VALUES["rate_per_km"]),
        gross_per_km=float(KNOWN_VALUES["gross_per_km"]),
        currency=str(KNOWN_VALUES["currency"]),
    )

    # Link the trip to route analytics state, mirroring the F1 test setup.
    fingerprint = f"route-known-{client_id}-{trip_id}"
    workflow_env.db.conn.execute(
        "INSERT INTO route_history_v2 (route_fingerprint, stops_json, geometry_encoding, "
        "created_at, last_calculated_at, total_distance_km) "
        "VALUES (?, '[]', 'zlib-json', datetime('now'), datetime('now'), ?)",
        (fingerprint, distance_km),
    )
    route_history_id = workflow_env.db.conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]
    workflow_env.db.conn.execute(
        "UPDATE trips SET route_history_v2_id = ?, place_of_loading = 'Depot', "
        "loading_country = 'RO', delivery_country = 'HU' WHERE id = ?",
        (route_history_id, trip_id),
    )
    workflow_env.db.conn.commit()

    trip = workflow_env.get_trip(trip_id)
    if trip is None:  # pragma: no cover — defensive; get_trip just succeeded above
        raise RuntimeError(f"make_known_financial_trip: trip {trip_id} not found after seeding")

    return {
        "client_id": client_id,
        "trip_id": trip_id,
        "route_history_id": route_history_id,
        "route_fingerprint": fingerprint,
        "trip": trip,
        "economics": dict(KNOWN_VALUES),
    }


# ═════════════════════════════════════════════════════════════════════════
# F1: Route Profit Consistency
# ═════════════════════════════════════════════════════════════════════════

def check_f1_route_profit(trip: Any) -> tuple[bool, dict[str, Any] | None]:
    """F1 — route profit consistency (pure trip-level encoding).

    ``test_financial_invariants.TestRouteProfitConsistency`` makes the
    analytics ``get_route_profitability`` output (per-route ``AVG(net_profit)``,
    ``profit_per_km = net_profit / distance_km``) match a delivered trip's
    stored economics.  For a single trip that forms the route this reduces to
    two trip-level identities:

    * the trip is route-visible (non-empty ``place_of_loading`` and
      ``delivery_country`` so analytics can label/aggregate it), and
    * its per-km route economics agree with the aggregate trip economics:
      ``rate_per_km  == ROUND_HALF_UP(total / distance, 2)``
      ``gross_per_km == ROUND_HALF_UP(net_profit / distance, 2)``

    Returns ``(ok, discrepancy)``; discrepancy is None when ok.
    """
    place_of_loading = _field(trip, "place_of_loading", "") or ""
    delivery_country = _field(trip, "delivery_country", "") or ""
    if not place_of_loading or not delivery_country:
        return False, _discrepancy(
            "route_label",
            "Trip is not route-visible: F1 requires non-empty place_of_loading "
            f"and delivery_country (got place_of_loading={place_of_loading!r}, "
            f"delivery_country={delivery_country!r})",
        )

    distance = _dec(_field(trip, "distance_km", None))
    if distance <= 0:
        return False, _discrepancy(
            "distance_km",
            f"F1 requires distance_km > 0 to derive per-km economics, got {distance}",
        )

    total = _trip_total(trip)
    if total is None:
        return False, _discrepancy(
            "total_price_eur",
            "F1 cannot check route profit: trip has neither total_price_eur nor price_eur",
        )

    net_profit = _field(trip, "net_profit", None)
    rate_stored = _field(trip, "rate_per_km", None)
    gross_stored = _field(trip, "gross_per_km", None)
    if net_profit is None or rate_stored is None or gross_stored is None:
        return False, _discrepancy(
            "net_profit/rate_per_km/gross_per_km",
            "F1 cannot check route profit: trip economics are incomplete "
            "(net_profit, rate_per_km and gross_per_km are all required)",
        )

    total_dec = _dec(total)
    net_dec = _dec(net_profit)

    expected_rate = _money(total_dec / distance)
    if not _close_enough(expected_rate, _money(rate_stored)):
        return False, _discrepancy(
            "rate_per_km",
            f"rate_per_km ({rate_stored}) does not match total_price_eur / distance_km "
            f"= {expected_rate}",
            expected=expected_rate,
            actual=_money(rate_stored),
        )

    expected_gross = _money(net_dec / distance)
    if not _close_enough(expected_gross, _money(gross_stored)):
        return False, _discrepancy(
            "gross_per_km",
            f"gross_per_km ({gross_stored}) does not match net_profit / distance_km "
            f"= {expected_gross}",
            expected=expected_gross,
            actual=_money(gross_stored),
        )

    return True, None


# ═════════════════════════════════════════════════════════════════════════
# F2: Invoice ↔ Trip Total Match
# ═════════════════════════════════════════════════════════════════════════

def check_f2_invoice_total(invoice: Any, trip: Any) -> tuple[bool, dict[str, Any] | None]:
    """F2 — invoice total_gross must equal the trip's total_price_eur.

    Mirrors ``TestInvoiceTripTotalMatch.test_invoice_total_equals_trip_price``.
    ``invoice`` may be an ``InvoiceResult``, an invoice DB row (dict) or any
    mapping with ``total_gross``/``total_amount``; ``trip`` any object with
    ``total_price_eur``/``price_eur``.  Comparison uses the < 0.01 tolerance.

    Returns ``(ok, discrepancy)``; discrepancy is None when ok.
    """
    inv_total = _invoice_total(invoice)
    if inv_total is None:
        return False, _discrepancy(
            "invoice.total_gross",
            "F2 cannot check invoice total: invoice has neither total_gross nor total_amount",
        )
    trip_total = _trip_total(trip)
    if trip_total is None:
        return False, _discrepancy(
            "trip.total_price_eur",
            "F2 cannot check invoice total: trip has neither total_price_eur nor price_eur",
        )

    inv_dec = _money(inv_total)
    trip_dec = _money(trip_total)
    if not _close_enough(inv_dec, trip_dec):
        return False, _discrepancy(
            "invoice.total_gross",
            f"Invoice total_gross ({inv_dec}) must equal trip total_price_eur ({trip_dec})",
            expected=trip_dec,
            actual=inv_dec,
        )
    return True, None


# ═════════════════════════════════════════════════════════════════════════
# F3: Amount Paid Invariant
# ═════════════════════════════════════════════════════════════════════════

def check_f3_payment_balance(invoice: Any) -> tuple[bool, dict[str, Any] | None]:
    """F3 — amount_paid + amount_remaining must equal the invoice total.

    Mirrors ``TestAmountPaidInvariant`` (and the P-INV partial/full payment
    checks): ``amount_paid + amount_remaining == total_gross`` (falling back
    to ``total_amount``).  Comparison uses the < 0.01 tolerance.

    Returns ``(ok, discrepancy)``; discrepancy is None when ok.
    """
    total = _invoice_total(invoice)
    if total is None:
        return False, _discrepancy(
            "invoice.total_gross",
            "F3 cannot check payment balance: invoice has neither total_gross nor total_amount",
        )
    paid = _dec(_field(invoice, "amount_paid", None))
    remaining = _dec(_field(invoice, "amount_remaining", None))
    total_dec = _money(total)

    balance = _money(paid + remaining)
    if not _close_enough(balance, total_dec):
        return False, _discrepancy(
            "amount_paid+amount_remaining",
            f"amount_paid ({paid}) + amount_remaining ({remaining}) = {balance} "
            f"must equal invoice total ({total_dec})",
            expected=total_dec,
            actual=balance,
        )
    return True, None


# ═════════════════════════════════════════════════════════════════════════
# F4: VAT Consistency
# ═════════════════════════════════════════════════════════════════════════

def _line_items(invoice: Any) -> list[Any]:
    """Line items from an InvoiceResult, invoice dict, or raw row dict."""
    items = _field(invoice, "line_items", None)
    if items is not None:
        return list(items)
    raw = _field(invoice, "line_items_json", None)
    if raw:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return list(parsed) if isinstance(parsed, list) else []
    return []


def _line_vat_expected(line: Any) -> tuple[Decimal, Decimal, Decimal]:
    """Expected (taxable, vat, line_total) for one line, ROUND_HALF_UP per cent.

    Mirrors the Romanian-compliant calculation in ``InvoiceService`` and the
    rounding expectations in ``TestRoundingConsistency``::

        taxable    = ROUND_HALF_UP(qty × unit_price − discount)
        vat        = ROUND_HALF_UP(taxable × vat_rate / 100)
        line_total = ROUND_HALF_UP(taxable + vat)
    """
    qty = _dec(_field(line, "quantity", None))
    if qty == 0:
        qty = Decimal("1")
    unit = _dec(_field(line, "unit_price", None))
    gross = _money(qty * unit)

    discount_amt = _dec(_field(line, "discount_amount", None))
    discount_pct = _dec(_field(line, "discount_percent", None))
    if discount_amt == 0 and discount_pct > 0:
        discount_amt = _money(gross * discount_pct / Decimal("100"))
    if discount_amt > gross:
        discount_amt = gross

    taxable = _money(gross - discount_amt)
    vat_rate = _dec(_field(line, "vat_rate", None))
    vat = _money(taxable * vat_rate / Decimal("100"))
    line_total = _money(taxable + vat)
    return taxable, vat, line_total


def _check_line_vat(line: Any, idx: int) -> tuple[bool, dict[str, Any] | None]:
    """Per-line net×rate consistency against any stored computed fields."""
    taxable_expected, vat_expected, total_expected = _line_vat_expected(line)

    stored_taxable = _field(line, "taxable_amount", None)
    if stored_taxable is not None and not _close_enough(
        _money(stored_taxable), taxable_expected
    ):
        return False, _discrepancy(
            f"line_items[{idx}].taxable_amount",
            f"line {idx} taxable_amount ({stored_taxable}) must equal "
            f"qty × unit_price rounded half-up ({taxable_expected})",
            expected=taxable_expected,
            actual=_money(stored_taxable),
        )

    stored_vat = _field(line, "vat_amount", None)
    if stored_vat is not None and not _close_enough(_money(stored_vat), vat_expected):
        return False, _discrepancy(
            f"line_items[{idx}].vat_amount",
            f"line {idx} vat_amount ({stored_vat}) must equal "
            f"taxable × vat_rate / 100 rounded half-up ({vat_expected})",
            expected=vat_expected,
            actual=_money(stored_vat),
        )

    stored_total = _field(line, "line_total", None)
    if stored_total is not None and not _close_enough(_money(stored_total), total_expected):
        return False, _discrepancy(
            f"line_items[{idx}].line_total",
            f"line {idx} line_total ({stored_total}) must equal "
            f"taxable + vat rounded half-up ({total_expected})",
            expected=total_expected,
            actual=_money(stored_total),
        )
    return True, None


def check_f4_vat(invoice: Any) -> tuple[bool, dict[str, Any] | None]:
    """F4 — VAT consistency: net × rate per line and across invoice totals.

    Mirrors ``TestVATConsistency`` and ``TestRoundingConsistency``: each line
    item's ``vat_amount`` must be ``ROUND_HALF_UP(taxable × vat_rate / 100)``
    and the invoice aggregates must follow::

        subtotal_net = Σ taxable
        total_vat    = Σ vat
        total_gross  = Σ (taxable + vat)

    An invoice without line items must have all-zero totals (or at minimum
    satisfy ``total_gross == subtotal_net + total_vat``).  Comparison uses the
    < 0.01 tolerance.

    Returns ``(ok, discrepancy)``; discrepancy is None when ok.
    """
    items = _line_items(invoice)
    subtotal_stored = _field(invoice, "subtotal_net", None)
    vat_stored = _field(invoice, "total_vat", None)
    total_stored = _invoice_total(invoice)

    if not items:
        # No line items: only a zero invoice, or a gross == net + vat invoice,
        # can be internally VAT-consistent.
        if subtotal_stored is None or vat_stored is None or total_stored is None:
            return True, None  # nothing stored to verify against
        sub = _dec(subtotal_stored)
        vat = _dec(vat_stored)
        gross = _dec(total_stored)
        if _close_enough(sub, Decimal("0")) and _close_enough(vat, Decimal("0")) \
                and _close_enough(gross, Decimal("0")):
            return True, None
        expected_gross = _money(sub + vat)
        if not _close_enough(_money(gross), expected_gross):
            return False, _discrepancy(
                "invoice.total_gross",
                f"Invoice has no line items but total_gross ({gross}) != "
                f"subtotal_net + total_vat ({expected_gross})",
                expected=expected_gross,
                actual=_money(gross),
            )
        return True, None

    subtotal_expected = Decimal("0")
    vat_total_expected = Decimal("0")
    gross_total_expected = Decimal("0")
    for idx, line in enumerate(items):
        ok, discrepancy = _check_line_vat(line, idx)
        if not ok:
            return False, discrepancy
        taxable, vat, line_total = _line_vat_expected(line)
        subtotal_expected += taxable
        vat_total_expected += vat
        gross_total_expected += line_total

    subtotal_expected = _money(subtotal_expected)
    vat_total_expected = _money(vat_total_expected)
    gross_total_expected = _money(gross_total_expected)

    if subtotal_stored is not None and not _close_enough(
        _money(subtotal_stored), subtotal_expected
    ):
        return False, _discrepancy(
            "invoice.subtotal_net",
            f"Invoice subtotal_net ({subtotal_stored}) must equal Σ line taxable "
            f"amounts ({subtotal_expected})",
            expected=subtotal_expected,
            actual=_money(subtotal_stored),
        )

    if vat_stored is not None and not _close_enough(_money(vat_stored), vat_total_expected):
        return False, _discrepancy(
            "invoice.total_vat",
            f"Invoice total_vat ({vat_stored}) must equal Σ line vat_amounts "
            f"({vat_total_expected})",
            expected=vat_total_expected,
            actual=_money(vat_stored),
        )

    if total_stored is not None and not _close_enough(
        _money(total_stored), gross_total_expected
    ):
        return False, _discrepancy(
            "invoice.total_gross",
            f"Invoice total_gross ({total_stored}) must equal Σ line totals "
            f"({gross_total_expected})",
            expected=gross_total_expected,
            actual=_money(total_stored),
        )

    return True, None


# ═════════════════════════════════════════════════════════════════════════
# F10: Cost Breakdown Sums
# ═════════════════════════════════════════════════════════════════════════

def check_f10_cost_sum(trip: Any) -> tuple[bool, dict[str, Any] | None]:
    """F10 — net_profit = total_price_eur − (fuel + toll + salary + extra).

    Mirrors ``TestCostBreakdownSums`` (and the F6 trip-costs rounding test):
    the cost components are summed and subtracted from the trip total with
    ROUND_HALF_UP at 0.01, then compared to the stored ``net_profit`` within
    the < 0.01 tolerance.

    Returns ``(ok, discrepancy)``; discrepancy is None when ok.
    """
    total = _trip_total(trip)
    if total is None:
        return False, _discrepancy(
            "total_price_eur",
            "F10 cannot check cost sums: trip has neither total_price_eur nor price_eur",
        )
    net_profit = _field(trip, "net_profit", None)
    if net_profit is None:
        return False, _discrepancy(
            "net_profit",
            "F10 cannot check cost sums: trip has no net_profit",
        )

    cost_fields = ("fuel_cost", "toll_cost", "salary_cost", "extra_costs")
    costs_sum = _money(sum((_dec(_field(trip, f, None)) for f in cost_fields), Decimal("0")))
    expected_profit = _money(_dec(total) - costs_sum)
    net_stored = _money(net_profit)

    if not _close_enough(net_stored, expected_profit):
        return False, _discrepancy(
            "net_profit",
            f"net_profit ({net_stored}) != total_price_eur ({_dec(total)}) − "
            f"costs ({costs_sum}) = {expected_profit}",
            expected=expected_profit,
            actual=net_stored,
        )
    return True, None
