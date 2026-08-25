"""Realistic multi-step workflows."""
from __future__ import annotations

from locust import task, tag
from tests.loadtest.factories import TokenManager


class MixedTasks:

    @task(1)
    @tag("mixed", "export")
    def export_report(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/trips/1/export/pdf",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="export_pdf") as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"Export failed: {resp.status_code}")
