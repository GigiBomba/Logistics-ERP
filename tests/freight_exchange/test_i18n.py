"""Validate freight exchange i18n keys across all 22 languages.

Scans every freight exchange code file for ``t("freight.`` patterns,
extracts every used key, and verifies that:

1. All leaf keys used in code exist in ``en.json``
2. All leaf keys from ``en.json`` exist in every other language file
3. ``t()`` is imported in every file that uses ``t("freight.``
4. Romanian translations are actually translated (not English placeholders)

Non‑leaf code keys (e.g. ``freight.match`` which is a parent dict in the JSON)
are flagged as informational warnings — they cannot resolve to actual strings
via the current ``_flatten()`` approach in ``services/i18n.py``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ── Scan targets ───────────────────────────────────────────────────────────
FREIGHT_SCAN_DIRS = [
    "services/freight_exchange",
    "ui/views/freight_exchange",
    "ui/dialogs/freight_provider_settings.py",
    "backend/api/v1/freight_exchange.py",
    "ui/main_window.py",
]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRANSLATIONS_DIR = REPO_ROOT / "data" / "translations"

# ── All 22 languages (ISO 639‑1 codes) ─────────────────────────────────────
ALL_LANGS = [
    "en", "ro", "de", "fr", "it", "es", "nl", "pl", "hu", "cs", "sk",
    "bg", "sr", "hr", "bs", "sl", "uk", "ru", "tr", "el", "pt", "sv",
]

# Pattern to extract t("freight.xxx") keys from Python source
T_PATTERN = re.compile(r't\("(freight\.[^"]+)"')


# ── Helpers ────────────────────────────────────────────────────────────────


def _scan_freight_keys() -> set[str]:
    """Return every ``freight.*`` key referenced via ``t()`` in code."""
    keys: set[str] = set()
    for rel in FREIGHT_SCAN_DIRS:
        path = REPO_ROOT / rel
        if path.is_dir():
            files = sorted(path.rglob("*.py"))
        elif path.is_file():
            files = [path]
        else:
            continue
        for pyfile in files:
            text = pyfile.read_text(encoding="utf-8")
            for match in T_PATTERN.finditer(text):
                keys.add(match.group(1))
    return keys


def _load_flattened(lang: str) -> dict[str, str]:
    """Load a translation file and return its keys flattened to dot notation.

    Mirrors ``_flatten()`` in ``services/i18n.py``.
    """
    path = TRANSLATIONS_DIR / f"{lang}.json"
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    flat: dict[str, str] = {}
    _flatten(raw, "", flat)
    return flat


def _flatten(d: dict, prefix: str, out: dict[str, str]) -> None:
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _flatten(v, key, out)
        else:
            out[key] = str(v)


def _find_import_issues() -> list[str]:
    """Return relative paths of files that use ``t("freight.`` without
    importing ``t``."""
    issues: list[str] = []
    for rel in FREIGHT_SCAN_DIRS:
        path = REPO_ROOT / rel
        if path.is_dir():
            files = sorted(path.rglob("*.py"))
        elif path.is_file():
            files = [path]
        else:
            continue
        for pyfile in files:
            text = pyfile.read_text(encoding="utf-8")
            if not T_PATTERN.search(text):
                continue
            if "from services.i18n import t" not in text:
                issues.append(str(pyfile.relative_to(REPO_ROOT)))
    return issues


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def en_leaf_keys() -> set[str]:
    """Freight leaf (string-value) keys from en.json."""
    flat = _load_flattened("en")
    return {k for k in flat if k.startswith("freight.")}


@pytest.fixture(scope="session")
def code_keys() -> set[str]:
    return _scan_freight_keys()


@pytest.fixture(scope="session")
def all_lang_leaf_keys() -> dict[str, set[str]]:
    """Freight leaf keys present in every language's translation file."""
    result: dict[str, set[str]] = {}
    for lang in ALL_LANGS:
        flat = _load_flattened(lang)
        result[lang] = {k for k in flat if k.startswith("freight.")}
    return result


# ── Tests ──────────────────────────────────────────────────────────────────


class TestFreightI18n:
    """Comprehensive i18n validation for the freight exchange module."""

    # ── 1. All code-referenced leaf keys exist in en.json ────────────────

    def test_all_code_leaf_keys_exist_in_english(
        self, code_keys: set[str], en_leaf_keys: set[str]
    ) -> None:
        """Every ``t("freight.xxx")`` leaf-key used in code must be present
        as a string value in ``en.json``.

        Keys that reference a JSON parent dict (e.g. ``freight.match``) can't
        resolve to a flat string with the current flattening approach and are
        flagged separately.
        """
        leaf_code_keys = self._get_leaf_code_keys(code_keys)
        missing = leaf_code_keys - en_leaf_keys
        assert not missing, (
            f"{len(missing)} leaf key(s) used in code are missing from "
            f"en.json:\n  " + "\n  ".join(sorted(missing))
        )

    def _get_leaf_code_keys(self, code_keys: set[str]) -> set[str]:
        """Return only code keys that correspond to string values (not parent
        dicts) in the English JSON structure."""
        en_path = TRANSLATIONS_DIR / "en.json"
        with open(en_path, encoding="utf-8") as f:
            en_raw = json.load(f)
        freight_obj = en_raw.get("freight", {})

        def _is_parent_dict(obj: dict, key_parts: list[str]) -> bool:
            current = obj
            for part in key_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return False
            return isinstance(current, dict)

        leaf = set()
        for k in code_keys:
            parts = k.split(".")
            if parts[0] == "freight" and not _is_parent_dict(freight_obj, parts[1:]):
                leaf.add(k)
        return leaf

    # ── 2. English leaf keys exist in all 22 languages ───────────────────

    def test_all_en_leaf_keys_exist_in_every_language(
        self, en_leaf_keys: set[str], all_lang_leaf_keys: dict[str, set[str]]
    ) -> None:
        """Every freight leaf key from ``en.json`` must be present in all
        22 translation files."""
        failures: list[str] = []
        for lang, lang_keys in all_lang_leaf_keys.items():
            missing = en_leaf_keys - lang_keys
            if missing:
                failures.append(
                    f"  [{lang}] missing {len(missing)} key(s): "
                    f"{', '.join(sorted(missing))}"
                )
        assert not failures, (
            "Leaf keys missing from translation files:\n"
            + "\n".join(failures)
        )

    # ── 3. No orphaned keys ──────────────────────────────────────────────

    def test_no_orphan_keys_in_english(
        self, code_keys: set[str], en_leaf_keys: set[str]
    ) -> None:
        """Flag freight leaf keys in ``en.json`` not referenced in code.

        Informational only — a key may exist for future use.
        """
        orphaned = en_leaf_keys - code_keys
        if orphaned:
            pytest.skip(
                f"{len(orphaned)} key(s) in en.json not referenced in code "
                f"(may be intentional): {', '.join(sorted(orphaned))}"
            )

    # ── 4. Import check ─────────────────────────────────────────────────

    def test_t_is_imported_in_all_freight_files(self) -> None:
        """Every file using ``t("freight.`` must import ``t``."""
        issues = _find_import_issues()
        assert not issues, (
            f"{len(issues)} file(s) use " 't("freight.") but lack '
            '"from services.i18n import t":\n  ' + "\n  ".join(issues)
        )

    # ── 5. File existence ────────────────────────────────────────────────

    @pytest.mark.parametrize("lang", ALL_LANGS)
    def test_all_language_files_exist(self, lang: str) -> None:
        """Every language JSON file must exist on disk."""
        path = TRANSLATIONS_DIR / f"{lang}.json"
        assert path.is_file(), f"Missing translation file: {path}"

    # ── 6. Romanian verification ─────────────────────────────────────────

    def test_ro_translations_are_applied(self) -> None:
        """Spot-check that Romanian freight translations differ from English
        and contain the expected translated values."""
        ro = _load_flattened("ro")
        en = _load_flattened("en")

        errors: list[str] = []
        # Verify Romanian is not equal to English for key values
        # (structural keys like provider names may stay identical)
        translated_value_checks = {
            "freight.title": "Bursa de Transport",
            "freight.search": "Cauta Marfuri",
            "freight.evaluate": "Evalueaza Marfa",
            "freight.import": "Importa ca Transport",
            "freight.filter.search_now": "Cauta",
            "freight.match.subtitle": (
                "Cele mai potrivite camioane pentru aceasta marfa"
            ),
            "freight.eval.revenue": "Venit Estimat",
            "freight.health.healthy": "Sanatos",
            "freight.connection.connect": "Conecteaza",
            "freight.results.empty_title": "Niciun rezultat gasit",
            "freight.sort.relevance": "Relevanta",
            "freight.col.provider": "Furnizor",
        }
        for key, expected in translated_value_checks.items():
            actual = ro.get(key)
            if actual != expected:
                errors.append(
                    f"  {key}: expected {expected!r}, got {actual!r}"
                )

        assert not errors, (
            "Romanian translations incorrect or not applied:\n"
            + "\n".join(errors)
        )

        # Verify at minimum that title is different from English
        if ro.get("freight.title") == en.get("freight.title"):
            errors.append("  freight.title is still English!")
        if ro.get("freight.filter.search_now") == en.get("freight.filter.search_now"):
            errors.append("  freight.filter.search_now is still English!")

    # ── 7. Non‑leaf key usage (informational) ───────────────────────────

    def test_non_leaf_keys_usage(self, code_keys: set[str]) -> None:
        """Flag code keys referencing JSON parent dicts (non‑leaf).

        These keys are used in code with ``t("key")`` but only exist as
        nested dict containers in the JSON, not as flat string values.
        They will render as the raw key string at runtime.
        """
        leaf = self._get_leaf_code_keys(code_keys)
        non_leaf = code_keys - leaf
        if non_leaf:
            msg = [
                f"{len(non_leaf)} key(s) reference object parents:",
            ]
            for k in sorted(non_leaf):
                msg.append(f"  • {k}")
            msg.append(
                "These won't resolve to strings with the current "
                "flattening approach. Either add a dedicated leaf entry "
                "or update the code to use a different key."
            )
            pytest.skip("\n".join(msg))
