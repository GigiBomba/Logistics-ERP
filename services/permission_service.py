"""
PermissionService — centralized authorization layer.

All write operations across every service MUST check permissions through
this service. No permission checks in widgets, views, or repositories.
"""
from __future__ import annotations

import logging
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PermissionCheckResult:
    allowed: bool
    reason: str = ""  # why denied (empty if allowed)


class PermissionService:
    """
    Single source of truth for all permission checks.
    
    Usage in any service:
        perm = PermissionService(db)
        if not perm.can_create_dispatch(user_id).allowed:
            raise PermissionError("User cannot create dispatches")
    """
    
    # Role constants
    ROLE_ADMIN = "admin"
    ROLE_MANAGER = "manager"
    ROLE_DISPATCHER = "dispatcher"
    ROLE_DRIVER = "driver"
    
    def __init__(self, db):
        self.db = db
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    def _get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        """Fetch a user by ID."""
        from repositories.user_repository import UserRepository
        repo = UserRepository(self.db)
        return repo.get_by_id(user_id)
    
    def _is_admin(self, user_id: int) -> bool:
        user = self._get_user(user_id)
        return user is not None and user.get("role") == self.ROLE_ADMIN
    
    def _is_active(self, user_id: int) -> bool:
        user = self._get_user(user_id)
        return user is not None and user.get("is_active", False)
    
    # ------------------------------------------------------------------
    # General checks
    # ------------------------------------------------------------------
    
    def is_authenticated(self, user_id: int) -> PermissionCheckResult:
        """Check that the user exists and is active."""
        if user_id is None:
            return PermissionCheckResult(False, "User ID is required")
        user = self._get_user(user_id)
        if user is None:
            return PermissionCheckResult(False, "User not found")
        if not user.get("is_active", False):
            return PermissionCheckResult(False, "User is inactive")
        return PermissionCheckResult(True)
    
    # ------------------------------------------------------------------
    # Dispatch permissions
    # ------------------------------------------------------------------
    
    def can_create_dispatch(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_DISPATCHER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot create dispatches")
    
    def can_cancel_dispatch(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_dispatch(user_id)  # same roles
    
    # ------------------------------------------------------------------
    # Trip permissions
    # ------------------------------------------------------------------
    
    def can_create_trip(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_DISPATCHER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot create trips")
    
    def can_update_trip(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_trip(user_id)
    
    def can_delete_trip(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] == self.ROLE_ADMIN:
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, "Only admins can delete trips")
    
    # ------------------------------------------------------------------
    # Client permissions
    # ------------------------------------------------------------------
    
    def can_create_client(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot create clients")
    
    def can_update_client(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_client(user_id)
    
    def can_delete_client(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] == self.ROLE_ADMIN:
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, "Only admins can delete clients")
    
    def can_merge_clients(self, user_id: int) -> PermissionCheckResult:
        return self.can_delete_client(user_id)  # merge is destructive
    
    # ------------------------------------------------------------------
    # Fleet/Vehicle permissions
    # ------------------------------------------------------------------
    
    def can_create_vehicle(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot create vehicles")
    
    def can_update_vehicle(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_vehicle(user_id)
    
    def can_delete_vehicle(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] == self.ROLE_ADMIN:
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, "Only admins can delete vehicles")
    
    # ------------------------------------------------------------------
    # Driver permissions
    # ------------------------------------------------------------------
    
    def can_create_driver(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot create drivers")
    
    def can_update_driver(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_driver(user_id)
    
    def can_delete_driver(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] == self.ROLE_ADMIN:
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, "Only admins can delete drivers")
    
    # ------------------------------------------------------------------
    # Invoice permissions
    # ------------------------------------------------------------------
    
    def can_create_invoice(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot create invoices")
    
    def can_finalize_invoice(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_invoice(user_id)
    
    def can_cancel_invoice(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, "Only admins/managers can cancel invoices")
    
    # ------------------------------------------------------------------
    # Receipt permissions
    # ------------------------------------------------------------------
    
    def can_create_receipt(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_invoice(user_id)

    def can_update_receipt(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_invoice(user_id)

    # ------------------------------------------------------------------
    # Proforma permissions
    # ------------------------------------------------------------------
    
    def can_create_proforma(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_invoice(user_id)

    def can_update_proforma(self, user_id: int) -> PermissionCheckResult:
        return self.can_create_invoice(user_id)

    # ------------------------------------------------------------------
    # CMR permissions
    # ------------------------------------------------------------------
    
    def can_generate_cmr(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_DISPATCHER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot generate CMRs")
    
    # ------------------------------------------------------------------
    # Payment/Bulk CSV permissions
    # ------------------------------------------------------------------
    
    def can_generate_payments(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot generate bulk payments")
    
    # ------------------------------------------------------------------
    # Document permissions
    # ------------------------------------------------------------------
    
    def can_upload_document(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_DISPATCHER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot upload documents")
    
    def can_email_document(self, user_id: int) -> PermissionCheckResult:
        return self.can_upload_document(user_id)
    
    def can_delete_document(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, "Only admins/managers can delete documents")
    
    # ------------------------------------------------------------------
    # Export permissions
    # ------------------------------------------------------------------
    
    def can_export_data(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER, self.ROLE_DISPATCHER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot export data")
    
    # ------------------------------------------------------------------
    # AutoMail permissions
    # ------------------------------------------------------------------
    
    def can_send_email(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot send emails")
    
    # ------------------------------------------------------------------
    # Maintenance permissions
    # ------------------------------------------------------------------
    
    def can_schedule_maintenance(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot schedule maintenance")
    
    # ------------------------------------------------------------------
    # Analytics permissions
    # ------------------------------------------------------------------
    
    def can_view_analytics(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot view analytics")

    # ------------------------------------------------------------------
    # Team management permissions (blueprint §8.3, Phase 4A)
    # ------------------------------------------------------------------

    def can_manage_users(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot manage users")

    # ------------------------------------------------------------------
    # Company settings permissions (blueprint §8.3, Phase 4A)
    # ------------------------------------------------------------------

    def can_view_company_settings(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot view company settings")

    def can_manage_company_settings(self, user_id: int) -> PermissionCheckResult:
        auth = self.is_authenticated(user_id)
        if not auth.allowed:
            return auth
        user = self._get_user(user_id)
        if user["role"] in (self.ROLE_ADMIN, self.ROLE_MANAGER):
            return PermissionCheckResult(True)
        return PermissionCheckResult(False, f"Role '{user['role']}' cannot manage company settings")
