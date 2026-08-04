"""Shared form-building utilities for Operion ERP."""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from ui.design_tokens import (
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_TEXT,
    COLOR_TEXT_TERTIARY,
    FONT_SIZE_SM,
    SPACE_1,
)


def add_required_indicator(label: QLabel) -> None:
    """Append a red asterisk to a field label to indicate it's required."""
    current = label.text()
    if current and not current.strip().endswith("*"):
        label.setText(f"{current}  *")
        label.setStyleSheet(
            f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_SM}px;"
        )


class FormField(QWidget):
    """A labeled input with optional helper text and inline error message.

    Layout::

        [label *]
        [input       ]
        [helper text ]  or  [error message in red]

    Use ``.value()`` to get the current text and ``.validate()`` to run
    the configured validator.
    """

    VALIDATORS: dict[str, Callable[[str], str | None]] = {
        "required": lambda v: "This field is required" if not v.strip() else None,
        "email": (
            lambda v: None
            if not v or ("@" in v and "." in v.split("@")[-1])
            else "Enter a valid email address"
        ),
        "phone": (
            lambda v: None
            if not v or len(v.strip()) >= 7
            else "Enter a valid phone number"
        ),
        "vat": (
            lambda v: None
            if not v or len(v.strip()) >= 4
            else "Enter a valid VAT number"
        ),
        "numeric": (
            lambda v: None
            if not v
            or v.replace(",", ".")
            .replace(" ", "")
            .replace("-", "")
            .replace(".", "", 1)
            .isdigit()
            else "Must be a number"
        ),
    }

    def __init__(
        self,
        parent=None,
        label: str = "",
        field_type: str = "required",
        placeholder: str = "",
        helper_text: str = "",
        default: str = "",
    ):
        super().__init__(parent)
        self._field_type = field_type
        self._validator = self.VALIDATORS.get(field_type)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_1)

        # Label
        self._label = QLabel(label)
        self._label.setProperty("role", "field-label")
        layout.addWidget(self._label)

        # Input
        self._input = QLineEdit()
        if placeholder:
            self._input.setPlaceholderText(placeholder)
        if default:
            self._input.setText(default)
        layout.addWidget(self._input)

        # Error label (hidden by default)
        self._error_label = QLabel()
        self._error_label.setProperty("role", "field-error")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        # Helper text label (shown when no error)
        self._helper_label: QLabel | None = None
        if helper_text:
            self._helper_label = QLabel(helper_text)
            self._helper_label.setProperty("role", "muted")
            layout.addWidget(self._helper_label)

        # Clear error on edit
        self._input.textChanged.connect(self._on_text_changed)

    # ── Public API ─────────────────────────────────────────────────────────

    def value(self) -> str:
        """Return the current input text."""
        return self._input.text()

    def set_text(self, text: str) -> None:
        """Set the input text without triggering persistent errors."""
        self._input.setText(text)

    def validate(self) -> bool:
        """Run validation, show error if invalid. Return True if valid."""
        if self._validator is None:
            self.clear_error()
            return True
        error = self._validator(self._input.text())
        if error is not None:
            self.set_error(error)
            return False
        self.clear_error()
        return True

    def set_error(self, message: str) -> None:
        """Display an inline error message and mark the input as invalid."""
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self._set_input_validation("error")
        if self._helper_label:
            self._helper_label.setVisible(False)

    def clear_error(self) -> None:
        """Hide the error message and reset the input validation state."""
        self._error_label.setVisible(False)
        self._set_input_validation("")
        if self._helper_label:
            self._helper_label.setVisible(True)

    def set_required(self, required: bool = True) -> None:
        """Add or remove the required-field indicator on the label."""
        if required:
            add_required_indicator(self._label)

    def input_widget(self) -> QLineEdit:
        """Return the inner QLineEdit for direct manipulation if needed."""
        return self._input

    @property
    def error_label(self) -> QLabel:
        return self._error_label

    @property
    def label_widget(self) -> QLabel:
        return self._label

    # ── Internals ──────────────────────────────────────────────────────────

    def _on_text_changed(self) -> None:
        """Clear validation state when the user types."""
        if self._error_label.isVisible():
            self.clear_error()

    def _set_input_validation(self, state: str) -> None:
        self._input.setProperty("validation", state)
        self._input.style().unpolish(self._input)
        self._input.style().polish(self._input)
