"""Tests for status_service — pure functions, no mocks needed."""

from __future__ import annotations

from services.status_service import (
    COLUMN_DEFS,
    STATUS_TO_COLUMN,
    VALID_TRANSITIONS,
    allowed_transitions,
    canonical_status,
    column_for_status,
    is_terminal,
    status_display_order,
)


# ── canonical_status ─────────────────────────────────────────────────


class TestCanonicalStatus:
    """Verify every known status string in STATUS_TO_COLUMN maps to its
    expected canonical value."""

    def test_canonical_status_known(self) -> None:
        """'InTransit' → 'In Transit'"""
        assert canonical_status("InTransit") == "In Transit"

    def test_canonical_status_planned_variants(self) -> None:
        """'Scheduled' / 'Pending' → 'Planned'"""
        assert canonical_status("Scheduled") == "Planned"
        assert canonical_status("Pending") == "Planned"

    def test_canonical_status_loading_variants(self) -> None:
        """'Preparing' / 'Pickup' → 'Loading'"""
        assert canonical_status("Preparing") == "Loading"
        assert canonical_status("Pickup") == "Loading"

    def test_canonical_status_in_transit_variants(self) -> None:
        """'Active' / 'InProgress' → 'In Transit'"""
        assert canonical_status("Active") == "In Transit"
        assert canonical_status("InProgress") == "In Transit"

    def test_canonical_status_delivered_variants(self) -> None:
        """'Completed' / 'Done' → 'Delivered'"""
        assert canonical_status("Completed") == "Delivered"
        assert canonical_status("Done") == "Delivered"

    def test_canonical_status_unknown_passthrough(self) -> None:
        """Unknown raw string is returned unchanged."""
        assert canonical_status("Unknown") == "Unknown"

    def test_canonical_status_consistency(self) -> None:
        """Every value in STATUS_TO_COLUMN is itself a valid key."""
        for raw, canon in STATUS_TO_COLUMN.items():
            assert canonical_status(canon) == canon, (
                f"Canonical value {canon!r} (from {raw!r}) is not stable"
            )


# ── allowed_transitions ─────────────────────────────────────────────


class TestAllowedTransitions:
    """Verify transition rules match VALID_TRANSITIONS."""

    def test_allowed_transitions_planned(self) -> None:
        assert allowed_transitions("Planned") == ["Loading", "Cancelled"]

    def test_allowed_transitions_loading(self) -> None:
        assert allowed_transitions("Loading") == VALID_TRANSITIONS["Loading"]

    def test_allowed_transitions_in_transit(self) -> None:
        assert allowed_transitions("In Transit") == VALID_TRANSITIONS["In Transit"]

    def test_allowed_transitions_delivered(self) -> None:
        assert allowed_transitions("Delivered") == VALID_TRANSITIONS["Delivered"]

    def test_allowed_transitions_cancelled(self) -> None:
        assert allowed_transitions("Cancelled") == VALID_TRANSITIONS["Cancelled"]

    def test_allowed_transitions_unknown_returns_empty(self) -> None:
        assert allowed_transitions("NonExistent") == []


# ── is_terminal ─────────────────────────────────────────────────────


class TestIsTerminal:
    """Terminal statuses: Delivered, Invoiced, Paid, Cancelled."""

    def test_is_terminal_delivered(self) -> None:
        assert is_terminal("Delivered") is True

    def test_is_terminal_invoiced(self) -> None:
        assert is_terminal("Invoiced") is True

    def test_is_terminal_paid(self) -> None:
        assert is_terminal("Paid") is True

    def test_is_terminal_cancelled(self) -> None:
        assert is_terminal("Cancelled") is True

    def test_is_terminal_planned(self) -> None:
        assert is_terminal("Planned") is False

    def test_is_terminal_loading(self) -> None:
        assert is_terminal("Loading") is False

    def test_is_terminal_in_transit(self) -> None:
        assert is_terminal("In Transit") is False

    def test_is_terminal_variant_maps_to_terminal(self) -> None:
        """'Completed' aliases to 'Delivered' which is terminal."""
        assert is_terminal("Completed") is True
        assert is_terminal("Done") is True


# ── column_for_status ───────────────────────────────────────────────


class TestColumnForStatus:
    """column_for_status is an alias for canonical_status."""

    def test_column_for_status_alias(self) -> None:
        """column_for_status returns the canonical column key."""
        assert column_for_status("InTransit") == "In Transit"
        assert column_for_status("Scheduled") == "Planned"
        assert column_for_status("Done") == "Delivered"
        assert column_for_status("Unknown") == "Unknown"


# ── status_display_order ────────────────────────────────────────────


class TestStatusDisplayOrder:
    """Ordered list of column keys from COLUMN_DEFS."""

    def test_status_display_order(self) -> None:
        expected = [c["key"] for c in COLUMN_DEFS]
        assert status_display_order() == expected

    def test_status_display_order_length(self) -> None:
        assert len(status_display_order()) == len(COLUMN_DEFS)
