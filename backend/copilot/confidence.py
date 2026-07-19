"""Confidence Engine — concrete weighted formula, not a label.

Blueprint: §10
"""

from __future__ import annotations

import logging
from typing import List

from backend.copilot.schemas import Entity, Intent

logger = logging.getLogger(__name__)

# Default weights (sum to 1.0, tunable per deployment via config)
DEFAULT_WEIGHTS = {
    "intent_match": 0.35,
    "entity_completeness": 0.30,
    "entity_confidence_avg": 0.20,
    "historical_success_rate": 0.15,
}

# Thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.85    # >= → plan proceeds without extra prompting
MEDIUM_CONFIDENCE_THRESHOLD = 0.55  # >= → planner surfaces "Here's what I understood" recap
# < MEDIUM_CONFIDENCE_THRESHOLD    → planner asks clarifying question, does not build a plan


def compute_confidence(
    intent: Intent,
    intent_match_score: float,
    historical_success_rate: float = 0.75,
    weights: dict = None,
) -> float:
    """Compute overall confidence score using the weighted formula from §10.

    overall_confidence = w1 * intent_match_score
                       + w2 * entity_completeness_score
                       + w3 * entity_extraction_confidence_avg
                       + w4 * historical_success_rate

    Args:
        intent: The extracted Intent with entities.
        intent_match_score: Planner's top-intent probability (0.0–1.0).
        historical_success_rate: successful_executions / total_executions for this intent+company.
            Defaults to 0.75 if fewer than 10 prior samples exist (§22 item 2 — per-company only).
        weights: Optional weight overrides (defaults to DEFAULT_WEIGHTS).

    Returns:
        Overall confidence score 0.0–1.0.
    """
    w = weights or DEFAULT_WEIGHTS

    # Entity completeness: how many required entities were found?
    total_required = len(intent.entities) + len(intent.missing_required_entities)
    if total_required == 0:
        entity_completeness = 1.0
    else:
        entity_completeness = len(intent.entities) / total_required

    # Entity extraction confidence: mean confidence of all extracted entities
    if intent.entities:
        entity_confidence_avg = sum(e.confidence for e in intent.entities) / len(intent.entities)
    else:
        entity_confidence_avg = 1.0

    score = (
        w["intent_match"] * intent_match_score
        + w["entity_completeness"] * entity_completeness
        + w["entity_confidence_avg"] * entity_confidence_avg
        + w["historical_success_rate"] * historical_success_rate
    )

    return max(0.0, min(1.0, score))


def confidence_bucket(score: float) -> str:
    """Return the confidence bucket: 'high', 'medium', or 'low'."""
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    elif score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def needs_clarification(score: float) -> bool:
    """Return True if confidence is too low to proceed without clarification."""
    return score < MEDIUM_CONFIDENCE_THRESHOLD


def needs_recap(score: float) -> bool:
    """Return True if planner should surface a one-line recap before proceeding."""
    return MEDIUM_CONFIDENCE_THRESHOLD <= score < HIGH_CONFIDENCE_THRESHOLD
