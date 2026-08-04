"""Team / User Management view for Operion ERP.

Provides an interface for inviting new team members and managing
existing users (deactivation, role changes).  Uses placeholder
methods for API integration — no real backend calls yet.
"""

from __future__ import annotations

import logging
from typing import Any

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from services.user_service import UserService
from ui.base_view import BaseView
from services.i18n import t
from ui.components import Btn, EmptyState, IconButton
from ui.design_tokens import SP
from ui.widgets import (
    StyledComboBox,
    StyledLineEdit,
    StyledTableWidget,
    field,
)

logger = logging.getLogger(__name__)


class QtTeamView(BaseView):
    """Team / User Management view.

    Sections:
        1. Add User — form to invite a new team member.
        2. Team Members — table of existing users with deactivate actions.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        db=None,
        api_client=None,
    ):
        super().__init__(parent)
        self.db = db
        self._api_client = api_client
        self._user_service = UserService(self.db) if db else None

        self._build_ui()
        self._register_i18n(self._on_language_changed)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the full view layout inside a scrollable container."""
        self.setAccessibleName("Team management")
        self._container = QWidget()
        self._container.setObjectName("team-view-container")
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(SP["10"], SP["6"], SP["10"], SP["10"])
        layout.setSpacing(SP["4"])
        layout.setAlignment(Qt.AlignTop)

        self._build_add_user_section(layout)
        self._build_team_members_section(layout)

        # Bottom spacer so content doesn't stretch to fill empty space
        layout.addStretch()

        self.setWidget(self._container)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

    # ── Section 1: Add User Card ──────────────────────────────────────────────

    def _build_add_user_section(self, parent_layout: QVBoxLayout) -> None:
        """Build the 'Add User' card with form fields."""
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("role", "card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])
        cl.setSpacing(SP["3"])

        # Title
        title = QLabel(t("team.add_user"))
        title.setProperty("fontRole", "h2")
        cl.addWidget(title)

        # Subtitle
        subtitle = QLabel(t("team.invite_subtitle"))
        subtitle.setProperty("fontRole", "muted")
        cl.addWidget(subtitle)

        # Form fields
        self._email_input = StyledLineEdit(placeholder="email@example.com")
        cl.addWidget(field(card, t("team.email_label"), self._email_input))

        self._password_input = StyledLineEdit(placeholder="\u2022" * 8)
        self._password_input.setEchoMode(StyledLineEdit.EchoMode.Password)
        cl.addWidget(field(card, t("team.password_label"), self._password_input))

        self._role_combo = StyledComboBox(values=[t("team.role_dispatcher"), t("team.role_driver")])
        self._role_combo.currentTextChanged.connect(self._on_role_changed)
        cl.addWidget(field(card, t("team.role_label"), self._role_combo))

        self._driver_combo = StyledComboBox(values=[])
        self._driver_combo_label = field(card, t("team.link_driver_label"), self._driver_combo)
        self._driver_combo_label.setVisible(False)
        cl.addWidget(self._driver_combo_label)

        # Add User button — right-aligned
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.addStretch()
        self._add_btn = Btn(
            btn_row,
            t("team.add_user"),
            variant="primary",
            command=self._on_add_user,
        )
        btn_row_layout.addWidget(self._add_btn)
        cl.addWidget(btn_row)

        parent_layout.addWidget(card)

    # ── Section 2: Team Members Card ──────────────────────────────────────────

    def _build_team_members_section(self, parent_layout: QVBoxLayout) -> None:
        """Build the 'Team Members' card with user table."""
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("role", "card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])
        cl.setSpacing(SP["3"])

        # Title
        title = QLabel(t("team.members_title"))
        title.setProperty("fontRole", "h2")
        cl.addWidget(title)

        # Subtitle
        subtitle = QLabel(t("team.members_subtitle"))
        subtitle.setProperty("fontRole", "muted")
        cl.addWidget(subtitle)

        # Density toggle
        density_row = QFrame()
        density_layout = QHBoxLayout(density_row)
        density_layout.setContentsMargins(0, 0, 0, 0)
        density_layout.addStretch()
        self._density_btn = IconButton(
            density_row,
            icon_name="fa5s.table",
            tooltip=t("table.density", "Row density"),
            variant="ghost",
            size=32,
        )
        self._density_btn.clicked.connect(self._show_density_menu)
        density_layout.addWidget(self._density_btn)
        cl.addWidget(density_row)

        # Table — last column (Actions) stretches
        columns: list[tuple] = [
            ("email",   t("team.col_email"),    200),
            ("role",    t("team.col_role"),     100),
            ("status",  t("team.col_status"),   100),
            ("created", t("team.col_created"),  140),
            ("actions", t("team.col_actions"),   80),
        ]
        self._table = StyledTableWidget(card, columns=columns, prefs_key="team_view")
        self._table.setAccessibleName("Team members table")
        cl.addWidget(self._table)

        # Empty state (hidden when table has data)
        self._empty_state = EmptyState(
            parent=card,
            icon_name="fa5s.users",
            title=t("team.empty_title", "No team members"),
            subtitle=t("team.empty_desc", "Invite team members to collaborate."),
        )
        self._empty_state.setVisible(False)
        cl.addWidget(self._empty_state)

        parent_layout.addWidget(card)

    # ── Density menu ──────────────────────────────────────────────────────

    def _show_density_menu(self):
        """Show row density menu for the team members table."""
        menu = self._table._build_density_menu(self._density_btn)
        if menu:
            menu.exec_(self._density_btn.mapToGlobal(
                self._density_btn.rect().bottomLeft()
            ))

    # ── Context menu ──────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        """Right-click context menu for the team members table."""
        index = self._table.indexAt(event.pos())
        if not index.isValid():
            return

        row = index.row()
        record = self._table._data[row] if 0 <= row < len(self._table._data) else None
        if record is None:
            return

        menu = QMenu(self)

        # Deactivate action
        deact_action = QAction(qta.icon("fa5s.user-slash"), t("team.deactivate"), self)
        deact_action.triggered.connect(lambda: self._on_deactivate_user(record))
        menu.addAction(deact_action)

        menu.exec_(event.globalPos())

    # ── i18n ──────────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang: str) -> None:
        """Rebuild UI text when language changes, preserving form state."""
        # Save form state
        email = self._email_input.text()
        password = self._password_input.text()
        role_index = self._role_combo.currentIndex()

        # Remove old container so rebuild is clean
        old = self.widget()
        if old is not None:
            old.setParent(None)
            old.deleteLater()

        # Rebuild UI with new translations
        self._build_ui()

        # Restore form state
        self._email_input.setText(email)
        self._password_input.setText(password)
        self._role_combo.setCurrentIndex(role_index)

        # Reload users to refresh table headers and deactivate buttons
        self._load_users()

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_role_changed(self, role: str) -> None:
        """Show or hide the Link Driver field based on the selected role."""
        visible = role == t("team.role_driver")
        self._driver_combo_label.setVisible(visible)

    def _on_add_user(self) -> None:
        """Validate the form and add a new user."""
        email = self._email_input.text().strip()
        password = self._password_input.text()
        role = self._role_combo.currentText()

        if not email:
            QMessageBox.warning(self, t("team.validation_title"), t("team.validation_email_required"))
            return
        if not password:
            QMessageBox.warning(self, t("team.validation_title"), t("team.validation_password_required"))
            return

        driver_plate: str | None = None
        if role == t("team.role_driver"):
            plate = self._driver_combo.currentText().strip()
            if plate:
                driver_plate = plate

        self._add_user(email, password, role, driver_plate)
        self._clear_form()
        self._load_users()

    def _on_deactivate_user(self, row_data: dict[str, Any]) -> None:
        """Deactivate a user after user confirmation."""
        email = row_data.get("email", "")
        reply = QMessageBox.question(
            self,
            t("team.deactivate_title"),
            t("team.deactivate_confirm", email=email),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._deactivate_user(row_data)
        self._load_users()

    # ── Placeholder API methods ───────────────────────────────────────────────

    def _load_users(self) -> None:
        """Fetch users from the API and populate the table."""
        rows: list[dict[str, Any]] = []
        try:
            if self._api_client is not None:
                result = self._api_client.list_users()
                rows = result.get("items", [])
            elif self._user_service is not None:
                rows = self._user_service.list_users()
        except Exception as exc:
            logger.error("Failed to load users: %s", exc)

        has_rows = bool(rows)
        self._table.setVisible(has_rows)
        self._empty_state.setVisible(not has_rows)
        if not has_rows:
            return

        self._table.set_data(rows)
        self._table.restore_column_widths()

        # Add Deactivate buttons to each row's Actions column
        actions_col = len(self._table._column_ids) - 1
        for r in range(self._table.rowCount()):
            row_data: dict[str, Any] = {}
            if hasattr(self._table, '_data') and r < len(self._table._data):
                row_data = self._table._data[r]
            deactivate_btn = Btn(self._table, t("team.deactivate"), variant="ghost", size="sm")
            deactivate_btn.clicked.connect(
                lambda checked=False, rd=row_data: self._on_deactivate_user(rd)
            )
            self._table.setCellWidget(r, actions_col, deactivate_btn)

    def _add_user(
        self,
        email: str,
        password: str,
        role: str,
        driver_plate: str | None = None,
    ) -> None:
        """Add a new user via the API or local database."""
        try:
            if self._api_client is not None:
                display_name = email.split("@")[0]
                self._api_client.create_user(
                    email=email.strip().lower(),
                    password=password,
                    role=role.lower(),
                    display_name=display_name,
                )
            elif self._user_service is not None:
                display_name = email.split("@")[0]
                self._user_service.create_user(
                    email.strip().lower(), password, role.lower(), display_name,
                )
            QMessageBox.information(self, t("team.success_title", "Success"), t("team.success_user_added"))
        except Exception as exc:
            logger.error("Failed to add user: %s", exc)
            QMessageBox.warning(self, t("common.error", "Error"), t("team.error_failed_add", "Failed to add user: {}", exc))

    def _deactivate_user(self, row_data: dict[str, Any]) -> None:
        """Deactivate a user via the API or local database."""
        user_id = row_data.get("id")
        if not user_id:
            return
        try:
            if self._api_client is not None:
                self._api_client.deactivate_user(user_id)
            elif self._user_service is not None:
                self._user_service.deactivate_user(user_id)
        except Exception as exc:
            logger.error("Failed to deactivate user: %s", exc)
            QMessageBox.warning(self, t("common.error", "Error"), t("team.error_failed_deactivate", "Failed to deactivate user: {}", exc))

    # ── Form helpers ──────────────────────────────────────────────────────────

    def _clear_form(self) -> None:
        """Reset the Add User form to its initial state."""
        self._email_input.clear()
        self._password_input.clear()
        self._role_combo.setCurrentIndex(0)
        self._driver_combo.clear()
        self._driver_combo_label.setVisible(False)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _load_data(self) -> None:
        """Load initial data when the view becomes active."""
        self._load_users()

    def wakeup(self) -> None:
        """Called when this view becomes active (tab switch, etc.)."""
        super().wakeup()
