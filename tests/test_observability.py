"""Tests for utils.observability — structured logger, metrics, perf_timer, timed."""

from __future__ import annotations

import json
import logging
import threading
from unittest.mock import patch

import pytest

from utils.observability import (
    _Metrics,
    _StructuredLogger,
    log,
    metrics,
    perf_timer,
    timed,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield


@pytest.fixture(autouse=True)
def _enable_all_logging():
    """Undo any module-level ``logging.disable(...)`` left by other suites.

    Some e2e modules call ``logging.disable(logging.CRITICAL)`` at import
    time; without a reset, ``_StructuredLogger._emit``'s ``isEnabledFor``
    check returns False and the underlying ``log`` call never fires — which
    makes these assertions see ``call_args is None``.  The root conftest also
    resets this per test, but being self-sufficient keeps this module green
    regardless of conftest state.
    """
    logging.disable(logging.NOTSET)
    yield


class TestStructuredLogger:
    """_StructuredLogger emits JSON lines with correct level, message, and fields."""

    @pytest.fixture(autouse=True)
    def _low_level(self):
        """Ensure logger accepts all levels during tests."""
        logging.getLogger("test_structured").setLevel(logging.DEBUG)

    def _make(self) -> _StructuredLogger:
        return _StructuredLogger("test_structured")

    def test_info_emits_json(self):
        logger = self._make()
        with patch.object(logger._logger, "log") as mock_log:
            logger.info("hello", user_id=42)
        mock_log.assert_called_once()
        args, _ = mock_log.call_args
        assert args[0] == logging.INFO
        record = json.loads(args[1])
        assert record["level"] == "INFO"
        assert record["message"] == "hello"
        assert record["user_id"] == 42

    def test_warning_level(self):
        logger = self._make()
        with patch.object(logger._logger, "log") as mock_log:
            logger.warning("warn")
        record = json.loads(mock_log.call_args[0][1])
        assert record["level"] == "WARNING"

    def test_error_level(self):
        logger = self._make()
        with patch.object(logger._logger, "log") as mock_log:
            logger.error("err")
        record = json.loads(mock_log.call_args[0][1])
        assert record["level"] == "ERROR"

    def test_debug_level(self):
        logger = self._make()
        with patch.object(logger._logger, "log") as mock_log:
            logger.debug("dbg")
        record = json.loads(mock_log.call_args[0][1])
        assert record["level"] == "DEBUG"

    def test_extra_fields_included(self):
        logger = self._make()
        with patch.object(logger._logger, "log") as mock_log:
            logger.info("op", duration_ms=12.5, count=3, tags=["a", "b"])
        record = json.loads(mock_log.call_args[0][1])
        assert record["duration_ms"] == 12.5
        assert record["count"] == 3
        assert record["tags"] == ["a", "b"]

    def test_timestamp_and_pid_always_present(self):
        logger = self._make()
        with patch.object(logger._logger, "log") as mock_log:
            logger.info("check")
        record = json.loads(mock_log.call_args[0][1])
        assert "timestamp" in record
        assert "pid" in record

    def test_skips_when_disabled(self):
        logger = self._make()
        logger._logger.setLevel(logging.CRITICAL + 1)
        with patch.object(logger._logger, "log") as mock_log:
            logger.info("should not fire")
        mock_log.assert_not_called()


class TestMetrics:
    """_Metrics is thread-safe and correctly tracks counters / gauges."""

    def test_increment_default_delta(self):
        m = _Metrics()
        m.increment("hits")
        assert m.get_counter("hits") == 1

    def test_increment_custom_delta(self):
        m = _Metrics()
        m.increment("hits", 5)
        assert m.get_counter("hits") == 5

    def test_increment_multiple_calls(self):
        m = _Metrics()
        for _ in range(3):
            m.increment("hits")
        assert m.get_counter("hits") == 3

    def test_get_counter_unknown_returns_zero(self):
        m = _Metrics()
        assert m.get_counter("nonexistent") == 0

    def test_gauge_set_and_get(self):
        m = _Metrics()
        m.gauge("temp", 36.5)
        assert m.get_gauge("temp") == 36.5

    def test_gauge_overwrite(self):
        m = _Metrics()
        m.gauge("temp", 36.5)
        m.gauge("temp", 37.0)
        assert m.get_gauge("temp") == 37.0

    def test_get_gauge_unknown_returns_zero(self):
        m = _Metrics()
        assert m.get_gauge("nonexistent") == 0.0

    def test_snapshot_includes_uptime(self):
        m = _Metrics()
        snap = m.snapshot()
        assert "uptime_seconds" in snap
        assert snap["counters"] == {}
        assert snap["gauges"] == {}

    def test_snapshot_contains_all_data(self):
        m = _Metrics()
        m.increment("a", 2)
        m.gauge("b", 1.5)
        snap = m.snapshot()
        assert snap["counters"]["a"] == 2
        assert snap["gauges"]["b"] == 1.5

    def test_reset_clears_all(self):
        m = _Metrics()
        m.increment("a")
        m.gauge("b", 1)
        m.reset()
        assert m.get_counter("a") == 0
        assert m.get_gauge("b") == 0.0

    def test_thread_safety(self):
        m = _Metrics()
        n = 100
        errors = []

        def worker():
            try:
                for _ in range(n):
                    m.increment("shared", 1)
                    m.gauge("g", 1.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert m.get_counter("shared") == 4 * n


class TestPerfTimer:
    """perf_timer context manager records metrics and logs timing."""

    def test_success_records_counter_and_gauge(self):
        with perf_timer("test_op"):
            pass
        assert metrics.get_counter("perf.test_op.count") == 1
        assert metrics.get_gauge("perf.test_op.last_ms") > 0

    def test_exception_does_not_record_metric(self):
        with pytest.raises(ValueError):
            with perf_timer("fail_op"):
                raise ValueError("boom")
        assert metrics.get_counter("perf.fail_op.count") == 0

    def test_log_result_false_skips_logging(self):
        logger = _StructuredLogger("operion_test")
        logger._logger.setLevel(logging.DEBUG)
        with patch.object(logger._logger, "log") as mock_log:
            with perf_timer("quiet", log_result=False):
                pass
            mock_log.assert_not_called()


class TestTimedDecorator:
    """@timed wraps a function with perf_timer."""

    def test_decorated_records_metric(self):
        @timed
        def my_func():
            return 42

        result = my_func()
        assert result == 42
        snap = metrics.snapshot()
        perf_counters = {k: v for k, v in snap["counters"].items() if k.startswith("perf.")}
        assert len(perf_counters) == 1
        assert list(perf_counters.values())[0] == 1

    def test_decorated_exception_bubbles(self):
        @timed
        def crash():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            crash()


class TestModuleSingletons:
    """Module-level ``log`` and ``metrics`` singletons are properly typed."""

    def test_log_is_structured_logger(self):
        assert isinstance(log, _StructuredLogger)

    def test_metrics_is_metrics(self):
        assert isinstance(metrics, _Metrics)
