"""Backend re-export for ``services.feature_flags.FeatureFlagService``."""
from __future__ import annotations

from services.feature_flags import FeatureFlagService, FEATURE_FLAGS
__all__ = ["FeatureFlagService", "FEATURE_FLAGS"]
