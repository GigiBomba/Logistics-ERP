"""QThread-based network worker for offloading API calls.

Prevents the PySide6 main UI thread from freezing on slow or blocking
HTTP requests by running ``httpx`` calls inside a dedicated background
thread.  Communicates results back to Qt widgets via PySide6 Signals
so the UI remains responsive during document uploads, OCR runs, and
other long-running API operations.

Usage::

    from client.network.network_worker import NetworkWorker

    worker = NetworkWorker()
    worker.progress.connect(self._on_progress)
    worker.finished.connect(self._on_finished)
    worker.error.connect(self._on_error)

    worker.call_action("POST", "/api/v1/ocr/run",
                       json_data={"document_id": 42, "engine": "auto"})
    worker.start()

Or for file uploads::

    worker.upload("/api/v1/documents/upload",
                  file_path="/path/to/invoice.pdf",
                  form_data={"category": "invoices", "uploaded_by": "user"})
    worker.start()
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

import httpx
from PySide6.QtCore import QThread, Signal

from client.config import ClientConfig, get_client_config

logger = logging.getLogger(__name__)


class NetworkWorker(QThread):
    """Offload a single HTTP call to a background thread.

    Signals
    -------
    progress : Signal(str, int)
        Emitted with a human-readable label and an integer percent (0-100).
    finished : Signal(dict)
        Emitted with the parsed JSON response body when the call succeeds.
    error : Signal(str)
        Emitted with a human-readable error message on failure.
    """

    progress = Signal(str, int)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        parent: Any | None = None,
        base_url: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        config: Optional[ClientConfig] = None,
    ) -> None:
        super().__init__(parent)
        if config is not None:
            self._config = config
            self._base_url = base_url or config.api_url
            self._verify_ssl = verify_ssl if verify_ssl is not None else config.verify_ssl
        else:
            self._config = get_client_config()
            self._base_url = base_url or self._config.api_url
            self._verify_ssl = verify_ssl if verify_ssl is not None else self._config.verify_ssl

        self._stop_event = threading.Event()
        self._method: str = "GET"
        self._path: str = "/"
        self._json_data: Optional[Dict[str, Any]] = None
        self._form_data: Optional[Dict[str, str]] = None
        self._file_path: Optional[str] = None
        self._params: Optional[Dict[str, Any]] = None
        self._action: Optional[str] = None

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def call_action(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._action = "call"
        self._method = method.upper()
        self._path = path
        self._json_data = json_data
        self._params = params
        self._file_path = None
        self._form_data = None

    def upload(
        self,
        path: str,
        file_path: str,
        form_data: Optional[Dict[str, str]] = None,
    ) -> None:
        self._action = "upload"
        self._method = "POST"
        self._path = path
        self._file_path = file_path
        self._form_data = form_data
        self._json_data = None
        self._params = None

    def run(self) -> None:
        self.progress.emit("Connecting...", 0)
        try:
            headers = {}
            if self._config.api_key:
                headers["X-API-Key"] = self._config.api_key
            client = httpx.Client(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(120.0, connect=10.0),
                verify=self._verify_ssl,
            )
            try:
                if self._action == "upload":
                    result = self._do_upload(client)
                else:
                    result = self._do_call(client)
                self.progress.emit("Done", 100)
                self.finished.emit(result)
            finally:
                client.close()
        except httpx.HTTPStatusError as exc:
            detail = "Unknown error"
            try:
                detail = exc.response.json().get("detail", str(exc))
            except Exception:
                detail = str(exc)
            msg = f"HTTP {exc.response.status_code}: {detail}"
            self.progress.emit("Failed", 0)
            self.error.emit(msg)
        except httpx.RequestError as exc:
            self.progress.emit("Failed", 0)
            self.error.emit(f"Network error: {exc}")
        except Exception as exc:
            self.progress.emit("Failed", 0)
            self.error.emit(f"Unexpected error: {exc}")

    def _do_call(self, client: httpx.Client) -> Dict[str, Any]:
        url = self._path
        if self._method == "GET":
            resp = client.get(url, params=self._params)
        elif self._method == "POST":
            resp = client.post(url, json=self._json_data)
        elif self._method == "PUT":
            resp = client.put(url, json=self._json_data)
        elif self._method == "DELETE":
            resp = client.delete(url)
        else:
            resp = client.request(self._method, url, json=self._json_data)
        self.progress.emit("Receiving...", 80)
        resp.raise_for_status()
        return resp.json()

    def _do_upload(self, client: httpx.Client) -> Dict[str, Any]:
        file_path = self._file_path or ""
        if not file_path or not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as fh:
            files = {"file": (file_name, fh)}
            self.progress.emit(f"Uploading {file_name} ({file_size >> 10} KB)...", 20)
            resp = client.post(
                self._path,
                files=files,
                data=self._form_data or {},
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
        self.progress.emit(f"Processing {file_name}...", 60)
        resp.raise_for_status()
        return resp.json()
