"""CoPilotConfirmationModal — diff view + typed confirmation for Level 2+ actions.

Blueprint: §12.3.

Shows before/after diff for the affected entity where feasible.
Level 2: simple confirmation with warning.
Level 3: typed confirmation phrase required.
OCR multi-candidate: ranked pick-list with "none of these" escape hatch.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t
from ui.copilot.models import ExecutionStep
from ui.design_tokens import (
    BTN_HEIGHT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRIMARY,
    COLOR_BG_BASE,
    COLOR_BG_ELEVATED,
    COLOR_BG_HOVER,
    COLOR_BG_OVERLAY,
    COLOR_BORDER_MEDIUM,
    COLOR_BORDER_SUBTLE,
    COLOR_ERROR_DEFAULT,
    COLOR_ERROR_SUBTLE,
    COLOR_ERROR_TEXT,
    COLOR_SUCCESS_DEFAULT,
    COLOR_SUCCESS_SUBTLE,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_DEFAULT,
    COLOR_WARNING_SUBTLE,
    COLOR_WARNING_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XS,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    INPUT_HEIGHT,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_2,
    SPACE_3,
    SPACE_4,
    SPACE_5,
    SPACE_6,
)


class CoPilotConfirmationModal(QDialog):
    """Modal dialog for confirming Co-Pilot actions.

    Supports three modes:
      1. Step review with before/after diff.
      2. Level 2/3 confirmation with optional typed phrase for Level 3.
      3. OCR multi-candidate ranked pick-list.

    Args:
        parent: Optional parent widget.
        steps: List of execution step dicts to be confirmed.
        confirmation_level: 2 (BUSINESS) or 3 (DESTRUCTIVE).
        confirmation_phrase: For Level 3, the phrase the user must type.
        ocr_candidates: Optional list of candidate strings for OCR disambiguation.
        summary_key: Optional translation key for the dialog subtitle.
        summary_params: Parameters for the summary translation.
    """

    confirmed = Signal()
    candidate_selected = Signal(int)  # -1 for "none of these"

    def __init__(
        self,
        parent: QWidget | None = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        confirmation_level: int = 2,
        confirmation_phrase: str = "",
        ocr_candidates: Optional[List[str]] = None,
        summary_key: str = "",
        summary_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("copilot.confirmation.title", default="Confirm Action"))
        self.setMinimumWidth(560)
        self.setMinimumHeight(400)
        self.setModal(True)
        self.setStyleSheet(f"background-color: {COLOR_BG_BASE};")

        self._steps = steps or []
        self._confirmation_level = confirmation_level
        self._confirmation_phrase = confirmation_phrase
        self._ocr_candidates = ocr_candidates or []
        self._summary_key = summary_key
        self._summary_params = summary_params or {}
        self._is_confirmed = False
        self._selected_candidate = -1

        self._build_ui()

    @classmethod
    def from_steps(
        cls,
        steps: List[ExecutionStep],
        parent: QWidget | None = None,
        confirmation_level: int = 2,
        confirmation_phrase: str = "",
        summary_key: str = "",
        summary_params: Optional[Dict[str, Any]] = None,
    ) -> "CoPilotConfirmationModal":
        """Construct a confirmation modal from ExecutionStep dataclass instances.

        Converts each ExecutionStep to the internal dict format the modal
        expects, preserving tool_name, confirmation_level, and parameters.

        Args:
            steps: List of ExecutionStep objects to confirm.
            parent: Optional parent widget.
            confirmation_level: 2 (BUSINESS) or 3 (DESTRUCTIVE).
            confirmation_phrase: For Level 3, the phrase the user must type.
            summary_key: Optional translation key for the dialog subtitle.
            summary_params: Parameters for the summary translation.

        Returns:
            A configured CoPilotConfirmationModal instance.
        """
        step_dicts: List[Dict[str, Any]] = []
        for step in steps:
            step_dicts.append({
                "tool_name": step.tool_name,
                "confirmation_level": int(step.confirmation_level),
                "parameters": dict(step.parameters),
                "before": None,
                "after": None,
            })
        return cls(
            parent=parent,
            steps=step_dicts,
            confirmation_level=confirmation_level,
            confirmation_phrase=confirmation_phrase,
            summary_key=summary_key,
            summary_params=summary_params,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACE_5)
        layout.setContentsMargins(SPACE_6, SPACE_6, SPACE_6, SPACE_5)

        # ── Header ───────────────────────────────────────────────────
        if self._summary_key:
            header_text = t(
                self._summary_key,
                default="Review the proposed action:",
                **self._summary_params,
            )
        else:
            header_text = t(
                "copilot.confirmation.review", default="Review the proposed action:"
            )
        header = QLabel(header_text)
        header.setWordWrap(True)
        header.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_LG}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
        )
        layout.addWidget(header)

        # ── Content area (steps or OCR) ──────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(SPACE_3)

        if self._ocr_candidates:
            ocr_widget = self._build_ocr_section()
            scroll_layout.addWidget(ocr_widget)
        elif self._steps:
            for i, step in enumerate(self._steps):
                step_frame = self._build_step_card(i, step)
                scroll_layout.addWidget(step_frame)
        else:
            no_conf = QLabel(
                t(
                    "copilot.confirmation.no_confirmation_needed",
                    default="No confirmation needed",
                )
            )
            no_conf.setStyleSheet(
                f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_BASE}px;"
            )
            scroll_layout.addWidget(no_conf)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # ── Warnings / typed confirmation ──────────────────────────────
        if self._ocr_candidates:
            # OCR mode: no level warnings, selection handled by pick-list
            pass
        elif self._confirmation_level >= 3:
            warning_text = t(
                "copilot.confirmation.level_3_warning",
                default="This action is IRREVERSIBLE. Type the {label} to confirm:",
                label=self._confirmation_phrase or "",
            )
            warning_lbl = QLabel(warning_text)
            warning_lbl.setWordWrap(True)
            warning_lbl.setStyleSheet(
                f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
                f"background-color: {COLOR_ERROR_SUBTLE}; border: 1px solid {COLOR_ERROR_DEFAULT}; "
                f"border-radius: {RADIUS_MD}px; padding: {SPACE_3}px;"
            )
            layout.addWidget(warning_lbl)

            self._phrase_input = QLineEdit()
            self._phrase_input.setPlaceholderText(
                t(
                    "copilot.confirmation.type_phrase",
                    default="Type '{phrase}' to confirm",
                    phrase=self._confirmation_phrase,
                )
            )
            self._phrase_input.setStyleSheet(
                f"""
                QLineEdit {{
                    background-color: {COLOR_BG_OVERLAY};
                    border: 1px solid {COLOR_BORDER_MEDIUM};
                    border-radius: {RADIUS_MD}px;
                    color: {COLOR_TEXT_PRIMARY};
                    padding: {SPACE_2}px {SPACE_3}px;
                    font-size: {FONT_SIZE_BASE}px;
                    height: {INPUT_HEIGHT}px;
                }}
                QLineEdit:focus {{
                    border-color: {COLOR_ACCENT_PRIMARY};
                }}
                """
            )
            self._phrase_input.textChanged.connect(self._on_phrase_changed)
            layout.addWidget(self._phrase_input)
        else:
            warning_lbl = QLabel(
                t(
                    "copilot.confirmation.level_2_warning",
                    default="This action will modify business data.",
                )
            )
            warning_lbl.setWordWrap(True)
            warning_lbl.setStyleSheet(
                f"color: {COLOR_WARNING_TEXT}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_MEDIUM}; "
                f"background-color: {COLOR_WARNING_SUBTLE}; border: 1px solid {COLOR_WARNING_DEFAULT}; "
                f"border-radius: {RADIUS_MD}px; padding: {SPACE_3}px;"
            )
            layout.addWidget(warning_lbl)

        # ── Buttons ──────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(SPACE_4)

        cancel_btn = QPushButton(t("copilot.confirmation.cancel", default="Cancel"))
        cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_2}px {SPACE_5}px;
                font-size: {FONT_SIZE_BASE}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                height: {BTN_HEIGHT}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BG_HOVER};
                border-color: {COLOR_BORDER_MEDIUM};
            }}
            """
        )
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._confirm_btn = QPushButton(t("copilot.confirmation.confirm", default="Confirm"))
        default_enabled = self._confirmation_level < 3 and not self._ocr_candidates
        self._confirm_btn.setEnabled(default_enabled)
        self._confirm_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_PRIMARY};
                color: white;
                border: none;
                border-radius: {RADIUS_MD}px;
                padding: {SPACE_2}px {SPACE_5}px;
                font-size: {FONT_SIZE_BASE}px;
                font-weight: {FONT_WEIGHT_MEDIUM};
                height: {BTN_HEIGHT}px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {COLOR_BG_OVERLAY};
                color: {COLOR_TEXT_TERTIARY};
            }}
            """
        )
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self._confirm_btn)

        layout.addLayout(btn_layout)

    def _build_step_card(self, index: int, step: Dict[str, Any]) -> QFrame:
        """Build a card showing a single step's details and optional diff."""
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLOR_BG_ELEVATED};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_MD}px;
            }}
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SPACE_4, SPACE_3, SPACE_4, SPACE_3)
        card_layout.setSpacing(SPACE_3)

        # Header row: tool name + level badge
        header_row = QHBoxLayout()
        tool_name = step.get("tool_name", "unknown")
        tool_lbl = QLabel(f"{index + 1}. {tool_name}")
        tool_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_MEDIUM};"
        )

        level = step.get("confirmation_level", 2)
        is_destructive = level >= 3
        level_badge = QLabel("DESTRUCTIVE" if is_destructive else "BUSINESS")
        badge_bg = COLOR_ERROR_SUBTLE if is_destructive else COLOR_SUCCESS_SUBTLE
        badge_text = COLOR_ERROR_TEXT if is_destructive else COLOR_SUCCESS_TEXT
        badge_border = COLOR_ERROR_DEFAULT if is_destructive else COLOR_SUCCESS_DEFAULT
        level_badge.setStyleSheet(
            f"""
            background-color: {badge_bg};
            color: {badge_text};
            border: 1px solid {badge_border};
            border-radius: {RADIUS_SM}px;
            padding: 2px {SPACE_2}px;
            font-size: {FONT_SIZE_XS}px;
            font-weight: {FONT_WEIGHT_BOLD};
            """
        )
        header_row.addWidget(tool_lbl)
        header_row.addWidget(level_badge)
        header_row.addStretch()
        card_layout.addLayout(header_row)

        # Diff view
        before = step.get("before")
        after = step.get("after")
        if before is not None or after is not None:
            diff_widget = self._build_diff_widget(before, after)
            card_layout.addWidget(diff_widget)
        else:
            params = step.get("parameters", {})
            if params:
                redacted_params = self._redact_params(params)
                params_text = ", ".join(
                    f"{k}={v}" for k, v in redacted_params.items() if v is not None
                )
                params_lbl = QLabel(params_text)
                params_lbl.setWordWrap(True)
                params_lbl.setStyleSheet(
                    f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_SM}px;"
                )
                card_layout.addWidget(params_lbl)

        return card

    @staticmethod
    def _redact_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Replace sensitive parameter values with asterisks.

        Sensitive keys: password, token, secret, key, auth, credential.
        Matching is case-insensitive substring check on the key name.
        """
        SENSITIVE = {"password", "token", "secret", "key", "auth", "credential"}
        redacted: Dict[str, Any] = {}
        for k, v in params.items():
            if any(sensitive in k.lower() for sensitive in SENSITIVE):
                redacted[k] = "****"
            else:
                redacted[k] = v
        return redacted

    def _build_diff_widget(self, before: Any, after: Any) -> QWidget:
        """Render a before/after diff panel."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(SPACE_2)
        layout.setContentsMargins(0, 0, 0, 0)

        # Before
        before_frame = QFrame()
        before_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLOR_ERROR_SUBTLE};
                border: 1px solid {COLOR_ERROR_DEFAULT};
                border-radius: {RADIUS_SM}px;
            }}
            """
        )
        before_layout = QVBoxLayout(before_frame)
        before_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        before_header = QLabel(t("copilot.confirmation.diff_before", default="Before"))
        before_header.setStyleSheet(
            f"color: {COLOR_ERROR_TEXT}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_BOLD};"
        )
        before_layout.addWidget(before_header)
        before_value = QLabel(self._format_value(before))
        before_value.setWordWrap(True)
        before_value.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px;")
        before_layout.addWidget(before_value)
        layout.addWidget(before_frame)

        # After
        after_frame = QFrame()
        after_frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLOR_SUCCESS_SUBTLE};
                border: 1px solid {COLOR_SUCCESS_DEFAULT};
                border-radius: {RADIUS_SM}px;
            }}
            """
        )
        after_layout = QVBoxLayout(after_frame)
        after_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        after_header = QLabel(t("copilot.confirmation.diff_after", default="After"))
        after_header.setStyleSheet(
            f"color: {COLOR_SUCCESS_TEXT}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_BOLD};"
        )
        after_layout.addWidget(after_header)
        after_value = QLabel(self._format_value(after))
        after_value.setWordWrap(True)
        after_value.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px;")
        after_layout.addWidget(after_value)
        layout.addWidget(after_frame)

        return container

    def _format_value(self, value: Any) -> str:
        """Pretty-format a diff value."""
        if value is None:
            return "-"
        if isinstance(value, dict):
            return "\n".join(f"  {k}: {v}" for k, v in value.items())
        return str(value)

    def _build_ocr_section(self) -> QWidget:
        """Build a ranked pick-list for OCR candidates with a 'none of these' option."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(SPACE_3)
        layout.setContentsMargins(0, 0, 0, 0)

        prompt = QLabel(
            t(
                "copilot.confirmation.select_candidate",
                default="Select the correct match:",
            )
        )
        prompt.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px; font-weight: {FONT_WEIGHT_MEDIUM};"
        )
        layout.addWidget(prompt)

        self._ocr_group = QButtonGroup(self)

        for i, candidate in enumerate(self._ocr_candidates):
            row = QFrame()
            row.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {COLOR_BG_OVERLAY};
                    border: 1px solid {COLOR_BORDER_SUBTLE};
                    border-radius: {RADIUS_MD}px;
                }}
                QFrame:hover {{
                    background-color: {COLOR_BG_HOVER};
                    border-color: {COLOR_BORDER_MEDIUM};
                }}
                """
            )
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)

            radio = QRadioButton()
            radio.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
            self._ocr_group.addButton(radio, i)

            rank_lbl = QLabel(f"#{i + 1}")
            rank_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_TERTIARY}; font-size: {FONT_SIZE_SM}px; font-weight: {FONT_WEIGHT_BOLD};"
            )

            candidate_lbl = QLabel(str(candidate))
            candidate_lbl.setStyleSheet(
                f"color: {COLOR_TEXT_PRIMARY}; font-size: {FONT_SIZE_BASE}px;"
            )
            candidate_lbl.setWordWrap(True)

            row_layout.addWidget(radio)
            row_layout.addWidget(rank_lbl)
            row_layout.addWidget(candidate_lbl, 1)
            layout.addWidget(row)

        # "None of these" escape hatch
        none_row = QFrame()
        none_row.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLOR_BG_OVERLAY};
                border: 1px solid {COLOR_BORDER_SUBTLE};
                border-radius: {RADIUS_MD}px;
            }}
            QFrame:hover {{
                background-color: {COLOR_BG_HOVER};
                border-color: {COLOR_BORDER_MEDIUM};
            }}
            """
        )
        none_layout = QHBoxLayout(none_row)
        none_layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)

        none_radio = QRadioButton()
        none_radio.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY};")
        self._ocr_group.addButton(none_radio, -1)

        none_lbl = QLabel(
            t("copilot.confirmation.none_of_these", default="None of these")
        )
        none_lbl.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: {FONT_SIZE_BASE}px; font-style: italic;"
        )

        none_layout.addWidget(none_radio)
        none_layout.addWidget(none_lbl, 1)
        layout.addWidget(none_row)

        self._ocr_group.buttonClicked.connect(self._on_candidate_changed)

        return container

    def _on_phrase_changed(self, text: str) -> None:
        """Enable confirm button only when typed phrase matches."""
        if self._confirmation_level >= 3:
            self._confirm_btn.setEnabled(text.strip() == self._confirmation_phrase)

    def _on_candidate_changed(self) -> None:
        """Enable confirm button when any OCR candidate (or none) is selected."""
        if self._ocr_candidates:
            self._confirm_btn.setEnabled(True)

    def _on_confirm(self) -> None:
        self._is_confirmed = True
        if self._ocr_candidates and hasattr(self, "_ocr_group"):
            self._selected_candidate = self._ocr_group.checkedId()
            self.candidate_selected.emit(self._selected_candidate)
        self.confirmed.emit()
        self.accept()

    @property
    def is_confirmed(self) -> bool:
        return self._is_confirmed

    @property
    def selected_candidate(self) -> int:
        """Selected OCR candidate index, or -1 for 'none of these'."""
        return self._selected_candidate
