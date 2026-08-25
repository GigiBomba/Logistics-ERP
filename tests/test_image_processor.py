"""Tests for image_processor module."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from services.document_automation.image_processor import (
    ImageProcessor,
    ProcessingError,
    _compute_output_size,
    _deskew,
    _enhance_single_image,
    _estimate_blur,
    _four_point_transform,
    _images_to_pdf,
    _order_points,
    _pdf_copy,
    _pdf_merge,
    _safe_import_cv2,
    _safe_import_fitz,
    _safe_import_pillow_heif,
)
from services.document_automation.types import ProcessingResult


class TestHelpers:
    def test_compute_output_size_within_limit(self):
        assert _compute_output_size(2000, 1500) == (2000, 1500)

    def test_compute_output_size_scales_down(self):
        w, h = _compute_output_size(6000, 4000)
        assert max(w, h) <= 4800

    def test_order_points(self):
        pts = [(10, 100), (100, 100), (100, 10), (10, 10)]  # TL, TR, BR, BL in random order
        ordered = _order_points(pts)
        assert ordered[0] == (10, 10)  # TL
        assert ordered[1] == (100, 10)  # TR
        assert ordered[2] == (100, 100)  # BR
        assert ordered[3] == (10, 100)  # BL

    def test_safe_import_cv2(self):
        result = _safe_import_cv2()
        # cv2 may or may not be installed
        assert result is None or hasattr(result, "imread")

    def test_safe_import_fitz(self):
        result = _safe_import_fitz()
        assert result is None or hasattr(result, "open")


class TestFourPointTransform:
    @patch("services.document_automation.image_processor._order_points")
    def test_degenerate_quad_returns_original(self, mock_order):
        mock_order.return_value = [(0, 0), (10, 0), (10, 10), (0, 10)]
        import numpy as np
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _four_point_transform(image, [(0, 0), (1, 0), (1, 1), (0, 1)], MagicMock(), np)
        # Quad too small (1x1) - should return original
        assert result.shape == image.shape


class TestEnhanceSingleImage:
    @patch("services.document_automation.image_processor._safe_import_cv2", return_value=None)
    def test_without_opencv_transcodes(self, mock_cv2):
        """When OpenCV is not available, just convert to PNG."""
        with patch("PIL.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_img.mode = "RGB"
            mock_img.size = (100, 100)
            mock_open.return_value.__enter__.return_value = mock_img

            size, enhanced, paths = _enhance_single_image("/fake/test.jpg", "/tmp/out.png")
            assert enhanced is False
            assert len(paths) == 1
            mock_img.save.assert_called_once_with("/tmp/out.png", "PNG")

    @patch("services.document_automation.image_processor._safe_import_cv2")
    def test_image_load_failure(self, mock_cv2):
        mock_cv2.return_value = None  # no cv2
        with patch("PIL.Image.open", side_effect=OSError("Cannot load")):
            with pytest.raises(ProcessingError, match="Cannot load"):
                _enhance_single_image("/fake/bad.jpg", "/tmp/out.png")


class TestDeskew:
    def test_no_lines_returns_zero(self):
        import numpy as np
        mock_cv2 = MagicMock()
        mock_cv2.Canny.return_value = MagicMock()
        mock_cv2.HoughLinesP.return_value = None
        result = _deskew(np.zeros((100, 100), dtype=np.uint8), mock_cv2)
        assert result == 0.0


class TestEstimateBlur:
    def test_blur_metric(self):
        import numpy as np
        mock_cv2 = MagicMock()
        mock_cv2.Laplacian.return_value = np.ones((10, 10), dtype=np.float64) * 5
        result = _estimate_blur(np.zeros((100, 100), dtype=np.uint8), mock_cv2)
        assert isinstance(result, float)


class TestPdfOperations:
    @patch("services.document_automation.image_processor._safe_import_fitz")
    def test_pdf_enhance_render_no_fitz(self, mock_fitz):
        """If PyMuPDF is not available, PDF rendering is a no-op."""
        mock_fitz.return_value = None
        from services.document_automation.image_processor import _render_pdf_pages_to_images
        paths, enhanced = _render_pdf_pages_to_images("/fake/test.pdf", "/tmp/enhanced", "job1")
        assert paths == []
        assert enhanced is False

    def test_images_to_pdf_via_pillow(self):
        """Test images_to_pdf converts images to PDF via Pillow."""
        import io as _io
        from PIL import Image
        # Create a small test image
        img = Image.new("RGB", (10, 10), color="red")
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        with patch("PIL.Image.open", return_value=img):
            with patch.object(img, "save") as mock_save:
                # Force Pillow fallback by removing img2pdf from sys.modules
                with patch.dict("sys.modules", {"img2pdf": None}):
                    result = _images_to_pdf(["/fake/img.png"], "/tmp/out.pdf")
                    assert result == 1  # one page


class TestImageProcessor:
    def test_process_no_inputs(self):
        processor = ImageProcessor()
        with pytest.raises(ProcessingError, match="No input files"):
            processor.process([], "/tmp/out")

    def test_process_skips_missing_files(self):
        processor = ImageProcessor()
        with patch("os.path.isfile", return_value=False), \
             patch("os.makedirs"):
            with pytest.raises(ProcessingError, match="No supported input files"):
                processor.process(["/missing/file.pdf"], "/tmp/out")

    @patch("os.makedirs")
    @patch("os.path.isfile", return_value=True)
    @patch("services.document_automation.image_processor._enhance_single_image")
    @patch("services.document_automation.image_processor._images_to_pdf", return_value=1)
    def test_process_single_image(self, mock_pdf, mock_enhance, mock_isfile, mock_makedirs):
        mock_enhance.return_value = ((100, 100), True, ["/tmp/enhanced/out.png"])

        processor = ImageProcessor()
        result = processor.process(
            ["/fake/test.jpg"],
            output_dir="/tmp/out",
            job_id="test",
        )

        assert isinstance(result, ProcessingResult)
        assert result.enhanced is True
        assert result.pages == 1
        assert result.method == "single_image_enhanced"

    @patch("os.makedirs")
    @patch("os.path.isfile", return_value=True)
    @patch("services.document_automation.image_processor._pdf_copy", return_value=3)
    @patch("services.document_automation.image_processor._images_to_pdf", return_value=3)
    def test_process_single_pdf(self, mock_pdf, mock_copy, mock_isfile, mock_makedirs):
        processor = ImageProcessor()

        with patch("services.document_automation.image_processor._render_pdf_pages_to_images",
                   return_value=(["/tmp/en/p1.png", "/tmp/en/p2.png", "/tmp/en/p3.png"], False)):
            result = processor.process(
                ["/fake/test.pdf"],
                output_dir="/tmp/out",
                job_id="test",
            )
            assert result.pages == 3
