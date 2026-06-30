"""Email subject + body templates for the automation pipeline.

Defaults are professional and bilingual-friendly.  Operators can
override them per installation via the ``settings`` table under the
keys:

    automation_email_subject_template
    automation_email_body_template
    automation_company_name

Any unknown ``{var}`` token is left in the output rather than
crashing the rendering — that way a typo in a template still produces
a usable email.

The subject is sanitised to remove CR/LF characters that could be
used for header-injection in the downstream SMTP layer.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from services.preferences import PreferencesManager

logger = logging.getLogger("document_automation.email_template")


DEFAULT_SUBJECT = "Documents for Trip #{trip_id} — {client_name}"

DEFAULT_BODY = """Dear {contact_name},

Please find attached the documents for trip #{trip_id} ({origin} → {destination}, {trip_date}).

Document package contents:
{document_list}

If you have any questions, please don't hesitate to contact us.

Kind regards,
{company_name}"""


_TOKEN_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
# Matches ASCII control characters + bare CR/LF used for header
# injection.  These are stripped from the subject before it reaches
# the SMTP layer.
_HEADER_INJECTION_RE = re.compile(r"[\r\n\t\0]")


def _sanitize_header_value(value: str) -> str:
    """Strip characters that could split a header line."""
    return _HEADER_INJECTION_RE.sub(" ", value or "").strip()


def render_template(template: str, context: dict[str, Any]) -> str:
    """Replace ``{var}`` tokens in ``template`` with values from
    ``context``.  Missing variables are left untouched.
    """
    def _replace(m):
        key = m.group(1)
        if key in context:
            value = context[key]
            return str(value) if value is not None else ""
        return m.group(0)
    return _TOKEN_RE.sub(_replace, template)


def _format_documents(documents: list[dict[str, Any]]) -> str:
    """Render a bulleted ``- filename (size)`` list."""
    if not documents:
        return "  (no documents)"
    lines: list[str] = []
    for doc in documents:
        name = doc.get("file_name") or doc.get("title") or "document"
        size = doc.get("file_size") or 0
        if isinstance(size, (int, float)) and size > 0:
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.0f} KB"
            else:
                size_str = f"{int(size)} B"
        else:
            size_str = "?"
        lines.append(f"  - {name} ({size_str})")
    return "\n".join(lines)


def _company_name_from_settings(prefs: PreferencesManager | None) -> str:
    if prefs is None:
        return "Operion ERP"
    try:
        name = prefs.get_setting("automation_company_name", "Operion ERP")
    except Exception:
        name = "Operion ERP"
    return name or "Operion ERP"


class EmailTemplateService:
    """Stateless renderer — reads overrides from :class:`PreferencesManager`."""

    def __init__(self, prefs: PreferencesManager | None = None) -> None:
        self.prefs = prefs

    def get_company_name(self) -> str:
        return _company_name_from_settings(self.prefs)

    def _subject_template(self) -> str:
        if self.prefs is None:
            return DEFAULT_SUBJECT
        try:
            override = self.prefs.get_setting(
                "automation_email_subject_template", DEFAULT_SUBJECT,
            )
        except Exception:
            override = DEFAULT_SUBJECT
        return override or DEFAULT_SUBJECT

    def _body_template(self) -> str:
        if self.prefs is None:
            return DEFAULT_BODY
        try:
            override = self.prefs.get_setting(
                "automation_email_body_template", DEFAULT_BODY,
            )
        except Exception:
            override = DEFAULT_BODY
        return override or DEFAULT_BODY

    def build_context(
        self,
        trip: dict[str, Any],
        customer,                       # CustomerInfo (may be None)
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return the substitution context for the templates."""
        origin = (
            trip.get("place_of_loading")
            or trip.get("loading_country")
            or "—"
        )
        destination = (
            trip.get("delivery_country")
            or trip.get("place_of_delivery")
            or "—"
        )
        trip_date = (
            trip.get("start_date")
            or trip.get("created_at")
            or ""
        )
        trip_date = str(trip_date)[:10] if trip_date else ""

        contact_name = "Sir/Madam"
        if customer is not None and customer.primary_contact is not None:
            full = (customer.primary_contact.get("full_name") or "").strip()
            if full:
                contact_name = full
        elif customer is not None and customer.client is not None:
            client_name_fb = (customer.client.get("contact_person") or "").strip()
            if client_name_fb:
                contact_name = client_name_fb
            elif customer.client.get("name"):
                contact_name = str(customer.client["name"])

        client_name = ""
        if customer is not None and customer.client is not None:
            client_name = (customer.client.get("name") or "").strip()

        return {
            "trip_id": trip.get("id", "?"),
            "client_name": client_name or "—",
            "contact_name": contact_name,
            "origin": origin or "—",
            "destination": destination or "—",
            "trip_date": trip_date or "—",
            "document_list": _format_documents(documents),
            "company_name": self.get_company_name(),
        }

    def render_subject(
        self,
        trip: dict[str, Any],
        customer,
    ) -> str:
        return _sanitize_header_value(
            render_template(
                self._subject_template(),
                self.build_context(trip, customer, []),
            )
        )

    def render_body(
        self,
        trip: dict[str, Any],
        customer,
        documents: list[dict[str, Any]],
    ) -> str:
        return render_template(
            self._body_template(),
            self.build_context(trip, customer, documents),
        )
