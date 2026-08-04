"""Tests for utils.logger — get_logger with once-per-name handler setup."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pytest

import utils.logger as logger_module


# ── Helpers ────────────────────────────────────────────────────────────


def _fresh_logger_module():
    """Reload the logger module to reset module-level state.

    Patch ``os.makedirs`` so the import-time call is a no-op, then
    re-import to get a clean ``_configured_loggers`` set and avoid
    real filesystem side effects.
    """
    with patch.object(logger_module.os, "makedirs") as mock_makedirs:
        # Python's import system caches; force a re-import.
        import importlib  # pylint: disable=import-outside-toplevel

        return importlib.reload(logger_module), mock_makedirs


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_logger_state():
    """Clear the ``_configured_loggers`` set before each test.

    Also clear handlers from ALL existing loggers so that MagicMock
    handlers installed by ``mock_file_handler`` in a previous test
    do not pollute later tests in the same process.
    """
    logger_module._configured_loggers.clear()
    logging.root.handlers.clear()
    logging.root.propagate = True
    logging.root.setLevel(logging.NOTSET)
    for name in list(logging.root.manager.loggerDict.keys()):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True
        log.setLevel(logging.NOTSET)
    yield


@pytest.fixture
def mock_file_handler():
    """Patch ``logging.handlers.RotatingFileHandler`` so no real files are
    created.

    ``utils.logger`` builds its file handlers via ``RotatingFileHandler``
    (10 MB x 5 backups), so that is the class the fixture intercepts.  The
    mock instance is a plain ``MagicMock`` (no spec) because the class itself
    is already replaced by the patch, preventing us from using
    ``spec=logging.handlers.RotatingFileHandler``.

    After the test, clear handlers from all loggers that were created
    during the patch so MagicMock handlers don't pollute other tests.
    """
    known_before = set(logging.root.manager.loggerDict.keys())
    with patch("logging.handlers.RotatingFileHandler") as m:
        mock_instance = MagicMock()
        m.return_value = mock_instance
        yield m, mock_instance
    # Clean up any loggers created during the patch
    logging.root.handlers.clear()
    logging.root.propagate = True
    logging.root.setLevel(logging.NOTSET)
    for name in set(logging.root.manager.loggerDict.keys()) - known_before:
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True
        log.setLevel(logging.NOTSET)


# ── Tests ──────────────────────────────────────────────────────────────


class TestGetLogger:
    """Tests for the ``get_logger`` function."""

    # ── Basic contract ─────────────────────────────────────────────

    def test_returns_logger_with_correct_name(self, mock_file_handler):
        """The returned logger should have the requested name."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("my_module")
        assert log.name == "my_module"

    def test_returns_logger_instance(self, mock_file_handler):
        """The returned object should be a ``logging.Logger`` instance."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("my_module")
        assert isinstance(log, logging.Logger)

    # ── One-time configuration ─────────────────────────────────────

    def test_handler_added_only_once(self, mock_file_handler):
        """Repeated ``get_logger`` calls for the same name must not add
        more than one handler."""
        mock_cls, _ = mock_file_handler
        logger_module.get_logger("dedup")
        logger_module.get_logger("dedup")
        logger_module.get_logger("dedup")
        assert mock_cls.call_count == 1, (
            f"Expected 1 FileHandler instantiation, got {mock_cls.call_count}"
        )

    def test_only_one_handler_on_logger(self, mock_file_handler):
        """The logger should have exactly one handler after repeated calls."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("handler_count")
        logger_module.get_logger("handler_count")
        assert len(log.handlers) == 1

    def test_second_call_returns_same_logger_object(self, mock_file_handler):
        """Multiple calls with the same name return the exact same object."""
        _, _ = mock_file_handler
        log1 = logger_module.get_logger("same_obj")
        log2 = logger_module.get_logger("same_obj")
        assert log1 is log2

    # ── propagate ──────────────────────────────────────────────────

    def test_propagate_is_false(self, mock_file_handler):
        """``propagate`` must be ``False`` so messages don't bubble up to
        the root logger."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("propagate_test")
        assert log.propagate is False

    # ── Logger levels ──────────────────────────────────────────────

    def test_default_level_is_info(self, mock_file_handler):
        """When no level is passed, the logger should be set to INFO."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("default_level")
        assert log.level == logging.INFO

    def test_custom_level_is_respected(self, mock_file_handler):
        """Passing an explicit level should be honoured."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("custom_level", level=logging.WARNING)
        assert log.level == logging.WARNING

    def test_custom_level_debug(self, mock_file_handler):
        """Passing ``logging.DEBUG`` explicitly should work for non-route
        loggers."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("explicit_debug", level=logging.DEBUG)
        assert log.level == logging.DEBUG

    def test_custom_level_error(self, mock_file_handler):
        """Passing ``logging.ERROR`` explicitly should work."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("explicit_error", level=logging.ERROR)
        assert log.level == logging.ERROR

    # ── route_debug special case ───────────────────────────────────

    def test_route_debug_gets_debug_level(self, mock_file_handler):
        """The special ``route_debug`` logger must always be DEBUG
        regardless of the passed level."""
        mock_cls, _ = mock_file_handler
        # Even if someone passes INFO, route_debug should be DEBUG.
        log = logger_module.get_logger("route_debug", level=logging.INFO)
        assert log.level == logging.DEBUG, (
            "route_debug logger should be DEBUG even when INFO is requested"
        )
        # Verify the correct file path was used.
        assert mock_cls.call_args[0][0] == "logs/route_debug.log"

    def test_route_debug_uses_separate_file(self, mock_file_handler):
        """route_debug must create a FileHandler pointed at the dedicated
        log file."""
        mock_cls, _ = mock_file_handler
        logger_module.get_logger("route_debug")
        call_args = mock_cls.call_args
        assert call_args is not None
        assert "route_debug.log" in str(call_args[0][0])

    # ── Regular loggers use app.log ────────────────────────────────

    def test_regular_logger_uses_app_log_file(self, mock_file_handler):
        """A non-route logger must create a FileHandler for ``logs/app.log``."""
        mock_cls, _ = mock_file_handler
        logger_module.get_logger("regular_module")
        assert mock_cls.call_args[0][0] == "logs/app.log"

    def test_different_file_paths_for_different_types(self, mock_file_handler):
        """route_debug and a regular logger should use different log files."""
        mock_cls, _ = mock_file_handler
        logger_module.get_logger("route_debug")
        logger_module.get_logger("some_other")
        # Two instantiations: one for route_debug, one for some_other.
        assert mock_cls.call_count == 2
        calls = mock_cls.call_args_list
        # Order depends on call order: route_debug first, then some_other.
        assert calls[0][0][0] == "logs/route_debug.log"
        assert calls[1][0][0] == "logs/app.log"

    # ── Handler configuration ──────────────────────────────────────

    def test_handler_has_formatter(self, mock_file_handler):
        """The rotating file handler should have a formatter set."""
        _, mock_instance = mock_file_handler
        logger_module.get_logger("formatter_test")
        mock_instance.setFormatter.assert_called_once()
        fmt_arg = mock_instance.setFormatter.call_args[0][0]
        assert isinstance(fmt_arg, logging.Formatter)

    def test_handler_type_is_rotating_file_handler(self, mock_file_handler):
        """The handler added to the logger should be a ``RotatingFileHandler``.

        ``logging.handlers.RotatingFileHandler`` is patched, so we verify the
        handler is the mock instance returned by the patched class.
        """
        mock_cls, _ = mock_file_handler
        log = logger_module.get_logger("type_check")
        assert len(log.handlers) == 1
        assert log.handlers[0] is mock_cls.return_value

    def test_regular_logger_rotates_at_10mb_with_5_backups(self, mock_file_handler):
        """app.log handlers must roll over at 10 MB keeping 5 backups."""
        mock_cls, _ = mock_file_handler
        logger_module.get_logger("rotation_check")
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["maxBytes"] == 10_000_000
        assert kwargs["backupCount"] == 5

    # ── _configured_loggers state ──────────────────────────────────

    def test_configured_loggers_is_populated(self, mock_file_handler):
        """After calling ``get_logger``, the module-level set should
        contain the logger name."""
        _, _ = mock_file_handler
        assert "state_check" not in logger_module._configured_loggers
        logger_module.get_logger("state_check")
        assert "state_check" in logger_module._configured_loggers

    def test_configured_loggers_tracks_multiple_names(self, mock_file_handler):
        """Multiple distinct logger names should all appear in the set."""
        _, _ = mock_file_handler
        logger_module.get_logger("alpha")
        logger_module.get_logger("beta")
        logger_module.get_logger("gamma")
        assert logger_module._configured_loggers == {"alpha", "beta", "gamma"}

    def test_duplicate_name_does_not_grow_set(self, mock_file_handler):
        """Calling ``get_logger`` repeatedly with the same name must not
        add duplicate entries to ``_configured_loggers``."""
        _, _ = mock_file_handler
        logger_module.get_logger("no_dup")
        logger_module.get_logger("no_dup")
        logger_module.get_logger("no_dup")
        assert len(logger_module._configured_loggers) == 1

    # ── Module-level side effects ──────────────────────────────────

    def test_os_makedirs_called_on_import(self):
        """``os.makedirs("logs", exist_ok=True)`` should be invoked when
        the module is first loaded."""
        mod, mock_makedirs = _fresh_logger_module()
        assert mod is not None
        mock_makedirs.assert_called_once_with("logs", exist_ok=True)

    # ── Edge cases ─────────────────────────────────────────────────

    def test_empty_string_name_returns_root(self, mock_file_handler):
        """An empty string is treated as the root logger by Python's
        logging framework (``logging.getLogger("")`` gives root)."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("")
        assert log.name == "root"
        assert log.propagate is False

    def test_logger_name_with_dots(self, mock_file_handler):
        """Hierarchical logger names (e.g. 'foo.bar.baz') should work."""
        _, _ = mock_file_handler
        log = logger_module.get_logger("foo.bar.baz")
        assert log.name == "foo.bar.baz"
        assert log.propagate is False

    def test_get_logger_with_none_name_returns_root_logger(self, mock_file_handler):
        """``logging.getLogger(None)`` returns the root logger; our
        wrapper should do the same."""
        _, _ = mock_file_handler
        log = logger_module.get_logger(None)  # type: ignore[arg-type]
        assert log.name == "root"
        assert log is logging.getLogger(None)
