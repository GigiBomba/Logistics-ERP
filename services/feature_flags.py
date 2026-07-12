"""Feature flags system for gradual rollout and A/B testing."""
import logging
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FlagScope(str, Enum):
    GLOBAL = "global"      # On/off for everyone
    PER_COMPANY = "company"  # Per company override
    PER_USER = "user"       # Per user override
    PERCENTAGE = "percentage"  # Percentage rollout


@dataclass
class FeatureFlag:
    """A single feature flag definition."""
    key: str
    description: str
    default: bool = False
    scope: FlagScope = FlagScope.GLOBAL
    metadata: dict = field(default_factory=dict)


# Registry of all feature flags
FEATURE_FLAGS: dict[str, FeatureFlag] = {
    "timocom_integration": FeatureFlag(
        key="timocom_integration",
        description="TIMOCOM freight exchange integration",
        default=False,
        scope=FlagScope.PER_COMPANY,
        metadata={"partner": "timocom", "requires_oauth2": True}
    ),
    "api_v2": FeatureFlag(
        key="api_v2",
        description="API v2 endpoints (experimental)",
        default=False,
        scope=FlagScope.PER_COMPANY,
    ),
    "new_route_planner": FeatureFlag(
        key="new_route_planner",
        description="Next-gen route planning algorithm",
        default=False,
        scope=FlagScope.PERCENTAGE,
        metadata={"rollout_pct": 10}
    ),
    "ocr_auto_process": FeatureFlag(
        key="ocr_auto_process",
        description="Automatic OCR processing on document upload",
        default=True,
        scope=FlagScope.GLOBAL,
    ),
    "background_pdf_generation": FeatureFlag(
        key="background_pdf_generation",
        description="Generate PDFs in background via Celery",
        default=True,
        scope=FlagScope.GLOBAL,
    ),
    "analytics_cache": FeatureFlag(
        key="analytics_cache",
        description="Enable analytics query result caching",
        default=False,
        scope=FlagScope.GLOBAL,
    ),
    "strict_validation": FeatureFlag(
        key="strict_validation",
        description="Enable strict input validation (rejects unknown fields)",
        default=False,
        scope=FlagScope.PER_COMPANY,
    ),
}


class FeatureFlagService:
    """Service to evaluate feature flags."""

    def __init__(self, db=None, redis=None):
        self.db = db
        self._redis = redis
        self._overrides: dict[str, dict] = {}  # In-memory overrides for tests

    def is_enabled(self, flag_key: str, company_id: int = 0, user_id: int = 0) -> bool:
        """Check if a feature flag is enabled.

        Priority: DB override > in-memory override > default
        """
        flag = FEATURE_FLAGS.get(flag_key)
        if not flag:
            logger.warning("Unknown feature flag: %s", flag_key)
            return False

        # Check in-memory override (for tests)
        if flag_key in self._overrides:
            return self._overrides[flag_key].get("enabled", flag.default)

        # Check DB override
        db_value = self._get_db_override(flag_key, company_id, user_id)
        if db_value is not None:
            return db_value

        # Check percentage rollout
        if flag.scope == FlagScope.PERCENTAGE:
            pct = flag.metadata.get("rollout_pct", 0)
            return self._is_in_percentage(company_id, pct)

        return flag.default

    def set_override(self, flag_key: str, enabled: bool, company_id: Optional[int] = None,
                     user_id: Optional[int] = None):
        """Set a DB-level override for a feature flag."""
        if not self.db:
            return

        try:
            key = f"feature_flag.{flag_key}"
            if company_id:
                key = f"feature_flag.{flag_key}.company.{company_id}"
            if user_id:
                key = f"feature_flag.{flag_key}.user.{user_id}"

            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository(self.db)
            repo.upsert_setting(key, "1" if enabled else "0")
            logger.info("Feature flag override: %s = %s", key, enabled)
        except Exception as e:
            logger.warning("Failed to set feature flag override: %s", e)

    def _get_db_override(self, flag_key: str, company_id: int, user_id: int) -> Optional[bool]:
        """Check for DB-level overrides. More specific overrides win."""
        if not self.db:
            return None

        try:
            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository(self.db)

            # Most specific first
            checks = [
                f"feature_flag.{flag_key}.user.{user_id}",
                f"feature_flag.{flag_key}.company.{company_id}",
                f"feature_flag.{flag_key}",
            ]

            for key in checks:
                value = repo.get_setting_value(key)
                if value is not None:
                    return value == "1"
        except Exception:
            pass

        return None

    def _is_in_percentage(self, company_id: int, pct: int) -> bool:
        """Deterministic percentage-based rollout using company_id."""
        if pct >= 100:
            return True
        if pct <= 0:
            return False
        return (company_id % 100) < pct

    # Test helpers
    def enable_for_test(self, flag_key: str):
        """Enable a flag for testing (in-memory only)."""
        self._overrides[flag_key] = {"enabled": True}

    def disable_for_test(self, flag_key: str):
        """Disable a flag for testing."""
        self._overrides[flag_key] = {"enabled": False}

    def reset_test_overrides(self):
        """Clear all test overrides."""
        self._overrides.clear()

    def list_flags(self) -> list[dict]:
        """List all registered feature flags with their current state."""
        result = []
        for key, flag in FEATURE_FLAGS.items():
            result.append({
                "key": flag.key,
                "description": flag.description,
                "default": flag.default,
                "scope": flag.scope,
                "current": self.is_enabled(key),
            })
        return result
