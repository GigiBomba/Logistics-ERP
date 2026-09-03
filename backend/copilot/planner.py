"""AI Planner — intent detection, entity extraction, and plan compilation.

Blueprint: §7 pipeline placement.

Phase 1: Keyword-based intent extraction (no LLM dependency).
Extracts intent name, entities, and builds a reasoning graph → execution plan.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.copilot.confidence import compute_confidence
from backend.copilot.human_handoff import HandoffTracker, should_handoff
from backend.copilot.reasoning import build_reasoning_graph, resolve_reasoning_graph
from backend.copilot.schemas import (
    CoPilotResponse,
    ConfirmationLevel,
    Entity,
    ExecutionPlan,
    ExecutionStep,
    GlobalContext,
    Intent,
    SessionContext,
    ToolResult,
    UIContext,
)
from backend.copilot.tools.registry import available_tools, get_tool

logger = logging.getLogger(__name__)

# i18n key surfaced when an intent's tool is not in the caller's permitted
# tool set (§15 — permission system).  The client resolves it via ``t()``
# exactly like every other ``copilot.*`` message key.
PERMISSION_DENIED_KEY = "copilot.error.permission_denied"

# ── Deterministic pre-pass gate (deterministic-first routing) ──────────────
# A high-confidence known intent (strong absolute score AND a clear margin
# over the runner-up) executes the deterministic keyword path BEFORE the LLM,
# so the LLM never gets a chance to hallucinate fleet/dispatch data.  Score
# floor: a doubled full-phrase match implies >= 2 significant words all
# present (each worth 2 points under _match_score).  Margin: the best intent
# must beat the runner-up by >= 2 to avoid collisions such as "flota" between
# vehicle.search and analytics.query.  help.* and unknown intents stay on the
# LLM (help questions are conversational, unknowns need the LLM's breadth).
DETERMINISTIC_MIN_SCORE: int = 4
DETERMINISTIC_MIN_MARGIN: int = 2

# ── UI-context entity resolution (§11) ────────────────────────────────────
# Maps the desktop client's ``UIContext.selected_entity_type`` vocabulary
# onto the planner's missing-entity types.  When a required entity is missing
# but the client reports the user has an entity of the matching type selected
# on screen, that selection is used BEFORE asking a clarification question.
_UI_CONTEXT_ENTITY_MAP: Dict[str, str] = {
    "vehicle": "vehicle_id",
    "driver": "driver_id",
    "client": "client_id",
    "trip": "trip_id",
}


def _apply_ui_context(intent: Intent, ui_context: UIContext) -> Intent:
    """Resolve a missing entity from the desktop client's UI selection (§11).

    Mutates *intent* in place: the matching missing entity is moved out of
    ``missing_required_entities`` into ``entities`` with source
    ``"session_context"`` (same resolution priority bucket as the session
    context, one step above a clarification question).  Returns the intent for
    convenience.
    """
    if ui_context is None or not ui_context.selected_entity_type or ui_context.selected_entity_id is None:
        return intent

    target_type = _UI_CONTEXT_ENTITY_MAP.get(ui_context.selected_entity_type)
    if target_type is None or target_type not in intent.missing_required_entities:
        return intent

    value = ui_context.selected_entity_id
    # Entity ids land in tool params as ints when they look numeric.
    if target_type.endswith("_id") and isinstance(value, str) and value.isdigit():
        value = int(value)

    intent.missing_required_entities = [
        m for m in intent.missing_required_entities if m != target_type
    ]
    intent.entities.append(Entity(
        type=target_type,
        value=value,
        source="session_context",
        confidence=1.0,
    ))
    logger.info(
        "Resolved missing entity %s from UI context selection (id=%s, screen=%s)",
        target_type, value, ui_context.active_screen,
    )
    return intent


def _record_confidence_metric(score: float) -> None:
    """Increment the ``copilot.confidence.<bucket>`` metrics counter (§23.6).

    The observability panel renders per-bucket counts from these counters;
    guarded so a metrics hiccup can never break the pipeline.
    """
    try:
        from backend.copilot.confidence import confidence_bucket
        from utils.observability import metrics
        metrics.increment(f"copilot.confidence.{confidence_bucket(score)}")
    except Exception:
        pass

# ── Tool auto-loading ───────────────────────────────────────────────────────

def _ensure_tools_loaded() -> None:
    """Import all tool modules to trigger @register_tool decorators."""
    try:
        import backend.copilot.tools.vehicle_tools       # noqa: F401
        import backend.copilot.tools.driver_tools        # noqa: F401
        import backend.copilot.tools.route_tools         # noqa: F401
        import backend.copilot.tools.trip_tools          # noqa: F401
        import backend.copilot.tools.client_tools        # noqa: F401
        import backend.copilot.tools.document_tools      # noqa: F401
        import backend.copilot.tools.currency_tools      # noqa: F401
        import backend.copilot.tools.tracking_tools      # noqa: F401
        import backend.copilot.tools.analytics_tools     # noqa: F401
        import backend.copilot.tools.freight_tools      # noqa: F401
        import backend.copilot.tools.help_tools         # noqa: F401
        import backend.copilot.tools.conversation_tools # noqa: F401
    except ImportError:
        pass  # Tools not yet implemented


def _ensure_llm_providers_loaded() -> None:
    """Import all LLM provider modules to trigger @register_llm_provider decorators.

    Must be called before any LLM routing decision so that the provider
    registry is populated and routing validation can pass.

    Same pattern as _ensure_tools_loaded() — each provider module
    self-registers at import time via its decorator.
    """
    try:
        import backend.copilot.llm.providers.google_provider   # noqa: F401
        import backend.copilot.llm.providers.ocr_ai_provider   # noqa: F401
    except ImportError:
        pass  # Providers not yet available

# ── Phase 1: Keyword-based intent mapping ───────────────────────────────────
# Maps user query patterns to (intent_name, entity_mappings)

# Each pattern: (keyword_hints, intent_name, entity_types)
# Matching uses partial word overlap — stronger than substring, weaker than phrase match.
# Split each keyword on spaces and check all words appear somewhere in utterance.

_STOPWORDS = frozenset({
    "a", "an", "as", "at", "be", "by", "do", "for", "he", "i", "in",
    "is", "it", "me", "of", "on", "or", "this", "to", "up", "we",
})


def _match_score(keyword_hints: str, utterance: str) -> int:
    """Score a keyword hint against the utterance.

    Uses word-boundary prefix matching (``\\bword\\w*``) so that:
    - ``how`` does **not** match inside ``show`` (word boundary at start)
    - ``document`` matches ``documents`` (prefix + trailing word chars)
    - ``profit`` matches ``profitability`` (stem extension)

    Common stopwords (``me``, ``do``, ``i``, ``to``, ``for`` …) are filtered
    out so they cannot inflate scores for unrelated intents.

    Full matches (all significant words present) score **double** to
    prioritise precise phrase hits over scattered partial overlaps.
    """
    significant = [w for w in keyword_hints.split() if w not in _STOPWORDS]
    if not significant:
        return 0
    matches = sum(
        1 for w in significant
        if re.search(r"\b" + re.escape(w) + r"\w*", utterance)
    )
    if matches == 0:
        return 0
    return matches * 2 if matches == len(significant) else matches


INTENT_PATTERNS: List[tuple] = [
    # (keyword_hints_list, intent_name, entity_types[, {lang: [phrases, ...]}])
    #
    # The OPTIONAL 4th element is a per-language phrase corpus (keyed by the
    # ISO code from backend.copilot.schemas.SUPPORTED_LANGUAGES) used for
    # multilingual intent matching (§23.4 Tier-B). English phrase coverage
    # stays in the base `keywords` list; only non-English languages go in the
    # dict. The dict is a PURE LITERAL (no variable references) because the
    # CI gate (scripts/ci_copilot_gates.py) hashes INTENT_PATTERNS via
    # ast.literal_eval. Phrases are lowercased so they match the lowercased
    # utterance under _match_score's word-boundary prefix matching, and they
    # deliberately contain NO entity numbers (numbers come from the utterance).
    # Intents without multilingual coverage leave the 4th element absent.

    # -- Vehicle --
    (["search vehicles", "find vehicles", "available trucks", "find truck", "look up vehicle",
      "list trucks", "show trucks", "which vehicles", "show all vehicles", "list all trucks"],
     "vehicle.search", [("query", "vehicle")],
     {
         "ro": ["caută vehicule libere", "vehiculele din flotă", "lista de vehicule", "ce camioane am in flota", "ce camioane am în flotă", "ce camioane am", "ce vehicule am in flota", "cate camioane am"],
         "de": ["finde verfügbare lkws", "suche nach freien lkw", "welche lkws sind frei"],
         "fr": ["trouve des camions disponibles", "cherche un véhicule libre", "liste les camions dispo"],
         "es": ["busca camiones disponibles", "encuentra vehículos libres", "qué camiones hay libres"],
         "pl": ["znajdź dostępne ciężarówki", "szukam wolnych pojazdów", "pokaż wolne ciężarówki"],
         "it": ["trova camion disponibili", "cerca un veicolo libero", "quali camion sono liberi"],
         "nl": ["vind beschikbare vrachtwagens", "zoek een vrije vrachtwagen", "welke trucks zijn vrij"],
         "pt": ["encontre caminhões disponíveis", "procura um veículo livre", "quais caminhões estão livres"],
         "ru": ["найти свободные грузовики", "покажи доступные машины", "какие грузовики свободны"],
         "uk": ["знайти вільні вантажівки", "покажи доступні машини", "які вантажівки вільні"],
         "tr": ["müsait kamyonları bul", "boş araç ara", "hangi kamyonlar müsait"],
         "hu": ["keress szabad kamionokat", "melyik teherautók szabadok", "szabad járművek keresése"],
         "cs": ["najdi dostupné kamiony", "hledám volný vůz", "které kamiony jsou volné"],
         "sk": ["nájdi dostupné kamióny", "hľadám voľné vozidlo", "ktoré kamióny sú voľné"],
         "sl": ["poišči proste tovornjake", "iščem prosto vozilo", "kateri tovornjaki so prosti"],
         "sr": ["нађи слободне камионе", "тражим слободно возило", "који камиони су слободни"],
         "hr": ["pronađi slobodne kamione", "tražim slobodno vozilo", "koji kamioni su slobodni"],
         "bs": ["pronađi slobodne kamione", "tražim slobodno vozilo", "koji kamioni su slobodni"],
         "sv": ["hitta lediga lastbilar", "sök ledig lastbil", "vilka lastbilar är lediga"],
         "el": ["βρες διαθέσιμα φορτηγά", "ψάχνω ελεύθερο όχημα", "ποια φορτηγά είναι διαθέσιμα"],
         "bg": ["намери свободни камиони", "търся свободно превозно средство", "кои камиони са свободни"],
     }),

    (["vehicle health", "truck health", "health score", "vehicle score", "truck score",
      "check vehicle", "vehicle condition", "truck condition", "fleet health"],
     "vehicle.health_score", [("vehicle_id", "vehicle")]),

    # -- Driver --
    (["driver hours", "check driver", "hours left", "driver available",
      "remaining hours", "how many hours", "driver schedule", "driver time"],
     "driver.check_hours", [("driver_id", "driver")],
     {
         "ro": ["verifică orele șoferului", "câte ore a lucrat șoferul", "orele de muncă"],
         "de": ["prüfe die stunden des fahrers", "wie viele stunden hat der fahrer", "fahrerstunden anzeigen"],
         "fr": ["vérifie les heures du chauffeur", "combien d heures a le conducteur", "affiche les heures de conduite"],
         "es": ["revisa las horas del conductor", "cuántas horas tiene el conductor", "muestra las horas del chofer"],
         "pl": ["sprawdź godziny kierowcy", "ile godzin ma kierowca", "pokaż godziny pracy kierowcy"],
         "it": ["controlla le ore dell autista", "quante ore ha il conducente", "mostra le ore del guidatore"],
         "nl": ["controleer de uren van de chauffeur", "hoeveel uur heeft de bestuurder", "toon de uren van de vrachtwagenchauffeur"],
         "pt": ["verifica as horas do motorista", "quantas horas tem o condutor", "mostra as horas do motorista"],
         "ru": ["проверь часы водителя", "сколько часов у водителя", "покажи часы работы водителя"],
         "uk": ["перевір години водія", "скільки годин у водія", "покажи години роботи водія"],
         "tr": ["sürücünün saatlerini kontrol et", "sürücünün kaç saati var", "sürücü saatlerini göster"],
         "hu": ["ellenőrizd a sofőr óráit", "hány órája van a sofőrnek", "mutasd a vezető óráit"],
         "cs": ["zkontroluj hodiny řidiče", "kolik hodin má řidič", "zobraz hodiny řidiče"],
         "sk": ["skontroluj hodiny vodiča", "koľko hodín má vodič", "zobraz hodiny vodiča"],
         "sl": ["preveri ure voznika", "koliko ur ima voznik", "prikaži ure voznika"],
         "sr": ["провери сате возача", "колико сати има возач", "прикажи сате вожње"],
         "hr": ["provjeri sate vozača", "koliko sati ima vozač", "prikaži sate vožnje"],
         "bs": ["provjeri sate vozača", "koliko sati ima vozač", "prikaži sate vožnje"],
         "sv": ["kontrollera förarens timmar", "hur många timmar har föraren", "visa förarens timmar"],
         "el": ["έλεγξε τις ώρες του οδηγού", "πόσες ώρες έχει ο οδηγός", "δείξε τις ώρες οδήγησης"],
         "bg": ["провери часовете на шофьора", "колко часа има шофьорът", "покажи часовете на водача"],
     }),

    # -- Route --
    (["calculate route", "plan route", "route distance", "how far", "distance between",
      "route from", "route to", "compute route", "get directions", "navigate to"],
     "route.calculate", [("stops", "route")],
     {
         "ro": ["calculează un traseu", "distanța dintre două puncte", "cât de departe"],
         "de": ["berechne eine route", "berechnung der route", "wie weit ist die strecke"],
         "fr": ["calcule un itinéraire", "calculer la distance du trajet", "quelle est la distance"],
         "es": ["calcula una ruta", "calcular la distancia del viaje", "cuál es la distancia"],
         "pl": ["oblicz trasę", "policz odległość trasy", "jaka jest odległość"],
         "it": ["calcola un percorso", "calcolare la distanza del viaggio", "qual è la distanza"],
         "nl": ["bereken een route", "bereken de afstand van de rit", "hoe ver is de route"],
         "pt": ["calcula uma rota", "calcular a distância da viagem", "qual é a distância"],
         "ru": ["рассчитай маршрут", "рассчитать расстояние поездки", "какое расстояние"],
         "uk": ["розрахуй маршрут", "розрахувати відстань поїздки", "яка відстань"],
         "tr": ["bir rota hesapla", "yolculuğun mesafesini hesapla", "mesafe ne kadar"],
         "hu": ["számíts ki egy útvonalat", "az út távolságának kiszámítása", "milyen messze van"],
         "cs": ["spočítej trasu", "vypočítat vzdálenost cesty", "jaká je vzdálenost"],
         "sk": ["vypočítaj trasu", "vypočítať vzdialenosť cesty", "aká je vzdialenosť"],
         "sl": ["izračunaj pot", "izračunati razdaljo poti", "koliko je razdalja"],
         "sr": ["израчунај руту", "израчунати удаљеност путовања", "колика је удаљеност"],
         "hr": ["izračunaj rutu", "izračunati udaljenost putovanja", "kolika je udaljenost"],
         "bs": ["izračunaj rutu", "izračunati udaljenost putovanja", "kolika je udaljenost"],
         "sv": ["beräkna en rutt", "beräkna avståndet för resan", "hur långt är det"],
         "el": ["υπολόγισε μια διαδρομή", "υπολογισμός της απόστασης του ταξιδιού", "πόση είναι η απόσταση"],
         "bg": ["изчисли маршрут", "изчисляване на разстоянието на пътуването", "колко е разстоянието"],
     }),

    (["cost estimate", "estimate cost", "fuel cost", "toll cost",
      "how much cost", "cost of route", "cost for trip", "expense estimate",
      "calculate cost", "trip cost", "route cost"],
     "route.estimate_cost", [("distance_km", "distance")]),

    (["multi stop", "multiple stops", "optimize route", "plan stops",
      "best route", "plan delivery", "delivery route", "tour plan",
      "multi destination", "several stops"],
     "route.plan_multistop", [("stops", "route")]),

    (["list routes", "show my routes", "recent routes", "saved routes"],
     "route.list", [("query", "route")]),

    (["route details", "show route by id", "fetch route"],
     "route.get", [("route_id", "route")]),

    # -- Trip --
    (["profit", "profitability", "trip profit", "calculate profit", "margin",
      "how profitable", "trip margin", "revenue estimate", "earnings estimate",
      "calculate earnings", "how much money"],
     "trip.calculate_profitability", [("km", "distance")],
     {
         "ro": ["profitabilitatea cursei", "care este profitul cursei", "marja călătoriei"],
         "de": ["berechne den gewinn", "wie profitabel ist die fahrt", "gewinn der tour berechnen"],
         "fr": ["calcule la rentabilité du trajet", "quel est le bénéfice", "marge du voyage"],
         "es": ["calcula la rentabilidad del viaje", "cuál es el beneficio", "margen del trayecto"],
         "pl": ["oblicz rentowność trasy", "jaki jest zysk", "marża podróży"],
         "it": ["calcola la redditività del viaggio", "qual è il profitto", "margine del percorso"],
         "nl": ["bereken de winstgevendheid van de rit", "wat is de winst", "marge van de reis"],
         "pt": ["calcula a rentabilidade da viagem", "qual é o lucro", "margem do percurso"],
         "ru": ["рассчитай прибыльность поездки", "какая прибыль", "маржа маршрута"],
         "uk": ["розрахуй прибутковість поїздки", "який прибуток", "маржа маршруту"],
         "tr": ["seferin kârlılığını hesapla", "kâr ne kadar", "rotanın marjı"],
         "hu": ["számítsd ki az út nyereségességét", "mekkora a nyereség", "az út árrés"],
         "cs": ["spočítej ziskovost jízdy", "jaký je zisk", "marže trasy"],
         "sk": ["vypočítaj ziskovosť jazdy", "aký je zisk", "marža trasy"],
         "sl": ["izračunaj donosnost vožnje", "kolikšen je dobiček", "marža poti"],
         "sr": ["израчунај профитабилност вожње", "колика је добит", "маржа руте"],
         "hr": ["izračunaj isplativost vožnje", "kolika je dobit", "marža rute"],
         "bs": ["izračunaj isplativost vožnje", "kolika je dobit", "marža rute"],
         "sv": ["beräkna resans lönsamhet", "hur stor är vinsten", "marginal för resan"],
         "el": ["υπολόγισε την κερδοφορία του ταξιδιού", "πόσο είναι το κέρδος", "περιθώριο της διαδρομής"],
         "bg": ["изчисли рентабилността на пътуването", "колко е печалбата", "марж на маршрута"],
     }),

    (["list trips", "recent trips", "show my trips"],
     "trip.list", [("query", "trip")]),

    (["trip details", "show trip by id", "fetch trip"],
     "trip.get", [("trip_id", "trip")]),

    (["recall conversation", "what did we discuss", "recent conversation",
      "conversation history", "recall recent conversation"],
     "conversation.recall_recent", [("query", "conversation")]),

    # -- Client --
    (["client payment", "payment summary", "client owes", "client balance",
      "how much client", "client billed", "client invoice", "client debt",
      "outstanding balance", "unpaid invoices"],
     "client.payment_summary", [("client_id", "client")],
     {
         "ro": ["sumarul plăților clientului", "cât datorează clientul", "facturile neplătite"],
         "de": ["zahlungssumme des kunden", "was schuldet der kunde", "offene rechnungen des kunden"],
         "fr": ["résumé des paiements du client", "combien doit le client", "factures impayées du client"],
         "es": ["resumen de pagos del cliente", "cuánto debe el cliente", "facturas pendientes del cliente"],
         "pl": ["podsumowanie płatności klienta", "ile klient jest winien", "niezapłacone faktury klienta"],
         "it": ["riepilogo dei pagamenti del cliente", "quanto deve il cliente", "fatture non pagate del cliente"],
         "nl": ["betalingssamenvatting van de klant", "hoeveel is de klant verschuldigd", "onbetaalde facturen van de klant"],
         "pt": ["resumo de pagamentos do cliente", "quanto o cliente deve", "faturas em aberto do cliente"],
         "ru": ["сводка платежей клиента", "сколько должен клиент", "неоплаченные счета клиента"],
         "uk": ["зведення платежів клієнта", "скільки винен клієнт", "неоплачені рахунки клієнта"],
         "tr": ["müşterinin ödeme özeti", "müşteri ne kadar borçlu", "müşterinin ödenmemiş faturaları"],
         "hu": ["az ügyfél fizetési összesítése", "mennyivel tartozik az ügyfél", "az ügyfél kifizetetlen számlái"],
         "cs": ["souhrn plateb klienta", "kolik klient dluží", "nezaplacené faktury klienta"],
         "sk": ["súhrn platieb klienta", "koľko klient dlhuje", "nezaplatené faktúry klienta"],
         "sl": ["povzetek plačil stranke", "koliko stranka dolguje", "neplačane fakture stranke"],
         "sr": ["резиме плаћања клијента", "колико клијент дугује", "неплаћене фактуре клијента"],
         "hr": ["sažetak plaćanja klijenta", "koliko klijent duguje", "neplaćene fakture klijenta"],
         "bs": ["sažetak plaćanja klijenta", "koliko klijent duguje", "neplaćene fakture klijenta"],
         "sv": ["betalningssammanfattning för kunden", "hur mycket är kunden skyldig", "obetalda fakturor för kunden"],
         "el": ["περίληψη πληρωμών του πελάτη", "πόσα χρωστάει ο πελάτης", "ανεξόφλητα τιμολόγια του πελάτη"],
         "bg": ["обобщение на плащанията на клиента", "колко дължи клиентът", "неплатени фактури на клиента"],
     }),

    # -- Document --
    (["search document", "find document", "document for", "look up document",
      "find paperwork", "find file", "search file", "locate document",
      "look up paperwork"],
     "document.search", [("query", "document")]),

    # -- Currency --
    (["exchange rate", "currency rate", "what is rate",
      "get rate", "show rate", "current rate", "fx rate"],
     "currency.get_rate", [("code", "currency")]),

    (["convert currency", "convert money", "convert to", "change currency",
      "currency conversion", "exchange to", "how much in"],
     "currency.convert", [("amount", "currency"), ("from_currency", "from_currency"), ("to_currency", "to_currency")]),

    # -- Tracking --
    (["track vehicle", "live position", "where is", "vehicle location", "gps position",
      "find location", "track fleet", "vehicle tracking",
      "where are", "current location", "show position", "locate vehicle"],
     "tracking.get_live_positions", []),

    (["vehicle history", "track history", "position history", "route history",
      "past locations", "where was", "previous route", "truck route history",
      "vehicle location history", "tracking history"],
     "tracking.get_vehicle_history", [("vehicle_id", "vehicle")]),

    # -- Analytics --
    (["analytics", "report", "statistics", "summary", "overview", "dashboard",
      "financial overview", "fleet analytics", "driver stats", "business report",
      "company overview", "performance report", "fleet report", "financial report",
      "revenue report", "profit report", "fleet summary"],
     "analytics.query", [("domain", "analytics")],
     {
         "ro": ["analiza flotei", "analizează datele flotei", "raport despre flotă"],
         "de": ["zeige die flottenanalytik", "analysiere die flottendaten", "bericht über die flotte"],
         "fr": ["affiche l analyse de la flotte", "montre les statistiques", "rapport sur la flotte"],
         "es": ["muestra el análisis de la flota", "analiza los datos de la flota", "informe de la flota"],
         "pl": ["pokaż analitykę floty", "analizuj dane floty", "raport o flocie"],
         "it": ["mostra l analisi della flotta", "analizza i dati della flotta", "rapporto sulla flotta"],
         "nl": ["toon de vlootanalyses", "analyseer de vlootgegevens", "rapport over de vloot"],
         "pt": ["mostra a análise da frota", "analisa os dados da frota", "relatório da frota"],
         "ru": ["покажи аналитику автопарка", "проанализируй данные парка", "отчет по автопарку"],
         "uk": ["покажи аналітику автопарку", "проаналізуй дані парку", "звіт по автопарку"],
         "tr": ["filo analitiğini göster", "filo verilerini analiz et", "filo raporu"],
         "hu": ["mutasd a flottaelemzést", "elemezd a flottaadatokat", "flottajelentés"],
         "cs": ["zobraz analýzu vozového parku", "analyzuj data vozového parku", "zpráva o vozovém parku"],
         "sk": ["zobraz analýzu vozového parku", "analyzuj údaje vozového parku", "správa o vozovom parku"],
         "sl": ["prikaži analitiko voznega parka", "analiziraj podatke voznega parka", "poročilo o voznem parku"],
         "sr": ["прикажи аналитику возног парка", "анализирај податке возног парка", "извештај о возном парку"],
         "hr": ["prikaži analitiku voznog parka", "analiziraj podatke voznog parka", "izvješće o voznom parku"],
         "bs": ["prikaži analitiku voznog parka", "analiziraj podatke voznog parka", "izvještaj o voznom parku"],
         "sv": ["visa flottans analys", "analysera flottans data", "rapport om flottan"],
         "el": ["δείξε την ανάλυση του στόλου", "ανάλυσε τα δεδομένα του στόλου", "αναφορά για τον στόλο"],
         "bg": ["покажи аналитиката на автопарка", "анализирай данните на автопарка", "отчет за автопарка"],
     }),

    # -- Help / Documentation --
    (["how do i", "what is", "what does", "how does", "where is", "where do i",
      "explain", "help with", "show me how", "what's a", "whats a",
      "tell me about", "i don't understand", "can you explain",
      "what does this", "how does this", "what's this", "what is this"],
     "help.answer_question", []),

    (["walk me through", "guide me", "show me the steps", "tutorial",
      "how to", "teach me", "step by step", "navigate to",
      "take me to", "show me how to"],
     "help.guide_workflow", []),

    # -- Greeting (direct response, no tool) --
    # Kept at the END so domain intents always outrank it on ties.  "hi"
    # prefix-matches "history", but the tracking patterns sum to higher
    # scores, so domain utterances still win.
    (["hey", "hello", "hi", "salut", "buna", "bună", "ce faci",
      "good morning", "good afternoon", "good evening", "howdy",
      "servus", "buna ziua", "bună ziua", "neata", "neața"],
     "help.greeting", [],
     {
         "ro": ["salut", "bună ziua", "bună dimineața"],
         "de": ["hallo", "guten tag", "servus"],
         "fr": ["bonjour", "salut"],
         "es": ["hola", "buenos días"],
         "pl": ["cześć", "dzień dobry"],
         "it": ["ciao", "buongiorno"],
         "nl": ["hallo", "goedemorgen"],
         "pt": ["olá", "bom dia"],
         "ru": ["привет", "здравствуйте"],
         "uk": ["привіт", "добрий день"],
         "tr": ["merhaba", "iyi günler"],
         "hu": ["szia", "jó napot"],
         "cs": ["ahoj", "dobrý den"],
         "sk": ["ahoj", "dobrý deň"],
         "sl": ["živjo", "dober dan"],
         "sr": ["здраво", "добар дан"],
         "hr": ["bok", "dobar dan"],
         "bs": ["zdravo", "dobar dan"],
         "sv": ["hej", "god morgon"],
         "el": ["γεια", "καλημέρα"],
         "bg": ["здравей", "добър ден"],
     }),
]


async def _extract_intent_scored(
    utterance: str,
    language: Optional[str] = None,
) -> Tuple[Intent, int, int]:
    """Score every intent pattern and return ``(intent, best_score, runner_up_score)``.

    Shared scoring core for :func:`extract_intent` and the deterministic
    pre-pass gate.  Tracks the top two pattern scores so callers can apply a
    confidence margin (best minus runner-up) in addition to an absolute floor.
    The intent construction is byte-for-byte what ``extract_intent`` returned
    historically — this refactor only surfaces the two scores.
    """
    utterance_lower = utterance.lower()

    best_match: Optional[tuple] = None
    best_score = 0
    runner_up_score = 0

    for pattern in INTENT_PATTERNS:
        keywords = pattern[0]
        intent_name = pattern[1]
        entity_mappings = pattern[2]
        # Optional 4th element: per-language phrase corpus ({lang: [phrases]}).
        # When a language is requested AND this pattern has one, extend the
        # keyword set with that language's phrases (English stays in `keywords`).
        if language is not None and len(pattern) > 3:
            lang_phrases = pattern[3].get(language)
            if lang_phrases:
                keywords = [*keywords, *lang_phrases]
        score = 0
        seen_sigs: set[tuple[str, ...]] = set()
        for kw in keywords:
            sig = tuple(sorted(w for w in kw.split() if w not in _STOPWORDS))
            if not sig or sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            score += _match_score(kw, utterance_lower)
        if score > best_score:
            runner_up_score = best_score
            best_score = score
            best_match = (keywords, intent_name, entity_mappings)
        elif score > runner_up_score:
            runner_up_score = score

    # Phase 1: require at least 2 total match points to avoid
    # false-positive matches from single common words (e.g. "is", "in").
    MIN_MATCH_THRESHOLD = 2
    if best_match and best_score >= MIN_MATCH_THRESHOLD:
        _, intent_name, entity_mappings = best_match
        entities: List[Entity] = []
        missing: List[str] = []

        for entity_type, _ in entity_mappings:
            # Try to extract numbers/IDs from the utterance
            import re
            # Extract vehicle IDs, driver IDs, client IDs, etc.
            numbers = re.findall(r'\b(\d+)\b', utterance)
            if numbers and entity_type in ("vehicle_id", "driver_id", "client_id", "distance_km"):
                entities.append(Entity(
                    type=entity_type,
                    value=int(numbers[0]) if entity_type.endswith("_id") else float(numbers[0]),
                    source="extracted",
                    confidence=0.7,
                ))
            else:
                missing.append(entity_type)

        # For entity-less intents (tracking), all good
        return Intent(
            name=intent_name,
            entities=entities,
            missing_required_entities=missing,
            raw_utterance=utterance,
        ), best_score, runner_up_score

    # No match found
    return Intent(
        name="unknown",
        entities=[],
        missing_required_entities=["intent"],
        raw_utterance=utterance,
    ), best_score, runner_up_score


async def extract_intent(utterance: str, language: Optional[str] = None) -> Intent:
    """Extract intent from user utterance using keyword matching (Phase 1).

    ``language`` (ISO code from ``SUPPORTED_LANGUAGES``) scopes multilingual
    matching (§23.4 Tier-B):
      * ``language=None`` (default) → score ONLY the base English keyword
        hints — byte-for-byte the historical behavior, so every existing
        caller keeps working unchanged.
      * ``language=<lang>`` → score the base English hints PLUS that
        language's phrase corpus (the optional 4th tuple element), so
        non-English utterances resolve to real intents instead of "unknown".

    Phase 2+ will use LLMProvider for NLP-based extraction.
    """
    intent, _, _ = await _extract_intent_scored(utterance, language)
    return intent


async def _is_autonomous_approved(
    plan: ExecutionPlan,
    global_ctx: GlobalContext,
    services: Optional[Dict[str, Any]],
) -> bool:
    """Decide whether a plan may execute without confirmation (§21 Ph.4).

    All three gates must pass:
      1. The per-company circuit breaker is healthy (§23.1) — a tripped
         breaker forces manual confirmation regardless of approvals.
      2. The caller's subscription tier enables the ``autonomous`` feature
         (see ``TIER_FEATURES`` in tier_gate.py).
      3. The company has an enabled pre-approval row for the plan's
         workflow (``intent.name``).

    Returns False (never raises) when the DB is unavailable or the approval
    check itself fails, so a broken lookup degrades to the existing
    confirmation flow rather than executing unchecked.
    """
    try:
        from backend.copilot.circuit_breaker import get_circuit_breaker
        if not get_circuit_breaker().is_allowed(global_ctx.company_id):
            return False

        from backend.copilot.tier_gate import has_feature
        if not has_feature(global_ctx.subscription_tier, "autonomous"):
            return False

        db = (services or {}).get("db")
        if db is None:
            return False

        from repositories.copilot_repository import CopilotAutonomyApprovalRepository
        return CopilotAutonomyApprovalRepository(db).is_approved(
            global_ctx.company_id, plan.intent.name,
        )
    except Exception as exc:
        logger.debug("Autonomy approval check failed open → confirmation flow: %s", exc)
        return False


async def process_utterance(
    utterance: str,
    global_ctx: GlobalContext,
    conversation_id: str,
    session_ctx: Optional[SessionContext] = None,
    services: Optional[Dict[str, Any]] = None,
    permitted_tools: Optional[List[str]] = None,
    conversation_history: Optional[List[dict]] = None,
    on_step_update: Optional[Any] = None,
    ui_context: Optional[UIContext] = None,
    help_only: bool = False,
) -> CoPilotResponse:
    """Process a user utterance through the full Co-Pilot pipeline.

    Pipeline: Understand → Build ReasoningGraph → Resolve → Compile ExecutionPlan
              → Execute (Level 0 only) → Summarize

    ``permitted_tools`` is the server-side RBAC-resolved set of tool names the
    caller may use (see ``backend/copilot/context.py:resolve_available_tools``).
    When provided, any intent whose tool is outside this set is rejected with a
    clear denial BEFORE a plan is compiled — the tool is never executed.

    ``conversation_history`` carries prior turns (``[{role, content}]``) from
    the conversation memory store; the free-form LLM chat branch feeds them to
    the model so the assistant can follow a multi-turn conversation (§11).

    ``on_step_update`` (if provided) is forwarded to the executor and invoked
    as ``on_step_update(step_id, status, tool_name)`` after each step status
    change — the API layer uses it to push WebSocket timeline updates (§12.1).

    ``ui_context`` carries the desktop client's current screen/selection
    (§8, §30).  When a required entity is missing it is resolved from the
    client's selected entity BEFORE a clarification question is asked (§11
    resolution order).

    ``help_only`` (§16, §33.4, §34.10) marks a Help-Mode-only tier (Pro):
    the pipeline answers ONLY Help Mode requests (help.answer_question /
    help.guide_workflow via the LLM-first help loop or the keyword path) and
    declines every known non-help intent with a friendly tier message.
    """
    # ── Graceful degradation (§23.5) — LLM provider calls should use
    # executor.execute_with_fallback() with a sensible timeout and a
    # fallback CoPilotResponse asking the user to try again or use
    # the normal UI. This is wired here as infrastructure; Phase 6+
    # will use it when LLM-based intent extraction is enabled.

    # Normalise the permitted set once — callers may pass a list or a set.
    permitted_set: Optional[set] = set(permitted_tools) if permitted_tools is not None else None

    # ── 0. Ensure all tool modules are loaded ───────────────────────────
    _ensure_tools_loaded()

    try:
        # ── 0b. Ensure LLM providers are loaded ────────────────────────────
        _ensure_llm_providers_loaded()

        # ── 0c. Blank input stays fully offline (§23.5) ────────────────────
        if not utterance.strip():
            HandoffTracker.record_failed_clarification(conversation_id)
            return CoPilotResponse(
                conversation_id=conversation_id,
                clarification_question_key="copilot.clarification.unknown_intent",
                clarification_params={"utterance": utterance[:200]},
            )

        # ── 0d. Help-only tier pre-check (§16, §33.4, §34.10) ───────────────
        # Pro-tier callers reach /chat through Help Mode only.  Deterministically
        # decline every KNOWN non-help intent with a friendly tier message;
        # help intents and unknown free-form questions continue to the
        # LLM-first help loop / keyword fallback below.
        if help_only:
            pre_intent = await extract_intent(utterance, global_ctx.language)
            if pre_intent.name not in (
                "help.answer_question", "help.guide_workflow",
                "help.greeting", "unknown",
            ):
                return CoPilotResponse(
                    conversation_id=conversation_id,
                    clarification_question_key="copilot.error.help_only_tier",
                    clarification_params={"intent": pre_intent.name},
                )

        # ── 0e. Deterministic pre-pass (deterministic-first routing) ────────
        # A high-confidence KNOWN intent (strong score + clear margin, not
        # help.*, not unknown) executes the deterministic keyword path BEFORE
        # the LLM — the LLM then only ever handles unknown/free-form/help
        # questions, so it cannot hallucinate fleet data it never computes.
        # When the gate fails, the utterance falls through to the LLM-first
        # tool loop unchanged (help.* stays conversational; unknown intents
        # need the LLM's breadth).
        if not help_only:
            pre_intent, best_score, runner_up = await _extract_intent_scored(
                utterance, global_ctx.language,
            )
            if (
                pre_intent.name != "unknown"
                and not pre_intent.name.startswith("help.")
                and best_score >= DETERMINISTIC_MIN_SCORE
                and best_score - runner_up >= DETERMINISTIC_MIN_MARGIN
            ):
                logger.info(
                    "Deterministic pre-pass: intent=%s score=%d margin=%d",
                    pre_intent.name, best_score, best_score - runner_up,
                )
                # ── Optional-entity resolution ─────────────────────────────
                # A missing entity whose tool parameter is OPTIONAL (has a
                # default) is not a "missing required entity": the LLM-first
                # path calls such tools with empty args anyway, and the
                # deterministic path now does the same.  Without this,
                # "ce camioane am in flota?" would ask for a clarification
                # instead of returning the fleet list.  Only drop an entity
                # when its type confidently matches an optional schema field
                # by name (case-insensitive); anything else keeps the
                # clarification.  pre_intent is a fresh local returned by
                # _extract_intent_scored, so the offline fallback path (which
                # calls extract_intent separately) is never affected.
                tool = get_tool(pre_intent.name)
                if tool is not None:
                    try:
                        schema = tool.parameters_schema.model_json_schema()
                    except Exception:
                        schema = {}
                    optional_params = {
                        p for p in schema.get("properties", {})
                        if p not in schema.get("required", [])
                    }
                    if optional_params:
                        still_missing: List[str] = []
                        for entity_type in pre_intent.missing_required_entities:
                            match = next(
                                (p for p in optional_params if p.lower() == entity_type.lower()),
                                None,
                            )
                            if match is not None:
                                default_value = schema["properties"].get(match, {}).get("default", "")
                                pre_intent.entities.append(Entity(
                                    type=entity_type,
                                    value=default_value,
                                    source="extracted",
                                    confidence=1.0,
                                ))
                                logger.debug(
                                    "Deterministic pre-pass: dropped optional entity %s for %s",
                                    entity_type, pre_intent.name,
                                )
                            else:
                                still_missing.append(entity_type)
                        pre_intent.missing_required_entities = still_missing
                return await _run_deterministic(
                    utterance, global_ctx, conversation_id, services, permitted_set,
                    conversation_history, on_step_update, ui_context, session_ctx,
                    help_only, pre_intent, llm_attempted=False,
                )

        # ── 1. LLM-first (§23.2, §23.4): every utterance goes to the LLM with
        # the RBAC-filtered tool catalog when a provider is usable.  The LLM
        # answers conversationally, calls tools (executed deterministically
        # through the executor — RBAC/audit/confirmation intact), or requests a
        # Level 2+ action that becomes a pending plan awaiting confirmation.
        from backend.copilot.llm.chat import chat_with_tools

        llm_result = await chat_with_tools(
            utterance, global_ctx, services,
            history=conversation_history,
            permitted_tools=permitted_set,
            conversation_id=conversation_id,
            on_step_update=on_step_update,
            ui_context=ui_context,
            session_ctx=session_ctx,
            help_only=help_only,
        )
        llm_attempted = llm_result.attempted

        if llm_result.final_answer is not None:
            graph = llm_result.reasoning_graph or {}
            _persist_reasoning_graph(services, conversation_id, graph)
            return CoPilotResponse(
                conversation_id=conversation_id,
                reasoning_graph=graph,
                summary_key="copilot.summary.llm_chat",
                summary_params={"answer": llm_result.final_answer},
            )

        if llm_result.pending_plan is not None:
            plan = llm_result.pending_plan
            graph = llm_result.reasoning_graph or {}
            _persist_reasoning_graph(services, conversation_id, graph)
            return CoPilotResponse(
                conversation_id=conversation_id,
                reasoning_graph=graph,
                plan=plan,
                timeline=plan.steps,
            )

        # ── 1b. Partial-execution guard (Gate 2 correction 5) ───────────────
        # The LLM executed ≥1 tool and the provider then failed mid-turn.  Do
        # NOT fall through to the keyword path: re-running the utterance could
        # re-execute INFORMATIONAL (Level 1) tools → duplicate side effects.
        # Surface the executed outcomes + a graceful note instead.
        if llm_result.tool_calls_executed > 0:
            graph = llm_result.reasoning_graph or {}
            _persist_reasoning_graph(services, conversation_id, graph)
            return CoPilotResponse(
                conversation_id=conversation_id,
                reasoning_graph=graph,
                clarification_question_key="copilot.error.model_unreachable",
                clarification_params={"utterance": utterance[:200]},
                timeline=list(llm_result.executed_steps),
            )

        # ── 2. Offline fallback (§23.5): keyword intent extraction. ────────
        # Reached when no provider is usable OR the provider was attempted and
        # failed.  The keyword matcher (INTENT_PATTERNS, language-scoped) is
        # the deterministic offline contract; the CI gate still hashes it.
        intent = await extract_intent(utterance, global_ctx.language)
        return await _run_deterministic(
            utterance, global_ctx, conversation_id, services, permitted_set,
            conversation_history, on_step_update, ui_context, session_ctx,
            help_only, intent, llm_attempted,
        )
    except Exception as exc:
        logger.exception("process_utterance failed: %s", exc)
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key="copilot.error.internal",
            clarification_params={"error": str(exc)},
        )


async def _run_deterministic(
    utterance: str,
    global_ctx: GlobalContext,
    conversation_id: str,
    services: Optional[Dict[str, Any]],
    permitted_set: Optional[set],
    conversation_history: Optional[List[dict]],
    on_step_update: Optional[Any],
    ui_context: Optional[UIContext],
    session_ctx: Optional[SessionContext],
    help_only: bool,
    intent: Intent,
    llm_attempted: bool,
) -> CoPilotResponse:
    """Execute the deterministic keyword path for an already-extracted intent.

    Shared body for the offline fallback (§23.5) and the deterministic pre-pass
    (deterministic-first routing): UI-context entity resolution, the unknown /
    greeting branches, RBAC, confidence, de-escalation, reasoning-graph build /
    resolve / persist, plan compilation, autonomous-mode confirmation gating,
    execution, and final summary response — byte-for-byte the historical
    offline body.  ``llm_attempted`` only selects the unknown-intent ladder key
    (a provider attempt that failed → ``model_unreachable``; never attempted →
    ``unknown_intent``); the deterministic pre-pass passes False because it
    excludes unknown intents.
    """
    # ── 2a. UI-context entity resolution (§11) ─────────────────────────
    # Prefer the entity the client has selected on screen over asking a
    # clarification question for a missing required entity.
    if ui_context is not None:
        _apply_ui_context(intent, ui_context)

    # Detect unknown intents.  Degradation ladder (Gate 1 correction 7):
    # a provider was attempted but failed → copilot.error.model_unreachable;
    # nothing usable configured → unknown_intent (offline fallback).
    if intent.name == "unknown":
        HandoffTracker.record_failed_clarification(conversation_id)
        key = ("copilot.error.model_unreachable" if llm_attempted
               else "copilot.clarification.unknown_intent")
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key=key,
            clarification_params={"utterance": utterance[:200]},
        )

    # Direct-response branch for greetings — no tool execution and no
    # RBAC gate applies (a greeting touches no data, so routing it
    # through a tool could hit a permission denial for no reason).
    if intent.name == "help.greeting":
        return CoPilotResponse(
            conversation_id=conversation_id,
            summary_key="copilot.summary.help.greeting",
            summary_params={},
        )

    # Check if the tool exists in the registry (not deprecated, available)
    tool = get_tool(intent.name)
    if tool is None or tool.deprecated:
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key="copilot.clarification.tool_unavailable",
            clarification_params={"intent": intent.name},
        )

    # ── 1b. RBAC permission gate (§15) ─────────────────────────────────
    # ``get_tool`` is a registry lookup, NOT an authorization check.  The
    # permitted set was resolved server-side from the caller's JWT role
    # before this request entered the pipeline (copilot_router →
    # resolve_available_tools).  An intent whose tool is missing from that
    # set must never be compiled or executed.
    if permitted_set is not None and intent.name not in permitted_set:
        logger.warning(
            "RBAC denied tool '%s' for role '%s' user=%s company=%s",
            intent.name, global_ctx.role, global_ctx.user_id, global_ctx.company_id,
        )
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key=PERMISSION_DENIED_KEY,
            clarification_params={
                "intent": intent.name,
                "role": global_ctx.role,
            },
        )

    # ── 2. Confidence check ─────────────────────────────────────────────
    confidence = compute_confidence(intent, intent_match_score=0.8)
    _record_confidence_metric(confidence)
    from backend.copilot.confidence import needs_clarification, needs_recap

    if needs_clarification(confidence):
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key="copilot.clarification.low_confidence",
            clarification_params={"utterance": utterance[:200]},
        )

    # ── 2b. De-escalation check (§23.7) ────────────────────────────────
    handoff = HandoffTracker.get(conversation_id)
    if handoff and should_handoff(handoff, intent.name):
        logger.info("Handing off conversation %s to manual UI (de-escalation triggered)", conversation_id)
        return CoPilotResponse(
            conversation_id=conversation_id,
            clarification_question_key="copilot.handoff.message",
            clarification_params={
                "intent": intent.name,
                "reason": handoff.reason,
            },
        )

    # ── 3. Build Reasoning Graph ────────────────────────────────────────
    from backend.copilot.telemetry import PhaseTimer
    with PhaseTimer("REASONING", conversation_id=conversation_id):
        graph = await build_reasoning_graph(conversation_id, intent)

        # ── 4. Resolve graph ─────────────────────────────────────────────
        graph = await resolve_reasoning_graph(
            graph,
            company_id=global_ctx.company_id,
            user_id=global_ctx.user_id,
            role=global_ctx.role,
            session_context=session_ctx,
            services=services,
        )

        # ── 4b. Persist the reasoning graph (§5.5) ──────────────────
        # Best-effort upsert so conversation history can replay the graph for
        # a conversation. Only possible when a request-scoped DB is available.
        if services is not None and services.get("db") is not None:
            try:
                import json

                from repositories.copilot_repository import CopilotReasoningGraphRepository

                CopilotReasoningGraphRepository(services["db"]).upsert(
                    conversation_id,
                    json.dumps(graph.model_dump(mode="json")),
                )
            except Exception:
                logger.debug("Reasoning graph persistence skipped", exc_info=True)

    # ── 5. Check if all requirements are resolved ───────────────────────
    unresolved = [
        node for node in graph.nodes.values()
        if node.status == "unresolved"
    ]
    if unresolved:
        missing_names = [node.label for node in unresolved]
        return CoPilotResponse(
            conversation_id=conversation_id,
            reasoning_graph=graph.model_dump(mode="json"),
            clarification_question_key="copilot.clarification.missing_entities",
            clarification_params={
                "intent": intent.name,
                "missing": missing_names,
                "example": _build_clarification_example(intent),
            },
        )

    # ── 6. Compile ExecutionPlan (Level 0 only) ─────────────────────────
    plan = await compile_execution_plan(
        conversation_id=conversation_id,
        reasoning_graph_id=graph.graph_id,
        intent=intent,
        global_ctx=global_ctx,
        session_ctx=session_ctx,
        services=services,
        permitted_tools=permitted_set,
    )

    if plan is None:
        return CoPilotResponse(
            conversation_id=conversation_id,
            reasoning_graph=graph.model_dump(mode="json"),
            clarification_question_key="copilot.clarification.cannot_compile",
        )

    # ── 6b. §23.3 guardrail fidelity ──────────────────────────────────
    # Stamp the REAL resolved-graph node count on the plan so the executor's
    # validate_guardrails enforces the node ceiling from facts (the actual
    # graph after resolve_reasoning_graph) instead of a step-count estimate.
    plan.reasoning_graph_nodes = len(graph.nodes)

    # ── 7. Check if any step needs confirmation ─────────────────────────
    needs_confirmation = any(s.confirmation_level >= ConfirmationLevel.BUSINESS for s in plan.steps)

    # ── 7a. Autonomous mode (§21 Ph.4 item 4, §23.1) ───────────────────
    # A workflow pre-approved for the company + the tier's "autonomous"
    # feature + a healthy circuit breaker skips the confirmation gate.
    # A tripped breaker forces manual confirmation regardless of approvals
    # (handled inside _is_autonomous_approved).
    autonomous = await _is_autonomous_approved(plan, global_ctx, services)

    if needs_confirmation and not autonomous:
        logger.info("Plan %s requires user confirmation (%d steps)", plan.plan_id, len(plan.steps))
    else:
        # ── 7. Execute ─────────────────────────────────────────
        if autonomous and needs_confirmation:
            # Executed now — must not be stored as an awaiting-confirmation
            # plan by the router afterwards.
            plan.requires_confirmation = False
            logger.info(
                "Autonomous mode: workflow %s pre-approved — executing without confirmation "
                "(company=%d user=%d)",
                plan.intent.name, global_ctx.company_id, global_ctx.user_id,
            )
        from backend.copilot.telemetry import PhaseTimer
        with PhaseTimer("EXECUTING", conversation_id=conversation_id):
            from backend.copilot.executor import execute_plan as do_execute
            plan = await do_execute(
                plan,
                services=services,
                on_step_update=on_step_update,
            )

    # ── 8. Build response ───────────────────────────────────────────────
    summary_parts = []
    for step in plan.steps:
        if step.status == "succeeded" and step.result:
            summary_parts.append(step.result.get("message_key", ""))
        elif step.status == "failed":
            summary_parts.append(step.error or "Failed")

    summary_key = f"copilot.summary.{intent.name}"
    summary_params = {
        "intent": intent.name,
        "steps_total": len(plan.steps),
        "steps_succeeded": sum(1 for s in plan.steps if s.status == "succeeded"),
    }

    for step in plan.steps:
        if step.status == "succeeded" and step.result:
            result_data = step.result.get("data", {})
            if isinstance(result_data, dict):
                for k, v in result_data.items():
                    if isinstance(v, (str, int, float, bool)):
                        summary_params[k] = v

    return CoPilotResponse(
        conversation_id=conversation_id,
        reasoning_graph=graph.model_dump(mode="json"),
        plan=plan,
        timeline=plan.steps,
        summary_key=summary_key,
        summary_params=summary_params,
    )


async def compile_execution_plan(
    conversation_id: str,
    reasoning_graph_id: str,
    intent: Intent,
    global_ctx: GlobalContext,
    session_ctx: Optional[SessionContext] = None,
    services: Optional[Dict[str, Any]] = None,
    permitted_tools: Optional[set] = None,
) -> Optional[ExecutionPlan]:
    """Compile an ExecutionPlan from a resolved ReasoningGraph and Intent.

    Phase 1: Creates a single-step ExecutionPlan for the resolved intent.
    Each entity becomes a parameter in the tool call.

    Defense-in-depth RBAC: when ``permitted_tools`` is provided and
    ``intent.name`` is not in it, NO step is created and ``None`` is
    returned (the caller surfaces a denial).  The authoritative check also
    runs earlier in :func:`process_utterance`; this guards any direct callers.
    """
    tool = get_tool(intent.name)
    if tool is None:
        return None

    if permitted_tools is not None and intent.name not in permitted_tools:
        logger.warning(
            "compile_execution_plan: RBAC denied tool '%s' for role '%s'",
            intent.name, global_ctx.role,
        )
        return None

    # Build parameters from entities
    params = {}
    for entity in intent.entities:
        params[entity.type] = entity.value

    # Seed free-text params (e.g. ``question`` on help.answer_question) from
    # the raw utterance.  Entity-less text intents otherwise reach execution
    # with an empty ``parameters`` dict and fail pydantic validation, dumping
    # a raw validation error into the UI instead of answering.
    model_fields = getattr(tool.parameters_schema, "model_fields", {})
    if "question" in model_fields and "question" not in params:
        params["question"] = intent.raw_utterance

    # For Phase 1: single-step plan
    step = ExecutionStep(
        step_id=f"{intent.name}-0",
        tool_name=intent.name,
        tool_version=tool.tool_version,
        parameters=params,
        depends_on=[],
        confirmation_level=tool.confirmation_level,
        status="pending",
    )

    plan = ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        reasoning_graph_id=reasoning_graph_id,
        intent=intent,
        steps=[step],
        overall_confidence=compute_confidence(intent, intent_match_score=0.8),
        requires_confirmation=(tool.confirmation_level >= ConfirmationLevel.BUSINESS),
    )

    _record_confidence_metric(plan.overall_confidence)

    return plan


def _persist_reasoning_graph(
    services: Optional[Dict[str, Any]],
    conversation_id: str,
    graph: dict,
) -> None:
    """Best-effort persistence of a serialized reasoning graph (§5.5).

    Same contract as the keyword path's inline persistence block — only when
    a request-scoped DB is available, and a failure never breaks the turn.
    """
    if services is None or services.get("db") is None:
        return
    try:
        import json

        from repositories.copilot_repository import CopilotReasoningGraphRepository

        CopilotReasoningGraphRepository(services["db"]).upsert(
            conversation_id,
            json.dumps(graph),
        )
    except Exception:
        logger.debug("Reasoning graph persistence skipped", exc_info=True)


def _build_clarification_example(intent: Intent) -> str:
    """Build a human-readable example of what's needed."""
    entity_map = {
        "distance_km": "1500",
        "vehicle_id": "42",
        "driver_id": "7",
        "client_id": "12",
        "km": "1500",
        "query": "ACME Corp",
        "domain": "financial",
        "code": "USD",
        "stops": "Berlin, Warsaw, Kyiv",
    }
    examples = ", ".join(
        f"{m}={entity_map.get(m, '?')}" for m in intent.missing_required_entities
    )
    return f"{intent.name}({examples})" if examples else intent.name
