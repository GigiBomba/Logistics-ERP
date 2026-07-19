"""Documentation search and answer service for Help Mode.

Blueprint: §33 — Help Mode.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.copilot.schemas import DocSource, HelpAnswer

logger = logging.getLogger(__name__)

# ── Initial knowledge base ─────────────────────────────────────────────────

_HELP_CONTENT: dict[str, list[dict[str, Any]]] = {
    "en": [
        {
            "article_id": "getting_started",
            "title_key": "help.getting_started.title",
            "content": (
                "Operion ERP helps manage your fleet, drivers, trips, and "
                "finances. The main navigation is on the left sidebar. "
                "Use the Overview screen to see key metrics at a glance. "
                "The Co-Pilot panel (AI icon in sidebar) lets you ask questions "
                "in natural language."
            ),
            "keywords": ["getting started", "welcome", "introduction", "beginner", "overview", "basics"],
            "screen": None,
        },
        {
            "article_id": "fleet_management",
            "title_key": "help.fleet_management.title",
            "content": (
                "The Fleet section shows all your vehicles. You can add new trucks, "
                "view maintenance history, track health scores, and monitor "
                "real-time locations. Use the 'Add Vehicle' button to register "
                "a new truck, or click any vehicle for detailed information."
            ),
            "keywords": ["fleet", "vehicles", "trucks", "add vehicle", "fleet management", "health score"],
            "screen": "fleet",
        },
        {
            "article_id": "driver_management",
            "title_key": "help.driver_management.title",
            "content": (
                "The Drivers section manages all driver information including "
                "contact details, licenses, tachograph data, and hours of service. "
                "Click 'Add Driver' to register a new driver. Use the tachograph "
                "import to analyze driver working hours."
            ),
            "keywords": ["driver", "drivers", "add driver", "tachograph", "hours of service", "license"],
            "screen": "drivers",
        },
        {
            "article_id": "trip_management",
            "title_key": "help.trip_management.title",
            "content": (
                "Trips are the core of Operion. Create a trip by selecting origin, "
                "destination, vehicle, and driver. The system calculates profitability "
                "including fuel costs, tolls, and driver salary. Use the Route Planner "
                "to optimize multi-stop routes with GraphHopper."
            ),
            "keywords": ["trip", "trips", "create trip", "route", "route planner", "multi-stop", "optimize route"],
            "screen": "trips",
        },
        {
            "article_id": "dispatch_board",
            "title_key": "help.dispatch_board.title",
            "content": (
                "The Dispatch Board is a Kanban-style view for assigning trucks and "
                "drivers to trips. Drag and drop trips between columns to update status. "
                "Use the bulk assign feature to assign multiple vehicles at once. "
                "Real-time tracking shows vehicle positions on the map."
            ),
            "keywords": ["dispatch", "kanban", "assign", "bulk assign", "drag drop", "board"],
            "screen": "dispatch_board",
        },
        {
            "article_id": "invoices",
            "title_key": "help.invoices.title",
            "content": (
                "Generate invoices for clients with automatic PDF generation. "
                "You can create drafts, finalize with fiscal numbering, and email "
                "them directly. The system supports proforma invoices, credit notes, "
                "and multi-currency billing."
            ),
            "keywords": ["invoice", "invoices", "factura", "billing", "pdf", "finalize", "proforma"],
            "screen": "invoices",
        },
        {
            "article_id": "cmr_documents",
            "title_key": "help.cmr_documents.title",
            "content": (
                "CMR documents are international consignment notes required for "
                "cross-border freight. Operion generates 24-box CMR forms with "
                "eFTI embedding, PDF/A-3 compliance, and ADR dangerous goods support."
            ),
            "keywords": ["cmr", "consignment", "cross-border", "efti", "adr", "dangerous goods"],
            "screen": "cmr",
        },
        {
            "article_id": "profitability",
            "title_key": "help.profitability.title",
            "content": (
                "Profit margin shows the difference between revenue and total trip costs "
                "(fuel, tolls, driver salary, maintenance). The Trip Calculator computes "
                "net profit, margin percentage, and cost breakdown per route. "
                "A positive margin means the trip is profitable."
            ),
            "keywords": ["profit", "profitability", "margin", "net profit", "cost", "revenue", "trip calculator"],
            "screen": "calculator",
        },
        {
            "article_id": "ocr_documents",
            "title_key": "help.ocr_documents.title",
            "content": (
                "The OCR system automatically processes uploaded documents. "
                "Printed/typed text uses PaddleOCR, while handwritten text uses "
                "a self-hosted AI model. Documents are automatically classified, "
                "extracted, and matched to clients/trips. You can review and confirm "
                "matches before they are attached to records."
            ),
            "keywords": ["ocr", "document", "scan", "upload", "paddleocr", "handwriting", "extract"],
            "screen": "documents",
        },
        {
            "article_id": "live_tracking",
            "title_key": "help.live_tracking.title",
            "content": (
                "Live Tracking shows real-time GPS positions of your fleet on a map. "
                "You can view vehicle history, estimated arrival times, and set up "
                "geofence alerts. Supports multiple tracking providers including "
                "Wialon, Frotcom, and Traccar."
            ),
            "keywords": ["tracking", "gps", "live", "real-time", "map", "geofence", "position"],
            "screen": "tracking",
        },
        {
            "article_id": "maintenance",
            "title_key": "help.maintenance.title",
            "content": (
                "The Maintenance section tracks vehicle service schedules, repairs, "
                "and inspections. Set up alerts for upcoming maintenance based on "
                "time or mileage. The system can forecast maintenance needs and "
                "alert you before critical thresholds are reached."
            ),
            "keywords": ["maintenance", "service", "repair", "inspection", "alert", "schedule"],
            "screen": "maintenance",
        },
        {
            "article_id": "co_pilot",
            "title_key": "help.co_pilot.title",
            "content": (
                "The AI Co-Pilot is your natural-language assistant. You can ask it "
                "questions about your data, request actions like creating trips or "
                "invoices, and get step-by-step guidance. Type or speak your request. "
                "The Co-Pilot works with all 22 supported languages and adapts to "
                "your subscription tier."
            ),
            "keywords": ["co-pilot", "copilot", "ai", "assistant", "help", "voice", "chat", "ask"],
            "screen": "copilot",
        },
    ],
}


def _romanian_fallback(article_id: str, en_content: str) -> str:
    """Return Romanian content or English fallback."""
    romanian_content = {
        "getting_started": (
            "Operion ERP vă ajută să gestionați flota, șoferii, cursele și "
            "finanțele. Navigarea principală este în bara laterală stângă. "
            "Ecranul Prezentare Generală arată indicatorii cheie. Panoul "
            "Co-Pilot (icoana AI din bara laterală) vă permite să puneți "
            "întrebări în limbaj natural."
        ),
        "fleet_management": (
            "Secțiunea Flotă arată toate vehiculele. Puteți adăuga camioane noi, "
            "vedea istoricul de întreținere, urmări scorurile de sănătate și "
            "monitoriza locațiile în timp real."
        ),
        "driver_management": (
            "Secțiunea Șoferi gestionează toate informațiile despre șoferi "
            "inclusiv date de contact, permise, date tahograf și ore de serviciu."
        ),
        "trip_management": (
            "Cursele sunt elementul central al Operion. Creați o cursă selectând "
            "originea, destinația, vehiculul și șoferul. Sistemul calculează "
            "profitabilitatea incluzând costurile de combustibil, taxe și salariul șoferului."
        ),
        "dispatch_board": (
            "Panoul de Dispecerat este o vedere tip Kanban pentru asignarea "
            "camioanelor și șoferilor la curse. Trageți și plasați cursele "
            "între coloane pentru a actualiza statusul."
        ),
        "invoices": (
            "Generați facturi pentru clienți cu generare automată PDF. "
            "Puteți crea ciorne, finaliza cu numerotare fiscală și trimite "
            "prin email direct."
        ),
        "cmr_documents": (
            "Documentele CMR sunt note de consignație internaționale necesare "
            "pentru transportul transfrontalier. Operion generează formulare CMR "
            "cu 24 de casete, încorporare eFTI și conformitate PDF/A-3."
        ),
        "profitability": (
            "Marja de profit arată diferența dintre venituri și costurile totale "
            "ale cursei (combustibil, taxe, salariu șofer, întreținere). Calculatorul "
            "de Curse calculează profitul net și procentul marjei."
        ),
        "ocr_documents": (
            "Sistemul OCR procesează automat documentele încărcate. "
            "Textul tipărit folosește PaddleOCR, iar textul de mână folosește "
            "un model AI găzduit local."
        ),
        "live_tracking": (
            "Urmărirea în Timp Real arată pozițiile GPS ale flotei pe o hartă. "
            "Puteți vizualiza istoricul vehiculelor și orele estimate de sosire."
        ),
        "maintenance": (
            "Secțiunea Întreținere urmărește programările de service, reparații "
            "și inspecții. Configurați alerte pentru întreținerea viitoare."
        ),
        "co_pilot": (
            "Co-Pilot AI este asistentul în limbaj natural. Îl puteți întreba "
            "orice despre datele dvs., solicita acțiuni și primi instrucțiuni "
            "pas cu pas."
        ),
    }
    return romanian_content.get(article_id, en_content)


# Also add Romanian translations for all articles
_HELP_CONTENT["ro"] = [
    {**a, "content": _romanian_fallback(a["article_id"], a["content"])} for a in _HELP_CONTENT["en"]
]


class DocumentationService:
    """Documentation Q&A service grounded in retrieved content."""

    def __init__(self):
        self._content = _HELP_CONTENT

    def search(self, question: str, language: str = "en", top_k: int = 3) -> list[dict]:
        """Search documentation by keyword matching.

        Phase 1: Simple keyword matching. Phase 2: pgvector embeddings.
        """
        question_lower = question.lower()
        question_words = set(question_lower.split())

        articles = self._content.get(language, self._content.get("en", []))
        if not articles:
            articles = self._content["en"]

        scored = []
        for article in articles:
            keywords = article.get("keywords", [])
            screen = article.get("screen")
            content_lower = article["content"].lower()

            # Score: keyword match + word overlap + screen match
            score = 0.0

            # Keyword matches
            for kw in keywords:
                if kw in question_lower:
                    score += 2.0

            # Word overlap with content
            content_words = set(content_lower.split())
            overlap = len(question_words & content_words)
            score += overlap * 0.5

            # Boost for screen-specific questions
            if screen and screen in question_lower:
                score += 1.0

            if score > 0:
                scored.append((score, article))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:top_k]]

    def search_and_answer(
        self,
        question: str,
        language: str = "en",
        active_screen: str | None = None,
    ) -> HelpAnswer:
        """Answer a question from documentation.

        Returns HelpAnswer with grounded sources.
        """
        results = self.search(question, language)

        # Filter by active screen if provided
        if active_screen and len(results) > 1:
            screen_results = [r for r in results if r.get("screen") == active_screen]
            if screen_results:
                results = screen_results + [r for r in results if r.get("screen") != active_screen]

        if not results:
            return HelpAnswer(
                answer_key="copilot.help.no_answer",
                answer_params={"question": question},
                sources=[],
                doc_corpus_version="1.0.0",
            )

        # Combine top results into a coherent answer
        top = results[0]
        sources = [
            DocSource(
                article_id=r["article_id"],
                title_key=r["title_key"],
                url=f"/help/{r['article_id']}",
                excerpt=r["content"][:200] + ("..." if len(r["content"]) > 200 else ""),
            )
            for r in results[:3]
        ]

        return HelpAnswer(
            answer_key="copilot.help.answer",
            answer_params={
                "answer": top["content"],
                "article_count": len(sources),
            },
            sources=sources,
            doc_corpus_version="1.0.0",
        )


# Singleton
_documentation_service: DocumentationService | None = None


def get_documentation_service() -> DocumentationService:
    global _documentation_service
    if _documentation_service is None:
        _documentation_service = DocumentationService()
    return _documentation_service
