"""Microsoft Lens / Adobe Scan-like image enhancement.

Turns a photo of a document into a clean, rectified, high-contrast PDF
page using OpenCV for boundary detection, perspective transform, deskew
and adaptive thresholding.  Falls back gracefully when the document
boundary cannot be detected (use the full image with a margin).

Inputs handled:
    - PDF (single or multi-page) — copied / merged
    - JPG / JPEG, PNG, BMP, TIFF, WEBP — enhanced
    - HEIC (iPhone photos) — decoded via pillow-heif if available

Output: a single A4-formatted PDF in ``output_dir``, with the enhanced
PNG sidecars kept for the OCR module to re-read if needed.
"""

from __future__ import annotations

import contextlib
import io
import logging
import math
import os
from collections.abc import Iterable

from .types import ProcessingResult

logger = logging.getLogger("document_automation.image_processor")

# Page dimensions (A4 at 72 DPI is the canonical PDF point size).
A4_WIDTH_PT = 595
A4_HEIGHT_PT = 842

# Image extensions we know how to enhance.
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".heic"}
_PDF_EXTENSIONS = {".pdf"}


class ProcessingError(Exception):
    """Raised when an input cannot be processed."""


def _safe_import_cv2():
    """Return cv2 module, or None if not installed."""
    try:
        import cv2  # type: ignore
        return cv2
    except ImportError:
        return None


def _safe_import_pillow_heif():
    """Register HEIC opener with Pillow if pillow-heif is available."""
    try:
        from pillow_heif import register_heif_opener  # type: ignore
        register_heif_opener()
        return True
    except Exception:
        return False


def _compute_output_size(orig_w: int, orig_h: int) -> tuple[int, int]:
    """Scale a (w, h) tuple so the long side is at most 4800 px.

    Increased from 2400 to 4800 to preserve full detail for PaddleOCR.
    PaddleOCR has its own internal downscaling for text detection, so
    providing a high-resolution input gives it more information to work
    with for the recognition stage.
    """
    max_side = 4800
    long_side = max(orig_w, orig_h)
    if long_side <= max_side:
        return orig_w, orig_h
    ratio = max_side / long_side
    return int(orig_w * ratio), int(orig_h * ratio)


_IMAGE_PROCESSOR_DEBUG = os.environ.get("IMAGE_PROCESSOR_DEBUG", "").strip().lower() in ("1", "true", "yes")
# Detection mode: "auto" (try both methods), "bg_seg" (distance only), "edge" (Canny only)
_IMAGE_PROCESSOR_DETECT_MODE = os.environ.get("IMAGE_PROCESSOR_DETECT_MODE", "auto").strip().lower()

def _save_debug_image(image, debug_dir: str, name: str) -> None:
    """Save a debug image sidecar (only when IMAGE_PROCESSOR_DEBUG=1)."""
    if not _IMAGE_PROCESSOR_DEBUG:
        return
    try:
        import cv2 as _cv2
        path = os.path.join(debug_dir, name)
        if len(image.shape) == 2:
            _cv2.imwrite(path, image)
        else:
            _cv2.imwrite(path, image)
    except Exception:
        pass


def _order_points(pts) -> list[tuple[float, float]]:
    """Return a list of 4 (x, y) tuples ordered: TL, TR, BR, BL.

    Uses the standard sum/difference method:
        TL = min(x + y)
        BR = max(x + y)
        TR = min(x - y)  (or max(y - x))
        BL = max(x - y)  (or min(y - x))
    """
    import numpy as np
    a = np.array(pts, dtype="float32")
    s = a.sum(axis=1)
    d = np.diff(a, axis=1)
    tl = tuple(a[np.argmin(s)])
    br = tuple(a[np.argmax(s)])
    tr = tuple(a[np.argmin(d)])
    bl = tuple(a[np.argmax(d)])
    return [tl, tr, br, bl]


def _detect_document_quad(
    image_bgr, cv2, np, debug_dir: str | None = None, image_name: str = ""
) -> list | None:
    """Detect the document quadrilateral in ``image_bgr``.

    Primary method: background-color distance segmentation (works on any
    background, even low contrast).  Fallback: adaptive Canny edge detection
    when the primary method finds no quad.

    Returns a list of 4 ``(x, y)`` tuples ordered TL, TR, BR, BL,
    or ``None`` if no valid quad was found.
    """
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    except Exception:
        return None
    h, w = image_bgr.shape[:2]
    img_area = h * w

    if debug_dir:
        _save_debug_image(gray, debug_dir, f"{image_name}_01_grayscale.jpg")

    def _find_quad_from_binary(thresh_bin):
        """Find a quadrilateral from a binary thresholded image."""
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned = cv2.morphologyEx(thresh_bin, cv2.MORPH_CLOSE, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(cleaned, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        contours = list(contours)
        contours.sort(key=cv2.contourArea, reverse=True)
        for c in contours[:15]:
            area = cv2.contourArea(c)
            if area < img_area * 0.02 or area > img_area * 0.98:
                continue
            hull_area = cv2.contourArea(cv2.convexHull(c))
            if hull_area > 0 and area / hull_area < 0.8:
                continue
            peri = cv2.arcLength(c, True)
            best_quad = None
            for eps_mult in (0.02, 0.03, 0.04):
                approx = cv2.approxPolyDP(c, eps_mult * peri, True)
                if len(approx) == 4:
                    best_quad = [tuple(p[0]) for p in approx]
                    break
                elif 5 <= len(approx) <= 6:
                    hull = cv2.convexHull(approx)
                    if len(hull) == 4:
                        best_quad = [tuple(p[0]) for p in hull]
                        break
                    hull_peri = cv2.arcLength(hull, True)
                    reduced = cv2.approxPolyDP(hull, 0.02 * hull_peri, True)
                    if len(reduced) == 4:
                        best_quad = [tuple(p[0]) for p in reduced]
                        break
            if best_quad is None:
                continue
            ordered = _order_points(best_quad)
            (tl, tr, br, bl) = ordered
            qw = max(abs(br[0] - bl[0]), abs(tr[0] - tl[0]))
            qh = max(abs(tr[1] - br[1]), abs(tl[1] - bl[1]))
            if qw < max(w, h) * 0.05 or qh < max(w, h) * 0.05:
                continue
            return ordered
        return None

    # ── Detection mode selection ────────────────────────────────────
    def _canny_detect():
        sigma = 0.33
        v = np.median(gray)
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        edges = cv2.Canny(gray, lower, upper)
        if debug_dir:
            _save_debug_image(edges, debug_dir, f"{image_name}_06_canny_edges.jpg")
        chosen = _find_quad_from_binary(edges)
        return chosen

    def _bg_distance_detect():
        border = np.concatenate([
            gray[:5, :].ravel(),
            gray[-5:, :].ravel(),
            gray[:, :5].ravel(),
            gray[:, -5:].ravel(),
        ])
        bg_mean = float(np.mean(border))
        bg_std = float(np.std(border)) + 1e-6
        dist = np.abs(gray.astype(np.float32) - bg_mean) / bg_std
        dist = np.clip(dist, 0, 255).astype(np.uint8)
        _, thresh = cv2.threshold(dist, 3, 255, cv2.THRESH_BINARY)
        if debug_dir:
            _save_debug_image(thresh, debug_dir, f"{image_name}_02_bg_dist_thresh.jpg")
        return _find_quad_from_binary(thresh)

    chosen = None
    if _IMAGE_PROCESSOR_DETECT_MODE == "bg_seg":
        chosen = _bg_distance_detect()
    elif _IMAGE_PROCESSOR_DETECT_MODE == "edge":
        chosen = _canny_detect()
    else:
        # "auto": try bg_distance first, fall back to Canny
        chosen = _bg_distance_detect()
        if chosen is None:
            if debug_dir:
                _save_debug_image(image_bgr, debug_dir, f"{image_name}_06_retry_canny.jpg")
            chosen = _canny_detect()

    if chosen is not None and debug_dir:
        _save_debug_image(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), debug_dir, f"{image_name}_07_selected_quad.jpg")
    return chosen


def _four_point_transform(image, pts, cv2, np):
    """Apply a perspective warp to flatten the document.

    The output is constrained to an A4-like aspect ratio (1:1.414) so
    that a skewed document is not stretched into a square, and a
    minimum-size guard prevents degenerate results from garbage quads.
    """
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    width_a = ((br[0] - bl[0]) ** 2 + (br[1] - bl[1]) ** 2) ** 0.5
    width_b = ((tr[0] - tl[0]) ** 2 + (tr[1] - tl[1]) ** 2) ** 0.5
    height_a = ((tr[0] - br[0]) ** 2 + (tr[1] - br[1]) ** 2) ** 0.5
    height_b = ((tl[0] - bl[0]) ** 2 + (tl[1] - bl[1]) ** 2) ** 0.5
    max_w = int(max(width_a, width_b))
    max_h = int(max(height_a, height_b))

    # ── Minimum-size guard ─────────────────────────────────────────
    if max_w < 50 or max_h < 50:
        logger.debug("four_point_transform: degenerate quad (%dx%d) — returning original", max_w, max_h)
        return image

    # ── Enforce A4 aspect ratio (≈1:1.414) ─────────────────────────
    # This prevents extreme stretching when the detected quad is
    # narrower or wider than a real document.
    aspect_target = 1.414
    if max_w > max_h:
        candidate_h = int(max_w / aspect_target)
        if candidate_h > max_h:
            max_h = candidate_h
        else:
            max_w = int(max_h * aspect_target)
    else:
        candidate_w = int(max_h / aspect_target)
        if candidate_w > max_w:
            max_w = candidate_w
        else:
            max_h = int(max_w * aspect_target)
    max_w = max(max_w, 1)
    max_h = max(max_h, 1)

    dst = [
        [0, 0],
        [max_w - 1, 0],
        [max_w - 1, max_h - 1],
        [0, max_h - 1],
    ]
    M = cv2.getPerspectiveTransform(
        np.array(rect, dtype="float32"),
        np.array(dst, dtype="float32"),
    )
    return cv2.warpPerspective(image, M, (max_w, max_h))


def _deskew(image_gray, cv2) -> float:
    """Estimate the skew angle of ``image_gray`` using Hough lines.

    Returns the rotation in degrees to bring the image upright.
    """
    try:
        edges = cv2.Canny(image_gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, 3.14159 / 180, threshold=80,
            minLineLength=image_gray.shape[1] // 4,
            maxLineGap=20,
        )
    except Exception:
        return 0.0
    if lines is None:
        return 0.0
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 == x1:
            continue
        ang = 57.2957795 * math.atan2(y2 - y1, x2 - x1)
        if -45 <= ang <= 45:
            angles.append(ang)
    if not angles:
        return 0.0
    angles.sort()
    return float(angles[len(angles) // 2])


def _estimate_blur(image_gray, cv2_mod) -> float:
    """Return variance of Laplacian — a blur/sharpness metric.

    Typical values:
        > 400   very sharp (professional scan)
        200-400 good quality (well-lit phone photo)
        120-200 acceptable (some motion blur)
        < 120   blurry (needs sharpening)
        < 60    very blurry (strong sharpening needed)
    """
    import numpy as np
    return float(np.array(cv2_mod.Laplacian(image_gray, cv2_mod.CV_64F)).var())


def _enhance_single_image(image_path: str, output_png_path: str) -> tuple[tuple[int, int], bool, list]:
    """Process one image: rectify, deskew, enhance, save PNG.

    Returns ``(orig_size, enhanced_flag, enhanced_paths)``.
    The ``enhanced_paths`` list contains any intermediate sidecars
    (always includes the final PNG).  ``enhanced_flag`` is False if
    OpenCV isn't available or the image couldn't be processed.
    """
    cv2 = _safe_import_cv2()
    if cv2 is None:
        # Without OpenCV we just transcode the file as-is.  OCR will
        # still work on the original.
        from PIL import Image  # type: ignore
        with Image.open(image_path) as img:
            orig_mode = img.mode
            if orig_mode not in ("RGB", "L", "1"):
                img = img.convert("RGB")
            orig_size = img.size
            img.save(output_png_path, "PNG")
        return orig_size, False, [output_png_path]

    import numpy as np  # type: ignore
    from PIL import Image, ImageOps  # type: ignore

    # Open the source image, auto-rotate from EXIF and normalise to RGB.
    try:
        with Image.open(image_path) as img:
            with contextlib.suppress(Exception):
                img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            orig_size = (img.size[0], img.size[1])
            image_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except (OSError, ValueError) as exc:
        logger.warning("Image load failed for %s: %s", image_path, exc)
        raise ProcessingError(f"Cannot load image: {image_path}") from exc

    # ── Document quad detection (downscaled, then mapped back) ────────
    # Downscale the image to ~1000 px on the longest side so that:
    #   • Gaussian blur covers a meaningful area (texture noise is suppressed)
    #   • Edge detection runs faster
    #   • The document boundary becomes the dominant edge feature
    img_h, img_w = image_bgr.shape[:2]
    detection_scale = min(1000.0 / max(img_h, img_w), 1.0)
    if detection_scale < 1.0:
        small = cv2.resize(
            image_bgr, None, fx=detection_scale, fy=detection_scale,
            interpolation=cv2.INTER_AREA,
        )
    else:
        small = image_bgr

    src_name = os.path.splitext(os.path.basename(image_path))[0]
    debug_dir = os.path.join(os.path.dirname(output_png_path), "_debug")
    if _IMAGE_PROCESSOR_DEBUG:
        os.makedirs(debug_dir, exist_ok=True)
        _save_debug_image(image_bgr, debug_dir, f"{src_name}_00_original.jpg")
        _save_debug_image(small, debug_dir, f"{src_name}_01_resized.jpg")

    quad = _detect_document_quad(small, cv2, np, debug_dir=debug_dir, image_name=src_name)

    enhanced_flag = False
    if quad is not None:
        # Map quad coordinates back to original resolution.
        if detection_scale < 1.0:
            quad = [
                (int(x / detection_scale), int(y / detection_scale))
                for (x, y) in quad
            ]

        # Debug: draw the detected quad on the original image
        overlay = image_bgr.copy()
        pts_array = np.array(quad, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [pts_array], isClosed=True, color=(0, 255, 0), thickness=3)
        labels_dbg = ["TL", "TR", "BR", "BL"]
        for (x, y), lbl in zip(quad, labels_dbg):
            cv2.circle(overlay, (int(x), int(y)), 8, (0, 0, 255), -1)
            cv2.putText(overlay, lbl, (int(x) - 15, int(y) - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        _save_debug_image(overlay, debug_dir, f"{src_name}_08_quad_on_original.jpg")

        # Perspective transform
        try:
            # Debug: save source/destination points before warp
            rect = _order_points(quad)
            (tl, tr, br, bl) = rect
            wa = ((br[0] - bl[0]) ** 2 + (br[1] - bl[1]) ** 2) ** 0.5
            wb = ((tr[0] - tl[0]) ** 2 + (tr[1] - tl[1]) ** 2) ** 0.5
            ha = ((tr[0] - br[0]) ** 2 + (tr[1] - br[1]) ** 2) ** 0.5
            hb = ((tl[0] - bl[0]) ** 2 + (tl[1] - bl[1]) ** 2) ** 0.5
            mw = int(max(wa, wb))
            mh = int(max(ha, hb))
            dst_pts = [[0, 0], [mw - 1, 0], [mw - 1, mh - 1], [0, mh - 1]]
            src_dbg = np.array(rect, dtype="float32")
            dst_dbg = np.array(dst_pts, dtype="float32")
            M_debug = cv2.getPerspectiveTransform(src_dbg, dst_dbg)
            warped_dbg = cv2.warpPerspective(image_bgr, M_debug, (mw, mh))
            _save_debug_image(warped_dbg, debug_dir, f"{src_name}_09_warped_before_aspect.jpg")

            image_bgr = _four_point_transform(image_bgr, quad, cv2, np)
            enhanced_flag = True
        except Exception as exc:
            logger.debug("Perspective transform failed: %s", exc)

    # Debug: result after crop (or original if no quad found)
    _save_debug_image(image_bgr, debug_dir, f"{src_name}_10_after_crop.jpg")

    # ── Deskew (on the cropped image, not the original) ──────────────
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        angle = _deskew(gray, cv2)
        if abs(angle) > 0.3:
            h, w = image_bgr.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
            image_bgr = cv2.warpAffine(
                image_bgr, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
            enhanced_flag = True
    except Exception as exc:
        logger.debug("Deskew skipped: %s", exc)
    _save_debug_image(image_bgr, debug_dir, f"{src_name}_11_after_deskew.jpg")

    # ── Smart quality pipeline (only enhance when needed) ────────────
    # Measure blur to decide how much (if any) enhancement to apply.
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = _estimate_blur(gray, cv2)
    except Exception:
        blur_score = 999.0  # assume sharp on error

    logger.debug("Blur score: %.1f", blur_score)

    # 1. Mild unsharp mask — only for blurry images (score < 120).
    if blur_score < 120:
        try:
            blurred = cv2.GaussianBlur(image_bgr, (0, 0), 0.5)
            image_bgr = cv2.addWeighted(image_bgr, 1.2, blurred, -0.2, 0)
            enhanced_flag = True
            logger.debug("Applied light sharpening (blur=%.1f)", blur_score)
        except Exception as exc:
            logger.debug("Sharpening skipped: %s", exc)

    # 2. CLAHE contrast enhancement on LAB L-channel — only for low-quality
    #    images (score < 200).  Applied on LAB lightness preserves color.
    if blur_score < 200:
        try:
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l_ch, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(16, 16))
            l_ch = clahe.apply(l_ch)
            lab = cv2.merge([l_ch, a, b])
            image_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            enhanced_flag = True
            logger.debug("Applied LAB CLAHE (blur=%.1f)", blur_score)
        except Exception as exc:
            logger.debug("CLAHE skipped: %s", exc)

    # Always output full-color RGB image (no grayscale conversion).
    out = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    out_w, out_h = out.size
    out_w2, out_h2 = _compute_output_size(out_w, out_h)
    if (out_w2, out_h2) != (out_w, out_h):
        out = out.resize((out_w2, out_h2), Image.LANCZOS)
    out.save(output_png_path, "PNG", optimize=True)

    return orig_size, enhanced_flag, [output_png_path]


def _pdf_copy(src: str, dst: str) -> int:
    """Copy a PDF and return its page count.  Strips encryption if any."""
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except ImportError as exc:
        raise ProcessingError("pypdf is required for PDF inputs") from exc
    try:
        with open(src, "rb") as fh:
            reader = PdfReader(fh)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ProcessingError(
                        f"PDF is password-protected: {src} ({exc})"
                    ) from exc
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
        with open(dst, "wb") as out:
            writer.write(out)
        return len(reader.pages)
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError(f"PDF copy failed for {src}: {exc}") from exc


def _pdf_merge(srcs: Iterable[str], dst: str) -> int:
    """Merge multiple PDFs into a single file.  Returns total page count."""
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except ImportError as exc:
        raise ProcessingError("pypdf is required for PDF inputs") from exc
    writer = PdfWriter()
    total = 0
    for src in srcs:
        try:
            with open(src, "rb") as fh:
                reader = PdfReader(fh)
                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        logger.warning("Skipping encrypted PDF: %s", src)
                        continue
                for page in reader.pages:
                    writer.add_page(page)
                    total += 1
        except Exception as exc:
            logger.warning("Skipping unreadable PDF %s: %s", src, exc)
            continue
    try:
        with open(dst, "wb") as out:
            writer.write(out)
    except Exception as exc:
        raise ProcessingError(f"PDF merge write failed: {exc}") from exc
    return total


def _safe_import_fitz():
    """Return fitz (PyMuPDF) module, or None if not installed."""
    try:
        import fitz  # type: ignore
        return fitz
    except ImportError:
        return None


def _render_pdf_pages_to_images(
    pdf_path: str, enhanced_dir: str, job_id: str, max_pages: int = 20,
) -> tuple[list[str], bool]:
    """Render PDF pages to images, enhance each one, return enhanced PNG paths.

    Each page is rendered at 200 DPI via PyMuPDF, saved as a PNG, then
    processed through ``_enhance_single_image()`` (crop, deskew, enhance).
    The enhanced PNGs are collected and returned for merging into a final PDF.

    Returns ``(enhanced_paths, any_enhanced_flag)``.
    """
    fitz = _safe_import_fitz()
    if fitz is None:
        logger.warning("PyMuPDF not available — cannot render PDF pages for enhancement")
        return [], False


    from PIL import Image  # type: ignore

    raw_dir = os.path.join(enhanced_dir, "raw_pages")
    os.makedirs(raw_dir, exist_ok=True)

    enhanced_paths: list[str] = []
    any_enhanced = False

    doc = None
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(max_pages, len(doc))
        for idx in range(total_pages):
            page = doc.load_page(idx)
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img.load()

            # Save raw page as temp PNG for _enhance_single_image
            raw_png = os.path.join(raw_dir, f"{job_id}_pdf_{idx:04d}.png")
            img.save(raw_png, "PNG")

            # Enhance (crop, deskew, contrast)
            out_png = os.path.join(enhanced_dir, f"{job_id}_pdf_{idx:04d}.png")
            try:
                _orig_size, flag, sidecars = _enhance_single_image(raw_png, out_png)
                enhanced_paths.extend(sidecars)
                any_enhanced = any_enhanced or flag
            except (ProcessingError, Exception) as exc:
                logger.warning("PDF page %d enhancement failed for %s: %s", idx, pdf_path, exc)
                # Fall back to raw rendered page
                img.save(out_png, "PNG")
                enhanced_paths.append(out_png)

            # Clean up raw temp
            with contextlib.suppress(OSError):
                os.remove(raw_png)

        logger.info(
            "Rendered %d PDF pages from %s (%d enhanced, %d total)",
            total_pages, pdf_path, sum(1 for _ in enhanced_paths), total_pages,
        )
    except Exception as exc:
        logger.warning("PDF page rendering failed for %s: %s", pdf_path, exc)
        raise ProcessingError(f"PDF page rendering failed: {pdf_path} ({exc})") from exc
    finally:
        if doc is not None:
            with contextlib.suppress(Exception):
                doc.close()
        # Clean up raw pages dir
        with contextlib.suppress(OSError):
            os.rmdir(raw_dir)

    return enhanced_paths, any_enhanced


def _images_to_pdf(image_paths: list[str], dst: str) -> int:
    """Combine multiple images into a single PDF.  Returns page count."""
    try:
        import img2pdf  # type: ignore
    except ImportError:
        img2pdf = None  # type: ignore[assignment]
    if img2pdf is not None:  # type: ignore[truthy-function]
        try:
            with open(dst, "wb") as fh:
                fh.write(img2pdf.convert([str(p) for p in image_paths]))
            return len(image_paths)
        except Exception as exc:
            logger.warning("img2pdf failed (%s), falling back to Pillow", exc)
    from PIL import Image  # type: ignore
    images = []
    try:
        for p in image_paths:
            img = Image.open(p)
            if img.mode != "RGB":
                img = img.convert("RGB")
            images.append(img)
        if not images:
            raise ProcessingError("No images to convert")
        first, rest = images[0], images[1:]
        first.save(dst, "PDF", save_all=True, append_images=rest)
        return len(images)
    finally:
        for img in images:
            with contextlib.suppress(Exception):
                img.close()


class ImageProcessor:
    """Top-level entry point for document enhancement.

    Stateless — ``process()`` is safe to call from worker threads.
    """

    def __init__(self, max_pages_for_enhance: int = 20) -> None:
        self.max_pages_for_enhance = max_pages_for_enhance

    def process(
        self,
        input_paths: list[str],
        output_dir: str,
        job_id: str = "job",
    ) -> ProcessingResult:
        """Process one or more files into a single PDF.

        Behaviour:
            - Single PDF input  → copy to ``output_dir`` (or merge pages).
            - Single image      → enhance, save as single-page PDF.
            - Multiple images   → enhance each, merge into multi-page PDF.
            - Mixed PDF+images  → enhance images, merge all into multi-page.
        """
        if not input_paths:
            raise ProcessingError("No input files")
        try:
            os.makedirs(output_dir, exist_ok=True)
            enhanced_dir = os.path.join(output_dir, "enhanced")
            os.makedirs(enhanced_dir, exist_ok=True)
        except OSError as exc:
            raise ProcessingError(
                f"Cannot create output directory {output_dir}: {exc}"
            ) from exc

        # Split inputs by type.
        pdfs: list[str] = []
        images: list[str] = []
        for p in input_paths:
            if not os.path.isfile(p):
                logger.warning("Skipping missing file: %s", p)
                continue
            ext = os.path.splitext(p)[1].lower()
            if ext in _PDF_EXTENSIONS:
                pdfs.append(p)
            elif ext in _IMAGE_EXTENSIONS:
                images.append(p)
            else:
                logger.warning("Skipping unsupported file: %s", p)

        if not pdfs and not images:
            raise ProcessingError("No supported input files")

        enhanced_paths: list[str] = []
        enhanced_flag = False
        orig_size: tuple[int, int] = (0, 0)

        # ── Process images ──────────────────────────────────────────────
        if images:
            _safe_import_pillow_heif()
            for idx, img_path in enumerate(images):
                base = os.path.splitext(os.path.basename(img_path))[0]
                out_png = os.path.join(enhanced_dir, f"{job_id}_{idx:03d}_{base}.png")
                try:
                    size, flag, sidecars = _enhance_single_image(img_path, out_png)
                except ProcessingError as exc:
                    logger.warning("Skipping %s: %s", img_path, exc)
                    continue
                enhanced_paths.extend(sidecars)
                enhanced_flag = enhanced_flag or flag
                if idx == 0:
                    orig_size = size
            if not enhanced_paths and not pdfs:
                raise ProcessingError("All images failed to process; nothing to produce.")

        # ── Process PDFs — render pages to images, enhance, reassemble ──
        if pdfs:
            for pdf_path in pdfs:
                pdf_enhanced, pdf_flag = _render_pdf_pages_to_images(
                    pdf_path, enhanced_dir, job_id,
                    max_pages=self.max_pages_for_enhance,
                )
                enhanced_paths.extend(pdf_enhanced)
                enhanced_flag = enhanced_flag or pdf_flag

        # ── Assemble final PDF from all enhanced pages ──────────────────
        if not enhanced_paths:
            raise ProcessingError("No pages were produced from any input")

        final_pdf = os.path.join(output_dir, f"{job_id}_final.pdf")
        _images_to_pdf(enhanced_paths, final_pdf)
        page_count = len(enhanced_paths)
        if len(input_paths) == 1 and all(p.endswith(".pdf") for p in input_paths):
            method = "single_native_pdf"
        elif len(enhanced_paths) > 1:
            method = "multi_pdf_merge"
        else:
            method = "single_image_enhanced" if enhanced_flag else "single_native_pdf"

        return ProcessingResult(
            pdf_path=final_pdf,
            pages=page_count,
            original_size=orig_size,
            enhanced=enhanced_flag,
            method=method,
            enhanced_image_paths=enhanced_paths,
        )
