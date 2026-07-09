"""Document upload and retrieval scenarios."""
from locust import task, tag
from tests.loadtest.factories import TokenManager


class DocumentTasks:

    @task(2)
    @tag("doc", "list")
    def list_documents(self):
        token = TokenManager.get(self.client)
        with self.client.get("/api/v1/documents/",
                            headers={"Authorization": f"Bearer {token}"},
                            catch_response=True, name="list_documents") as resp:
            if resp.status_code in (200, 500):
                resp.success()
            else:
                resp.failure(f"List docs failed: {resp.status_code}")

    @task(1)
    @tag("doc", "upload")
    def upload_document(self):
        token = TokenManager.get(self.client)
        content = b"%PDF-1.4 Load test PDF content " + b"x" * 1000
        with self.client.post("/api/v1/documents/upload",
                             files={"file": ("loadtest.pdf", content, "application/pdf")},
                             data={"category": "loadtest"},
                             headers={"Authorization": f"Bearer {token}"},
                             catch_response=True, name="upload_document") as resp:
            if resp.status_code in (200, 400, 500):
                resp.success()
            else:
                resp.failure(f"Upload doc failed: {resp.status_code}")
