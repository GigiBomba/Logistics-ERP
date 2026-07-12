"""Integration tests for translation file integrity.

Validates:
  - Every .json file is valid JSON
  - All non-en files have no missing keys compared to en.json
  - All non-en files have no extra keys not in en.json
  - Placeholder consistency across all files
  - No empty translation values (keys present but with empty string values)
"""
from __future__ import annotations

import json
import os
import re

import pytest

TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "translations"
)


def _flatten(d: dict, prefix: str = "") -> dict[str, object]:
    items: dict[str, object] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten(v, key))
        else:
            items[key] = v
    return items


def _extract_placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{[^}]*\}", str(text)))


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def en_flat():
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    return _flatten(_load_json(en_path))


@pytest.fixture(scope="module")
def translation_files():
    return sorted(
        f for f in os.listdir(TRANSLATIONS_DIR) if f.endswith(".json")
    )


@pytest.fixture(scope="module")
def non_en_files(translation_files):
    return [f for f in translation_files if f != "en.json"]


# ── JSON validity ────────────────────────────────────────────────────

class TestJsonValidity:
    def test_en_json_is_valid(self):
        _load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))

    def test_all_files_are_valid_json(self, translation_files):
        for fname in translation_files:
            path = os.path.join(TRANSLATIONS_DIR, fname)
            try:
                _load_json(path)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                pytest.fail(f"{fname}: {e}")

    def test_all_files_are_objects(self, translation_files):
        for fname in translation_files:
            data = _load_json(os.path.join(TRANSLATIONS_DIR, fname))
            assert isinstance(data, dict), f"{fname}: root must be a JSON object, got {type(data).__name__}"


# ── Key coverage ─────────────────────────────────────────────────────

class TestKeyCoverage:
    def test_no_missing_keys(self, en_flat, non_en_files):
        """Every non-en file must have all keys present in en.json."""
        for fname in non_en_files:
            path = os.path.join(TRANSLATIONS_DIR, fname)
            lang_flat = _flatten(_load_json(path))
            missing = [k for k in en_flat if k not in lang_flat]
            assert not missing, (
                f"{fname}: missing {len(missing)} keys from en.json:\n"
                + "\n".join(f"  - {k}" for k in missing[:20])
            )

    def test_no_extra_keys(self, en_flat, non_en_files):
        """No file should have keys not present in en.json."""
        for fname in non_en_files:
            path = os.path.join(TRANSLATIONS_DIR, fname)
            lang_flat = _flatten(_load_json(path))
            extra = [k for k in lang_flat if k not in en_flat]
            assert not extra, (
                f"{fname}: {len(extra)} extra keys not in en.json:\n"
                + "\n".join(f"  - {k}" for k in extra)
            )


# ── Placeholder consistency ──────────────────────────────────────────

class TestPlaceholders:
    def test_all_placeholders_match(self, en_flat, non_en_files):
        """Every key in every file must have matching placeholders with en.json."""
        en_with_placeholders = {
            k: v for k, v in en_flat.items() if _extract_placeholders(str(v))
        }
        for fname in non_en_files:
            path = os.path.join(TRANSLATIONS_DIR, fname)
            lang_flat = _flatten(_load_json(path))
            mismatches = []
            for k, en_val in en_with_placeholders.items():
                en_ph = _extract_placeholders(str(en_val))
                if k in lang_flat:
                    lang_ph = _extract_placeholders(str(lang_flat[k]))
                    if en_ph != lang_ph:
                        missing = en_ph - lang_ph
                        extra = lang_ph - en_ph
                        parts = []
                        if missing:
                            parts.append(f"missing: {missing}")
                        if extra:
                            parts.append(f"extra: {extra}")
                        mismatches.append(f"  {k}: {', '.join(parts)}")
            assert not mismatches, (
                f"{fname}: {len(mismatches)} placeholder mismatches:\n"
                + "\n".join(mismatches[:20])
            )


# ── Required sections ────────────────────────────────────────────────

REQUIRED_SECTIONS = {"language_name", "app", "nav", "main", "fleet", "history", "settings"}


class TestRequiredSections:
    def test_en_has_all_required_sections(self):
        data = _load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))
        top_keys = set(data.keys())
        missing = REQUIRED_SECTIONS - top_keys
        assert not missing, f"en.json missing required sections: {missing}"

    def test_all_files_have_language_name(self, non_en_files):
        for fname in non_en_files:
            data = _load_json(os.path.join(TRANSLATIONS_DIR, fname))
            assert isinstance(data.get("language_name"), str), (
                f"{fname}: missing or invalid 'language_name'"
            )
            assert len(data["language_name"].strip()) > 0, (
                f"{fname}: 'language_name' is empty"
            )


# ── No empty string values ───────────────────────────────────────────

class TestNoEmptyValues:
    def test_en_has_no_empty_string_values(self, en_flat):
        empty = [k for k, v in en_flat.items() if v == ""]
        assert not empty, (
            f"en.json has {len(empty)} empty string values:\n"
            + "\n".join(f"  - {k}" for k in empty[:20])
        )


# ── Translation count consistency ────────────────────────────────────

class TestTranslationCount:
    def test_all_files_have_same_number_of_keys(self, en_flat, non_en_files):
        """All files must have exactly the same number of flattened keys as en.json."""
        en_count = len(en_flat)
        for fname in non_en_files:
            lang_flat = _flatten(_load_json(os.path.join(TRANSLATIONS_DIR, fname)))
            assert len(lang_flat) == en_count, (
                f"{fname}: has {len(lang_flat)} keys, expected {en_count}"
            )
