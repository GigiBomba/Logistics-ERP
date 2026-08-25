"""Tests for cmr_models.py — CMR create, mandatory fields, successive carrier chain."""
from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError
from models.cmr_models import CmrGenerateRequest, CmrResult


class TestCmrGenerateRequest:
    @pytest.mark.parametrize(
        "trip_id, language, copies, include_stamps, sender_name, carrier_name",
        [
            (1, "ro", 3, True, "Sender SRL", "Carrier SRL"),
            (2, "en", 3, False, "", ""),
            (3, "de", 5, True, "Firma A", "Spedition B"),
            (4, "fr", 2, False, "Expéditeur", "Transporteur"),
            (5, "ro", 1, True, "", "Carrier Only"),
        ],
    )
    def test_cmr_generate_valid(self, trip_id, language, copies, include_stamps, sender_name, carrier_name):
        req = CmrGenerateRequest(
            trip_id=trip_id,
            language=language,
            copies=copies,
            include_stamps=include_stamps,
            sender_name=sender_name,
            carrier_name=carrier_name,
        )
        assert req.trip_id == trip_id
        assert req.language == language
        assert req.copies == copies
        assert req.include_stamps == include_stamps

    def test_cmr_generate_defaults(self):
        req = CmrGenerateRequest(trip_id=42)
        assert req.language == "ro"
        assert req.copies == 3
        assert req.include_stamps is True
        assert req.sender_name == ""
        assert req.sender_address == ""
        assert req.carrier_name == ""
        assert req.carrier_license == ""
        assert req.remarks == ""

    @pytest.mark.parametrize(
        "field, value",
        [
            ("language", "ro"),
            ("language", "en"),
            ("language", "de"),
            ("language", "fr"),
        ],
    )
    def test_cmr_languages_accepted(self, field, value):
        req = CmrGenerateRequest(trip_id=1, **{field: value})
        assert getattr(req, field) == value

    def test_cmr_with_remarks(self):
        req = CmrGenerateRequest(
            trip_id=10,
            sender_name="Sender Srl",
            sender_address="Str. Mare 10",
            carrier_name="Carrier Srl",
            carrier_license="RO-12345",
            remarks="Fragile goods",
        )
        assert req.sender_address == "Str. Mare 10"
        assert req.carrier_license == "RO-12345"
        assert req.remarks == "Fragile goods"

    def test_minimal_cmr_request(self):
        req = CmrGenerateRequest(trip_id=100)
        assert req.trip_id == 100
        assert req.include_stamps is True


class TestCmrResult:
    def test_cmr_result_minimal(self):
        now = datetime.now()
        r = CmrResult(
            cmr_number="CMR-001",
            trip_id=1,
            file_path="/cmrs/cmr_001.pdf",
            copies=3,
            generated_at=now,
        )
        assert r.cmr_number == "CMR-001"
        assert r.trip_id == 1
        assert r.file_path == "/cmrs/cmr_001.pdf"
        assert r.cmr_data == {}

    def test_cmr_result_with_data(self):
        now = datetime.now()
        data = {"sender": "Sender", "recipient": "Recipient", "plate": "AB123CD"}
        r = CmrResult(
            cmr_number="CMR-002",
            trip_id=2,
            file_path="/cmrs/cmr_002.pdf",
            copies=5,
            generated_at=now,
            cmr_data=data,
        )
        assert r.cmr_data["sender"] == "Sender"
        assert r.cmr_data["plate"] == "AB123CD"
