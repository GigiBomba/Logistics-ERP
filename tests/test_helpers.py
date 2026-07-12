"""Comprehensive unit tests for utils/helpers.py.

Tests cover remove_accents — including accented characters,
empty string, None, no-accent strings, and mixed input.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from utils.helpers import remove_accents


# ── In-memory SQLite database for E2E / integration tests ─────


from database.db_manager import DatabaseManager


class InMemoryDB(DatabaseManager):
    """In-memory SQLite database with the full application schema.

    Subclasses ``DatabaseManager`` so it provides ``conn``, ``row_to_dict``,
    ``rows_to_dicts``, and the engine attributes expected by
    ``BaseRepository`` subclasses.
    """

    def __init__(self) -> None:
        super().__init__(":memory:")


def make_db() -> InMemoryDB:
    """Create a fresh InMemoryDB instance for testing.

    Returns an ``InMemoryDB`` backed by an in-memory SQLite database with
    the full schema, indexes, and migrations applied.
    """
    return InMemoryDB()


# ──────────────────────────────────────────────────────────────
# remove_accents
# ──────────────────────────────────────────────────────────────


class TestRemoveAccents:
    """Strip diacritics from strings via NFKD normalization."""

    def test_accented_characters(self):
        assert remove_accents("café") == "cafe"

    def test_spanish_accent(self):
        assert remove_accents("año") == "ano"

    def test_german_umlaut_decomposes(self):
        # ü decomposes to u + combining diaeresis → 'u'
        assert remove_accents("München") == "Munchen"

    def test_french_cedilla(self):
        assert remove_accents("garçon") == "garcon"

    def test_french_accent_aigu(self):
        assert remove_accents("résumé") == "resume"

    def test_polish_characters(self):
        # ą → a, ć → c, ę → e, ń → n, ó → o, ś → s, ź → z, ż → z
        # Note: Ł (L with stroke) does NOT decompose via NFKD, so it passes through
        assert remove_accents("Łódź") == "Łodz"

    def test_czech_hacek(self):
        assert remove_accents("čeština") == "cestina"

    def test_nordic_o_slash_passes_through(self):
        # ø (o with stroke) does NOT decompose via NFKD
        assert remove_accents("føroya") == "føroya"

    def test_nordic_a_ring_decomposes(self):
        # å (a with ring) decomposes via NFKD
        assert remove_accents("ångström") == "angstrom"

    def test_empty_string(self):
        assert remove_accents("") == ""

    def test_none_returns_empty_string(self):
        # not None → True → early return ""
        assert remove_accents(None) == ""

    def test_no_accents(self):
        assert remove_accents("hello world") == "hello world"

    def test_mixed_string(self):
        assert remove_accents("Málaga 2024") == "Malaga 2024"

    def test_numbers_and_symbols(self):
        assert remove_accents("123 !@#") == "123 !@#"

    def test_unicode_accents_combined(self):
        # Single character representations: é = \u00e9
        assert remove_accents("\u00e9") == "e"

    def test_unicode_macron(self):
        # ō (o with macron) decomposes via NFKD
        assert remove_accents("Tōkyō") == "Tokyo"

    def test_vietnamese_characters(self):
        # Đ (D with stroke) doesn't decompose via NFKD, but à and ẵ do
        assert remove_accents("Đà Nẵng") == "Đa Nang"

    def test_icelandic_thorn_passes_through(self):
        # 'þ' (thorn) NFKD keeps it, so it passes through
        assert remove_accents("þorn") == "þorn"

    def test_dutch_ij_digraph(self):
        # 'ĳ' decomposes to 'ij' via NFKD
        assert remove_accents("ĳs") == "ijs"

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("", ""),
            ("abc", "abc"),
            ("àáâãä", "aaaaa"),
            ("èéêë", "eeee"),
            ("ìíîï", "iiii"),
            ("òóôõö", "ooooo"),
            ("ùúûü", "uuuu"),
            ("ýÿ", "yy"),
            ("ñ", "n"),
            ("ç", "c"),
            ("ÀÁÂÃÄ", "AAAAA"),
            ("ÈÉÊË", "EEEE"),
            ("Ñ", "N"),
            ("Ç", "C"),
        ],
    )
    def test_parametrized_accents(self, input_str, expected):
        assert remove_accents(input_str) == expected
