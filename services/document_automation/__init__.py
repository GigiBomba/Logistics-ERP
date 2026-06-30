"""Document Automation Pipeline.

Eight-stage pipeline that turns arbitrary images and PDFs into
searchable, trip-linked, customer-emailable document packages.

Public entry points are re-exported from submodules:
    - :class:`ImageProcessor`     — image enhancement
    - :class:`OcrExtractor`       — text extraction
    - :class:`TripMatcher`        — trip matching
    - :class:`DocumentGrouper`    — link docs to trip
    - :class:`CustomerDetector`   — find the customer
    - :class:`EmailTemplateService` — render email subject/body
    - :class:`PackageBuilder`     — collect linked docs into a package
"""

__all__ = [
    "CustomerDetector",
    "CustomerInfo",
    "DocumentGrouper",
    "EmailTemplateService",
    "ExtractionResult",
    "ImageProcessor",
    "MatchCandidate",
    "MatchResult",
    "OcrExtractor",
    "PackageBuilder",
    "PipelineStage",
    "ProcessingResult",
    "TripMatcher",
]

from .customer_detector import CustomerDetector
from .document_grouper import DocumentGrouper
from .email_template import EmailTemplateService
from .image_processor import ImageProcessor, ProcessingError  # noqa: F401
from .ocr_extractor import OcrExtractor
from .package_builder import PackageBuilder
from .trip_matcher import TripMatcher
from .types import (
    NON_TERMINAL_STAGES,  # noqa: F401
    CustomerInfo,
    ExtractionResult,
    MatchCandidate,
    MatchResult,
    PipelineStage,
    ProcessingResult,
)
