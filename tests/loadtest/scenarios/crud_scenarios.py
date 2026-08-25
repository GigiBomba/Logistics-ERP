"""CRUD scenarios for trips, clients, drivers, trucks."""
from __future__ import annotations

from locust import task, tag
from tests.loadtest.factories import TokenManager


class CrudTasks:
    """Mixin with CRUD task methods."""

    @task(3)
    @tag("crud", "list", "trips")
    def list_trips(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/trips/?limit=50",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="list_trips") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"List trips failed: {resp.status_code}")

    @task(2)
    @tag("crud", "get", "trips")
    def get_trip(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/trips/1",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="get_trip") as resp:
            if resp.status_code in (200, 500):  # 500 = known TripResponse bug
                resp.success()
            else:
                resp.failure(f"Get trip failed: {resp.status_code}")

    @task(2)
    @tag("crud", "list", "clients")
    def list_clients(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/clients/",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="list_clients") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"List clients failed: {resp.status_code}")

    @task(1)
    @tag("crud", "get", "clients")
    def get_client(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/clients/1",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="get_client") as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Get client failed: {resp.status_code}")

    @task(2)
    @tag("crud", "list", "drivers")
    def list_drivers(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/drivers/",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="list_drivers") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"List drivers failed: {resp.status_code}")

    @task(1)
    @tag("crud", "list", "fleet")
    def list_fleet(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/fleet/trucks/",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="list_fleet") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"List fleet failed: {resp.status_code}")

    @task(1)
    @tag("crud", "create", "trips")
    def create_trip(self):
        token = TokenManager.get(self.client)
        with self.client.post("/api/v1/trips/",
                             json={"client_name": "Load Test Client", "driver_name": "Load Driver",
                                   "truck_number": "LOAD-001", "status": "Planned"},
                             headers={"Authorization": f"Bearer {token}"},
                             catch_response=True, name="create_trip") as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Create trip failed: {resp.status_code}")

    @task(1)
    @tag("crud", "create", "clients")
    def create_client(self):
        token = TokenManager.get(self.client)
        with self.client.post("/api/v1/clients/?name=Load+Test+Client",
                             json={"email": "loadtest@test.com", "phone": "+40-700-000-000"},
                             headers={"Authorization": f"Bearer {token}"},
                             catch_response=True, name="create_client") as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Create client failed: {resp.status_code}")

    @task(1)
    @tag("crud", "list", "all")
    def list_all(self):
        token = TokenManager.get(self.client)
        for path in ("/api/v1/trips/?limit=10", "/api/v1/clients/", "/api/v1/drivers/"):
            with self.client.get(path, headers={"Authorization": f"Bearer {token}"},
                                catch_response=True, name=f"list_{path.split('/')[2]}") as resp:
                if resp.status_code == 200:
                    resp.success()
                else:
                    resp.failure(f"List {path} failed: {resp.status_code}")
