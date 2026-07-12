"""Integration test: Client create → search → merge flow."""
import pytest
from models.client_models import ClientCreate, ClientUpdate, ClientContact
from services.client_service import ClientService


class TestClientWorkflow:
    def test_create_client_typed(self, seeded_db):
        """ClientService.create() with typed ClientCreate."""
        service = ClientService(seeded_db)
        request = ClientCreate(name="Integration Test Client", email="test@test.com")
        result = service.create(request, user_id=1)
        assert result.success
        assert result.data.name == "Integration Test Client"

    def test_list_clients(self, seeded_db):
        """ClientService.list_all() returns typed results."""
        service = ClientService(seeded_db)
        result = service.list_all()
        assert result.success
        assert len(result.data) >= 1

    def test_update_client(self, seeded_db):
        """ClientService.update() with typed ClientUpdate."""
        service = ClientService(seeded_db)
        # Create
        create_req = ClientCreate(name="Update Test Client")
        created = service.create(create_req, user_id=1)
        assert created.success

        # Update
        update_req = ClientUpdate(name="Updated Name")
        result = service.update(created.data.id, update_req, user_id=1)
        assert result.success
        assert result.data.name == "Updated Name"
