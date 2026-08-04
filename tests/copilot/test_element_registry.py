"""Tests for element_registry module — symbolic ID ↔ objectName mapping.

Blueprint: §34.3 — Stable UI Element IDs.
"""

from __future__ import annotations

import pytest
from ui.copilot import element_registry


# ── Sample scripts for validate_script_targets tests ────────────────

SAMPLE_SCRIPTS = [
    {
        "workflow_id": "test_flow",
        "steps": [
            {"step_id": "s1", "target_element_id": "nav_overview"},
            {"step_id": "s2", "target_element_id": "btn_add_driver"},
        ],
    },
    {
        "workflow_id": "bad_flow",
        "steps": [
            {"step_id": "s1", "target_element_id": "NONEXISTENT"},
        ],
    },
]

# Unique prefix to avoid collision with real registry entries.
_TMP_PREFIX = "tmp_test_er_"


# ── TestResolveElement ───────────────────────────────────────────────

class TestResolveElement:
    """Forward lookup: symbolic ID → widget objectName."""

    def test_resolve_known_element(self) -> None:
        assert element_registry.resolve_element("nav_overview") == "sidebar-item-overview"

    def test_resolve_unknown_element(self) -> None:
        assert element_registry.resolve_element("nonexistent") is None

    def test_resolve_empty_string(self) -> None:
        assert element_registry.resolve_element("") is None


# ── TestResolveObjectName ────────────────────────────────────────────

class TestResolveObjectName:
    """Reverse lookup: widget objectName → symbolic ID."""

    def test_reverse_lookup_known(self) -> None:
        assert element_registry.resolve_object_name("sidebar-item-overview") == "nav_overview"

    def test_reverse_lookup_unknown(self) -> None:
        assert element_registry.resolve_object_name("nonexistent-object-name") is None

    def test_bidirectional_consistency(self) -> None:
        """Every ELEMENT_REGISTRY[k] == v must imply resolve_object_name(v) == k."""
        for symbolic_id, object_name in element_registry.ELEMENT_REGISTRY.items():
            assert (
                element_registry.resolve_object_name(object_name) == symbolic_id
            ), f"Reverse lookup failed for {symbolic_id} -> {object_name}"


# ── TestRegisterElement ──────────────────────────────────────────────

class TestRegisterElement:
    """Dynamic registration of new element mappings."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _remove(symbolic_id: str, object_name: str) -> None:
        """Safely remove one mapping from both dicts."""
        element_registry.ELEMENT_REGISTRY.pop(symbolic_id, None)
        element_registry._OBJECT_NAME_TO_SYMBOLIC.pop(object_name, None)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_register_new_element(self) -> None:
        sid = _TMP_PREFIX + "new"
        obj = _TMP_PREFIX + "new_obj"
        try:
            element_registry.register_element(sid, obj)
            assert element_registry.resolve_element(sid) == obj
            assert element_registry.resolve_object_name(obj) == sid
        finally:
            self._remove(sid, obj)

    def test_register_overwrites_existing(self) -> None:
        """Re-registering the same symbolic_id updates the forward map
        and adds an entry for the new objectName in the reverse map.
        (Note: the old objectName entry in the reverse map is *not*
        removed by the current implementation.)"""
        sid = _TMP_PREFIX + "ow"
        obj_a = _TMP_PREFIX + "ow_a"
        obj_b = _TMP_PREFIX + "ow_b"
        try:
            element_registry.register_element(sid, obj_a)
            element_registry.register_element(sid, obj_b)

            # Forward now points at the new objectName
            assert element_registry.resolve_element(sid) == obj_b

            # New objectName resolves correctly
            assert element_registry.resolve_object_name(obj_b) == sid
        finally:
            self._remove(sid, obj_b)
            self._remove(sid, obj_a)

    def test_register_creates_reverse_too(self) -> None:
        """After register_element, resolve_object_name(new_obj_name) works."""
        sid = _TMP_PREFIX + "rev"
        obj = _TMP_PREFIX + "rev_obj"
        try:
            element_registry.register_element(sid, obj)
            assert element_registry.resolve_object_name(obj) == sid
        finally:
            self._remove(sid, obj)


# ── TestValidateScriptTargets ────────────────────────────────────────

class TestValidateScriptTargets:
    """CI validation that every target_element_id in scripts resolves."""

    def test_validate_all_present(self) -> None:
        """Supply scripts where every target_element_id is valid → returns []."""
        scripts = [
            {
                "workflow_id": "wf1",
                "steps": [
                    {"step_id": "a", "target_element_id": "nav_overview"},
                    {"step_id": "b", "target_element_id": "btn_add_driver"},
                ],
            },
        ]
        assert element_registry.validate_script_targets(scripts) == []

    def test_validate_some_missing(self) -> None:
        """Supply scripts with an unknown target → returns list with one entry."""
        missing = element_registry.validate_script_targets(SAMPLE_SCRIPTS)
        assert len(missing) == 1
        assert "bad_flow" in missing[0]
        assert "NONEXISTENT" in missing[0]

    def test_validate_empty_scripts(self) -> None:
        """Empty list of scripts → returns []."""
        assert element_registry.validate_script_targets([]) == []

    def test_validate_no_steps(self) -> None:
        """Script with an empty 'steps' list → returns []."""
        scripts = [{"workflow_id": "wf1", "steps": []}]
        assert element_registry.validate_script_targets(scripts) == []

    def test_validate_none_target(self) -> None:
        """Step whose target_element_id is None → skipped without error."""
        scripts = [
            {
                "workflow_id": "wf1",
                "steps": [
                    {"step_id": "a", "target_element_id": None},
                    {"step_id": "b", "target_element_id": "nav_overview"},
                ],
            },
        ]
        assert element_registry.validate_script_targets(scripts) == []
