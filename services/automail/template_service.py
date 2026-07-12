"""Template rendering and variable management for AutoMail.

Supports both plain-text and HTML email templates with
``{variable_name}`` substitution. Unknown variables are left untouched
so the user can see them in preview and fix the name.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from models.automail_models import EmailTemplateCreate
from models.common import ServiceResult, ErrorDetail
from repositories.automail_repository import AutoMailRepository
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

_WATERMARK_HTML = '<p style="color:#888;font-style:italic;border:1px dashed #555;padding:8px;margin-bottom:12px">Preview with sample data</p>'
_WATERMARK_TEXT = "--- Preview with sample data ---"

_VARIABLE_DEFINITIONS: list[dict[str, str]] = [
    {"name": "invoice_number", "label": "Invoice Number", "example": "INV-2026-0042",
     "description": "The invoice number"},
    {"name": "total_amount", "label": "Total Amount", "example": "1,250.00",
     "description": "Formatted total amount"},
    {"name": "currency", "label": "Currency", "example": "EUR",
     "description": "Invoice currency code"},
    {"name": "due_date", "label": "Due Date", "example": "2026-07-05",
     "description": "Payment due date"},
    {"name": "days_overdue", "label": "Days Overdue", "example": "3",
     "description": "Number of days past due (0 if not yet overdue)"},
    {"name": "company_name", "label": "Your Company", "example": "Cargo Dyvagri SRL",
     "description": "Your company name from profile settings"},
    {"name": "client_name", "label": "Client Company Name", "example": "ACME Logistics GmbH",
     "description": "The client's company name"},
    {"name": "client_contact", "label": "Client Contact Person", "example": "Hans Müller",
     "description": "The client's primary contact person"},
    {"name": "trip_id", "label": "Trip Number", "example": "42",
     "description": "The trip/load ID number"},
    {"name": "truck_plate", "label": "Truck Plate", "example": "B-123-ABC",
     "description": "Truck plate number for the trip"},
    {"name": "driver_name", "label": "Driver Name", "example": "Ion Popescu",
     "description": "Driver assigned to the trip"},
]


def get_available_variables() -> list[dict[str, str]]:
    """Return the canonical list of supported template variables."""
    return list(_VARIABLE_DEFINITIONS)


def get_sample_context() -> dict[str, str]:
    """Return a dict of realistic sample values for preview rendering.

    Values are clearly marked as preview data so the user instantly
    recognises they are not real.
    """
    return {
        "invoice_number": "INV-2026-0042 (sample)",
        "total_amount": "1,250.00",
        "currency": "EUR",
        "due_date": "2026-07-05",
        "days_overdue": "0",
        "company_name": "Your Company (sample)",
        "client_name": "ACME Logistics GmbH (sample)",
        "client_contact": "Hans Müller (sample)",
        "trip_id": "42 (sample)",
        "truck_plate": "B-123-ABC (sample)",
        "driver_name": "Ion Popescu (sample)",
    }


def render_template(
    template: str,
    context: dict[str, str],
) -> str:
    """Replace ``{key}`` tokens in *template* with values from *context*.

    Unknown tokens are left untouched so the user can see missing
    variables in the preview.
    """
    for key, value in context.items():
        token = "{" + key + "}"
        replacement = str(value) if value is not None else ""
        template = template.replace(token, replacement)
    return template


class TemplateService:
    """Service for managing and rendering email templates."""

    def __init__(self, db) -> None:
        self._repo = AutoMailRepository(db)

    def get_all_templates(self) -> list[dict[str, Any]]:
        return self._repo.get_all_templates()

    def get_template_by_id(self, template_id: int) -> Optional[dict[str, Any]]:
        return self._repo.get_template_by_id(template_id)

    def get_default_template(self) -> Optional[dict[str, Any]]:
        return self._repo.get_default_template()

    def create_template(
        self,
        request: EmailTemplateCreate | dict[str, Any],
        user_id: int | None = None,
    ) -> ServiceResult[dict]:
        """Create a new email template.

        The preferred calling convention uses a typed :class:`EmailTemplateCreate`
        and an explicit *user_id*.  For backward compatibility a plain *dict*
        is still accepted (but deprecated).

        Args:
            request: Either an :class:`EmailTemplateCreate` (preferred) or a
                     plain dict (deprecated).
            user_id: Required when *request* is an ``EmailTemplateCreate``.

        Returns:
            ServiceResult containing the created template dict.
        """
        # Backward compat: accept plain dict (deprecated)
        if isinstance(request, dict):
            logger.warning(
                "Deprecated: create_template(data=dict) is deprecated. "
                "Use create_template(request=EmailTemplateCreate, user_id=int)."
            )
            try:
                template_id = self._repo.create_template(request)
                template = self._repo.get_template_by_id(template_id)
                logger.info("Template #%d created (dict path)", template_id)
                return ServiceResult(success=True, data=template)
            except Exception as exc:
                logger.error("Failed to create template: %s", exc)
                return ServiceResult(
                    success=False,
                    errors=[ErrorDetail(message=str(exc), code="create_failed")],
                )

        # New typed path
        if user_id is None:
            raise ValueError("user_id is required when using EmailTemplateCreate")
        logger.info("Creating template '%s' by user #%d", request.name, user_id)

        perm = PermissionService(self._repo.db)
        perm_result = perm.can_send_email(user_id)
        if not perm_result.allowed:
            logger.warning(
                "Permission denied for user #%d to create template: %s",
                user_id, perm_result.reason,
            )
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=perm_result.reason, code="permission_denied")],
            )

        try:
            data = request.model_dump()
            template_id = self._repo.create_template(data)
            template = self._repo.get_template_by_id(template_id)
            logger.info("Template #%d created successfully by user #%d", template_id, user_id)
            return ServiceResult(success=True, data=template)
        except Exception as exc:
            logger.error("Failed to create template: %s", exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="create_failed")],
            )

    def list_templates(self) -> ServiceResult[list[dict]]:
        """Return all email templates.

        Returns:
            ServiceResult containing the list of template dicts.
        """
        try:
            templates = self._repo.get_all_templates()
            logger.info("Listed %d templates", len(templates))
            return ServiceResult(success=True, data=templates)
        except Exception as exc:
            logger.error("Failed to list templates: %s", exc)
            return ServiceResult(
                success=False,
                errors=[ErrorDetail(message=str(exc), code="list_failed")],
            )

    def update_template(self, template_id: int, data: dict[str, Any]) -> None:
        self._repo.update_template(template_id, data)

    def delete_template(self, template_id: int) -> None:
        self._repo.delete_template(template_id)

    def render_email(
        self,
        template: dict[str, Any],
        context: dict[str, str],
    ) -> tuple[str, str, str]:
        """Render a template dict into (subject, body_text, body_html).

        *subject* is sanitised to remove CR/LF characters that could
        be used for header injection.
        """
        subject = template.get("subject", "")
        body_text = template.get("body_text", "")
        body_html = template.get("body_html", "")

        subject = render_template(subject, context)
        body_text = render_template(body_text, context)
        body_html = render_template(body_html, context)

        # Sanitise subject header (strip newlines/tabs)
        subject = re.sub(r"[\r\n\t\0]", " ", subject).strip()

        return subject, body_text, body_html

    def preview_email(
        self,
        template: dict[str, Any],
        sample_context: Optional[dict[str, str]] = None,
    ) -> tuple[str, str, str]:
        """Render a preview with sample data for the live preview panel.

        Returns (subject, body_text_with_watermark, body_html_with_watermark).
        """
        ctx = sample_context or get_sample_context()
        subject, body_text, body_html = self.render_email(template, ctx)

        # Prepend watermark
        body_text = _WATERMARK_TEXT + "\n\n" + body_text
        body_html = _WATERMARK_HTML + body_html

        return subject, body_text, body_html
