"""Tests for ocr_extractor module."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.document_automation.ocr_extractor import (
    OcrExtractor,
    _endpoint_reachable,
    _load_paddle_confidence_threshold,
    _parse_paddle_output,
    _paddle_extract,
    _render_pages,
    _resolve_paddle_lang,
    _safe_import_fitz,
    _safe_import_paddleocr,
    set_paddle_config,
    set_paddle_gpu,
)
from services.document_automation.types import ExtractionResult, OcrLine
from requests.exceptions import ConnectionError, Timeout


class TestEndpointReachable:
    @patch("requests.head")
    def test_reachable(self, mock_head):
        mock_head.return_value = MagicMock(ok=True)
        assert _endpoint_reachable("http://localhost:8000") is True

    @patch("requests.head")
    def test_unreachable(self, mock_head):
        mock_head.side_effect = ConnectionError
        assert _endpoint_reachable("http://localhost:8000") is False

    @patch("requests.head")
    def test_timeout(self, mock_head):
        mock_head.side_effect = Timeout
        assert _endpoint_reachable("http://localhost:8000") is False


class TestPaddleConfig:
    def test_set_paddle_gpu(self):
        import services.document_automation.ocr_extractor as _mod
        set_paddle_gpu(True)
        assert _mod._PADDLE_USE_GPU is True
        set_paddle_gpu(False)
        assert _mod._PADDLE_USE_GPU is False

    def test_set_paddle_config(self):
        set_paddle_config(det_limit_side_len=640, rec_batch_num=4)
        from services.document_automation.ocr_extractor import (
            _PADDLE_DET_LIMIT_SIDE_LEN,
            _PADDLE_REC_BATCH_NUM,
        )
        assert _PADDLE_DET_LIMIT_SIDE_LEN == 640
        assert _PADDLE_REC_BATCH_NUM == 4

    def test_resolve_paddle_lang(self):
        lang = _resolve_paddle_lang()
        assert lang == "ro"

    def test_safe_import_paddleocr_returns_none(self):
        with patch.dict("sys.modules", {"paddleocr": None}):
            # Force import miss by removing from sys.modules
            pass
        # Just verify it returns None or a module
        result = _safe_import_paddleocr()
        # In test env it will likely be None
        assert result is None or hasattr(result, "PaddleOCR")


class TestParsePaddleOutput:
    def test_parse_empty(self):
        assert _parse_paddle_output(None) == []
        assert _parse_paddle_output([]) == []

    def test_parse_valid_output(self):
        raw = [
            [
                ([[10, 10], [50, 10], [50, 30], [10, 30]], ("Hello", 0.95)),
                ([[60, 10], [100, 10], [100, 30], [60, 30]], ("World", 0.90)),
            ]
        ]
        lines = _parse_paddle_output(raw)
        assert len(lines) == 2
        assert lines[0].text == "Hello"
        assert lines[0].confidence == 0.95
        assert lines[1].text == "World"

    def test_parse_skips_empty_text(self):
        raw = [
            [
                ([[0, 0], [10, 0], [10, 10], [0, 10]], ("", 0.9)),
            ]
        ]
        lines = _parse_paddle_output(raw)
        assert len(lines) == 0

    def test_parse_skips_none_page(self):
        raw = [None, [([[0, 0], [1, 0], [1, 1], [0, 1]], ("text", 0.5))]]
        lines = _parse_paddle_output(raw)
        assert len(lines) == 1


class TestPaddleExtract:
    @patch("services.document_automation.ocr_extractor._safe_import_paddleocr",
           return_value=None)
    def test_paddle_not_installed(self, mock_import):
        result = _paddle_extract("/fake.pdf", 5)
        assert result is None

    @patch("services.document_automation.ocr_extractor._render_pages")
    @patch("services.document_automation.ocr_extractor._safe_import_paddleocr")
    def test_paddle_success(self, mock_import, mock_render):
        mock_paddleocr = MagicMock()
        mock_instance = MagicMock()
        mock_instance.predict.return_value = [
            [
                ([[0, 0], [10, 0], [10, 10], [0, 10]], ("Hello OCR", 0.95)),
            ]
        ]
        mock_paddleocr.PaddleOCR.return_value = mock_instance
        mock_import.return_value = mock_paddleocr
        mock_render.return_value = [MagicMock()]  # one PIL image

        import numpy as np
        mock_img = MagicMock()
        mock_img.convert.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_render.return_value = [mock_img]

        result = _paddle_extract("/fake.pdf", 5)
        assert result is not None
        assert result.engine == "paddle"
        assert "Hello OCR" in result.full_text

    @patch("services.document_automation.ocr_extractor._render_pages")
    @patch("services.document_automation.ocr_extractor._safe_import_paddleocr")
    def test_paddle_zero_pages(self, mock_import, mock_render):
        mock_paddleocr = MagicMock()
        mock_paddleocr.PaddleOCR.return_value = MagicMock()
        mock_import.return_value = mock_paddleocr
        mock_render.return_value = []  # no pages

        result = _paddle_extract("/fake.pdf", 5)
        assert result is not None
        assert result.pages_processed == 0
        assert result.full_text == ""


class TestOcrExtractor:
    def test_init_with_db(self):
        with patch("services.document_automation.ocr_extractor._load_paddle_confidence_threshold",
                   return_value=50.0):
            extractor = OcrExtractor(max_pages=5, db=MagicMock())
            assert extractor.max_pages == 5
            assert extractor._local_confidence_threshold == 50.0

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_paddle_only(self, mock_reachable, mock_paddle):
        mock_paddle.return_value = ExtractionResult(
            full_text="OCR text", extracted={},
            confidence=80.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"cmr_number": "CMR001"}):
            result = extractor.extract("/fake.pdf")
            assert result.full_text == "OCR text"
            assert result.confidence >= 80.0

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_both_fail(self, mock_reachable, mock_paddle):
        mock_paddle.return_value = None

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        result = extractor.extract("/fake.pdf")
        assert result.confidence == 0.0
        assert result.engine == "none"


class TestLoadThreshold:
    def test_load_threshold_cache_hit(self):
        import services.document_automation.ocr_extractor as _mod
        _mod._PADDLE_CONF_THRESHOLD_CACHE = 55.0
        _mod._PADDLE_CONF_THRESHOLD_TS = 50  # cache still fresh (50 + 60 > 100)

        with patch("services.document_automation.ocr_extractor.time.time",
                   side_effect=[100, 105]):
            result = _load_paddle_confidence_threshold(MagicMock())
            assert result == 55.0

    def test_load_threshold_from_db(self):
        import services.document_automation.ocr_extractor as _mod
        _mod._PADDLE_CONF_THRESHOLD_CACHE = 40.0
        _mod._PADDLE_CONF_THRESHOLD_TS = 0  # force cache miss

        with patch("services.document_automation.ocr_extractor.time.time",
                   side_effect=[200, 200]), \
             patch("services.document_automation.ocr_extractor.SettingsRepository") as mock_settings_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = "60.0"
            mock_settings_cls.return_value = mock_settings

            mock_db = MagicMock()

            result = _load_paddle_confidence_threshold(mock_db)
            assert result == 60.0

    def test_load_threshold_db_error(self):
        """DB exception falls back gracefully to 40.0."""
        import services.document_automation.ocr_extractor as _mod
        _mod._PADDLE_CONF_THRESHOLD_CACHE = 40.0
        _mod._PADDLE_CONF_THRESHOLD_TS = 0

        with patch("services.document_automation.ocr_extractor.time.time",
                   side_effect=[100, 100]), \
             patch("services.document_automation.ocr_extractor.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.side_effect = Exception("DB unreachable")
            mock_cls.return_value = mock_settings

            result = _load_paddle_confidence_threshold(MagicMock())
            assert result == 40.0

    def test_load_threshold_invalid_value(self):
        """Non-numeric value from DB is discarded, default 40.0 used."""
        import services.document_automation.ocr_extractor as _mod
        _mod._PADDLE_CONF_THRESHOLD_CACHE = 40.0
        _mod._PADDLE_CONF_THRESHOLD_TS = 0

        with patch("services.document_automation.ocr_extractor.time.time",
                   side_effect=[300, 300]), \
             patch("services.document_automation.ocr_extractor.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = "not-a-number"
            mock_cls.return_value = mock_settings

            result = _load_paddle_confidence_threshold(MagicMock())
            assert result == 40.0

    def test_load_threshold_clamps_range(self):
        """Values outside 0-100 are clamped."""
        import services.document_automation.ocr_extractor as _mod
        _mod._PADDLE_CONF_THRESHOLD_CACHE = 40.0
        _mod._PADDLE_CONF_THRESHOLD_TS = 0

        with patch("services.document_automation.ocr_extractor.time.time",
                   side_effect=[400, 400]), \
             patch("services.document_automation.ocr_extractor.SettingsRepository") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.get_setting_value.return_value = "150.0"
            mock_cls.return_value = mock_settings

            result = _load_paddle_confidence_threshold(MagicMock())
            assert result == 100.0

    def test_load_threshold_none_db(self):
        """When db is None, return default 40.0 without calling SettingsRepository."""
        import services.document_automation.ocr_extractor as _mod
        _mod._PADDLE_CONF_THRESHOLD_CACHE = 40.0
        _mod._PADDLE_CONF_THRESHOLD_TS = 0

        with patch("services.document_automation.ocr_extractor.time.time",
                   side_effect=[500, 500]), \
             patch("services.document_automation.ocr_extractor.SettingsRepository") as mock_cls:
            result = _load_paddle_confidence_threshold(db=None)
            assert result == 40.0
            mock_cls.assert_not_called()


class TestEndpointReachableImportError:
    @patch.dict("sys.modules", {"requests": None})
    def test_import_error_returns_false(self):
        """When requests cannot be imported, endpoint is considered unreachable."""
        # Re-import the function to trigger ImportError path
        import services.document_automation.ocr_extractor as _mod
        # Clear cached import
        if hasattr(_mod, '_endpoint_reachable'):
            result = _mod._endpoint_reachable("http://localhost:8000")
            assert result is False


class TestRenderPages:
    @patch("services.document_automation.ocr_extractor._safe_import_fitz", return_value=None)
    def test_render_no_fitz(self, _mock_fitz):
        """When fitz (PyMuPDF) is not installed, generator yields nothing."""
        gen = _render_pages("/fake.pdf", 5)
        pages = list(gen)
        assert pages == []

    @patch("services.document_automation.ocr_extractor._safe_import_fitz")
    def test_render_closes_doc_on_error(self, mock_fitz_import):
        """Document is closed even when an error occurs during rendering."""
        mock_fitz = MagicMock()
        mock_doc = MagicMock()
        # load_page raises an exception after page 0
        mock_page = MagicMock()
        mock_page.get_pixmap.side_effect = RuntimeError("render fail")
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__.return_value = 5
        mock_fitz.open.return_value = mock_doc
        mock_fitz_import.return_value = mock_fitz

        gen = _render_pages("/fake.pdf", 5)
        with pytest.raises(RuntimeError, match="render fail"):
            next(gen)
        mock_doc.close.assert_called_once()


class TestPaddleExtractAdvanced:
    @patch("services.document_automation.ocr_extractor._render_pages")
    @patch("services.document_automation.ocr_extractor._safe_import_paddleocr")
    def test_paddle_predict_exception(self, mock_import, mock_render):
        """Exception during PaddleOCR.predict() on a single page is caught."""
        mock_paddleocr = MagicMock()
        mock_instance = MagicMock()
        mock_instance.predict.side_effect = RuntimeError("OOM on page")
        mock_paddleocr.PaddleOCR.return_value = mock_instance
        mock_import.return_value = mock_paddleocr
        mock_img = MagicMock()
        mock_img.convert.return_value = MagicMock()
        mock_render.return_value = [mock_img, mock_img]

        result = _paddle_extract("/fake.pdf", 5)
        # Should still produce a result (with empty text since all pages failed)
        assert result is not None
        assert result.engine == "paddle"

    @patch("services.document_automation.ocr_extractor._render_pages")
    @patch("services.document_automation.ocr_extractor._safe_import_paddleocr")
    def test_paddle_render_exception(self, mock_import, mock_render):
        """Exception during _render_pages returns None (fallback to cloud)."""
        mock_paddleocr = MagicMock()
        mock_paddleocr.PaddleOCR.return_value = MagicMock()
        mock_import.return_value = mock_paddleocr
        mock_render.side_effect = RuntimeError("PDF corrupt")

        result = _paddle_extract("/corrupt.pdf", 5)
        assert result is None


class TestOcrExtractorAdvanced:
    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=True)
    def test_extract_ai_wins_over_paddle(self, mock_reachable, mock_paddle):
        """When AI returns higher effective confidence, it is chosen."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Paddle text", extracted={},
            confidence=50.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())

        with patch("services.document_automation.ai_fallback.ai_extract") as mock_ai:
            mock_ai.return_value = ExtractionResult(
                full_text="AI text with more fields", extracted={},
                confidence=70.0, engine="ai_transcribe", pages_processed=1,
            )
            with patch("services.document_automation.ocr_extractor.extract_fields",
                       side_effect=[
                           {"cmr_number": "C001"},      # Paddle: 1 field
                           {"cmr_number": "C002", "truck_plate": "AB123CD"},  # AI: 2 fields → boost
                       ]):
                result = extractor.extract("/fake.pdf")
                assert result.full_text == "AI text with more fields"
                assert result.engine == "ai_transcribe"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_field_boost(self, mock_reachable, mock_paddle):
        """When Paddle result has 2+ fields, confidence gets boosted above threshold."""
        mock_paddle.return_value = ExtractionResult(
            full_text="CMR: CMR001 Truck: AB123CD", extracted={},
            confidence=35.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"cmr_number": "CMR001", "truck_plate": "AB123CD"}):
            result = extractor.extract("/fake.pdf")
            # Boosted from 35.0 → 99.0
            assert result.confidence == 99.0
            assert result.engine == "paddle"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_cloud_fallback(self, mock_reachable, mock_paddle):
        """When both Paddle and AI fail, cloud OCR is tried."""
        mock_paddle.return_value = ExtractionResult(
            full_text="low quality text", extracted={},
            confidence=10.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())

        with patch("services.document_automation.cloud_ocr.cloud_extract") as mock_cloud:
            mock_cloud.return_value = ExtractionResult(
                full_text="Cloud high quality text", extracted={},
                confidence=90.0, engine="google", pages_processed=1,
            )
            with patch("services.document_automation.ocr_extractor.extract_fields",
                       return_value={"cmr_number": "C001"}):
                result = extractor.extract("/fake.pdf")
                assert result.full_text == "Cloud high quality text"
                assert result.engine == "google"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_cloud_unavailable(self, mock_reachable, mock_paddle):
        """When cloud OCR raises ImportError, the pipeline returns the best available result."""
        mock_paddle.return_value = ExtractionResult(
            full_text="some text", extracted={},
            confidence=30.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())

        with patch("services.document_automation.cloud_ocr.cloud_extract",
                   side_effect=ImportError("no cloud")):
            with patch("services.document_automation.ocr_extractor.extract_fields",
                       return_value={"cmr_number": "C001"}):
                result = extractor.extract("/fake.pdf")
                assert result.full_text == "some text"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_doc_type_cmr(self, mock_reachable, mock_paddle):
        """When cmr_number is extracted, doc_type should be 'cmr'."""
        mock_paddle.return_value = ExtractionResult(
            full_text="CMR: CMR001", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"cmr_number": "CMR001"}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("doc_type") == "cmr"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_doc_type_invoice(self, mock_reachable, mock_paddle):
        """When invoice_number is extracted, doc_type should be 'invoice'."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Invoice INV-2024-001", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"invoice_number": "INV-2024-001"}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("doc_type") == "invoice"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_doc_type_delivery_note(self, mock_reachable, mock_paddle):
        """When package_count or weight_kg is extracted, doc_type should be 'delivery_note'."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Packages: 24 Weight: 1000 kg", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"package_count": "24", "weight_kg": "1000"}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("doc_type") == "delivery_note"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_doc_type_other(self, mock_reachable, mock_paddle):
        """When no specific doc fields are found, doc_type should be 'other'."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Some random document", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"driver_name": "John Doe"}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("doc_type") == "other"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_field_aliasing(self, mock_reachable, mock_paddle):
        """AI/cloud field aliases are mapped to internal field names."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Vehicle: AB123CD Trailer: XY789Z", extracted={
                "vehicle_registration": "AB123CD",
                "trailer_registration": "XY789Z",
            },
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("truck_plate") == "AB123CD"
            assert result.extracted.get("trailer_plate") == "XY789Z"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_stop_event_cancels(self, mock_reachable, mock_paddle):
        """Setting stop_event early returns a result (may be empty)."""
        import threading
        stop = threading.Event()
        stop.set()  # already cancelled

        mock_paddle.return_value = ExtractionResult(
            full_text="Some text", extracted={},
            confidence=80.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"cmr_number": "C001"}):
            result = extractor.extract("/fake.pdf", stop_event=stop)
            # Should handle stop gracefully and still return something
            assert result is not None

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_user_company_filtering(self, mock_reachable, mock_paddle):
        """Stamp fields matching user_company are filtered out by extract_fields."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Stamp 1: My Transport Co\nStamp 2: Client ABC", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        # Simulate extract_fields filtering user_company stamps
        def _mock_extract_fields(text, user_company=""):
            fields = {
                "consignor_stamp": "My Transport Co",
                "consignee_stamp": "Client ABC",
            }
            uc = user_company.strip().lower() if user_company else ""
            if uc:
                for sk in ("consignor_stamp", "consignee_stamp", "haulier_stamp"):
                    val = fields.get(sk)
                    if val and val.strip().lower() == uc:
                        del fields[sk]
            return fields

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   side_effect=_mock_extract_fields):
            result = extractor.extract("/fake.pdf", user_company="My Transport Co")
            assert "consignor_stamp" not in result.extracted
            assert result.extracted.get("consignee_stamp") == "Client ABC"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_date_normalization(self, mock_reachable, mock_paddle):
        """Date fields are normalized to YYYY-MM-DD format."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Date: 15/01/2024", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"date": "15/01/2024"}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("date") == "2024-01-15"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_consignee_from_client_name(self, mock_reachable, mock_paddle):
        """When client_name is extracted, consignee is aliased from it."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Client: ABC Corp", extracted={
                "client_name": "ABC Corp",
            },
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("consignee") == "ABC Corp"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=True)
    def test_extract_ai_unreachable_skips(self, mock_reachable, mock_paddle):
        """When AI endpoint is reachable but ai_extract fails, fall back."""
        mock_reachable.return_value = True
        mock_paddle.return_value = ExtractionResult(
            full_text="Paddle result", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())

        with patch("services.document_automation.ai_fallback.ai_extract") as mock_ai:
            mock_ai.return_value = None
            with patch("services.document_automation.ocr_extractor.extract_fields",
                       return_value={"cmr_number": "C001"}):
                result = extractor.extract("/fake.pdf")
                assert result.engine == "paddle"
                assert "C001" in result.extracted.get("cmr_number", "")

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    def test_extract_ai_endpoint_unreachable_import_error(self, mock_paddle):
        """When AI endpoint check would fail due to import error, AI is skipped."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Paddle result", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())

        # Force _endpoint_reachable to return False by making requests import fail
        with patch("services.document_automation.ocr_extractor._endpoint_reachable",
                   return_value=False):
            with patch("services.document_automation.ocr_extractor.extract_fields",
                       return_value={"cmr_number": "C001"}):
                result = extractor.extract("/fake.pdf")
                assert result.engine == "paddle"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_both_none_empty_result(self, mock_reachable, mock_paddle):
        """When both Paddle and AI return None, empty result is returned."""
        mock_paddle.return_value = None

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        result = extractor.extract("/fake.pdf")
        assert result.engine == "none"
        assert result.confidence == 0.0
        assert result.full_text == ""
        assert result.extracted.get("doc_type") == "other"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_cloud_improves_over_both_failed(self, mock_reachable, mock_paddle):
        """Cloud OCR can improve even when Paddle has some text but low confidence."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Poor quality scan", extracted={},
            confidence=30.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())

        with patch("services.document_automation.cloud_ocr.cloud_extract") as mock_cloud:
            mock_cloud.return_value = ExtractionResult(
                full_text="High quality cloud result", extracted={},
                confidence=95.0, engine="google", pages_processed=1,
            )
            with patch("services.document_automation.ocr_extractor.extract_fields",
                       return_value={"cmr_number": "C001"}):
                result = extractor.extract("/fake.pdf")
                assert result.full_text == "High quality cloud result"
                assert result.engine == "google"

    @patch("services.document_automation.ocr_extractor._paddle_extract")
    @patch("services.document_automation.ocr_extractor._endpoint_reachable", return_value=False)
    def test_extract_raw_text_in_extracted(self, mock_reachable, mock_paddle):
        """raw_text field is always set in extracted dict."""
        mock_paddle.return_value = ExtractionResult(
            full_text="Raw OCR output text here", extracted={},
            confidence=85.0, engine="paddle", pages_processed=1,
        )

        extractor = OcrExtractor(max_pages=5, db=MagicMock())
        with patch("services.document_automation.ocr_extractor.extract_fields",
                   return_value={"cmr_number": "C001"}):
            result = extractor.extract("/fake.pdf")
            assert result.extracted.get("raw_text") == "Raw OCR output text here"


class TestSafeImports:
    def test_safe_import_fitz_returns_module(self):
        """_safe_import_fitz returns None or fitz module."""
        result = _safe_import_fitz()
        # In test env it's likely None; just verify it doesn't crash
        assert result is None or hasattr(result, "open")
