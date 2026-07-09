"""Team / User Management view for Operion ERP.

Provides an interface for inviting new team members and managing
existing users (deactivation, role changes).  Uses placeholder
methods for API integration — no real backend calls yet.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ui.base_view import BaseView
from ui.components import Btn
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

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the full view layout inside a scrollable container."""
        self._container = QWidget()
        self._container.setObjectName("team-view-container")
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(SP["10"], SP["6"], SP["10"], SP["10"])
        layout.setSpacing(SP["6"])
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
        card.setProperty("role", "card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])
        cl.setSpacing(SP["3"])

        # Title
        title = QLabel("Add User")
        title.setProperty("fontRole", "h2")
        cl.addWidget(title)

        # Subtitle
        subtitle = QLabel("Invite a new team member")
        subtitle.setProperty("fontRole", "muted")
        cl.addWidget(subtitle)

        # Form fields
        self._email_input = StyledLineEdit(placeholder="email@example.com")
        cl.addWidget(field(card, "EMAIL", self._email_input))

        self._password_input = StyledLineEdit(placeholder="\u2022" * 8)
        self._password_input.setEchoMode(StyledLineEdit.EchoMode.Password)
        cl.addWidget(field(card, "PASSWORD", self._password_input))

        self._role_combo = StyledComboBox(values=["Dispatcher", "Driver"])
        self._role_combo.currentTextChanged.connect(self._on_role_changed)
        cl.addWidget(field(card, "ROLE", self._role_combo))

        self._driver_combo = StyledComboBox(values=[])
        self._driver_combo_label = field(card, "LINK DRIVER", self._driver_combo)
        self._driver_combo_label.setVisible(False)
        cl.addWidget(self._driver_combo_label)

        # Add User button — right-aligned
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.addStretch()
        self._add_btn = Btn(
            btn_row,
            "Add User",
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
        card.setProperty("role", "card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(SP["4"], SP["5"], SP["4"], SP["5"])
        cl.setSpacing(SP["3"])

        # Title
        title = QLabel("Team Members")
        title.setProperty("fontRole", "h2")
        cl.addWidget(title)

        # Subtitle
        subtitle = QLabel("Manage existing users")
        subtitle.setProperty("fontRole", "muted")
        cl.addWidget(subtitle)

        # Table — last column (Actions) stretches
        columns: list[tuple] = [
            ("email",   "Email",    200),
            ("role",    "Role",     100),
            ("status",  "Status",   100),
            ("created", "Created",  140),
            ("actions", "Actions",   80),
        ]
        self._table = StyledTableWidget(card, columns=columns)
        cl.addWidget(self._table)

        parent_layout.addWidget(card)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_role_changed(self, role: str) -> None:
        """Show or hide the Link Driver field based on the selected role."""
        visible = role == "Driver"
        self._driver_combo_label.setVisible(visible)

    def _on_add_user(self) -> None:
        """Validate the form and add a new user."""
        email = self._email_input.text().strip()
        password = self._password_input.text()
        role = self._role_combo.currentText()

        if not email:
            QMessageBox.warning(self, "Validation", "Email is required.")
            return
        if not password:
            QMessageBox.warning(self, "Validation", "Password is required.")
            return

        driver_plate: str | None = None
        if role == "Driver":
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
            "Deactivate User",
            f"Are you sure you want to deactivate {email}?",
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
            elif self.db is not None:
                from database.db_manager import DatabaseManager
                if isinstance(self.db, DatabaseManager):
                    db_rows = self.db.conn.execute(
                        "SELECT id, email, role, display_name, is_active, created_at FROM users ORDER BY role, email"
                    ).fetchall()
                    rows = [dict(r) for r in db_rows]
        except Exception as exc:
            logger.error("Failed to load users: %s", exc)

        self._table.set_data(rows)

        # Add Deactivate buttons to each row's Actions column
        actions_col = len(self._table._column_ids) - 1
        for r in range(self._table.rowCount()):
            row_data: dict[str, Any] = {}
            if hasattr(self._table, '_data') and r < len(self._table._data):
                row_data = self._table._data[r]
            deactivate_btn = Btn(self._table, "Deactivate", variant="ghost", size="sm")
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
            elif self.db is not None:
                from backend.security import hash_password
                from database.db_manager import DatabaseManager
                if isinstance(self.db, DatabaseManager):
                    pwhash = hash_password(password)
                    self.db.conn.execute(
                        "INSERT INTO users (email, password_hash, role, is_active) VALUES (?, ?, ?, 1)",
                        (email.strip().lower(), pwhash, role.lower()),
                    )
                    self.db.conn.commit()
            QMessageBox.information(self, "Success", "User added successfully.")
        except Exception as exc:
            logger.error("Failed to add user: %s", exc)
            QMessageBox.warning(self, "Error", f"Failed to add user: {exc}")

    def _deactivate_user(self, row_data: dict[str, Any]) -> None:
        """Deactivate a user via the API or local database."""
        user_id = row_data.get("id")
        if not user_id:
            return
        try:
            if self._api_client is not None:
                self._api_client.deactivate_user(user_id)
            elif self.db is not None:
                from database.db_manager import DatabaseManager
                if isinstance(self.db, DatabaseManager):
                    self.db.conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
                    self.db.conn.commit()
        except Exception as exc:
            logger.error("Failed to deactivate user: %s", exc)
            QMessageBox.warning(self, "Error", f"Failed to deactivate user: {exc}")

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
