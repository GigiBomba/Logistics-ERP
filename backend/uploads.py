"""Server-side upload hardening helpers (stdlib only).

Shared by the document upload endpoint (``backend/api/v1/documents.py``)
and the avatar endpoint (``backend/api/v1/avatars.py``).

* Magic-byte sniffing before trusting MIME/extension.
* Filename sanitization (basename + whitelisted extension, no path
  separators / ``..`` / control characters).
* JPEG EXIF (APP1) stripping via raw bytes — no Pillow dependency.

PNG has no EXIF container by default (EXIF lives in the ``eXIf``
ancillary chunk), so no stripping is needed for PNG.
"""

from __future__ import annotations

import os
from typing import Optional, Set

# ── Magic-byte signatures ────────────────────────────────────────────────
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_PDF = b"%PDF-"
MAGIC_TIFF_LE = b"II*\x00"
MAGIC_TIFF_BE = b"MM\x00*"
MAGIC_ZIP = b"PK\x03\x04"
MAGIC_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc / .xls

# Plain-text types have no binary magic — validated via _looks_like_text().
_TEXT_MIME_TYPES = {"text/plain", "text/csv"}

# MIME type -> accepted leading signatures (first bytes).
MIME_SIGNATURES = {
    "application/pdf": (MAGIC_PDF,),
    "image/jpeg": (MAGIC_JPEG,),
    "image/png": (MAGIC_PNG,),
    "image/tiff": (MAGIC_TIFF_LE, MAGIC_TIFF_BE),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (MAGIC_ZIP,),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (MAGIC_ZIP,),
    # Legacy .doc/.xls are OLE2 compound files; docx/xlsx (same family) are ZIP.
    "application/msword": (MAGIC_ZIP, MAGIC_OLE2),
    "application/vnd.ms-excel": (MAGIC_ZIP, MAGIC_OLE2),
}

# Safe extensions accepted for stored filenames (documents upload surface).
# Mirrors ALLOWED_DOCUMENT_MIME_TYPES in backend/api/v1/documents.py.
DOCUMENT_SAFE_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff",
    ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv",
}

# Avatar upload surface.
AVATAR_SAFE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Extra safety-net extensions that the document storage layer already
# tolerates but that we never want to derive from a client filename.
_BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".ps1", ".sh", ".msi", ".com",
    ".scr", ".vbs", ".jar", ".reg", ".dll",
}


def sanitize_filename(
    filename: Optional[str],
    allow_extensions: Optional[Set[str]] = None,
) -> str:
    """Return a safe basename with a whitelisted extension.

    Strips path separators (both ``/`` and ``\\``), ``..`` components and
    control characters.  The returned name is the bare basename only; if
    the extension is not on the whitelist it is dropped.  Falls back to
    ``unnamed_file`` when nothing usable remains.

    Args:
        filename: Raw client-supplied filename (may be ``None``).
        allow_extensions: Set of allowed lower-case extensions.  Defaults
            to :data:`DOCUMENT_SAFE_EXTENSIONS`.

    Returns:
        A safe, storage-friendly filename.
    """
    if not filename:
        return "unnamed_file"

    # Normalize Windows separators then take only the final basename.
    name = os.path.basename(filename.replace("\\", "/"))
    # Remove any residual path-traversal tokens.
    name = name.replace("..", "")
    # Keep only safe characters; drop everything else (incl. control chars).
    name = "".join(c for c in name if c.isalnum() or c in "._- ").strip(" .")

    if not name:
        return "unnamed_file"

    allowed = allow_extensions if allow_extensions is not None else DOCUMENT_SAFE_EXTENSIONS
    base, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext in _BLOCKED_EXTENSIONS or ext not in allowed:
        # Reject dangerous / unknown extensions outright — never store them.
        return ""
    if ext and not base:
        return "unnamed_file" + ext
    # Normalise the extension to lower-case; keep the base name's case.
    return base + ext


def validate_magic_bytes(data: bytes, mime_type: Optional[str]) -> bool:
    """Return True when *data*'s leading bytes match *mime_type*.

    Plain-text MIME types are checked with :func:`_looks_like_text` (no
    reliable binary signature).  Unknown MIME types pass through (the
    caller's MIME whitelist already gates them).
    """
    if not data:
        return False
    mime_type = (mime_type or "").lower()

    if mime_type in _TEXT_MIME_TYPES:
        return _looks_like_text(data)

    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"

    signatures = MIME_SIGNATURES.get(mime_type)
    if not signatures:
        return True  # nothing to sniff against — MIME whitelist is the gate
    return any(data.startswith(sig) for sig in signatures)


def _looks_like_text(data: bytes) -> bool:
    """Best-effort plain-text check for txt/csv payloads."""
    sample = data[:8192]
    if not sample:
        return True
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    printable = sum(
        1 for b in sample
        if b in (9, 10, 13) or 32 <= b < 127 or b >= 128
    )
    return printable / len(sample) >= 0.9


def strip_exif(jpeg_bytes: bytes) -> bytes:
    """Remove all EXIF APP1 (0xFFE1) segments from a JPEG (stdlib only).

    Walks the JPEG marker structure between SOI and SOS; every APP1
    segment is dropped.  From the SOS marker onward the bytes are
    entropy-coded scan data, copied verbatim (EXIF lives in the header).
    If the input is not a valid JPEG or the structure is malformed, the
    original bytes are returned untouched so a payload we cannot safely
    parse is never corrupted.
    """
    if len(jpeg_bytes) < 4 or not jpeg_bytes.startswith(b"\xff\xd8"):
        return jpeg_bytes

    out = bytearray(jpeg_bytes[:2])  # SOI
    i = 2
    n = len(jpeg_bytes)

    while i < n:
        if jpeg_bytes[i] != 0xFF:
            # Scan data reached without a marker — keep remainder verbatim.
            out += jpeg_bytes[i:]
            return bytes(out)

        # Consume a run of 0xFF fill bytes, then the segment byte.
        j = i
        while j < n and jpeg_bytes[j] == 0xFF:
            j += 1
        if j >= n:
            out += jpeg_bytes[i:]
            return bytes(out)

        seg = jpeg_bytes[j]
        # Standalone markers carry no length field: TEM, RST0-7, SOI.
        if seg == 0x01 or 0xD0 <= seg <= 0xD7 or seg == 0xD8:
            out += jpeg_bytes[i:j + 1]
            i = j + 1
            continue
        if seg == 0xD9:  # EOI — end of image
            out += jpeg_bytes[i:j + 1]
            return bytes(out)

        # Markers with a 2-byte big-endian length (includes the length field).
        if j + 3 > n:
            out += jpeg_bytes[i:]
            return bytes(out)
        length = int.from_bytes(jpeg_bytes[j + 1:j + 3], "big")
        if length < 2 or j + 1 + length > n:
            return jpeg_bytes  # malformed — keep original

        end = j + 1 + length
        if seg == 0xE1:  # APP1 = EXIF — strip it
            pass
        else:
            out += jpeg_bytes[i:end]

        if seg == 0xDA:  # SOS — the rest is compressed scan data; keep as-is.
            out += jpeg_bytes[end:]
            return bytes(out)
        i = end

    return bytes(out)
