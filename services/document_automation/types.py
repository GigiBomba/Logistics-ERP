"""Pipeline stage enum and result dataclasses shared by all modules.

These types are imported by every other module in the package, so they
have no dependencies on any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, NamedTuple

class PipelineStage(str, Enum):
    """Discrete states a single import transitions through.

    ``import``      - file dropped / picked, run row created
    ``processing``  - image enhancement / PDF merge running
    ``enhance``     - dedicated image quality enhancement stage
    ``ocr``         - text extraction running
    ``validate``    - OCR quality assessment
    ``ai_fallback`` - AI Vision model for handwriting / low-quality scans
    ``matching``    - trip candidate scoring
    ``auto_attach`` - automatic document-to-trip linking
    ``verify``      - human verification (manual trip selection)
    ``package``     - document packaging / ZIP creation
    ``email``       - email automation step
    ``complete``    - terminal success
    ``failed``      - terminal error (see ``error_message``)
    """

    IMPORT = "import"
    PROCESSING = "processing"
    ENHANCE = "enhance"
    OCR = "ocr"
    VALIDATE = "validate"
    AI_FALLBACK = "ai_fallback"
    MATCHING = "matching"
    AUTO_ATTACH = "auto_attach"
    VERIFY = "verify"
    GROUPING = "grouping"
    PACKAGE = "package"
    EMAIL = "email"
    COMPLETE = "complete"
    FAILED = "failed"

    @classmethod
    def ordered(cls) -> list[PipelineStage]:
        """Return stages in pipeline execution order for progress tracking."""
        return [
            cls.IMPORT, cls.PROCESSING, cls.ENHANCE, cls.OCR,
            cls.VALIDATE, cls.AI_FALLBACK, cls.MATCHING,
            cls.AUTO_ATTACH, cls.GROUPING, cls.VERIFY, cls.PACKAGE, cls.EMAIL,
            cls.COMPLETE, cls.FAILED,
        ]


# Stages where the run is still in flight (used by crash recovery).
NON_TERMINAL_STAGES: tuple[str, ...] = (
    PipelineStage.IMPORT.value,
    PipelineStage.PROCESSING.value,
    PipelineStage.ENHANCE.value,
    PipelineStage.OCR.value,
    PipelineStage.VALIDATE.value,
    PipelineStage.AI_FALLBACK.value,
    PipelineStage.MATCHING.value,
    PipelineStage.AUTO_ATTACH.value,
    PipelineStage.GROUPING.value,
    PipelineStage.VERIFY.value,
    PipelineStage.PACKAGE.value,
    PipelineStage.EMAIL.value,
)


@dataclass
class ProcessingResult:
    """Output of :class:`ImageProcessor.process`."""

    pdf_path: str
    pages: int
    original_size: tuple[int, int]
    enhanced: bool
    method: str
    enhanced_image_paths: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Output of :class:`OcrExtractor.extract`."""

    full_text: str
    extracted: dict[str, str]
    confidence: float
    engine: str
    pages_processed: int


class OcrLine(NamedTuple):
    """A single line of text recognised by PaddleOCR.

    Replaces the raw nested ``list[tuple[list[float], tuple[str, float]]]``
    that PaddleOCR's ``predict()`` returns with a named structure so the
    rest of the code never touches magic indices like ``line[1][1]``.
    """

    text: str
    confidence: float
    bbox: list[float] | None = None


@dataclass
class ValidationResult:
    """Output of :class:`OcrValidator.validate`."""

    score: float                          # 0.0–1.0 overall quality
    needs_ai_fallback: bool               # True if AI Vision should be tried
    missing_fields: list[str]             # Critical fields not found
    text_quality: float                    # 0.0–1.0 heuristic text quality
    structure_ok: bool                     # Whether extracted fields are coherent


@dataclass
class MatchCandidate:
    """One possible trip match for a single import."""

    trip: dict[str, Any]
    confidence: float
    signals: dict[str, float] = field(default_factory=dict)


@dataclass
class MatchResult:
    """Output of :class:`TripMatcher.match`."""

    best_match: dict[str, Any] | None
    confidence: float
    candidates: list[MatchCandidate]
    signals: dict[str, float]

    @property
    def is_auto_attach(self) -> bool:
        """Confidence >= 0.95 means the system can attach the document
        without asking the user."""
        return self.best_match is not None and self.confidence >= 0.95

    @property
    def is_suggested(self) -> bool:
        """0.70 <= confidence < 0.95 means the user should pick a
        candidate from a sidebar."""
        return (
            self.best_match is not None
            and 0.70 <= self.confidence < 0.95
        )

    @property
    def needs_manual(self) -> bool:
        """confidence < 0.70 means no good signal — user must search
        manually."""
        return self.confidence < 0.70 or self.best_match is None


@dataclass
class CustomerInfo:
    """Output of :class:`CustomerDetector.detect_for_trip`."""

    client: dict[str, Any] | None
    primary_contact: dict[str, Any] | None
    all_emails: list[str]
    default_email: str
