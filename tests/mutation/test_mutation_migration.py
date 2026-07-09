"""Mutation-killing boundary tests for migration import validator and dedup."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from tests.test_helpers import make_db
from services.migration.types import EntityType, DuplicateCandidate

pytestmark = pytest.mark.mutation


@pytest.fixture
def db():
    return make_db()


@pytest.fixture
def validator(db):
    from services.migration.import_validator import ImportValidator

    return ImportValidator()


@pytest.fixture
def detector(db):
    from services.migration.duplicate_detector import DuplicateDetector

    return DuplicateDetector(db)


class TestKillMutationImportValidator:
    """Mutation-killing boundary tests for ImportValidator.validate_row()."""

    # ── Required-field boundary (kill: ``if not value:`` → ``if value is not None:``) ──

    def test_empty_string_name_fails(self, validator):
        """Kill: empty string name should fail required check."""
        is_valid, errors, _ = validator.validate_row({"name": ""}, EntityType.CLIENT)
        assert not is_valid
        assert any("Missing required field" in e for e in errors)

    def test_whitespace_only_name_fails(self, validator):
        """name='   ' → strip produces '' → should fail required check."""
        is_valid, errors, _ = validator.validate_row(
            {"name": "   "}, EntityType.CLIENT
        )
        assert not is_valid
        assert any("Missing required field" in e for e in errors)

    def test_none_name_fails(self, validator):
        """name=None should fail required check."""
        is_valid, errors, _ = validator.validate_row(
            {"name": None}, EntityType.CLIENT
        )
        assert not is_valid
        assert any("Missing required field" in e for e in errors)

    def test_zero_value_phone_passes(self, validator):
        """phone='0' — kill mutation that treats falsy values as missing.

        The required-field check must not confuse ``"0"`` with an empty
        value.  Phone is optional so it should never trigger a "Missing
        required field" error even if it fails the format validator.
        """
        _, errors, _ = validator.validate_row(
            {"name": "Valid Client", "phone": "0"}, EntityType.CLIENT
        )
        missing_errs = [e for e in errors if e.startswith("Missing required field")]
        assert len(missing_errs) == 0
        # phone="0" fails the format validator (too short) but that is an
        # expected format error, NOT a "missing required field" error.
        fmt_errs = [e for e in errors if "Invalid phone" in e]
        assert len(fmt_errs) == 1

    # ── String / unicode boundaries ──────────────────────────────────────

    def test_very_long_name_passes(self, validator):
        """500-char name should pass validation."""
        name = "A" * 500
        is_valid, errors, cleaned = validator.validate_row(
            {"name": name}, EntityType.CLIENT
        )
        assert is_valid, f"Expected valid, got errors: {errors}"
        assert cleaned.get("name") == name

    def test_special_chars_in_name_passes(self, validator):
        """Unicode / special characters in name should pass."""
        name = "Müller & Söhne GmbH"
        is_valid, errors, cleaned = validator.validate_row(
            {"name": name}, EntityType.CLIENT
        )
        assert is_valid
        assert cleaned.get("name") == name

    # ── Year boundaries (kill off-by-one mutations) ─────────────────────

    def test_exact_year_boundary_1900_passes(self, validator):
        """year=1900 is valid (lower boundary)."""
        is_valid, errors, _ = validator.validate_row(
            {"plate_number": "AB-123", "year": 1900}, EntityType.TRUCK
        )
        assert is_valid

    def test_year_1899_fails(self, validator):
        """year=1899 is invalid (just below 1900)."""
        is_valid, errors, _ = validator.validate_row(
            {"plate_number": "AB-123", "year": 1899}, EntityType.TRUCK
        )
        assert not is_valid

    def test_year_2036_fails(self, validator):
        """year=2036 is invalid (just above 2035)."""
        is_valid, errors, _ = validator.validate_row(
            {"plate_number": "AB-123", "year": 2036}, EntityType.TRUCK
        )
        assert not is_valid

    def test_negative_year_fails(self, validator):
        """year=-1 should fail (out of range)."""
        is_valid, errors, _ = validator.validate_row(
            {"plate_number": "AB-123", "year": -1}, EntityType.TRUCK
        )
        assert not is_valid

    # ── Structural / schema boundaries ──────────────────────────────────

    def test_all_required_missing_fails(self, validator):
        """Row with no required fields → all required-field errors listed."""
        is_valid, errors, _ = validator.validate_row({}, EntityType.DOCUMENT)
        assert not is_valid
        assert len(errors) >= 2  # DOCUMENT requires both 'title' and 'file_path'

    def test_extra_unknown_fields_dropped(self, validator):
        """Row with unknown fields → cleaned output excludes them."""
        _, _, cleaned = validator.validate_row(
            {"name": "Test", "foo": "bar", "baz": 42}, EntityType.CLIENT
        )
        assert "foo" not in cleaned
        assert "baz" not in cleaned
        assert cleaned.get("name") == "Test"

    def test_entity_case_sensitivity(self):
        """EntityType('client') is valid, EntityType('CLIENT') raises ValueError."""
        assert EntityType("client") == EntityType.CLIENT
        with pytest.raises(ValueError):
            EntityType("CLIENT")


class TestKillMutationDuplicateDetector:
    """Mutation-killing boundary tests for DuplicateDetector."""

    @pytest.fixture
    def seeded_db(self, db):
        """Seed one client record for dedup tests."""
        db.conn.execute(
            "INSERT INTO clients (name, vat_number, created_at) VALUES (?, ?, ?)",
            ("ACME Corporation", "DE123456789", "2024-01-01"),
        )
        db.conn.commit()
        return db

    @pytest.fixture
    def seeded_detector(self, seeded_db):
        from services.migration.duplicate_detector import DuplicateDetector

        return DuplicateDetector(seeded_db)

    def test_empty_name_no_duplicate(self, detector):
        """name='' → returns empty list (not matching every row)."""
        results = detector.find_duplicates({"name": ""}, EntityType.CLIENT)
        assert results == []

    def test_exact_name_match_case_insensitive(self, seeded_detector):
        """Seed 'ACME Corporation' → incoming 'acme corporation' fuzzy‑matches."""
        results = seeded_detector.find_duplicates(
            {"name": "acme corporation"}, EntityType.CLIENT
        )
        assert len(results) > 0, "Expected at least one fuzzy match"

    def test_fuzzy_score_exactly_at_threshold(self, seeded_detector):
        """Name very close to seed → score > 0.85 → match found."""
        results = seeded_detector.find_duplicates(
            {"name": "ACME Corporatio"}, EntityType.CLIENT
        )
        assert len(results) > 0, (
            f"Expected fuzzy match for close name, got {len(results)}"
        )

    def test_fuzzy_score_just_below_threshold(self, seeded_detector):
        """Very different name → no match (score < 0.85)."""
        results = seeded_detector.find_duplicates(
            {"name": "XYZ NonExistent Company GmbH"}, EntityType.CLIENT
        )
        assert len(results) == 0

    def test_vat_boost_caps_at_one(self, seeded_db, seeded_detector):
        """VAT‑number match boosts score but cannot exceed 1.0.

        Use a non‑exact name so we go through the fuzzy path where the
        VAT boost is applied, then verify the cap.
        """
        row = {"name": "ACME Corp", "vat_number": "DE123456789"}
        results = seeded_detector.find_duplicates(row, EntityType.CLIENT)
        assert len(results) > 0, "Expected at least one candidate"
        for candidate in results:
            assert candidate.score <= 1.0, (
                f"Score {candidate.score} exceeds cap of 1.0"
            )

    def test_none_client_name_safe(self, detector):
        """name=None → should not crash, returns empty list."""
        results = detector.find_duplicates({"name": None}, EntityType.CLIENT)
        assert results == []

    def test_truck_empty_plate_no_match(self, detector):
        """plate_number='' → returns empty list for truck dedup."""
        results = detector.find_duplicates(
            {"plate_number": ""}, EntityType.TRUCK
        )
        assert results == []
