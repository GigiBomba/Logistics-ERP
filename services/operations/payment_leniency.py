"""Rule-based payment leniency — conservative approximation of blueprint §4.6.

LEGAL / PRODUCT VALIDATION
--------------------------
Blueprint §4.6 (``archive/completed/Operion_Website_SGrade_Blueprint.md``)
describes an *AI-driven* payment-leniency feature: the AI Copilot, seeing the
customer's own accounts receivable, proactively defers Operion's subscription
charge when it detects a cash crunch. The blueprint explicitly holds the
feature for accountant/legal review **before** building:

* it is a form of **automated credit extension** — deciding to defer payment
  on an automated inference about a customer's cash position edges toward a
  credit decision with regulatory considerations;
* a deferred-payment invoice must **still be issued and reported** (Romanian
  e-Factura obligations are tied to the transaction/service period, not to
  cash movement) — deferred is **not** discounted;
* **revenue recognition** must be confirmed for "deferred, not discounted".

This module is a CONSERVATIVE, DETERMINISTIC, rule-based approximation of that
intent, scoped to the in-app dunning path only:

* it does **not** defer fiscal invoicing, does **not** change revenue
  recognition, and does **not** communicate anything to the client;
* its only effect is temporarily pausing *internal* dunning/reminder emails
  for a bounded window when a client's payment track record is otherwise clean
  and a single invoice slips.

The ML/score component from the blueprint (a receivables-ratio risk signal) is
explicitly FUTURE WORK. The feature ships DISABLED behind the
``payment_leniency`` feature flag (default off) and product/legal must still
re-validate before the flag is enabled for any real tenant.

The rules are deterministic and unit-testable — no ML dependencies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, List, Optional

logger = logging.getLogger("operations.payment_leniency")

# Statuses treated as fully cleared — they never count as "overdue" in the
# client's track record. Deliberately narrow: anything ambiguous (e.g. an
# issued-but-unpaid 'finalized' invoice) still counts toward the track record,
# which is the conservative direction (it can only deny leniency).
_CLEARED_STATUSES = frozenset({"paid", "cleared"})

# Default reason attached to every grant decision.
GRANT_REASON_DEFAULT = (
    "one-off slip: invoice within 60 days, no invoice overdue >30d in the "
    "last 180 days, no leniency granted this quarter"
)


@dataclass(frozen=True)
class LeniencyGrant:
    """A single rule-based leniency grant decision."""

    pause_days: int
    reason: str
    granted_at: date


@dataclass
class ClientPaymentHistory:
    """Snapshot of a client's payment track record used to evaluate leniency.

    ``invoices`` entries are dicts carrying at least ``id``/``invoice_id``,
    ``issue_date``, ``due_date`` and ``status`` (statuses in ``_CLEARED_STATUSES``
    are treated as cleared). ``leniency_grants`` entries carry a ``granted_at``
    date (a ``date`` object or ``YYYY-MM-DD`` string) for the quarterly cap and
    grant-window checks.
    """

    invoices: List[dict] = field(default_factory=list)
    leniency_grants: List[dict] = field(default_factory=list)


class PaymentLeniencyEngine:
    """Deterministic rule-based approximation of blueprint §4.6.

    A grant is produced only when ALL of the following hold:

    1. the invoice under evaluation is overdue (past ``due_date``) and its age
       (from ``issue_date``, falling back to ``due_date``) is at most
       ``max_invoice_age_days`` (default 60) — a fresh, one-off slip;
    2. the client has no *other* unpaid invoice overdue by more than
       ``max_overdue_days`` (default 30) within the last ``lookback_days``
       (default 180) — the client's track record is otherwise clean;
    3. no leniency was already granted in the current calendar quarter
       (one grant per quarter per client).

    All rules use the injected ``today`` date, so behaviour is fully
    deterministic for a given input snapshot.
    """

    DEFAULT_PAUSE_DAYS = 14

    def __init__(
        self,
        *,
        today: Optional[date] = None,
        max_overdue_days: int = 30,
        lookback_days: int = 180,
        max_invoice_age_days: int = 60,
        pause_days: int = DEFAULT_PAUSE_DAYS,
    ) -> None:
        self._today = today or date.today()
        self._max_overdue_days = max_overdue_days
        self._lookback_days = lookback_days
        self._max_invoice_age_days = max_invoice_age_days
        self._pause_days = pause_days

    # ── Public API ─────────────────────────────────────────────────────

    def grant_leniency(
        self,
        client_id: Any,
        invoice: dict,
        history: ClientPaymentHistory,
    ) -> Optional[LeniencyGrant]:
        """Evaluate whether *invoice* for *client_id* qualifies for leniency.

        Returns a :class:`LeniencyGrant` when every rule holds, otherwise
        ``None`` (deny).
        """
        today = self._today

        # Guard 1 — the invoice must actually be overdue.
        due_date = self._parse_date(invoice.get("due_date"))
        if due_date is None:
            logger.debug("Leniency denied (client #%s): invoice has no due date", client_id)
            return None
        days_past_due = (today - due_date).days
        if days_past_due <= 0:
            logger.debug("Leniency denied (client #%s): invoice is not overdue", client_id)
            return None

        # Guard 2 — the invoice must be a fresh one-off slip, not a stale debt.
        issue_date = self._parse_date(invoice.get("issue_date"))
        age_date = issue_date or due_date
        if age_date is not None and (today - age_date).days > self._max_invoice_age_days:
            logger.debug(
                "Leniency denied (client #%s): invoice older than %d days",
                client_id, self._max_invoice_age_days,
            )
            return None

        # Guard 3 — the client's track record must be otherwise clean: no OTHER
        # invoice overdue by more than max_overdue_days inside the lookback
        # window. The invoice under evaluation is excluded (it *is* the slip).
        current_id = self._invoice_id(invoice)
        for other in history.invoices or []:
            other_id = self._invoice_id(other)
            if current_id is not None and other_id is not None and current_id == other_id:
                continue
            status = str(other.get("status") or "").strip().lower()
            if status in _CLEARED_STATUSES:
                continue
            other_due = self._parse_date(other.get("due_date"))
            if other_due is None:
                continue
            days_late = (today - other_due).days
            if days_late <= 0:
                continue  # not overdue
            if days_late > self._lookback_days:
                continue  # outside the recent track-record window
            if days_late > self._max_overdue_days:
                logger.debug(
                    "Leniency denied (client #%s): chronic overdue invoice (#%s, %d days late)",
                    client_id, other_id, days_late,
                )
                return None

        # Guard 4 — quarterly cap: one leniency grant per client per quarter.
        if self._has_grant_in_current_quarter(history):
            logger.debug("Leniency denied (client #%s): already granted this quarter", client_id)
            return None

        grant = LeniencyGrant(
            pause_days=self._pause_days,
            reason=GRANT_REASON_DEFAULT,
            granted_at=today,
        )
        logger.info("Payment leniency granted for client #%s: %s", client_id, grant.reason)
        return grant

    def is_paused(self, client_id: Any, history: ClientPaymentHistory) -> bool:
        """True when the client has an active grant in the current quarter.

        An active grant is one whose ``granted_at + pause_days`` window still
        covers *today*. Used by callers to keep dunning defused across daily
        cycles without issuing a new grant every cycle.
        """
        current = self._quarter_key(self._today)
        for grant in history.leniency_grants or []:
            granted = self._parse_date(grant.get("granted_at"))
            if granted is None:
                continue
            if self._quarter_key(granted) != current:
                continue
            window_end = granted + timedelta(days=self._pause_days)
            if self._today <= window_end:
                return True
        return False

    def has_grant_in_current_quarter(self, history: ClientPaymentHistory) -> bool:
        """True when any leniency grant in *history* falls in the current quarter."""
        return self._has_grant_in_current_quarter(history)

    # ── Internal helpers ───────────────────────────────────────────────

    def _has_grant_in_current_quarter(self, history: ClientPaymentHistory) -> bool:
        current = self._quarter_key(self._today)
        for grant in history.leniency_grants or []:
            granted = self._parse_date(grant.get("granted_at"))
            if granted is None:
                continue
            if self._quarter_key(granted) == current:
                return True
        return False

    @staticmethod
    def _quarter_key(d: date) -> str:
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        """Parse a ``YYYY-MM-DD`` string / ``datetime`` / ``date`` into a ``date``."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()[:10]
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _invoice_id(invoice: Optional[dict]) -> Optional[int]:
        """Return the invoice id under either the dunner (``invoice_id``) or
        repository (``id``) key."""
        if not invoice:
            return None
        raw = invoice.get("invoice_id")
        if raw is None:
            raw = invoice.get("id")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None