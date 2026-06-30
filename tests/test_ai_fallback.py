"""Tests for services.document_automation.ai_fallback."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

from services.document_automation.ai_fallback import (
    _MAX_STREAM_CHARS,
    _build_prompt,
    _call_with_retry,
    _check_rpm,
    _setting,
    close_session,
    preload_model,
)


class TestBuildPrompt(unittest.TestCase):
    def test_build_prompt_returns_string(self):
        prompt = _build_prompt()
        self.assertIsInstance(prompt, str)
        self.assertIn("Transcribe", prompt)

    def test_build_prompt_with_user_company(self):
        prompt = _build_prompt(user_company="My Co SRL")
        self.assertIn("My Co SRL", prompt)

    def test_build_prompt_mentions_stamp(self):
        prompt = _build_prompt()
        self.assertIn("stamp", prompt.lower())
        self.assertIn("Field 1", prompt)
        self.assertIn("Field 2", prompt)
        self.assertIn("Field 16", prompt)

    def test_build_prompt_mentions_plate_and_date(self):
        prompt = _build_prompt()
        self.assertIn("plate", prompt.lower())
        self.assertIn("license", prompt.lower())


class TestSetting(unittest.TestCase):
    def setUp(self):
        from services.document_automation.ai_fallback import (
            _db_overrides, _db_lock,
        )
        with _db_lock:
            self._old = dict(_db_overrides)
            _db_overrides.clear()
            _db_overrides.update({"qwen_model": "test_model", "qwen_endpoint": ""})

    def tearDown(self):
        from services.document_automation.ai_fallback import (
            _db_overrides, _db_lock,
        )
        with _db_lock:
            _db_overrides.clear()
            _db_overrides.update(self._old)

    def test_setting_returns_db_value(self):
        self.assertEqual(_setting("qwen_model", "default"), "test_model")

    def test_setting_returns_default_when_key_missing(self):
        self.assertEqual(_setting("nonexistent", "fallback"), "fallback")

    def test_setting_returns_default_when_value_empty(self):
        self.assertEqual(
            _setting("qwen_endpoint", "https://default.com"),
            "https://default.com",
        )


class TestCheckRpm(unittest.TestCase):
    def test_check_rpm_zero_limit_always_allows(self):
        self.assertTrue(_check_rpm(0))

    def test_check_rpm_positive_limit_allows_up_to_limit(self):
        for _ in range(10):
            self.assertTrue(_check_rpm(10))


class TestCallWithRetry(unittest.TestCase):
    @patch("services.document_automation.ai_fallback._session")
    def test_success_returns_response(self, mock_session):
        mock_session.post.return_value = MagicMock(status_code=200)
        resp = _call_with_retry("http://test", {}, timeout_s=5, retries=3)
        self.assertIsNotNone(resp)
        if resp is not None:
            self.assertEqual(resp.status_code, 200)

    @patch("services.document_automation.ai_fallback._session")
    def test_server_error_retries(self, mock_session):
        resp_502 = MagicMock(status_code=502)
        resp_ok = MagicMock(status_code=200)
        mock_session.post.side_effect = [resp_502, resp_502, resp_ok]
        resp = _call_with_retry("http://test", {}, timeout_s=5, retries=3)
        self.assertEqual(mock_session.post.call_count, 3)
        self.assertIsNotNone(resp)

    @patch("services.document_automation.ai_fallback._session")
    def test_all_retries_exhausted_returns_last_response(self, mock_session):
        mock_session.post.return_value = MagicMock(status_code=503)
        resp = _call_with_retry("http://test", {}, timeout_s=5, retries=2)
        self.assertIsNotNone(resp)
        if resp is not None:
            self.assertEqual(resp.status_code, 503)


class TestPreloadModel(unittest.TestCase):
    @patch("services.document_automation.ai_fallback._call_with_retry")
    def test_preload_model_calls_retry(self, mock_retry):
        preload_model()
        mock_retry.assert_called_once()
        args, kwargs = mock_retry.call_args
        self.assertIn("/api/generate", args[0])


class TestCloseSession(unittest.TestCase):
    def test_close_session_does_not_raise(self):
        close_session()
        # Call twice to verify idempotent
        close_session()


class TestConstants(unittest.TestCase):
    def test_max_stream_chars_defined(self):
        self.assertGreater(_MAX_STREAM_CHARS, 0)
        self.assertEqual(_MAX_STREAM_CHARS, 100_000)


if __name__ == "__main__":
    unittest.main()
