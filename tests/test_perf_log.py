"""Comprehensive unit tests for utils/perf_log.py.

Tests cover perf_enabled, perf_log, and perf_timer — including
env-var-based enabling, the timer context manager, and log
formatting with and without detail.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import utils.perf_log as perf_log_module


# ──────────────────────────────────────────────────────────────
# perf_enabled
# ──────────────────────────────────────────────────────────────


class TestPerfEnabled:
    """Check whether performance logging is enabled."""

    def test_disabled_by_default(self):
        # The module-level _PERF_ENABLED is False unless env var is set
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            assert perf_log_module.perf_enabled() is False

    def test_enabled_when_flag_is_true(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            assert perf_log_module.perf_enabled() is True

    def test_directly_returns_module_constant(self):
        # Verify it's reading _PERF_ENABLED by patching the module var
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            assert perf_log_module.perf_enabled() is True

        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            assert perf_log_module.perf_enabled() is False

    def test_env_var_controls_enabled(self):
        # Test the actual import-time behaviour via a fresh import
        with patch.dict("os.environ", {"ROUTE_PERF_LOG": "1"}):
            # Re-import to trigger the env-var read
            import importlib
            import utils.perf_log as reloaded_perf_log
            importlib.reload(reloaded_perf_log)
            assert reloaded_perf_log.perf_enabled() is True

    def test_env_var_false_values(self):
        for val in ("0", "", "false", "no"):
            with patch.dict("os.environ", {"ROUTE_PERF_LOG": val}):
                import importlib
                import utils.perf_log as reloaded_perf_log
                importlib.reload(reloaded_perf_log)
                assert reloaded_perf_log.perf_enabled() is False


# ──────────────────────────────────────────────────────────────
# perf_log
# ──────────────────────────────────────────────────────────────


class TestPerfLog:
    """Log a performance message with optional detail."""

    def test_disabled_does_not_log(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("test_op", 123.45)
                mock_info.assert_not_called()

    def test_enabled_logs_message(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("test_op", 123.45)
                mock_info.assert_called_once_with(
                    "[perf] test_op: 123.5ms"
                )

    def test_log_with_detail(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("calc", 50.0, detail="route_id=42")
                mock_info.assert_called_once_with(
                    "[perf] calc: 50.0ms (route_id=42)"
                )

    def test_log_milli_rounding(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("op", 0.1234)
                mock_info.assert_called_once_with(
                    "[perf] op: 0.1ms"
                )

    def test_log_zero_ms(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("fast", 0.0)
                mock_info.assert_called_once_with(
                    "[perf] fast: 0.0ms"
                )

    def test_log_with_empty_detail(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("op", 10.0, detail="")
                # Empty string is truthy? "" → bool("") is False → no detail appended
                mock_info.assert_called_once_with(
                    "[perf] op: 10.0ms"
                )


# ──────────────────────────────────────────────────────────────
# perf_timer
# ──────────────────────────────────────────────────────────────


class TestPerfTimer:
    """Context manager that logs elapsed time."""

    def test_disabled_does_not_log(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            mock_logger = MagicMock()
            with perf_log_module.perf_timer("test", logger=mock_logger):
                pass
            mock_logger.info.assert_not_called()

    def test_enabled_logs_elapsed_time(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("timed_op"):
                    pass
                mock_info.assert_called_once()
                call_args = mock_info.call_args[0][0]
                assert call_args.startswith("[perf] timed_op: ")
                assert call_args.endswith("ms")

    def test_custom_logger(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            mock_logger = MagicMock()
            with perf_log_module.perf_timer("custom", logger=mock_logger):
                pass
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "[perf] custom:" in call_args

    def test_timer_works_in_body(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                side_effect = []
                with perf_log_module.perf_timer("with_body"):
                    side_effect.append(1)
                assert side_effect == [1]
                mock_info.assert_called_once()

    def test_timer_logs_after_body_executes(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("ordered"):
                    pass
                # The log must have been called (after the yield)
                mock_info.assert_called_once()

    def test_timer_raises_logs_still_called(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                class TestError(Exception):
                    pass

                with pytest.raises(TestError):
                    with perf_log_module.perf_timer("error_op"):
                        raise TestError("boom")

                # The finally block should still log
                mock_info.assert_called_once()
                call_args = mock_info.call_args[0][0]
                assert "[perf] error_op:" in call_args

    def test_default_logger_is_module_logger(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("default_logger"):
                    pass
                mock_info.assert_called_once()

    def test_timer_label_in_log_message(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("my_label"):
                    pass
                message = mock_info.call_args[0][0]
                assert "[perf] my_label:" in message
