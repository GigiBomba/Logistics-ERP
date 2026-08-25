"""Shared label mapping utilities for GraphHopper route profiles.

These functions provide bidirectional mapping between technical
GraphHopper profile names (e.g. ``"truck"``, ``"truck_fast"``) and
human-readable UI labels (e.g. ``"Recommended"``, ``"Fastest"``).

Placed here rather than in ``services/`` or ``ui/`` because both
layers need access to the mapping.
"""
from __future__ import annotations


from config import Config

GRAPHHOPPER_PROFILES = Config.GRAPHHOPPER_PROFILES


def ui_label_for_profile(gh_profile: str) -> str:
    reverse = {v: k for k, v in GRAPHHOPPER_PROFILES.items()}
    return reverse.get(gh_profile, gh_profile or "Recommended")


def gh_profile_for_ui_label(label: str) -> str:
    return GRAPHHOPPER_PROFILES.get(label, "truck")
