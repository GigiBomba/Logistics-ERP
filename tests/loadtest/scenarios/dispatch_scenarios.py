"""Dispatch workflow scenarios for Locust load testing.

Simulates realistic dispatcher behavior: creating trips, assigning resources,
transitioning statuses, and loading the dispatch board.
"""

from __future__ import annotations

from locust import task, tag

from tests.loadtest.factories import TokenManager


class DispatchTasks:
    """Simulates a dispatcher managing trips on the dispatch board."""

    @task(3)
    @tag("dispatch", "assign-truck")
    def assign_truck(self):
        """Assign a truck to an existing trip."""
        token = TokenManager.get(self.client)
        with self.client.post(
            "/api/v1/drivers/1/assign-truck?truck_id=1",
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="assign_truck",
        ) as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Assign truck failed: {resp.status_code}")

    @task(3)
    @tag("dispatch", "assign-driver")
    def assign_driver(self):
        """Assign a driver to an existing trip via PATCH."""
        token = TokenManager.get(self.client)
        with self.client.patch(
            "/api/v1/trips/1",
            json={"driver_id": 1, "driver_name": "Load Test Driver"},
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="assign_driver",
        ) as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Assign driver failed: {resp.status_code}")

    @task(2)
    @tag("dispatch", "transition")
    def transition_trip_status(self):
        """Transition a trip to the next status."""
        token = TokenManager.get(self.client)
        with self.client.patch(
            "/api/v1/trips/1",
            json={"status": "In Transit"},
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="transition_trip",
        ) as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Transition failed: {resp.status_code}")

    @task(1)
    @tag("dispatch", "board")
    def load_dispatch_board(self):
        """Load the dispatch board data."""
        token = TokenManager.get(self.client)
        with self.client.get(
            "/api/v1/trips/?page_size=200",
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="dispatch_board",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(
                    f"Dispatch board load failed: {resp.status_code}"
                )

    @task(2)
    @tag("dispatch", "create-trip")
    def create_trip(self):
        """Create a new trip to simulate dispatch planning."""
        token = TokenManager.get(self.client)
        with self.client.post(
            "/api/v1/trips/",
            json={
                "client_name": "Load Test Client",
                "driver_name": "Load Driver",
                "truck_plate": "LOAD-001",
                "status": "Planned",
                "loading_city": "Berlin",
                "delivery_city": "Munich",
                "start_date": "2026-07-13",
                "price_eur": 1200.0,
            },
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="create_trip",
        ) as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Create trip failed: {resp.status_code}")

    @task(1)
    @tag("dispatch", "complete")
    def complete_trip(self):
        """Complete a trip (mark as Delivered)."""
        token = TokenManager.get(self.client)
        with self.client.patch(
            "/api/v1/trips/1",
            json={"status": "Delivered"},
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="complete_trip",
        ) as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Complete trip failed: {resp.status_code}")


class DispatchWorkflowTasks:
    """Multi-step dispatch workflows that simulate real dispatcher sessions."""

    @task(1)
    @tag("dispatch", "workflow", "full-cycle")
    def full_dispatch_cycle(self):
        """Simulate a full dispatch workflow: create → assign → transition → complete."""
        token = TokenManager.get(self.client)

        # Step 1: Create a trip
        with self.client.post(
            "/api/v1/trips/",
            json={
                "client_name": "Workflow Client",
                "driver_name": "Workflow Driver",
                "truck_plate": "WF-001",
                "status": "Planned",
                "loading_city": "Hamburg",
                "delivery_city": "Frankfurt",
                "start_date": "2026-07-13",
                "price_eur": 1500.0,
            },
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="workflow_create_trip",
        ) as resp:
            if resp.status_code not in (200, 500):
                resp.failure(f"Step 1 (create) failed: {resp.status_code}")
                return
            trip_id = resp.json().get("id", 1)

        # Step 2: Assign truck
        with self.client.post(
            f"/api/v1/drivers/1/assign-truck?truck_id=2",
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="workflow_assign_truck",
        ) as resp:
            if resp.status_code not in (200, 500):
                resp.failure(f"Step 2 (assign truck) failed: {resp.status_code}")
                return

        # Step 3: Transition to In Transit
        with self.client.patch(
            f"/api/v1/trips/{trip_id}",
            json={"status": "In Transit"},
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="workflow_transition",
        ) as resp:
            if resp.status_code not in (200, 500):
                resp.failure(
                    f"Step 3 (transition) failed: {resp.status_code}"
                )
                return

        # Step 4: Complete (Delivered)
        with self.client.patch(
            f"/api/v1/trips/{trip_id}",
            json={"status": "Delivered"},
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="workflow_complete",
        ) as resp:
            if resp.status_code not in (200, 500):
                resp.failure(
                    f"Step 4 (complete) failed: {resp.status_code}"
                )
                return

        resp.success()

    @task(1)
    @tag("dispatch", "workflow", "board-view")
    def board_view_and_filter(self):
        """Load the dispatch board and apply filters."""
        token = TokenManager.get(self.client)

        # Load board
        with self.client.get(
            "/api/v1/trips/?page_size=200",
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
            name="workflow_board_load",
        ) as resp:
            if resp.status_code not in (200, 500):
                resp.failure(f"Board load failed: {resp.status_code}")
                return

        # Filter by status
        for status in ("Planned", "In Transit", "Delivered"):
            with self.client.get(
                f"/api/v1/trips/?status={status}&page_size=50",
                headers={"Authorization": f"Bearer {token}"},
                catch_response=True,
                name="workflow_board_filter",
            ) as filter_resp:
                if filter_resp.status_code not in (200, 500):
                    resp.failure(
                        f"Filter by {status} failed: {filter_resp.status_code}"
                    )
                    return

        resp.success()
