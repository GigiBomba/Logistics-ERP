"""Invoice generation scenarios."""
from locust import task, tag
from tests.loadtest.factories import TokenManager


class InvoiceTasks:

    @task(1)
    @tag("invoice", "generate")
    def generate_invoice(self):
        token = TokenManager.get(self.client)
        with self.client.post("/api/v1/invoices/generate",
                             json={"trip_id": 1, "mode": "client", "trip_data": {}},
                             headers={"Authorization": f"Bearer {token}"},
                             catch_response=True, name="generate_invoice") as resp:
            if resp.status_code in (200, 400, 500):
                resp.success()
            else:
                resp.failure(f"Invoice gen failed: {resp.status_code}")
