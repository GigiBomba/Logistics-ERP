"""Route compliance / metadata analysis (no UI dependencies)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from services.i18n import t

TOLL_COUNTRIES = frozenset({"IT", "FR", "ES", "PT", "PL", "SI", "HR", "DE"})


@dataclass
class RouteComplianceSummary:
    traversed: List[str]
    toll_countries: List[str]
    excluded_avoided: List[str]
    border_crossings: int
    extra_distance_km: float
    reroute_reason: str
    note: str
    summary_text: str
    explanation_text: str


class RouteComplianceAnalyzer:
    def analyze(self, route: Dict[str, Any]) -> RouteComplianceSummary:
        countries = list(route.get("detected_countries") or [])
        exclusions = list(route.get("excluded_countries_requested") or [])
        avoided = [c for c in exclusions if c not in countries]
        tolls = [c for c in countries if c in TOLL_COUNTRIES]
        borders = max(0, len(countries) - 1)
        extra_km = float(route.get("extra_distance_km") or 0.0)

        summary_lines = [
            t("compliance.traversed").format(', '.join(countries) if countries else 'N/A'),
            t("compliance.toll_countries").format(', '.join(tolls) if tolls else 'None'),
            t("compliance.excluded_avoided").format(', '.join(avoided) if avoided else 'None'),
            t("compliance.border_crossings").format(borders),
        ]
        if extra_km > 0:
            summary_lines.append(t("compliance.extra_distance").format(extra_km))

        reason = route.get("reroute_reason") or ("cached" if route.get("cached") else "chosen")
        note = route.get("note") or ""
        explanation = t("compliance.why_chosen").format(reason, note).strip()

        return RouteComplianceSummary(
            traversed=countries,
            toll_countries=tolls,
            excluded_avoided=avoided,
            border_crossings=borders,
            extra_distance_km=extra_km,
            reroute_reason=str(reason),
            note=str(note),
            summary_text="\n".join(summary_lines),
            explanation_text=explanation,
        )
