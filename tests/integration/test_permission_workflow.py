"""Integration test: Permission checks across services."""
import pytest
from services.permission_service import PermissionService, PermissionCheckResult
from services.trip_service import TripService
from models.trip_models import TripCreate


class TestPermissionWorkflow:
    def test_permission_service_allows_admin(self, seeded_db):
        """Admin user can create trips."""
        perm = PermissionService(seeded_db)
        result = perm.can_create_trip(user_id=1)  # admin
        assert result.allowed

    def test_permission_service_denies_inactive(self, seeded_db):
        """Inactive user denied."""
        cur = seeded_db.conn.cursor()
        cur.execute(
            "INSERT INTO users (id, email, password_hash, role, display_name, is_active, company_id) "
            "VALUES (2, 'inactive@test.com', 'hash', 'admin', 'Inactive', 0, 1)"
        )
        seeded_db.conn.commit()
        perm = PermissionService(seeded_db)
        result = perm.can_create_trip(user_id=2)
        assert not result.allowed
        assert "inactive" in result.reason.lower()

    def test_trip_create_respects_permissions(self, seeded_db):
        """TripService.create() enforces permission check."""
        service = TripService(seeded_db)
        request = TripCreate(
            client_id=1, reference="PERM-TEST",
            start_date="2026-07-15", price_eur=100.0,
        )
        # Should fail for user_id=999 (non-existent)
        result = service.create(request, user_id=999)
        assert not result.success
        assert len(result.errors) > 0
