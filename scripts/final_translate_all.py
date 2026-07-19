#!/usr/bin/env python3
"""Final batch translation for remaining untranslated keys in de, es, fr."""
import json, os, re

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def flatten(d, prefix=""):
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                subkey = f"{key}[{i}]"
                if isinstance(item, str):
                    items[subkey] = item
                elif isinstance(item, (dict, list)):
                    items.update(flatten(item, subkey))
        else:
            items[key] = v
    return items

def set_nested(d, key_parts, value):
    cur = d
    for p in key_parts[:-1]:
        if "[" in p:
            name = p[:p.index("[")]
            idx = int(p[p.index("[")+1:p.index("]")])
            cur = cur[name][idx]
        else:
            cur = cur.setdefault(p, {})
    last = key_parts[-1]
    if "[" in last:
        name = last[:last.index("[")]
        idx = int(last[last.index("[")+1:last.index("]")])
        cur[name][idx] = value
    else:
        cur[last] = value

en = load_json(os.path.join(TRANS_DIR, "en.json"))
en_flat = flatten(en)

PRESERVE = {"ID","KM","VIN","EUR","N/A","CSV","PDF","OCR","GPS","API","CMR","KPI",
            "SMTP","DSO","SLA","SOC","GDPR","CUI","VAT","ETA","SMS","GBP","USD",
            "RON","JSON","BOM","UTF-8","DDD","TGD","POD","AI","COD"}

def should_translate(val):
    if not isinstance(val, str) or not val: return False
    if val.strip() in PRESERVE: return False
    if re.match(r"^\{.*\}$", val.strip()): return False
    return True

# =====================================================================
# GERMAN supplementary translations (key -> value)
# =====================================================================
DE_MAP = {
    "app.subtitle": "ERP",
    "team.invite_subtitle": "Neues Teammitglied einladen",
    "team.members_subtitle": "Vorhandene Benutzer verwalten",
    "team.email_label": "E-MAIL",
    "team.password_label": "PASSWORT",
    "team.role_label": "ROLLE",
    "team.link_driver_label": "FAHRER VERKNÜPFEN",
    "team.col_actions": "Aktionen",
    "team.deactivate": "Deaktivieren",
    "team.validation_email_required": "E-Mail ist erforderlich.",
    "team.validation_password_required": "Passwort ist erforderlich.",
    "team.success_user_added": "Benutzer erfolgreich hinzugefügt.",
    "team.error_failed_add": "Fehler beim Hinzufügen des Benutzers: {}",
    "team.error_failed_deactivate": "Fehler beim Deaktivieren des Benutzers: {}",
    "team.deactivate_title": "Benutzer deaktivieren",
    "team.validation_title": "Validierung",
    "team.email_required": "E-Mail ist erforderlich.",
    "team.password_required": "Passwort ist erforderlich.",
    "team.deactivate_user": "Benutzer deaktivieren",
    "team.deactivate_button": "Deaktivieren",
    "team.no_api_client": "Kein API-Client oder Datenbank verfügbar.",
    "team.success_title": "Erfolg",
    "team.user_added": "Benutzer erfolgreich hinzugefügt.",
    "team.add_user_failed": "Fehler beim Hinzufügen des Benutzers: {error}",
    "team.deactivate_failed": "Fehler beim Deaktivieren des Benutzers: {error}",
    "main.vat_checkbox": "MwSt. hinzufügen",
    "main.offer_price_pre_vat": "Preis (vor MwSt.):",
    "main.offer_price_post_vat": "Preis (nach MwSt.):",
    "main.results_header": "BERECHNUNGSERGEBNIS",
    "main.empty_calc_title": "Formular ausfüllen, um Gewinn zu berechnen",
    "main.empty_calc_subtitle": "Fahrtdaten eingeben und Berechnen drücken.",
    "main.result_revenue": "Bruttoumsatz",
    "main.result_cost": "Gesamtkosten",
    "main.result_profit": "Nettogewinn",
    "main.result_rate": "Satz / km",
    "main.result_margin": "Marge",
    "main.module_not_migrated": "{module}\n(Modul noch nicht migriert)",
    "main.vat_percent_placeholder": "MwSt. %",
    "fleet.select_truck_first": "Wählen Sie zuerst einen LKW aus.",
    "fleet.status_active": "Aktiv",
    "fleet.no_engine": "Keine Motordaten",
    "fleet.maint_kpi_alerts": "Offene Warnungen",
    "fleet.maint_kpi_cost_month": "Kosten/Monat",
    "fleet.maint_history_desc": "Wartungsverlauf",
    "fleet.open_maintenance_manager": "Wartung öffnen",
    "fleet.truck_title": "LKW {}",
    "fleet.form_tracking_device_id": "Tracking-Geräte-ID",
    "fleet.table_vin": "VIN",
    "history.button_load_more": "Mehr laden",
    "history.button_documents": "Dokumente",
    "history.col_km": "Strecke (km)",
    "history.email_done": "E-Mail gesendet",
    "history.email_done_msg": "Fahrt erfolgreich per E-Mail gesendet",
    "history.invoice_done_msg": "Rechnung erfolgreich generiert",
    "history.search_placeholder": "Fahrten suchen...",
    "history.button_export_pdf": "PDF exportieren",
    "history.button_export_excel": "Excel exportieren",
    "history.button_email_invoice": "Rechnung per E-Mail",
    "history.subtitle": "Betriebs- und Rechnungsverwaltung",
    "history.trip_title": "Fahrt #{}",
    "analytics.empty_subtitle": "",
    "analytics.client_insight": "Einblick: {client} erzielt {rev_pct}% des Umsatzes, aber nur {profit_pct}% des Gewinns.",
    "analytics.kpi_expiring": "Ablaufend",
    "analytics.months": "Monate",
    "analytics.doc_other": "Sonstige",
    "analytics.trucks": "LKWs",
    "analytics.active": "Aktiv",
    "analytics.extra": "Sonstige",
    "analytics.insufficient_route_data": "Unzureichende Daten für das Diagramm — fügen Sie weitere Fahrten hinzu",
    "analytics.no_data": "Noch keine Umsatzdaten",
    "analytics.doc_expires": "Läuft ab",
    "analytics.kpi_kpi_avg_trips": "Durchschn. Fahrten",
    "analytics.kpi_top_driver": "Top-Fahrer",
    "analytics.kpi_total_drivers": "Fahrer gesamt",
    "analytics.kpi_total_violations": "Verstöße gesamt",
    "analytics.section_driver_metrics": "Fahrerkennzahlen",
    "analytics.section_driver_performance": "Fahrerleistung",
    "analytics.section_volume_safety": "Volumen & Sicherheit",
    "analytics.cost_breakdown": "Kostenaufschlüsselung",
    "analytics.fuel_cost_trend": "Kraftstoffkostentrend",
    "analytics.fuel_efficiency_trend": "Kraftstoffeffizienztrend",
    "analytics.idle_vs_active": "Leerlauf vs. Aktiv",
    "analytics.kpi_revenue_concentration": "Konzentration",
    "analytics.section_route_performance": "Routenleistung",
    "analytics.waterfall_other": "Sonstige",
    "analytics.waterfall_net": "Netto",
    "analytics.group_total": "Gesamt",
    "analytics.group_top3": "Top 3",
    "analytics.group_others": "Andere",
    "analytics.group_clients": "Kunden",
    "analytics.daily_activity": "Tägliche Aktivität",
    "analytics.cost_per_truck": "Kosten pro LKW",
    "analytics.driver_driving_hours": "Fahrerstunden",
    "analytics.driver_ranking": "Fahrerranking",
    "analytics.driver_rest_hours": "Fahrerruhezeiten",
    "analytics.extra_costs": "Zusatzkosten",
    "analytics.invoiced": "Abgerechnet",
    "analytics.invoiced_vs_paid": "Abgerechnet vs. Bezahlt",
    "analytics.maintenance_cost": "Wartungskosten",
    "analytics.mileage_ranking": "Kilometerranking",
    "analytics.profit_vs_distance": "Gewinn vs. Strecke",
    "analytics.quarterly_revenue": "Quartalsumsatz",
    "analytics.revenue_per_client_trend": "Umsatz pro Kunde (Trend)",
    "analytics.revenue_vs_profit_scatter": "Umsatz vs. Gewinn (Streudiagramm)",
    "analytics.toll": "Maut",
    "analytics.total_distance": "Gesamtstrecke",
    "analytics.truck_age_distribution": "LKW-Altersverteilung",
    "analytics.aging_31_60": "31-60 Tage",
    "analytics.aging_61_90": "61-90 Tage",
    "analytics.aging_current": "Aktuell (0-30 Tage)",
    "analytics.aging_overdue": "90+ Tage",
    "analytics.all_countries": "Alle Länder",
    "analytics.col_profit_km": "Gewinn/KM",
    "analytics.doc_actual_uploads": "Tatsächliche Uploads",
    "analytics.doc_expected_uploads": "Erwartet (Fahrten)",
    "analytics.doc_see_all": "Alle anzeigen ({count})",
    "analytics.doc_upload_vs_expected": "Dokumentenuploads vs. Erwartet",
    "analytics.driver_unassigned_note": "{count} Fahrten ohne zugewiesenen Fahrer (ausgeschlossen)",
    "analytics.kpi_active_drivers": "Aktive Fahrer",
    "analytics.kpi_avg_profit_per_driver": "Durchschn. Gewinn/Fahrer",
    "analytics.kpi_avg_route_profit": "Durchschn. Gewinn/Route",
    "analytics.kpi_avg_trips_per_driver": "Durchschn. Fahrten/Fahrer",
    "analytics.kpi_cost_per_km": "Durchschn. Kosten/km",
    "analytics.kpi_dso_subtitle": "Durchschn. Zahlungseingangsfrist",
    "analytics.kpi_dso": "DSO (Tage)",
    "analytics.kpi_most_frequent": "Am häufigsten",
    "analytics.kpi_new_clients": "Neue Kunden",
    "analytics.kpi_top_client_rev": "Top-Kunde",
    "analytics.kpi_top_country_route": "Top-Land",
    "analytics.kpi_unassigned_trips": "Nicht zugewiesene Fahrten",
    "analytics.kpi_unique_routes": "Eindeutige Routen",
    "analytics.no_driver_data": "Keine Fahrerdaten für diesen Zeitraum.",
    "analytics.outstanding": "Ausstehend",
    "analytics.payment_target": "Ziel 30 Tage",
    "analytics.refresh_tooltip": "Daten aktualisieren",
    "analytics.revenue_profit_trend": "Umsatz vs. Gewinntrend",
    "analytics.route_country_treemap": "Umsatz nach Land",
    "analytics.route_frequency": "Routenhäufigkeit",
    "analytics.section_driver_activity": "Fahreraktivitätszeitachse",
    "analytics.section_invoice_aging": "Rechnungsalterung",
    "analytics.section_payment_timeline": "Zahlungsverhalten",
    "analytics.section_revenue_trend": "Umsatz- & Gewinntrend",
}

# =====================================================================
# SPANISH supplementary translations (key -> value)
# =====================================================================
ES_MAP = {
    "app.subtitle": "ERP",
    "team.col_actions": "Acciones",
    "team.validation_title": "Validación",
    "team.deactivate": "Desactivar",
    "team.deactivate_title": "Desactivar Usuario",
    "team.deactivate_button": "Desactivar",
}

# =====================================================================
# FRENCH supplementary translations (key -> value)
# =====================================================================
FR_MAP = {
    "about.value_innovation_title": "Innovation",
    "admin.config_flags": "Configuration",
    "admin.diagnostics": "Diagnostics",
    "admin.email": "Email",
    "alerts.severity_info": "Info",
    "analytics.col_km": "KM",
    "analytics.distance_km": "Distance (km)",
    "analytics.distance_label": "Distance (km)",
    "analytics.group_clients": "Clients",
    "analytics.group_top3": "Top 3",
    "analytics.group_total": "Total",
    "analytics.kpi_revenue_concentration": "Concentration",
    "analytics.tab_client": "Clients",
    "analytics.tab_document": "Documents",
    "analytics.waterfall_net": "Net",
    "auth.email_label": "Email",
    "auth.login_brand": "Operion",
    "auth.register_brand": "Operion",
    "automation.label_document": "Doc #{}",
    "automation.mode_simple": "Simple",
    "client.field_email": "Email",
    "client.field_notes": "Notes",
    "client.section_contacts": "Contacts",
    "client.table_email": "Email",
    "client.title": "Clients",
    "cmr.date": "Date",
    "cmr.destination": "Destination",
    "common.currency_eur": "EUR",
    "common.id": "ID",
    "dispatch_board.detail_client": "Client",
    "dispatch_board.detail_distance": "Distance",
    "dispatch_board.detail_eta": "ETA",
    "dispatch_board.detail_notes": "Notes",
    "dispatch_board.export_csv": "CSV",
    "dispatch_board.export_pdf": "PDF",
    "dispatch_board.live": "LIVE",
    "dispatch_board.resource_eta": "ETA",
    "docs.cat_proformas": "Proformas",
    "docs.email": "Email",
    "docs.next": ">",
    "docs.ocr_section": "OCR",
    "docs.prev": "<",
    "docs.tab_documents": "Documents",
    "docs.tab_proforma": "Proforma",
    "driver_manager.col_id": "ID",
    "driver_manager.documents_button": "Documents",
    "driver_manager.field_email": "Email",
    "email_logs.col_id": "ID",
    "file_filter.images": "Images",
    "fleet.documents_button": "Documents",
    "fleet.expenses_table_id": "ID",
    "fleet.maintenance_table_id": "ID",
    "fleet.maintenance_table_km": "KM",
    "fleet.table_consumption": "L/100km",
    "fleet.table_id": "ID",
    "fleet.table_km": "KM",
    "fleet.table_vin": "VIN",
    "fleet.unit_km": "km",
    "fleet.alert_format": "[{type}] {msg}",
    "fleet.add_maintenance": "Ajouter un entretien",
    "fleet_dashboard.date": "Date",
    "generators.cmr_actions_title": "Actions",
    "generators.cmr_options_title": "Options",
    "generators.tab_cmr": "CMR",
    "history.button_documents": "Documents",
    "history.button_email": "Email",
    "history.button_excel": "Excel",
    "history.button_pdf": "PDF",
    "history.col_client": "Client",
    "history.col_data": "Date",
    "history.col_id": "ID",
    "history.col_km": "Distance (km)",
    "history.table_id": "ID",
    "history.table_km": "KM",
    "home.testimonial_1_author": "Mihai Popescu",
    "home.testimonial_3_author": "John Smith",
    "home.testimonial_3_role": "CEO, Smith Logistics",
    "invoice_editor.description": "Description",
    "invoice_editor.distance": "Distance",
    "invoice_editor.email": "Email",
    "invoice_editor.logo": "Logo",
    "invoice_editor.net_30": "Net 30",
    "invoice_editor.net_15": "Net 15",
    "invoice_editor.net_60": "Net 60",
    "invoice_editor.notes": "Notes",
    "invoice_editor.notes_section": "Notes",
    "invoice_editor.signature": "Signature",
    "invoice_editor.total": "Total",
    "invoice_pdf.default_cui": "RO12345678",
    "invoice_pdf.default_email": "contact@firma.ro",
    "invoice_pdf.default_phone": "07xx xxx xxx",
    "invoice_pdf.default_reg": "J40/123/2023",
    "invoice_pdf.desc_header": "Description",
    "invoice_pdf.distance": "Distance",
    "invoice_pdf.total_header": "Total (EUR)",
    "main.section_identify": "IDENTIFICATION",
    "maint.col_description": "Description",
    "maint.excellent": "Excellent",
    "maint.form_notes": "Notes",
    "maint.severity_info": "Info",
    "maint.unit_km": " km",
    "maint_analytics.col_count": "Services",
    "maint_analytics.type": "Type",
    "maint_timeline.date": "Date",
    "maint_timeline.description": "Description",
    "maint_timeline.field_date": "Date",
    "maint_timeline.field_notes": "Notes",
    "maint_timeline.field_type": "Type",
    "maint_timeline.km": "KM",
    "maint_timeline.type": "Type",
    "nav.clients": "Clients",
    "nav.group_administration": "Administration",
    "proforma_editor.description": "Description",
    "proforma_editor.email": "Email",
    "proforma_editor.logo": "Logo",
    "proforma_editor.net_30": "Net 30",
    "proforma_editor.net_15": "Net 15",
    "proforma_editor.net_60": "Net 60",
    "proforma_editor.notes": "Notes",
    "proforma_editor.signature": "Signature",
    "proforma_editor.total": "Total",
    "receipt.attach_type_cmr": "CMR",
    "receipt.attach_type_document": "Document",
    "receipt.attach_type_image": "Image",
    "receipt.attach_type_pod": "POD",
    "receipt.notes_label": "Notes",
    "receipt.section_notes": "NOTES",
    "receipt.section_parties": "PARTIES",
    "receipt.signature_label": "Signature",
    "receipt.total_label": "Total",
    "receipt.validation.date_format": "{field} doit être au format AAAA-MM-JJ.",
    "receipt.validation.date_required": "La date d'émission est requise.",
    "receipt.validation.number_required": "Le numéro de reçu est requis.",
    "receipt.validation.recipient_required": "Le destinataire (Reçu de) est requis.",
    "receipt.validation.vat_invalid": "Le taux de TVA doit être entre 0 et 100.",
    "result.minute": "minute",
    "result.minutes": "minutes",
    "route.open_in_gmaps": "Google Maps",
    "route.result.distance": "Distance",
    "route.section.options": "OPTIONS",
    "route.stop_destination": "Destination",
    "route_history.table_destination": "Destination",
    "route_history.table_distance": "Distance",
    "settings.section_email": "EMAIL & SMTP",
    "tacho.hdr_date": "Date",
    "tacho.hdr_type": "Type",
    "tacho.status_ok": "OK",
    "text_danger": "Danger",
    "trip.speed_display": "{speed:.0f} km/h",
    "receipt.editor.draft_name": "Nom du brouillon :",
    "receipt.editor.draft_save_failed": "Échec de l'enregistrement du brouillon.",
    "receipt.editor.draft_saved": "Brouillon enregistré",
    "receipt.editor.draft_saved_msg": "Brouillon \"{name}\" enregistré.",
    "receipt.editor.duplicated": "Reçu dupliqué",
    "receipt.editor.duplicated_msg": "Copie créée avec un nouveau numéro.",
    "receipt.editor.email": "Email",
    "receipt.editor.generate_pdf": "Générer le PDF",
    "receipt.editor.load": "Charger",
    "receipt.editor.load_draft": "Charger le brouillon",
    "receipt.editor.no_attachments": "Aucun fichier joint.",
    "receipt.editor.no_drafts": "Aucun brouillon enregistré.",
    "receipt.editor.pdf_generated": "Reçu généré",
    "receipt.editor.pdf_generated_msg": "PDF enregistré vers : {path}",
    "receipt.editor.print": "Imprimer",
    "receipt.editor.print_no_number": "Pas de numéro de reçu. Générez d'abord.",
    "receipt.editor.print_no_file": "Aucun fichier PDF trouvé. Générez d'abord.",
    "receipt.editor.save_draft": "Enregistrer le brouillon",
    "receipt.editor.select_file": "Sélectionner un fichier",
    "receipt.editor.subtitle": "Créez des reçus professionnels pour les paiements, remboursements et dépenses.",
    "receipt.editor.title": "Générateur de reçus",
    "receipt.editor.validation_error": "Erreur de validation",
    "receipt.editor.browse": "Parcourir",
    "receipt.editor.email_placeholder": "Fonctionnalité email bientôt disponible.",
}

# Apply translations
for code, mapping in [("de", DE_MAP), ("es", ES_MAP), ("fr", FR_MAP)]:
    tgt = load_json(os.path.join(TRANS_DIR, f"{code}.json"))
    tgt_flat = flatten(tgt)
    
    applied = 0
    for flat_key, translation in mapping.items():
        if flat_key in tgt_flat and flat_key in en_flat:
            if isinstance(tgt_flat[flat_key], str) and isinstance(en_flat[flat_key], str) and tgt_flat[flat_key] == en_flat[flat_key]:
                # Apply translation
                parts = flat_key.split(".")
                set_nested(tgt, parts, translation)
                applied += 1
    
    save_json(os.path.join(TRANS_DIR, f"{code}.json"), tgt)
    print(f"{code}: applied {applied} translations")

# Show final stats
print("\n=== FINAL COVERAGE ===")
for code in ["de", "es", "fr"]:
    tgt = load_json(os.path.join(TRANS_DIR, f"{code}.json"))
    tgt_flat = flatten(tgt)
    total = 0; untranslated = 0
    for k, v in en_flat.items():
        if not should_translate(v): continue
        total += 1
        if k in tgt_flat and isinstance(tgt_flat[k], str) and tgt_flat[k] == v:
            untranslated += 1
    pct = round((1 - untranslated/total) * 100, 1) if total else 0
    print(f"  {code}.json: {pct}% ({total-untranslated}/{total}, {untranslated} untranslated)")
