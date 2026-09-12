"""workflow_data.py — shared canonical data for workflow-integrity fixtures.

Module-level constants mirror the values asserted across the golden-flow and
parity suites so tests can reuse one source of truth instead of re-hard-coding
numbers:

* ``KNOWN_VALUES``         — the 450 km trip financials used by
                            ``test_full_trip_lifecycle`` (values copied exactly)
* ``OCR_SAMPLES``          — extracted-json OCR payloads at 0.97 / 0.72 / 0.12
                            confidence, matching ``test_ocr_recovery``
* ``FREIGHT_LOADS``        — freight-exchange loads with origins, destinations
                            and margins matching ``test_freight_exchange_import``
* ``MAINTENANCE_TICKETS``  — vehicle-fault tickets modelled on
                            ``test_maintenance_blocking``
* ``DUNNING_SCHEDULE``     — receivables reminder ladder (days 1 / 7 / 14 / 30)
* ``TACHO_SAMPLES``        — driver-activity samples near EU driving-time limits
                            (8.5 h daily / 55 h weekly, both within the law)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "KNOWN_VALUES",
    "OCR_SAMPLES",
    "FREIGHT_LOADS",
    "MAINTENANCE_TICKETS",
    "DUNNING_SCHEDULE",
    "TACHO_SAMPLES",
]


# ═════════════════════════════════════════════════════════════════════════
# 450 km trip financials — copy of test_full_trip_lifecycle's canonical trip
# ═════════════════════════════════════════════════════════════════════════

KNOWN_VALUES: dict[str, float | str] = {
    # The exact financials passed when test_full_trip_lifecycle builds the
    # 450 km / EUR 1350 trip (distance_km=450.0, price_eur=1350.0, ...).
    "distance_km": 450.0,
    "price_eur": 1350.0,
    "total_price_eur": 1350.0,  # total_price_eur stored on the trip
    "fuel_cost": 135.0,
    "toll_cost": 45.0,
    "salary_cost": 275.0,
    "extra_costs": 25.0,
    "net_profit": 870.0,        # 1350 - 135 - 45 - 275 - 25
    "rate_per_km": 3.0,         # 1350 / 450
    "gross_per_km": 1.93,       # profit per km, as stored in the golden flow
    "currency": "EUR",
}


# ═════════════════════════════════════════════════════════════════════════
# OCR extraction samples — test_ocr_recovery.confidence threshold is 0.7
# ═════════════════════════════════════════════════════════════════════════

OCR_SAMPLES: list[dict[str, Any]] = [
    {
        # High confidence → auto-capture, no human review.
        "title": "cmr_high_confidence.pdf",
        "category": "cmr",
        "confidence": 0.97,
        "needs_human_review": False,
        "ocr_text": (
            "CMR-00123456 Metro Cash & Carry Bucharest RO -> Budapest HU "
            "450 km EUR 1350 gross 870 net"
        ),
        "extracted_data": {
            "cmr_number": "CMR-00123456",
            "invoice_number": "INV-2026-0712",
            "confidence": 0.97,
        },
    },
    {
        # Near-threshold confidence — still above 0.7, flagged for a glance.
        "title": "cmr_medium_confidence.pdf",
        "category": "cmr",
        "confidence": 0.72,
        "needs_human_review": True,
        "ocr_text": (
            "CMR-00876543 partially legible CMR number, amount read with "
            "low certainty"
        ),
        "extracted_data": {
            "cmr_number": "CMR-00876543",
            "invoice_number": "INV-2026-0713",
            "confidence": 0.72,
        },
    },
    {
        # Below threshold → recovery: human correction then propagation.
        "title": "cmr_low_confidence.pdf",
        "category": "cmr",
        "confidence": 0.12,
        "needs_human_review": True,
        "ocr_text": "unreadable scan — smudged CMR, no number or amount legible",
        "extracted_data": {
            "cmr_number": "",
            "invoice_number": "",
            "confidence": 0.12,
        },
    },
]


# ═════════════════════════════════════════════════════════════════════════
# Freight-exchange loads — margins match test_freight_exchange_import.
# Convention: net_profit = price_eur - fuel - toll - salary - extra
# ═════════════════════════════════════════════════════════════════════════

FREIGHT_LOADS: list[dict[str, Any]] = [
    {
        # Matches test_import_load_creates_trip (850 km / EUR 2450).
        "reference": "TX-2026-0711",
        "exchange": "trans_eu",
        "origin": "Cluj-Napoca, RO",
        "destination": "Munich, DE",
        "distance_km": 850.0,
        "price_eur": 2450.0,
        "fuel_cost": 395.0,
        "toll_cost": 180.0,
        "salary_cost": 350.0,
        "extra_costs": 25.0,
        "net_profit": 1500.0,        # 2450 - 950
        "margin_pct": 61.22,         # 1500 / 2450 * 100
        "currency": "EUR",
        "status": "Planned",
    },
    {
        # Matches test_margin_evaluation exactly (500 km / EUR 1500 costs).
        "reference": "TC-2026-0502",
        "exchange": "timocom",
        "origin": "Oradea, RO",
        "destination": "Budapest, HU",
        "distance_km": 500.0,
        "price_eur": 1500.0,
        "fuel_cost": 150.0,
        "toll_cost": 50.0,
        "salary_cost": 300.0,
        "extra_costs": 0.0,
        "net_profit": 1000.0,        # 1500 - 500
        "margin_pct": 66.67,         # 1000 / 1500 * 100
        "currency": "EUR",
        "status": "Planned",
    },
    {
        # The canonical 450 km trip from KNOWN_VALUES, as an exchange load.
        "reference": "TC-2026-0450",
        "exchange": "timocom",
        "origin": "Bucharest, RO",
        "destination": "Arad, RO",
        "distance_km": 450.0,
        "price_eur": 1350.0,
        "fuel_cost": 135.0,
        "toll_cost": 45.0,
        "salary_cost": 275.0,
        "extra_costs": 25.0,
        "net_profit": 870.0,         # 1350 - 480
        "margin_pct": 64.44,         # 870 / 1350 * 100
        "currency": "EUR",
        "status": "Planned",
    },
]


# ═════════════════════════════════════════════════════════════════════════
# Maintenance tickets — modelled on test_maintenance_blocking
# (FleetMaintenanceService.add_record(truck_id, maint_type, date, notes)).
# truck_id is intentionally absent: tests assign the persona's real truck id.
# ═════════════════════════════════════════════════════════════════════════

MAINTENANCE_TICKETS: list[dict[str, Any]] = [
    {
        "reference": "MNT-2026-071",
        "maint_type": "engine",
        "date": "2026-07-21",
        "notes": "Engine fault — truck cannot operate",
        "severity": "critical",
        "blocks_dispatch": True,
    },
    {
        "reference": "MNT-2026-072",
        "maint_type": "brakes",
        "date": "2026-07-20",
        "notes": "Brake pad wear below legal minimum",
        "severity": "high",
        "blocks_dispatch": True,
    },
    {
        "reference": "MNT-2026-073",
        "maint_type": "service",
        "date": "2026-07-18",
        "notes": "Scheduled 60 000 km service",
        "severity": "low",
        "blocks_dispatch": False,
    },
]


# ═════════════════════════════════════════════════════════════════════════
# Dunning / receivables ladder — escalation on days 1 / 7 / 14 / 30 past due
# ═════════════════════════════════════════════════════════════════════════

DUNNING_SCHEDULE: list[dict[str, Any]] = [
    {
        "day": 1,
        "stage": "reminder_1",
        "channel": "email",
        "template": "dunning_reminder_1",
        "subject": "Invoice overdue — friendly payment reminder",
        "escalation": False,
    },
    {
        "day": 7,
        "stage": "reminder_2",
        "channel": "email",
        "template": "dunning_reminder_2",
        "subject": "Invoice still outstanding — please arrange payment",
        "escalation": False,
    },
    {
        "day": 14,
        "stage": "warning",
        "channel": "email_letter",
        "template": "dunning_warning",
        "subject": "Second notice — payment required within 7 days",
        "escalation": True,
    },
    {
        "day": 30,
        "stage": "final_notice",
        "channel": "registered_letter",
        "template": "dunning_final_notice",
        "subject": "Final notice — account handed to collection",
        "escalation": True,
    },
]


# ═════════════════════════════════════════════════════════════════════════
# Tachograph samples — near, but within, EU driving-time limits.
# EU daily limit 9 h (10 h twice/week), weekly 56 h, fortnight 90 h.
# ═════════════════════════════════════════════════════════════════════════

TACHO_SAMPLES: dict[str, Any] = {
    "eu_limits": {
        "daily_hours": 9.0,
        "daily_extended_hours": 10.0,
        "weekly_hours": 56.0,
        "fortnight_hours": 90.0,
    },
    # 8.5 h driving day — comfortably inside the 9 h daily limit.
    "daily_within_limit": {
        "activity_date": "2026-07-20",
        "driving_minutes": 510,
        "driving_hours": 8.5,
    },
    # 55 h driving week — inside the 56 h weekly limit. Individual days
    # never exceed 9 h. Daily minutes: 510+480+540+480+510+450+330 = 3300.
    "weekly_within_limit": {
        "week_start": "2026-07-20",
        "driving_minutes": 3300,
        "driving_hours": 55.0,
        "daily_minutes": [510, 480, 540, 480, 510, 450, 330],
        "days_within_daily_limit": True,
    },
}
