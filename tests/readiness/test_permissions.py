"""Tests for PermissionService — the centralized authorization layer.

All write operations across every service MUST check permissions through
this service. These tests verify the role-based access control rules.
"""
from unittest.mock import MagicMock

import pytest

from services.permission_service import PermissionService, PermissionCheckResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """A mock database connection — we never hit a real DB in these tests."""
    return MagicMock()


@pytest.fixture
def mock_users():
    """Return a dict of user_id → user dict representing the fake DB.

    Roles: 1=admin, 2=manager, 3=dispatcher, 4=driver, 5=inactive, 99=wrong-role
    """
    return {
        1: {"id": 1, "role": "admin", "is_active": True, "email": "admin@test.com", "display_name": "Admin"},
        2: {"id": 2, "role": "manager", "is_active": True, "email": "manager@test.com", "display_name": "Manager"},
        3: {"id": 3, "role": "dispatcher", "is_active": True, "email": "disp@test.com", "display_name": "Dispatcher"},
        4: {"id": 4, "role": "driver", "is_active": True, "email": "driver@test.com", "display_name": "Driver"},
        5: {"id": 5, "role": "admin", "is_active": False, "email": "inactive@test.com", "display_name": "Inactive"},
        99: {"id": 99, "role": "unknown", "is_active": True, "email": "unknown@test.com", "display_name": "Unknown"},
    }


@pytest.fixture
def service(mock_db):
    """A PermissionService wired with a mock db — ready to test."""
    return PermissionService(mock_db)


@pytest.fixture
def patch_get_by_id(service, mock_users):
    """Replace the service's ``_get_user`` so it returns our fake user dicts.

    This avoids the complexity of mocking a ``UserRepository.get_by_id`` that
    doesn't exist yet, and keeps the tests focused on permission logic rather
    than database access.
    """
    saved = service._get_user
    service._get_user = lambda user_id: mock_users.get(user_id)
    yield
    service._get_user = saved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_allowed(result: PermissionCheckResult, msg: str = ""):
    """Assert a PermissionCheckResult indicates the action is allowed."""
    assert result.allowed is True, (
        f"{msg}: expected allowed=True, got allowed={result.allowed}, "
        f"reason={result.reason!r}"
    )


def assert_denied(result: PermissionCheckResult, msg: str = ""):
    """Assert a PermissionCheckResult indicates the action is denied."""
    assert result.allowed is False, (
        f"{msg}: expected allowed=False, got allowed={result.allowed}"
    )
    assert result.reason, f"{msg}: denied result must have a non-empty reason"


# ---------------------------------------------------------------------------
# 1. Admin can do everything
# ---------------------------------------------------------------------------

class TestAdminPermissions:
    """Verify the admin role passes every permission check."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 1  # admin user

    def test_admin_can_do_everything(self):
        svc, uid = self.svc, self.uid

        # – General
        assert_allowed(svc.is_authenticated(uid), "is_authenticated")

        # – Dispatch
        assert_allowed(svc.can_create_dispatch(uid))
        assert_allowed(svc.can_cancel_dispatch(uid))

        # – Trip
        assert_allowed(svc.can_create_trip(uid))
        assert_allowed(svc.can_update_trip(uid))
        assert_allowed(svc.can_delete_trip(uid))

        # – Client
        assert_allowed(svc.can_create_client(uid))
        assert_allowed(svc.can_update_client(uid))
        assert_allowed(svc.can_delete_client(uid))
        assert_allowed(svc.can_merge_clients(uid))

        # – Vehicle
        assert_allowed(svc.can_create_vehicle(uid))
        assert_allowed(svc.can_update_vehicle(uid))
        assert_allowed(svc.can_delete_vehicle(uid))

        # – Driver
        assert_allowed(svc.can_create_driver(uid))
        assert_allowed(svc.can_update_driver(uid))
        assert_allowed(svc.can_delete_driver(uid))

        # – Invoice
        assert_allowed(svc.can_create_invoice(uid))
        assert_allowed(svc.can_finalize_invoice(uid))
        assert_allowed(svc.can_cancel_invoice(uid))

        # – Receipt / Proforma
        assert_allowed(svc.can_create_receipt(uid))
        assert_allowed(svc.can_create_proforma(uid))

        # – CMR
        assert_allowed(svc.can_generate_cmr(uid))

        # – Payments
        assert_allowed(svc.can_generate_payments(uid))

        # – Document
        assert_allowed(svc.can_upload_document(uid))
        assert_allowed(svc.can_email_document(uid))
        assert_allowed(svc.can_delete_document(uid))

        # – Export
        assert_allowed(svc.can_export_data(uid))

        # – Email
        assert_allowed(svc.can_send_email(uid))

        # – Maintenance
        assert_allowed(svc.can_schedule_maintenance(uid))

        # – Analytics
        assert_allowed(svc.can_view_analytics(uid))


# ---------------------------------------------------------------------------
# 2. Manager permissions
# ---------------------------------------------------------------------------

class TestManagerPermissions:
    """Manager can create/update most entities but NOT delete."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 2  # manager user

    def test_manager_permissions(self):
        svc, uid = self.svc, self.uid

        # – Should be allowed (create / update)
        assert_allowed(svc.can_create_dispatch(uid))
        assert_allowed(svc.can_cancel_dispatch(uid))

        assert_allowed(svc.can_create_trip(uid))
        assert_allowed(svc.can_update_trip(uid))

        assert_allowed(svc.can_create_client(uid))
        assert_allowed(svc.can_update_client(uid))

        assert_allowed(svc.can_create_vehicle(uid))
        assert_allowed(svc.can_update_vehicle(uid))

        assert_allowed(svc.can_create_driver(uid))
        assert_allowed(svc.can_update_driver(uid))

        assert_allowed(svc.can_create_invoice(uid))
        assert_allowed(svc.can_finalize_invoice(uid))
        assert_allowed(svc.can_cancel_invoice(uid))

        assert_allowed(svc.can_create_receipt(uid))
        assert_allowed(svc.can_create_proforma(uid))

        assert_allowed(svc.can_generate_cmr(uid))
        assert_allowed(svc.can_generate_payments(uid))

        assert_allowed(svc.can_upload_document(uid))
        assert_allowed(svc.can_email_document(uid))
        assert_allowed(svc.can_delete_document(uid))

        assert_allowed(svc.can_export_data(uid))
        assert_allowed(svc.can_send_email(uid))
        assert_allowed(svc.can_schedule_maintenance(uid))
        assert_allowed(svc.can_view_analytics(uid))

        # – Should be denied (delete — admin-only)
        assert_denied(svc.can_delete_trip(uid), "manager delete trip")
        assert_denied(svc.can_delete_client(uid), "manager delete client")
        assert_denied(svc.can_merge_clients(uid), "manager merge clients")
        assert_denied(svc.can_delete_vehicle(uid), "manager delete vehicle")
        assert_denied(svc.can_delete_driver(uid), "manager delete driver")


# ---------------------------------------------------------------------------
# 3. Dispatcher permissions
# ---------------------------------------------------------------------------

class TestDispatcherPermissions:
    """Dispatcher can create dispatches/trips but NOT invoices/clients."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 3  # dispatcher user

    def test_dispatcher_permissions(self):
        svc, uid = self.svc, self.uid

        # – Allowed: dispatch & trip ops
        assert_allowed(svc.can_create_dispatch(uid))
        assert_allowed(svc.can_cancel_dispatch(uid))
        assert_allowed(svc.can_create_trip(uid))
        assert_allowed(svc.can_update_trip(uid))
        assert_allowed(svc.can_generate_cmr(uid))
        assert_allowed(svc.can_upload_document(uid))
        assert_allowed(svc.can_email_document(uid))
        assert_allowed(svc.can_export_data(uid))

        # – Denied: client ops
        assert_denied(svc.can_create_client(uid), "dispatcher create client")
        assert_denied(svc.can_update_client(uid), "dispatcher update client")
        assert_denied(svc.can_delete_client(uid), "dispatcher delete client")
        assert_denied(svc.can_merge_clients(uid), "dispatcher merge clients")

        # – Denied: vehicle ops
        assert_denied(svc.can_create_vehicle(uid), "dispatcher create vehicle")
        assert_denied(svc.can_update_vehicle(uid), "dispatcher update vehicle")
        assert_denied(svc.can_delete_vehicle(uid), "dispatcher delete vehicle")

        # – Denied: driver ops
        assert_denied(svc.can_create_driver(uid), "dispatcher create driver")
        assert_denied(svc.can_update_driver(uid), "dispatcher update driver")
        assert_denied(svc.can_delete_driver(uid), "dispatcher delete driver")

        # – Denied: invoice ops
        assert_denied(svc.can_create_invoice(uid), "dispatcher create invoice")
        assert_denied(svc.can_finalize_invoice(uid), "dispatcher finalize invoice")
        assert_denied(svc.can_cancel_invoice(uid), "dispatcher cancel invoice")
        assert_denied(svc.can_create_receipt(uid), "dispatcher create receipt")
        assert_denied(svc.can_create_proforma(uid), "dispatcher create proforma")

        # – Denied: payments, email, maintenance, analytics
        assert_denied(svc.can_generate_payments(uid), "dispatcher generate payments")
        assert_denied(svc.can_send_email(uid), "dispatcher send email")
        assert_denied(svc.can_schedule_maintenance(uid), "dispatcher schedule maintenance")
        assert_denied(svc.can_view_analytics(uid), "dispatcher view analytics")

        # – Denied: delete ops
        assert_denied(svc.can_delete_trip(uid), "dispatcher delete trip")
        assert_denied(svc.can_delete_document(uid), "dispatcher delete document")


# ---------------------------------------------------------------------------
# 4. Driver permissions
# ---------------------------------------------------------------------------

class TestDriverPermissions:
    """Drivers have minimal permissions — only basic auth passes."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 4  # driver user

    def test_driver_permissions(self):
        svc, uid = self.svc, self.uid

        # – Only is_authenticated should succeed
        assert_allowed(svc.is_authenticated(uid))

        # – Everything else denied
        assert_denied(svc.can_create_dispatch(uid))
        assert_denied(svc.can_cancel_dispatch(uid))
        assert_denied(svc.can_create_trip(uid))
        assert_denied(svc.can_update_trip(uid))
        assert_denied(svc.can_delete_trip(uid))
        assert_denied(svc.can_create_client(uid))
        assert_denied(svc.can_update_client(uid))
        assert_denied(svc.can_delete_client(uid))
        assert_denied(svc.can_merge_clients(uid))
        assert_denied(svc.can_create_vehicle(uid))
        assert_denied(svc.can_update_vehicle(uid))
        assert_denied(svc.can_delete_vehicle(uid))
        assert_denied(svc.can_create_driver(uid))
        assert_denied(svc.can_update_driver(uid))
        assert_denied(svc.can_delete_driver(uid))
        assert_denied(svc.can_create_invoice(uid))
        assert_denied(svc.can_finalize_invoice(uid))
        assert_denied(svc.can_cancel_invoice(uid))
        assert_denied(svc.can_create_receipt(uid))
        assert_denied(svc.can_create_proforma(uid))
        assert_denied(svc.can_generate_cmr(uid))
        assert_denied(svc.can_generate_payments(uid))
        assert_denied(svc.can_upload_document(uid))
        assert_denied(svc.can_email_document(uid))
        assert_denied(svc.can_delete_document(uid))
        assert_denied(svc.can_export_data(uid))
        assert_denied(svc.can_send_email(uid))
        assert_denied(svc.can_schedule_maintenance(uid))
        assert_denied(svc.can_view_analytics(uid))


# ---------------------------------------------------------------------------
# 5. Inactive user denied
# ---------------------------------------------------------------------------

class TestInactiveUser:
    """An inactive (deactivated) user must fail is_authenticated."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 5  # inactive admin

    def test_inactive_user_denied(self):
        result = self.svc.is_authenticated(self.uid)
        assert_denied(result, "inactive user")
        assert "inactive" in result.reason.lower()

    def test_inactive_user_denied_all_operations(self):
        """Every can_* method should also be denied for inactive users."""
        svc, uid = self.svc, self.uid
        for method_name in dir(svc):
            if method_name.startswith("can_") or method_name == "is_authenticated":
                method = getattr(svc, method_name)
                if callable(method):
                    result = method(uid)
                    assert isinstance(result, PermissionCheckResult)
                    assert_denied(result, f"{method_name} for inactive user")
                    assert "inactive" in result.reason.lower(), (
                        f"{method_name} reason should mention inactive, "
                        f"got: {result.reason!r}"
                    )


# ---------------------------------------------------------------------------
# 6. Nonexistent user denied
# ---------------------------------------------------------------------------

class TestNonexistentUser:
    """A user_id not present in the database must fail."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 999  # not in mock_users

    def test_nonexistent_user_denied(self):
        result = self.svc.is_authenticated(self.uid)
        assert_denied(result, "nonexistent user")
        assert "not found" in result.reason.lower()

    def test_nonexistent_user_denied_all_operations(self):
        svc, uid = self.svc, self.uid
        for method_name in dir(svc):
            if method_name.startswith("can_") or method_name == "is_authenticated":
                method = getattr(svc, method_name)
                if callable(method):
                    result = method(uid)
                    assert isinstance(result, PermissionCheckResult)
                    assert_denied(result, f"{method_name} for nonexistent user")

    def test_none_user_id_denied(self):
        """Passing None as user_id should also be rejected."""
        result = self.svc.is_authenticated(None)
        assert_denied(result, "None user_id")
        assert "required" in result.reason.lower()


# ---------------------------------------------------------------------------
# 7. Every can_* method returns PermissionCheckResult
# ---------------------------------------------------------------------------

class TestAllOperationsCovered:
    """Verify every can_* method returns a proper PermissionCheckResult."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service
        self.uid = 1  # use admin so all checks pass

    def test_all_write_operations_covered(self):
        svc, uid = self.svc, self.uid
        checked = 0
        for attr_name in dir(svc):
            if attr_name.startswith("can_"):
                method = getattr(svc, attr_name)
                if callable(method):
                    result = method(uid)
                    assert isinstance(result, PermissionCheckResult), (
                        f"{attr_name} did not return PermissionCheckResult, "
                        f"got {type(result).__name__}"
                    )
                    checked += 1
        # Ensure we didn't accidentally skip a bunch
        assert checked >= 25, (
            f"Expected at least 25 can_* methods, found {checked}. "
            "New permission methods may have been added — update this test."

        )


# ---------------------------------------------------------------------------
# 8. PermissionCheckResult structure
# ---------------------------------------------------------------------------

class TestPermissionCheckResultStructure:
    """Verify the PermissionCheckResult dataclass fields work correctly."""

    def test_permission_check_result_structure(self):
        allowed = PermissionCheckResult(True)
        assert allowed.allowed is True
        assert allowed.reason == ""

        denied = PermissionCheckResult(False, "Insufficient privileges")
        assert denied.allowed is False
        assert denied.reason == "Insufficient privileges"

        # Verify it's a dataclass with the expected fields
        import dataclasses
        fields = {f.name for f in dataclasses.fields(PermissionCheckResult)}
        assert "allowed" in fields
        assert "reason" in fields


# ---------------------------------------------------------------------------
# 9–21. Category-specific permission tests
# ---------------------------------------------------------------------------

class TestSpecificPermissions:
    """Granular tests for each permission category."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service

    # -- Trip permissions ---------------------------------------------------

    def test_trip_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_create_trip(1))
        assert_allowed(svc.can_update_trip(1))
        assert_allowed(svc.can_delete_trip(1))
        # Manager
        assert_allowed(svc.can_create_trip(2))
        assert_allowed(svc.can_update_trip(2))
        assert_denied(svc.can_delete_trip(2))
        # Dispatcher
        assert_allowed(svc.can_create_trip(3))
        assert_allowed(svc.can_update_trip(3))
        assert_denied(svc.can_delete_trip(3))
        # Driver
        assert_denied(svc.can_create_trip(4))
        assert_denied(svc.can_update_trip(4))
        assert_denied(svc.can_delete_trip(4))

    # -- Client permissions -------------------------------------------------

    def test_client_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_create_client(1))
        assert_allowed(svc.can_update_client(1))
        assert_allowed(svc.can_delete_client(1))
        assert_allowed(svc.can_merge_clients(1))
        # Manager
        assert_allowed(svc.can_create_client(2))
        assert_allowed(svc.can_update_client(2))
        assert_denied(svc.can_delete_client(2))
        assert_denied(svc.can_merge_clients(2))
        # Dispatcher
        assert_denied(svc.can_create_client(3))
        assert_denied(svc.can_update_client(3))
        assert_denied(svc.can_delete_client(3))
        assert_denied(svc.can_merge_clients(3))
        # Driver
        assert_denied(svc.can_create_client(4))

    # -- Vehicle permissions ------------------------------------------------

    def test_vehicle_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_create_vehicle(1))
        assert_allowed(svc.can_update_vehicle(1))
        assert_allowed(svc.can_delete_vehicle(1))
        # Manager
        assert_allowed(svc.can_create_vehicle(2))
        assert_allowed(svc.can_update_vehicle(2))
        assert_denied(svc.can_delete_vehicle(2))
        # Dispatcher
        assert_denied(svc.can_create_vehicle(3))
        assert_denied(svc.can_update_vehicle(3))
        assert_denied(svc.can_delete_vehicle(3))

    # -- Driver permissions (CRUD on driver entities) -----------------------

    def test_driver_crud_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_create_driver(1))
        assert_allowed(svc.can_update_driver(1))
        assert_allowed(svc.can_delete_driver(1))
        # Manager — create/update yes, delete no
        assert_allowed(svc.can_create_driver(2))
        assert_allowed(svc.can_update_driver(2))
        assert_denied(svc.can_delete_driver(2))
        # Dispatcher
        assert_denied(svc.can_create_driver(3))
        assert_denied(svc.can_update_driver(3))
        assert_denied(svc.can_delete_driver(3))

    # -- Invoice permissions ------------------------------------------------

    def test_invoice_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_create_invoice(1))
        assert_allowed(svc.can_finalize_invoice(1))
        assert_allowed(svc.can_cancel_invoice(1))
        # Manager
        assert_allowed(svc.can_create_invoice(2))
        assert_allowed(svc.can_finalize_invoice(2))
        assert_allowed(svc.can_cancel_invoice(2))
        # Dispatcher
        assert_denied(svc.can_create_invoice(3))
        assert_denied(svc.can_finalize_invoice(3))
        assert_denied(svc.can_cancel_invoice(3))

    # -- Dispatch permissions -----------------------------------------------

    def test_dispatch_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_create_dispatch(1))
        assert_allowed(svc.can_cancel_dispatch(1))
        # Manager
        assert_allowed(svc.can_create_dispatch(2))
        assert_allowed(svc.can_cancel_dispatch(2))
        # Dispatcher
        assert_allowed(svc.can_create_dispatch(3))
        assert_allowed(svc.can_cancel_dispatch(3))
        # Driver
        assert_denied(svc.can_create_dispatch(4))
        assert_denied(svc.can_cancel_dispatch(4))

    # -- CMR permissions ----------------------------------------------------

    def test_cmr_permissions(self):
        svc = self.svc
        assert_allowed(svc.can_generate_cmr(1))  # admin
        assert_allowed(svc.can_generate_cmr(2))  # manager
        assert_allowed(svc.can_generate_cmr(3))  # dispatcher
        assert_denied(svc.can_generate_cmr(4))   # driver

    # -- Payment permissions ------------------------------------------------

    def test_payment_permissions(self):
        svc = self.svc
        assert_allowed(svc.can_generate_payments(1))  # admin
        assert_allowed(svc.can_generate_payments(2))  # manager
        assert_denied(svc.can_generate_payments(3))   # dispatcher
        assert_denied(svc.can_generate_payments(4))   # driver

    # -- Document permissions -----------------------------------------------

    def test_document_permissions(self):
        svc = self.svc
        # Admin
        assert_allowed(svc.can_upload_document(1))
        assert_allowed(svc.can_email_document(1))
        assert_allowed(svc.can_delete_document(1))
        # Manager
        assert_allowed(svc.can_upload_document(2))
        assert_allowed(svc.can_email_document(2))
        assert_allowed(svc.can_delete_document(2))
        # Dispatcher — upload/email yes, delete no
        assert_allowed(svc.can_upload_document(3))
        assert_allowed(svc.can_email_document(3))
        assert_denied(svc.can_delete_document(3))
        # Driver
        assert_denied(svc.can_upload_document(4))

    # -- Export permissions -------------------------------------------------

    def test_export_permissions(self):
        svc = self.svc
        assert_allowed(svc.can_export_data(1))  # admin
        assert_allowed(svc.can_export_data(2))  # manager
        assert_allowed(svc.can_export_data(3))  # dispatcher
        assert_denied(svc.can_export_data(4))   # driver

    # -- Email permissions --------------------------------------------------

    def test_email_permissions(self):
        svc = self.svc
        assert_allowed(svc.can_send_email(1))  # admin
        assert_allowed(svc.can_send_email(2))  # manager
        assert_denied(svc.can_send_email(3))   # dispatcher
        assert_denied(svc.can_send_email(4))   # driver

    # -- Maintenance permissions --------------------------------------------

    def test_maintenance_permissions(self):
        svc = self.svc
        assert_allowed(svc.can_schedule_maintenance(1))  # admin
        assert_allowed(svc.can_schedule_maintenance(2))  # manager
        assert_denied(svc.can_schedule_maintenance(3))   # dispatcher
        assert_denied(svc.can_schedule_maintenance(4))   # driver

    # -- Analytics permissions ----------------------------------------------

    def test_analytics_permissions(self):
        svc = self.svc
        assert_allowed(svc.can_view_analytics(1))  # admin
        assert_allowed(svc.can_view_analytics(2))  # manager
        assert_denied(svc.can_view_analytics(3))   # dispatcher
        assert_denied(svc.can_view_analytics(4))   # driver


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases like unknown roles, None IDs, etc."""

    @pytest.fixture(autouse=True)
    def _setup(self, patch_get_by_id, service):
        self.svc = service

    def test_unknown_role_denied(self):
        """A user with an unrecognised role should be denied."""
        svc = self.svc
        for method_name in dir(svc):
            if method_name.startswith("can_"):
                method = getattr(svc, method_name)
                if callable(method):
                    result = method(99)  # unknown role
                    assert isinstance(result, PermissionCheckResult)
                    assert_denied(result, f"{method_name} for unknown role")

    def test_none_id_on_can_methods(self):
        """Passing None as user_id to can_* should be handled gracefully."""
        svc = self.svc
        for method_name in dir(svc):
            if method_name.startswith("can_"):
                method = getattr(svc, method_name)
                if callable(method):
                    result = method(None)
                    assert isinstance(result, PermissionCheckResult)
                    assert_denied(result, f"{method_name}(None)")

    def test_reason_messages_are_informative(self):
        """Denied results should contain contextual info (role name, reason)."""
        svc = self.svc
        # Driver denied for creating a client
        result = svc.can_create_client(4)
        assert_denied(result)
        assert "driver" in result.reason.lower()

        # Dispatcher denied for creating an invoice
        result = svc.can_create_invoice(3)
        assert_denied(result)
        assert "dispatcher" in result.reason.lower()

        # Manager denied for deleting a trip
        result = svc.can_delete_trip(2)
        assert_denied(result)
        assert "admin" in result.reason.lower()
