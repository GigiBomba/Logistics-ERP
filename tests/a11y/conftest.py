"""Pytest fixtures and helpers for accessibility (a11y) tests."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QWidget


def assert_accessible_name(widget: QWidget, expected_name: str):
    """Assert that a widget's accessibleName matches the expected value."""
    actual = widget.accessibleName()
    assert actual == expected_name, (
        f"accessibleName mismatch for {type(widget).__name__}:\n"
        f"  Expected: '{expected_name}'\n"
        f"  Actual:   '{actual}'"
    )


def assert_accessible_name_not_empty(widget: QWidget):
    """Assert that a widget has a non-empty accessibleName."""
    actual = widget.accessibleName()
    assert actual, (
        f"accessibleName is empty for {type(widget).__name__} "
        f"(objectName='{widget.objectName() or 'not set'}')"
    )


def assert_accessible_description_not_empty(widget: QWidget):
    """Assert that a widget has a non-empty accessibleDescription."""
    actual = widget.accessibleDescription()
    assert actual, (
        f"accessibleDescription is empty for {type(widget).__name__} "
        f"(objectName='{widget.objectName() or 'not set'}')"
    )


def assert_accessible_role_is(widget: QWidget, expected_role: QAccessible.Role):
    """Assert widget's accessible role via QAccessible interface.

    Uses QAccessible.queryAccessibleInterface() because QWidget.accessibleRole()
    is not available in all PySide6 versions.
    """
    iface = QAccessible.queryAccessibleInterface(widget)
    assert iface is not None, (
        f"No QAccessibleInterface available for {type(widget).__name__}"
    )
    actual = iface.role()
    assert actual == expected_role, (
        f"accessibleRole mismatch for {type(widget).__name__}:\n"
        f"  Expected: {expected_role}\n"
        f"  Actual:   {actual}"
    )


def assert_widget_has_focus(widget: QWidget):
    """Assert that a widget currently has keyboard focus."""
    assert widget.hasFocus(), (
        f"{type(widget).__name__} should have focus but doesn't"
    )


def collect_focusable_children(parent: QWidget) -> list[QWidget]:
    """Return flat list of focusable descendant widgets in tab order."""
    focusable = []
    for child in parent.findChildren(QWidget):
        if child.focusPolicy() != Qt.FocusPolicy.NoFocus and child.isVisible():
            focusable.append(child)
    return focusable
