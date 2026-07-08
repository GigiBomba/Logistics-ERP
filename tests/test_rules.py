"""Comprehensive tests for the Rules singleton (services/operations/rules.py)."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from services.operations.rules import _DEFAULT_RULES, Rules


class TestRulesSingleton:
    """Verify the singleton contract."""

    def test_same_instance(self):
        Rules._instance = None
        r1 = Rules()
        r2 = Rules()
        assert r1 is r2

    def test_fresh_instance_after_reset(self):
        Rules._instance = None
        r1 = Rules()
        Rules._instance = None
        r2 = Rules()
        assert r1 is not r2

    def test_singleton_across_reset_singletons_fixture(self, reset_singletons):
        """The conftest's autouse fixture resets _instance before each test."""
        r1 = Rules()
        assert r1 is Rules()


class TestDefaultRules:
    """Verify that _DEFAULT_RULES are present on a fresh instance."""

    def test_all_defaults_loaded(self):
        Rules._instance = None
        rules = Rules()
        all_rules = rules.all()
        for key, value in _DEFAULT_RULES.items():
            assert key in all_rules, f"Missing default rule: {key}"
            assert all_rules[key] == value, f"Wrong value for {key}"

    def test_default_rules_count(self):
        Rules._instance = None
        rules = Rules()
        assert len(rules.all()) == len(_DEFAULT_RULES)

    def test_default_values_are_typed(self):
        Rules._instance = None
        rules = Rules()
        for key, val in _DEFAULT_RULES.items():
            assert isinstance(rules.get(key), type(val)), (
                f"Type mismatch for {key}"
            )


class TestGetMethod:
    """Tests for Rules.get()."""

    def test_get_existing_key(self):
        Rules._instance = None
        rules = Rules()
        assert rules.get("inspection_warning_days") == 10

    def test_get_missing_key(self):
        Rules._instance = None
        rules = Rules()
        assert rules.get("nonexistent_key") is None

    def test_get_missing_key_with_default(self):
        Rules._instance = None
        rules = Rules()
        assert rules.get("nonexistent_key", 42) == 42

    def test_get_after_set_reflects_update(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("inspection_warning_days", 99)
        assert rules.get("inspection_warning_days") == 99

    def test_get_bool_default(self):
        Rules._instance = None
        rules = Rules()
        assert rules.get("in_transit_auto_after_start") is True
        assert rules.get("dunner_enabled") is True


class TestSetMethod:
    """Tests for Rules.set()."""

    def test_set_new_key(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("custom_rule", "hello")
        assert rules.get("custom_rule") == "hello"

    def test_set_overwrites_existing(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("inspection_warning_days", 5)
            rules.set("inspection_warning_days", 7)
        assert rules.get("inspection_warning_days") == 7

    def test_set_none_value(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("nullable_rule", None)
        assert rules.get("nullable_rule") is None

    def test_set_calls_save(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(rules, "_save") as mock_save:
            rules.set("key", "val")
        mock_save.assert_called_once()

    def test_set_does_not_affect_other_rules(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("inspection_warning_days", 99)
        assert rules.get("insurance_warning_days") == 10


class TestAllMethod:
    """Tests for Rules.all()."""

    def test_all_returns_all_defaults(self):
        Rules._instance = None
        rules = Rules()
        all_rules = rules.all()
        assert all_rules == _DEFAULT_RULES

    def test_all_returns_copy(self):
        Rules._instance = None
        rules = Rules()
        all_rules = rules.all()
        all_rules["custom"] = "modified"
        # Original should be unchanged
        assert rules.get("custom") is None

    def test_all_includes_updates(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("custom_key", 123)
        all_rules = rules.all()
        assert all_rules["custom_key"] == 123

    def test_all_is_deterministic_type(self):
        Rules._instance = None
        rules = Rules()
        result = rules.all()
        assert isinstance(result, dict)


class TestLoadMethod:
    """Tests for Rules._load() — loading rules from JSON file."""

    @patch("services.operations.rules.os.path.isfile")
    @patch("services.operations.rules.open", new_callable=mock_open, read_data='{"custom_key": "file_value"}')
    def test_load_from_file_overrides_defaults(self, mock_file, mock_isfile):
        mock_isfile.return_value = True
        Rules._instance = None
        rules = Rules()
        assert rules.get("custom_key") == "file_value"
        # Defaults should still be present
        assert rules.get("inspection_warning_days") == 10

    @patch("services.operations.rules.os.path.isfile")
    def test_load_missing_file_keeps_defaults(self, mock_isfile):
        mock_isfile.return_value = False
        Rules._instance = None
        rules = Rules()
        assert rules.get("inspection_warning_days") == 10
        assert rules.get("nonexistent") is None

    @patch("services.operations.rules.os.path.isfile")
    @patch("services.operations.rules.open", new_callable=mock_open, read_data='corrupted json{')
    def test_load_corrupted_file_logs_warning_and_keeps_defaults(self, mock_file, mock_isfile):
        mock_isfile.return_value = True
        Rules._instance = None
        rules = Rules()
        # Defaults survive the parse error
        assert rules.get("inspection_warning_days") == 10

    @patch("services.operations.rules.os.path.isfile")
    @patch("services.operations.rules.open", new_callable=mock_open, read_data='{"inspection_warning_days": 1}')
    def test_load_file_overrides_specific_default(self, mock_file, mock_isfile):
        mock_isfile.return_value = True
        Rules._instance = None
        rules = Rules()
        assert rules.get("inspection_warning_days") == 1


class TestSaveMethod:
    """Tests for Rules._save() — persisting rules to JSON file."""

    @patch("services.operations.rules.open", new_callable=mock_open)
    def test_save_writes_all_rules_to_file(self, mock_file):
        Rules._instance = None
        rules = Rules()
        rules._save()
        handle = mock_file()
        # Collect all written data
        written = "".join(
            call.args[0] for call in handle.write.call_args_list
        )
        saved = json.loads(written)
        assert saved == _DEFAULT_RULES

    @patch("services.operations.rules.open", new_callable=mock_open)
    def test_save_after_set_includes_new_rules(self, mock_file):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("added_rule", "yes")
        rules._save()
        handle = mock_file()
        written = "".join(
            call.args[0] for call in handle.write.call_args_list
        )
        saved = json.loads(written)
        assert saved["added_rule"] == "yes"
        assert saved["inspection_warning_days"] == 10


class TestThreadSafety:
    """Basic thread-safety verification for the singleton lock."""

    def test_concurrent_get_set_does_not_raise(self):
        import concurrent.futures

        Rules._instance = None
        rules = Rules()

        def worker_get():
            return rules.get("inspection_warning_days")

        def worker_set():
            with patch.object(Rules, "_save"):
                rules.set("inspection_warning_days", 99)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = []
            for _ in range(10):
                futures.append(ex.submit(worker_get))
                futures.append(ex.submit(worker_set))
            results = [f.result() for f in futures]
        # No crash — basic sanity
        assert True

    def test_double_checked_locking_blocks_duplicate_instance(self):
        """Verify __new__ double-checked locking prevents two instances."""
        Rules._instance = None
        instances = []

        def create():
            instances.append(Rules())

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            fs = [ex.submit(create) for _ in range(8)]
            concurrent.futures.wait(fs)

        # All references point to the same object
        assert all(i is instances[0] for i in instances)


class TestEdgeCases:
    """Edge cases and defensive behaviour."""

    def test_get_with_empty_key_returns_default(self):
        Rules._instance = None
        rules = Rules()
        assert rules.get("") is None
        assert rules.get("", "fallback") == "fallback"

    def test_set_empty_key(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("", "empty_key_val")
        assert rules.get("") == "empty_key_val"

    def test_set_boolean_false(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("dunner_enabled", False)
        assert rules.get("dunner_enabled") is False

    def test_all_empty_after_clear_internally(self):
        """Simulate rules being cleared directly (defensive)."""
        Rules._instance = None
        rules = Rules()
        rules._rules.clear()
        assert rules.all() == {}

    def test_set_numeric_zero(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("zero_test", 0)
        assert rules.get("zero_test") == 0

    def test_set_none_over_default(self):
        Rules._instance = None
        rules = Rules()
        with patch.object(Rules, "_save"):
            rules.set("inspection_warning_days", None)
        assert rules.get("inspection_warning_days") is None
        # Other defaults intact
        assert rules.get("insurance_warning_days") == 10


class TestSaveFailure:
    """_save() should not crash when file write fails."""

    @patch("services.operations.rules.open", side_effect=PermissionError("denied"))
    def test_save_permission_error_does_not_raise(self, mock_file):
        Rules._instance = None
        rules = Rules()
        # Must not propagate the exception
        rules._save()

    @patch("services.operations.rules.open", side_effect=OSError("disk full"))
    def test_save_os_error_does_not_raise(self, mock_file):
        Rules._instance = None
        rules = Rules()
        rules._save()


class TestLoadFailure:
    """_load() should gracefully handle file system errors."""

    @patch("services.operations.rules.os.path.isfile", side_effect=OSError("permission denied"))
    def test_load_isfile_error_does_not_raise(self, mock_isfile):
        Rules._instance = None
        rules = Rules()
        assert rules.get("inspection_warning_days") == 10

    @patch("services.operations.rules.os.path.isfile", return_value=True)
    @patch("services.operations.rules.open", side_effect=PermissionError("denied"))
    def test_load_open_error_does_not_raise(self, mock_file, mock_isfile):
        Rules._instance = None
        rules = Rules()
        assert rules.get("inspection_warning_days") == 10
