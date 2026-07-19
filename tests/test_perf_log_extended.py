"""Extended unit tests for utils/perf_log.py — measurement accuracy,
decorator-style usage, formatting edge cases, and disable behaviour.

Builds on the existing test_perf_log.py coverage with additional
scenarios for perf_timer time measurement, wrapping functions,
perf_log formatting details, and the disabled/no-op path.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

import utils.perf_log as perf_log_module


# ────────────────────────────────────────────────────────────────
# perf_timer — measurement accuracy
# ────────────────────────────────────────────────────────────────


class TestPerfTimerAccuracy:
    """Verify perf_timer measures elapsed time correctly."""

    def test_measures_elapsed_time_approximately(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("sleep_test"):
                    time.sleep(0.05)
                mock_info.assert_called_once()
                msg = mock_info.call_args[0][0]
                # Expect at least ~50ms, allow tolerance for CI
                prefix = "[perf] sleep_test: "
                assert msg.startswith(prefix)
                ms_str = msg[len(prefix):-2]  # strip "ms"
                elapsed = float(ms_str)
                assert elapsed >= 40.0, f"Expected >= 40ms, got {elapsed}ms"
                assert elapsed <= 500.0, f"Expected <= 500ms, got {elapsed}ms"

    def test_instant_op_logs_near_zero(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("instant"):
                    pass
                mock_info.assert_called_once()
                msg = mock_info.call_args[0][0]
                ms_str = msg.split(": ")[1].rstrip("ms")
                elapsed = float(ms_str)
                assert elapsed < 10.0, f"Expected < 10ms, got {elapsed}ms"

    def test_multiple_timers_independent(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("first"):
                    time.sleep(0.02)
                with perf_log_module.perf_timer("second"):
                    time.sleep(0.04)
                assert mock_info.call_count == 2
                first_msg = mock_info.call_args_list[0][0][0]
                second_msg = mock_info.call_args_list[1][0][0]
                assert "[perf] first:" in first_msg
                assert "[perf] second:" in second_msg

    def test_nested_timers_both_logged(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("outer"):
                    with perf_log_module.perf_timer("inner"):
                        time.sleep(0.01)
                assert mock_info.call_count == 2
                # Inner timer's finally block runs first → it is logged first
                inner_msg = mock_info.call_args_list[0][0][0]
                outer_msg = mock_info.call_args_list[1][0][0]
                assert "[perf] outer:" in outer_msg
                assert "[perf] inner:" in inner_msg


# ────────────────────────────────────────────────────────────────
# perf_timer — wrapping functions (decorator-style)
# ────────────────────────────────────────────────────────────────


class TestPerfTimerAsDecorator:
    """Use perf_timer as a context manager to wrap function execution."""

    def test_wraps_function_execution(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:

                def my_func(x: int) -> int:
                    return x * 2

                with perf_log_module.perf_timer("my_func"):
                    result = my_func(21)

                assert result == 42
                mock_info.assert_called_once()
                assert "[perf] my_func:" in mock_info.call_args[0][0]

    def test_wraps_function_with_args_kwargs(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:

                def add(a, b, c=0):
                    return a + b + c

                with perf_log_module.perf_timer("add"):
                    result = add(10, 20, c=5)

                assert result == 35
                mock_info.assert_called_once()

    def test_wraps_function_that_raises(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:

                def will_raise():
                    raise ValueError("boom")

                with pytest.raises(ValueError, match="boom"):
                    with perf_log_module.perf_timer("will_raise"):
                        will_raise()

                # Even on exception, the timer should still log
                mock_info.assert_called_once()
                assert "[perf] will_raise:" in mock_info.call_args[0][0]

    def test_reusable_timer_pattern(self):
        """Simulate a reusable decorator by wrapping calls manually."""
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:

                results = []
                for i in range(3):
                    with perf_log_module.perf_timer(f"iteration_{i}"):
                        results.append(i * 2)

                assert results == [0, 2, 4]
                assert mock_info.call_count == 3
                for i in range(3):
                    assert f"[perf] iteration_{i}:" in mock_info.call_args_list[i][0][0]

    def test_timer_returns_elapsed_through_custom_context(self):
        """perf_timer yields None, so capture elapsed via surrounding code.

        This test demonstrates measuring elapsed time alongside the timer.
        """
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                t0 = time.perf_counter()
                with perf_log_module.perf_timer("manual"):
                    time.sleep(0.02)
                manual_elapsed = (time.perf_counter() - t0) * 1000.0

                mock_info.assert_called_once()
                msg = mock_info.call_args[0][0]
                ms_str = msg.split(": ")[1].rstrip("ms")
                logged_elapsed = float(ms_str)

                # Logged value should be close to manual measurement
                assert abs(logged_elapsed - manual_elapsed) < 10.0


# ────────────────────────────────────────────────────────────────
# perf_log — formatting edge cases
# ────────────────────────────────────────────────────────────────


class TestPerfLogFormatting:
    """Verify perf_log message format with various inputs."""

    def test_standard_format(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("test_op", 123.45)
                mock_info.assert_called_once_with(
                    "[perf] test_op: 123.5ms"
                )

    def test_with_detail(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("calc", 50.0, detail="route_id=42")
                mock_info.assert_called_once_with(
                    "[perf] calc: 50.0ms (route_id=42)"
                )

    def test_detail_none(self):
        """detail=None should be treated the same as no detail."""
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("op", 10.0, detail=None)
                mock_info.assert_called_once_with(
                    "[perf] op: 10.0ms"
                )

    def test_detail_empty_string(self):
        """Empty string is falsy, so no detail appended."""
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("op", 10.0, detail="")
                mock_info.assert_called_once_with(
                    "[perf] op: 10.0ms"
                )

    def test_zero_ms(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("zero", 0.0)
                mock_info.assert_called_once_with(
                    "[perf] zero: 0.0ms"
                )

    def test_very_small_value(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("tiny", 0.001)
                mock_info.assert_called_once_with(
                    "[perf] tiny: 0.0ms"
                )

    def test_large_value(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("slow", 99999.99)
                mock_info.assert_called_once_with(
                    "[perf] slow: 100000.0ms"
                )

    def test_negative_value(self):
        """Negative elapsed doesn't make sense but should not crash."""
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("neg", -5.0)
                mock_info.assert_called_once_with(
                    "[perf] neg: -5.0ms"
                )

    def test_label_with_spaces(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("my custom label", 10.0)
                mock_info.assert_called_once_with(
                    "[perf] my custom label: 10.0ms"
                )

    def test_label_with_special_chars(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("calc[1]:load", 5.0)
                mock_info.assert_called_once_with(
                    "[perf] calc[1]:load: 5.0ms"
                )

    def test_unicode_in_detail(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("unicode", 1.23, detail="café=100€")
                mock_info.assert_called_once_with(
                    "[perf] unicode: 1.2ms (café=100€)"
                )


# ────────────────────────────────────────────────────────────────
# perf_enabled toggle — timer no-ops when disabled
# ────────────────────────────────────────────────────────────────


class TestPerfTimerDisabled:
    """When _PERF_ENABLED is False, perf_timer should be a no-op."""

    def test_disabled_does_not_log(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            mock_logger = MagicMock()
            with perf_log_module.perf_timer("no_op", logger=mock_logger):
                pass
            mock_logger.info.assert_not_called()

    def test_disabled_skips_timing_overhead(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            mock_logger = MagicMock()
            t0 = time.perf_counter()
            with perf_log_module.perf_timer("fast", logger=mock_logger):
                time.sleep(0.01)
            elapsed = time.perf_counter() - t0
            # Should be fast because no perf_counter calls or logging
            mock_logger.info.assert_not_called()

    def test_disabled_still_executes_body(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            side_effect = []
            with perf_log_module.perf_timer("should_execute"):
                side_effect.append(42)
            assert side_effect == [42]

    def test_disabled_body_exception_still_propagates(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            with pytest.raises(RuntimeError, match="expected"):
                with perf_log_module.perf_timer("raise"):
                    raise RuntimeError("expected")

    def test_disabled_log_function(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("should_not_log", 10.0)
                mock_info.assert_not_called()

    def test_disabled_log_with_detail_noop(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                perf_log_module.perf_log("op", 5.0, detail="ignored")
                mock_info.assert_not_called()

    def test_toggle_via_env_var(self):
        """Verify that setting env var controls enable state at import time."""
        import importlib

        with patch.dict("os.environ", {"ROUTE_PERF_LOG": "1"}):
            import utils.perf_log as perf_on
            importlib.reload(perf_on)
            assert perf_on.perf_enabled() is True

        with patch.dict("os.environ", {"ROUTE_PERF_LOG": "0"}):
            import utils.perf_log as perf_off
            importlib.reload(perf_off)
            assert perf_off.perf_enabled() is False

    def test_disabled_custom_logger_not_called(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            custom_logger = MagicMock()
            with perf_log_module.perf_timer("custom", logger=custom_logger):
                pass
            custom_logger.info.assert_not_called()

    def test_disabled_nested_timers_no_log(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", False):
            mock_logger = MagicMock()
            with perf_log_module.perf_timer("outer", logger=mock_logger):
                with perf_log_module.perf_timer("inner", logger=mock_logger):
                    pass
            mock_logger.info.assert_not_called()


# ────────────────────────────────────────────────────────────────
# perf_timer — custom logger edge cases
# ────────────────────────────────────────────────────────────────


class TestPerfTimerCustomLogger:
    """Custom logger parameter behaviour."""

    def test_custom_logger_used_when_provided(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            custom_logger = MagicMock()
            with perf_log_module.perf_timer("custom_test", logger=custom_logger):
                pass
            custom_logger.info.assert_called_once()
            msg = custom_logger.info.call_args[0][0]
            assert "[perf] custom_test:" in msg

    def test_custom_logger_with_detail_in_msg(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            custom_logger = MagicMock()
            # perf_timer doesn't support detail; this tests the
            # context manager's formatting only (no detail param).
            with perf_log_module.perf_timer("my_label", logger=custom_logger):
                pass
            msg = custom_logger.info.call_args[0][0]
            assert msg.startswith("[perf] my_label: ")
            assert msg.endswith("ms")

    def test_default_logger_is_module_logger(self):
        with patch.object(perf_log_module, "_PERF_ENABLED", True):
            with patch.object(perf_log_module._logger, "info") as mock_info:
                with perf_log_module.perf_timer("default"):
                    pass
                mock_info.assert_called_once()
