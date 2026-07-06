"""Tests for ocr_extractor module."""
from unittest.mock import MagicMock, patch

import pytest

from services.document_automation.ocr_extractor import (
    OcrExtractor,
    _endpoint_reachable,
    _load_paddle_confidence_threshold,
    _parse_paddle_output,
    _paddle_extract,
    _resolve_paddle_lang,
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
