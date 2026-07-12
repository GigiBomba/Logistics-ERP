"""Audit service — centralized audit logging for all business operations."""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditService:
    """Centralized audit logging service.

    Thin wrapper around ``AuditRepository`` that enriches every event with
    a correlation ID (if available) and provides a consistent logging
    surface for all business services.
    """

    def __init__(self, db) -> None:
        self.db = db

    def log(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        user_id: int = 0,
        data: Optional[dict] = None,
        company_id: int = 0,
    ) -> None:
        """Log a business event to the audit trail.

        Args:
            event_type:  Dot-separated event type, e.g. ``"trip.created"``.
            entity_type: Type of the primary entity, e.g. ``"trip"``.
            entity_id:   String ID of the primary entity.
            user_id:     ID of the user who performed the action.
            data:        Arbitrary key-value payload (will be JSON-serialised).
            company_id:  Company scope override.
        """
        try:
            from repositories.audit_repository import AuditRepository

            repo = AuditRepository(self.db)

            # Enrich with correlation ID if available
            enriched_data: dict[str, Any] = dict(data or {})
            try:
                from backend.middleware.correlation_middleware import get_correlation_id

                cid = get_correlation_id()
                if cid:
                    enriched_data["_correlation_id"] = cid
            except (ImportError, LookupError):
                pass

            repo.log_event(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=str(entity_id),
                data=enriched_data,
                user_id=user_id,
                company_id=company_id,
            )
            logger.debug("Audit: %s %s id=%s user=%d", event_type, entity_type, entity_id, user_id)
        except Exception as e:
            logger.warning("Audit logging failed for %s: %s", event_type, e)
