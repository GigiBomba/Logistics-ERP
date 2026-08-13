"""Unit tests for TachoService pure methods — no DB, no mocking.

Tests cover three groups of static/pure methods:
  • TachoService._safe_str(val)       — static
  • TachoService._get_nested(d, …)    – static
  • TachoService._parse_tacho_date(…) — instance method (no ``self`` use)
"""

from __future__ import annotations

from datetime import date
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from services.tacho_service import TachoService


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def service() -> TachoService:
    """Return a TachoService instance with a fake ``db``.

    The pure methods tested here never touch ``self.db``, so a mock is
    sufficient.
    """
    return TachoService(db=MagicMock())


# ======================================================================
# _safe_str
# ======================================================================


class TestSafeStr:
    """Cover all branches of ``TachoService._safe_str``."""

    def test_safe_str_none(self) -> None:
        """None → empty string."""
        assert TachoService._safe_str(None) == ""

    def test_safe_str_plain_string(self) -> None:
        """Plain string passes through unchanged."""
        assert TachoService._safe_str("hello") == "hello"

    def test_safe_str_dict_with_value_key(self) -> None:
        """Dict with ``value`` key returns that value."""
        assert TachoService._safe_str({"value": "X"}) == "X"

    def test_safe_str_dict_with_name_only(self) -> None:
        """Dict without ``value`` falls back to ``name``."""
        assert TachoService._safe_str({"name": "Y"}) == "Y"

    def test_safe_str_int_passthrough(self) -> None:
        """Non-dict non-None is passed through ``str()``."""
        assert TachoService._safe_str(42) == "42"

    def test_safe_str_empty_dict(self) -> None:
        """Empty dict → empty string (no value, no name)."""
        assert TachoService._safe_str({}) == ""

    def test_safe_str_float(self) -> None:
        """Float gets converted via ``str()``."""
        assert TachoService._safe_str(3.14) == "3.14"


# ======================================================================
# _get_nested
# ======================================================================


class TestGetNested:
    """Cover single-key, dotted-path, fallback and default behaviour."""

    def test_get_nested_simple_key(self) -> None:
        """Single key present returns the value."""
        assert TachoService._get_nested({"a": 1}, "a") == 1

    def test_get_nested_dotted_path(self) -> None:
        """Dotted path traverses nested dicts."""
        assert TachoService._get_nested({"a": {"b": 2}}, "a.b") == 2

    def test_get_nested_fallback_path(self) -> None:
        """When the first path misses, the second path is used."""
        data = {"x": {"y": 42}}
        result = TachoService._get_nested(data, "a.b", "x.y")
        assert result == 42

    def test_get_nested_all_missing_returns_default(self) -> None:
        """All paths missing → supplied default."""
        result = TachoService._get_nested(
            {"a": 1}, "b.c", "d.e", default="fallback"
        )
        assert result == "fallback"

    def test_get_nested_deeply_nested(self) -> None:
        """Three-level dotted path."""
        data = {"level1": {"level2": {"level3": "found"}}}
        assert TachoService._get_nested(data, "level1.level2.level3") == "found"

    def test_get_nested_key_error_skips_path(self) -> None:
        """Missing intermediate key is treated as a miss and skipped."""
        data = {"a": {"c": 1}}
        result = TachoService._get_nested(data, "a.b", "a.c")
        assert result == 1

    def test_get_nested_none_value_skips_path(self) -> None:
        """Explicit ``None`` in the dict is skipped (treated as not found)."""
        data = {"a": None, "b": 2}
        result = TachoService._get_nested(data, "a", "b")
        assert result == 2

    def test_get_nested_empty_paths_returns_default(self) -> None:
        """No paths given → default returned."""
        assert TachoService._get_nested({"a": 1}, default=99) == 99

    def test_get_nested_default_none(self) -> None:
        """When no path matches and default is None → None."""
        assert TachoService._get_nested({"a": 1}, "b") is None


# ======================================================================
# _parse_tacho_date
# ======================================================================


class TestParseTachoDate:
    """Cover ISO strings, Unix timestamps, epoch offsets, and edge cases."""

    # -- ISO string variants -------------------------------------------

    def test_parse_tacho_date_iso_string(self, service: TachoService) -> None:
        """Plain ISO date string → ``date``."""
        assert service._parse_tacho_date("2026-07-09") == date(2026, 7, 9)

    def test_parse_tacho_date_iso_with_time(self, service: TachoService) -> None:
        """ISO date-time string → date portion only."""
        assert service._parse_tacho_date("2026-07-09T12:00:00") == date(2026, 7, 9)

    # -- Unix timestamps -----------------------------------------------

    def test_parse_tacho_date_unix_timestamp(self, service: TachoService) -> None:
        """Large int treated as Unix timestamp (post 2001-01-01 threshold)."""
        # 2026-07-09 00:00:00 UTC in Unix seconds
        ts = 1783555200
        assert service._parse_tacho_date(ts) == date(2026, 7, 9)

    # -- Epoch offsets (pre-2001 threshold) ----------------------------

    def test_parse_tacho_date_epoch_offset(self, service: TachoService) -> None:
        """Smaller int treated as seconds from 2001-01-01."""
        # 2001-01-01 + 190 days = 2001-07-10
        result = service._parse_tacho_date(190 * 86400)
        assert result == date(2001, 7, 10)

    # -- None / zero / invalid -----------------------------------------

    def test_parse_tacho_date_none_returns_none(self, service: TachoService) -> None:
        """``None`` input → ``None``."""
        assert service._parse_tacho_date(None) is None

    def test_parse_tacho_date_zero_returns_none(self, service: TachoService) -> None:
        """Zero integer → ``None`` (special-cased)."""
        assert service._parse_tacho_date(0) is None

    def test_parse_tacho_date_invalid_returns_none(self, service: TachoService) -> None:
        """Garbage string that can't be parsed → ``None``."""
        assert service._parse_tacho_date("not-a-date") is None

    def test_parse_tacho_date_empty_string_returns_none(
        self, service: TachoService
    ) -> None:
        """Empty string → ``None`` (falls through to int('') → ValueError)."""
        assert service._parse_tacho_date("") is None

    def test_parse_tacho_date_whitespace_string(
        self, service: TachoService
    ) -> None:
        """Whitespace-padded ISO string is stripped before parsing."""
        assert service._parse_tacho_date("  2026-07-09  ") == date(2026, 7, 9)

    def test_parse_tacho_date_overflow_returns_none(
        self, service: TachoService
    ) -> None:
        """OverflowError (e.g. huge int) is caught → ``None``."""
        assert service._parse_tacho_date(10**20) is None


# ======================================================================
# _resolve_parser_path (F5 version probe)
# ======================================================================


class TestResolveParserPath:
    """The exists-check is now followed by a ``--version`` capability probe.

    A missing binary, a broken binary (non-zero exit), a probe timeout, or
    a subprocess failure must all yield ``None`` so the existing graceful
    "no parser found" error path fires.
    """

    @pytest.fixture(autouse=True)
    def _reset_parser_cache(self) -> Iterator[None]:
        """Clear the module-level ``_parser_verified_path`` cache.

        ``_resolve_parser_path`` caches a successfully probed binary path at
        module level; without a reset here a successful probe test would leak
        ``'C:/tools/tachograph.exe'`` into the probe-failure tests below (they
        would hit the cache and return the path instead of ``None``).
        """
        import services.tacho_service as tacho_service
        tacho_service._parser_verified_path = None
        yield
        tacho_service._parser_verified_path = None

    def test_missing_binary_returns_none(self, service: TachoService) -> None:
        with patch("services.tacho_service.os.path.exists", return_value=False):
            assert service._resolve_parser_path() is None

    def test_valid_binary_with_version_probe_returns_path(
        self, service: TachoService,
    ) -> None:
        with (
            patch("services.tacho_service.TACHOGRAPH_PATH", "C:/tools/tachograph.exe"),
            patch("services.tacho_service.os.path.exists", return_value=True),
            patch(
                "services.tacho_service.subprocess.run",
                return_value=MagicMock(
                    returncode=0, stdout=b"tachograph version 1.2.3\n", stderr=b"",
                ),
            ) as mock_run,
        ):
            path = service._resolve_parser_path()
        assert path == "C:/tools/tachograph.exe"
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert "--version" in args

    def test_non_zero_exit_probe_returns_none(
        self, service: TachoService,
    ) -> None:
        with (
            patch("services.tacho_service.os.path.exists", return_value=True),
            patch(
                "services.tacho_service.subprocess.run",
                return_value=MagicMock(returncode=1, stdout=b"", stderr=b"broken"),
            ),
        ):
            assert service._resolve_parser_path() is None

    def test_probe_timeout_returns_none(self, service: TachoService) -> None:
        with (
            patch("services.tacho_service.os.path.exists", return_value=True),
            patch(
                "services.tacho_service.subprocess.run",
                side_effect=__import__("subprocess").TimeoutExpired("tachograph", 5),
            ),
        ):
            assert service._resolve_parser_path() is None

    def test_probe_subprocess_error_returns_none(self, service: TachoService) -> None:
        with (
            patch("services.tacho_service.os.path.exists", return_value=True),
            patch(
                "services.tacho_service.subprocess.run",
                side_effect=OSError("cannot execute"),
            ),
        ):
            assert service._resolve_parser_path() is None
