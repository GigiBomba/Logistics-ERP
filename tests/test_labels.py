"""Comprehensive unit tests for utils/labels.py.

Tests cover ui_label_for_profile and gh_profile_for_ui_label —
including known profiles, unknown profiles, and empty strings.
"""

from __future__ import annotations

import pytest

from utils.labels import gh_profile_for_ui_label, ui_label_for_profile


# ──────────────────────────────────────────────────────────────
# ui_label_for_profile
# ──────────────────────────────────────────────────────────────


class TestUiLabelForProfile:
    """Map GraphHopper profile name to human-readable UI label."""

    def test_truck_returns_recommended(self):
        assert ui_label_for_profile("truck") == "Recommended"

    def test_truck_fast_returns_fastest(self):
        assert ui_label_for_profile("truck_fast") == "Fastest"

    def test_truck_cheap_returns_cheapest(self):
        assert ui_label_for_profile("truck_cheap") == "Cheapest"

    def test_truck_safe_returns_safest(self):
        assert ui_label_for_profile("truck_safe") == "Safest"

    def test_truck_short_returns_shortest(self):
        assert ui_label_for_profile("truck_short") == "Shortest"

    def test_unknown_profile_returns_original(self):
        assert ui_label_for_profile("unknown_profile") == "unknown_profile"

    def test_empty_string_returns_default(self):
        # empty string or '' → or evaluates to "Recommended"
        assert ui_label_for_profile("") == "Recommended"

    def test_case_sensitive_mismatch(self):
        # Profiles are lower-case keys; case matters
        assert ui_label_for_profile("Truck") == "Truck"


# ──────────────────────────────────────────────────────────────
# gh_profile_for_ui_label
# ──────────────────────────────────────────────────────────────


class TestGhProfileForUiLabel:
    """Map human-readable UI label to GraphHopper profile name."""

    def test_recommended_returns_truck(self):
        assert gh_profile_for_ui_label("Recommended") == "truck"

    def test_fastest_returns_truck_fast(self):
        assert gh_profile_for_ui_label("Fastest") == "truck_fast"

    def test_cheapest_returns_truck_cheap(self):
        assert gh_profile_for_ui_label("Cheapest") == "truck_cheap"

    def test_safest_returns_truck_safe(self):
        assert gh_profile_for_ui_label("Safest") == "truck_safe"

    def test_shortest_returns_truck_short(self):
        assert gh_profile_for_ui_label("Shortest") == "truck_short"

    def test_unknown_label_returns_default_truck(self):
        assert gh_profile_for_ui_label("Unknown") == "truck"

    def test_empty_string_returns_default_truck(self):
        assert gh_profile_for_ui_label("") == "truck"

    def test_case_sensitive_mismatch(self):
        # Labels in Config are title-case; case matters
        assert gh_profile_for_ui_label("recommended") == "truck"
