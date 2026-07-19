"""Tests for client.network.network_worker — QThread-based HTTP worker.

These tests use ``qtbot`` for Qt signal verification and mock ``httpx.Client``
to avoid real network I/O.
"""

from __future__ import annotations

import os
import threading
from unittest.mock import MagicMock, PropertyMock, call, patch

import httpx
import pytest
from PySide6.QtCore import QThread

from client.network.network_worker import NetworkWorker


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_mock_response(status_code: int = 200, json_data: dict | None = None):
    """Build a standard mock ``httpx.Response``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


# ── Construction ─────────────────────────────────────────────────────────


class TestNetworkWorkerConstruction:
    def test_is_qthread(self):
        worker = NetworkWorker()
        assert isinstance(worker, QThread)

    def test_has_signals(self):
        worker = NetworkWorker()
        assert hasattr(worker, "progress")
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")

    def test_has_stop_event(self):
        worker = NetworkWorker()
        assert isinstance(worker.stop_event, threading.Event)
        assert not worker.stop_event.is_set()

    def test_default_base_url_from_config(self):
        worker = NetworkWorker()
        assert worker._base_url is not None

    def test_custom_base_url(self):
        worker = NetworkWorker(base_url="https://custom.api.com")
        assert worker._base_url == "https://custom.api.com"

    def test_custom_verify_ssl(self):
        worker = NetworkWorker(verify_ssl=False)
        assert worker._verify_ssl is False

    def test_verify_ssl_defaults_from_config(self):
        # In the test environment OPERION_ENV=testing, so verify_ssl=False
        worker = NetworkWorker()
        assert worker._verify_ssl is False

    def test_custom_config_overrides_global(self):
        config = MagicMock()
        config.api_url = "https://from.config.com"
        config.verify_ssl = True
        config.api_key = ""
        worker = NetworkWorker(config=config)
        assert worker._base_url == "https://from.config.com"
        assert worker._verify_ssl is True

    def test_default_action_values(self):
        worker = NetworkWorker()
        assert worker._method == "GET"
        assert worker._path == "/"
        assert worker._json_data is None
        assert worker._form_data is None
        assert worker._file_path is None
        assert worker._params is None
        assert worker._action is None

    def test_call_action_sets_attributes(self):
        worker = NetworkWorker()
        worker.call_action(
            "POST",
            "/api/resource",
            json_data={"name": "test"},
            params={"page": 1},
        )
        assert worker._action == "call"
        assert worker._method == "POST"
        assert worker._path == "/api/resource"
        assert worker._json_data == {"name": "test"}
        assert worker._params == {"page": 1}
        assert worker._file_path is None
        assert worker._form_data is None

    def test_upload_sets_attributes(self):
        worker = NetworkWorker()
        worker.upload("/api/upload", "/path/to/file.pdf", form_data={"cat": "docs"})
        assert worker._action == "upload"
        assert worker._method == "POST"
        assert worker._path == "/api/upload"
        assert worker._file_path == "/path/to/file.pdf"
        assert worker._form_data == {"cat": "docs"}
        assert worker._json_data is None
        assert worker._params is None


# ── Signal emissions (success) ──────────────────────────────────────────


class TestNetworkWorkerSignalsSuccess:
    """Verifies signals emitted during a successful request."""

    def test_finished_emitted_on_get(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(
                200, {"result": "ok"}
            )

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert blocker.args[0] == {"result": "ok"}

    def test_progress_emitted_during_run(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        progress_signals = []

        def capture_progress(label, pct):
            progress_signals.append((label, pct))

        worker.progress.connect(capture_progress)

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

        assert len(progress_signals) >= 2
        assert progress_signals[0] == ("Connecting...", 0)
        assert progress_signals[-1] == ("Done", 100)

    def test_post_returns_created(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.post.return_value = _make_mock_response(201, {"id": 1})

            worker.call_action("POST", "/api/resource", json_data={"name": "x"})
            with qtbot.wait_signal(worker.finished, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert blocker.args[0] == {"id": 1}

    def test_put_returns_updated(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.put.return_value = _make_mock_response(200, {"updated": True})

            worker.call_action("PUT", "/api/resource/1", json_data={"name": "y"})
            with qtbot.wait_signal(worker.finished, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert blocker.args[0] == {"updated": True}

    def test_delete_succeeds(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.delete.return_value = _make_mock_response(204, {})

            worker.call_action("DELETE", "/api/resource/1")
            with qtbot.wait_signal(worker.finished, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert blocker.args[0] == {}


# ── Signal emissions (errors) ───────────────────────────────────────────


class TestNetworkWorkerSignalsError:
    """Verifies error signals on various failure modes."""

    def test_error_on_http_404(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 404
            error_response.json.return_value = {"detail": "Not found"}
            mock_instance.get.side_effect = httpx.HTTPStatusError(
                "404 Client Error",
                request=MagicMock(),
                response=error_response,
            )

            worker.call_action("GET", "/api/missing")
            with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        error_msg = blocker.args[0]
        assert "HTTP 404" in error_msg
        assert "Not found" in error_msg

    def test_error_on_http_500(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 500
            error_response.json.return_value = {"detail": "Internal error"}
            mock_instance.get.side_effect = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=error_response,
            )

            worker.call_action("GET", "/api/error")
            with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert "HTTP 500" in blocker.args[0]

    def test_error_on_http_status_without_json_detail(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 403
            # .json() raises, so fallback to str(exc)
            error_response.json.side_effect = ValueError("No json")
            mock_instance.get.side_effect = httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=error_response,
            )

            worker.call_action("GET", "/api/forbidden")
            with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert "HTTP 403" in blocker.args[0]

    def test_error_on_network_failure(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.side_effect = httpx.RequestError(
                "Connection refused", request=MagicMock()
            )

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert "Network error" in blocker.args[0]

    def test_error_on_unexpected_exception(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.side_effect = ValueError("Something went wrong")

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert "Unexpected error" in blocker.args[0]

    def test_error_emits_progress_failed(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        progress_signals = []

        def capture_progress(label, pct):
            progress_signals.append((label, pct))

        worker.progress.connect(capture_progress)

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.side_effect = httpx.RequestError(
                "Timeout", request=MagicMock()
            )

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.error, timeout=3000):
                worker.start()
            worker.wait(500)

        assert any(label == "Failed" for label, _ in progress_signals)


# ── Request method delegation ────────────────────────────────────────────


class TestNetworkWorkerRequestMethods:
    """Verify the correct httpx method is called."""

    def test_get_calls_client_get(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource", params={"q": "test"})
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            mock_instance.get.assert_called_once_with("/api/resource", params={"q": "test"})

    def test_post_calls_client_post(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.post.return_value = _make_mock_response(201, {})

            worker.call_action("POST", "/api/resource", json_data={"name": "x"})
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            mock_instance.post.assert_called_once_with("/api/resource", json={"name": "x"})

    def test_put_calls_client_put(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.put.return_value = _make_mock_response(200, {})

            worker.call_action("PUT", "/api/resource/1", json_data={"key": "val"})
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            mock_instance.put.assert_called_once_with("/api/resource/1", json={"key": "val"})

    def test_delete_calls_client_delete(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.delete.return_value = _make_mock_response(204, {})

            worker.call_action("DELETE", "/api/resource/1")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            mock_instance.delete.assert_called_once_with("/api/resource/1")

    def test_method_upper_cased(self, qtbot):
        """call_action uppercases the method string."""
        worker = NetworkWorker(base_url="http://test.com")
        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("get", "/api/resource")
            assert worker._method == "GET"


# ── Headers & auth ───────────────────────────────────────────────────────


class TestNetworkWorkerHeaders:
    def test_api_key_header_added(self, qtbot):
        config = MagicMock()
        config.api_url = "http://test.com"
        config.verify_ssl = False
        config.api_key = "sk-1234"
        worker = NetworkWorker(config=config)

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["headers"]["X-API-Key"] == "sk-1234"

    def test_no_api_key_header_when_empty(self, qtbot):
        config = MagicMock()
        config.api_url = "http://test.com"
        config.verify_ssl = False
        config.api_key = ""
        worker = NetworkWorker(config=config)

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            call_kwargs = mock_cls.call_args[1]
            assert "X-API-Key" not in call_kwargs.get("headers", {})

    def test_base_url_and_verify_passed_to_client(self, qtbot):
        worker = NetworkWorker(base_url="https://my.api.com", verify_ssl=True)

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["base_url"] == "https://my.api.com"
            assert call_kwargs["verify"] is True


# ── Timeout configuration ────────────────────────────────────────────────


class TestNetworkWorkerTimeout:
    def test_default_timeout_on_client(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            call_kwargs = mock_cls.call_args[1]
            timeout = call_kwargs["timeout"]
            assert timeout.connect == 10.0
            assert timeout.read == 120.0

    def test_upload_uses_longer_timeout(self, qtbot, tmp_path):
        """Uploads use a 300s timeout on the POST call."""
        upload_file = tmp_path / "test.pdf"
        upload_file.write_text("dummy content")

        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.post.return_value = _make_mock_response(200, {"ok": True})

            worker.upload("/api/upload", str(upload_file), form_data={"cat": "docs"})
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            call_kwargs = mock_instance.post.call_args[1]
            timeout = call_kwargs["timeout"]
            assert timeout.connect == 10.0
            assert timeout.read == 300.0


# ── File upload ──────────────────────────────────────────────────────────


class TestNetworkWorkerUpload:
    def test_upload_missing_file_raises_error(self, qtbot):
        worker = NetworkWorker(base_url="http://test.com")

        with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
            worker.upload("/api/upload", "/nonexistent/file.pdf")
            worker.start()
            worker.wait(500)

        assert "File not found" in blocker.args[0]

    def test_upload_success(self, qtbot, tmp_path):
        upload_file = tmp_path / "invoice.pdf"
        upload_file.write_bytes(b"%PDF-1.4 mock content")

        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.post.return_value = _make_mock_response(200, {"id": 99})

            worker.upload("/api/documents/upload", str(upload_file))
            with qtbot.wait_signal(worker.finished, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert blocker.args[0] == {"id": 99}


# ── Clean shutdown ───────────────────────────────────────────────────────


class TestNetworkWorkerShutdown:
    def test_quit_after_start(self, qtbot):
        """Worker can be quit without error."""
        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            worker.start()
            worker.quit()
            worker.wait(1000)
            assert worker.isFinished()

    def test_stop_event_can_be_set_externally(self):
        worker = NetworkWorker()
        assert not worker.stop_event.is_set()
        worker.stop_event.set()
        assert worker.stop_event.is_set()

    def test_stop_event_accessible_property(self):
        worker = NetworkWorker()
        assert worker.stop_event is worker._stop_event


# ── Edge cases ───────────────────────────────────────────────────────────


class TestNetworkWorkerEdgeCases:
    def test_malformed_json_response(self, qtbot):
        """If the server returns invalid JSON, an error signal is emitted."""
        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_response = _make_mock_response(200)
            mock_response.json.side_effect = ValueError("Malformed JSON")
            mock_instance.get.return_value = mock_response

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.error, timeout=3000) as blocker:
                worker.start()
            worker.wait(500)

        assert "Unexpected error" in blocker.args[0]

    def test_client_closed_after_request(self, qtbot):
        """The httpx.Client is closed in the finally block."""
        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

            mock_instance.close.assert_called_once()

    def test_client_closed_on_error(self, qtbot):
        """Client is closed even when an error occurs."""
        worker = NetworkWorker(base_url="http://test.com")

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.side_effect = httpx.RequestError(
                "fail", request=MagicMock()
            )

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.error, timeout=3000):
                worker.start()
            worker.wait(500)

            mock_instance.close.assert_called_once()

    def test_run_emits_connecting_progress_first(self, qtbot):
        """The very first emission is always 'Connecting...'."""
        worker = NetworkWorker(base_url="http://test.com")

        first_signal = []

        def capture_first(label, pct):
            if not first_signal:
                first_signal.append((label, pct))

        worker.progress.connect(capture_first)

        with patch("client.network.network_worker.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            mock_instance.get.return_value = _make_mock_response(200, {})

            worker.call_action("GET", "/api/resource")
            with qtbot.wait_signal(worker.finished, timeout=3000):
                worker.start()
            worker.wait(500)

        assert first_signal[0] == ("Connecting...", 0)
