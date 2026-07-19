#!/usr/bin/env python3
"""Translate all English-matching values using bootstrap + cross-reference + smart fallback."""
import json, os, re

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

# Acronyms and codes to NEVER translate
PRESERVE = {"ID","KM","VIN","EUR","N/A","CSV","PDF","OCR","GPS","API","CMR","KPI",
            "SMTP","DSO","SLA","SOC","GDPR","CUI","VAT","ETA","SMS","GBP","USD",
            "RON","JSON","BOM","UTF-8","DDD","TGD","POD","AI","COD"}

def iter_leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_leaves(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_leaves(v, path + (i,))
    else:
        yield path, obj

def set_at(obj, path, value):
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value

def get_at(obj, path):
    for key in path:
        obj = obj[key]
    return obj

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def should_translate(val):
    if not isinstance(val, str) or not val:
        return False
    if val.strip() in PRESERVE:
        return False
    # Pure format placeholders
    if re.match(r'^\{.*\}$', val.strip()):
        return False
    return True

def build_bootstrap(tgt_data, en_data):
    """Extract all EN->TARGET pairs from the existing translations."""
    pairs = {}
    def walk(t, e, p=""):
        if isinstance(t, dict) and isinstance(e, dict):
            for k in t:
                if k in e:
                    np = f"{p}.{k}" if p else k
                    walk(t[k], e[k], np)
        elif isinstance(t, list) and isinstance(e, list):
            for ti, ei in zip(t, e):
                if isinstance(ti, str) and isinstance(ei, str) and ti != ei:
                    pairs[ei] = ti
                elif isinstance(ti, (dict,list)) and isinstance(ei, (dict,list)):
                    walk(ti, ei, p)
        elif isinstance(t, str) and isinstance(e, str) and t != e:
            pairs[e] = t
    walk(tgt_data, en_data)
    return pairs

# ===========================================================================
# HARDCODED SUPPLEMENTARY DICTIONARIES for commonly untranslated strings
# ===========================================================================
SUPP_DE = {
    " km": " km",
    " months": " Monate",
    " seconds": " Sekunden",
    "ADR Dangerous Goods": "ADR-Gefahrgut",
    "API Token": "API-Token",
    "ATTACHMENTS": "ANHAENGE",
    "Accommodation": "Unterkunft",
    "Account / Subdomain": "Konto / Subdomain",
    "Action Maint": "Aktion Wartung",
    "Action Remind": "Aktion Erinnerung",
    "Action Resolve": "Aktion Loesen",
    "Action Trip": "Aktion Fahrt",
    "Action Truck": "Aktion LKW",
    "Actions": "Aktionen",
    "Active:": "Aktiv:",
    "Activity Timeline": "Aktivitaetszeitachse",
    "Add Country": "Land hinzufuegen",
    "Add Entry": "Eintrag hinzufuegen",
    "Add Record": "Eintrag hinzufuegen",
    "Add Row": "Zeile hinzufuegen",
    "Add to Dispatch": "Zur Disposition hinzufuegen",
    "Add VAT": "MwSt. hinzufuegen",
    "Administration": "Verwaltung",
    "Administrative Copy": "Verwaltungsexemplar",
    "Advance Payment": "Vorauszahlung",
    "Alert Days Ahead:": "Vorwarnung (Tage):",
    "Alert Email Recipients:": "E-Mail-Empfaenger fuer Warnungen:",
    "Alert Plural": "Warnungen (Pl.)",
    "Alert S": "Warnung (Sg.)",
    "Alerts & Ops": "Warnungen & Betrieb",
    "All Countries": "Alle Laender",
    "All Files": "Alle Dateien",
    "All alerts have been resolved": "Alle Warnungen wurden behoben",
    "All copies generated: {path}": "Alle Kopien generiert: {path}",
    "All systems nominal": "Alle Systeme in Ordnung",
    "All time": "Gesamter Zeitraum",
    "All trips are fully assigned": "Alle Fahrten vollstaendig zugewiesen",
    "All trips assigned": "Alle Fahrten zugewiesen",
    "Already have an account?": "Bereits ein Konto?",
    "Already linked.": "Bereits verknuepft.",
    "Amount in Words": "Betrag in Worten",
    "Amount is required and must be positive.": "Betrag erforderlich und muss positiv sein.",
    "Analytics & Reporting": "Analytik & Berichte",
    "Application Settings": "Anwendungseinstellungen",
    "Apply Filters": "Filter anwenden",
    "Apr": "Apr",
    "Archive these routes?": "Diese Routen archivieren?",
    "Archived:": "Archiviert:",
    "Are you sure you want to cancel trip {trip_id}?": "Fahrt {trip_id} wirklich stornieren?",
    "Arriving Today": "Heute ankommend",
    "Assign Both": "Beide zuweisen",
    "Assign Driver Only": "Nur Fahrer zuweisen",
    "Assign Truck + Driver": "LKW + Fahrer zuweisen",
    "Assign Truck Only": "Nur LKW zuweisen",
    "Assign jobs automatically": "Auftraege automatisch zuweisen",
    "Assigned to {count} trips": "{count} Fahrten zugewiesen",
    "Assignment Summary": "Zuweisungsuebersicht",
    "At least 8 characters": "Mindestens 8 Zeichen",
    "Attach Files": "Dateien anhaengen",
    "Attachment Type": "Anhangstyp",
    "Attachment:": "Anhang:",
    "Attachments Empty": "Keine Anhaenge",
    "Aug": "Aug",
    "Auto-Fill": "Auto-Ausfuellen",
    "Auto-Fill from Doc": "Auto-Ausfuellen aus Dokument",
    "Auto-calculated": "Automatisch berechnet",
    "Auto-generated": "Automatisch generiert",
    "Automated Invoicing": "Automatische Rechnungsstellung",
    "Automated Job Assignment": "Automatische Auftragszuweisung",
    "Automation": "Automatisierung",
    "Avg Profit/Trip": "Durchschn. Gewinn/Fahrt",
    "BRANDING": "BRANDING",
    "BRANDING & SIGNATURES": "BRANDING & UNTERSCHRIFTEN",
    "Back": "Zurueck",
    "Back to home": "Zurueck zur Startseite",
    "Bank Reference": "Bankreferenz",
    "Bill To": "Rechnung an",
    "Billed": "In Rechnung gestellt",
    "Body template:": "Textvorlage:",
    "Body:": "Text:",
    "Boxes 1-2": "Felder 1-2",
    "Boxes 13-17": "Felder 13-17",
    "Boxes 18-19": "Felder 18-19",
    "Boxes 21-24": "Felder 21-24",
    "Boxes 3-5": "Felder 3-5",
    "Boxes 6-7": "Felder 6-7",
    "Boxes 8-14": "Felder 8-14",
    "Branch / Office": "Filiale / Standort",
    "Branding": "Branding",
    "Browse": "Durchsuchen",
    "Browse Title": "Titel durchsuchen",
    "Browse...": "Durchsuchen...",
    "Built for real logistics results": "Fuer echte Logistikergebnisse entwickelt",
    "Button Email": "E-Mail-Button",
    "CALCULATION RESULT": "BERECHNUNGSERGEBNIS",
    "CEO, Smith Logistics": "CEO, Smith Logistics",
    "CMR": "CMR",
    "CMR International Consignment Note": "CMR Internationaler Frachtbrief",
    "CMR Number": "CMR-Nummer",
    "CMR Trip #{}": "CMR-Fahrt #{}",
    "CMR Trip #{} - {} COPY": "CMR-Fahrt #{} - {} KOPIE",
    "CMR Waybill": "CMR-Frachtbrief",
    "CMR generated: {path}": "CMR generiert: {path}",
    "CMR generation failed: {error}": "CMR-Generierung fehlgeschlagen: {error}",
    "CSV": "CSV",
    "Calculate Route": "Route berechnen",
    "Calculate a route to see details.": "Route berechnen, um Details zu sehen.",
    "Calibration": "Kalibrierung",
    "Cancel Status": "Status abbrechen",
    "Cannot read input: {}": "Eingabe kann nicht gelesen werden: {}",
    "Cargo Description": "Frachtbeschreibung",
    "Cargo Details": "Frachtdetails",
    "Carrier (Transporter)": "Frachtfuehrer (Transporteur)",
    "Carrier Copy": "Frachtfuehrerexemplar",
    "Carrier reservations and observations": "Vorbehalte des Frachtfuehrers",
    "Charges (Box 20)": "Frachtkosten (Feld 20)",
    "Choose Company Color": "Unternehmensfarbe waehlen",
    "City / Country": "Stadt / Land",
    "Clear": "Loeschen",
    "Clear Filters": "Filter loeschen",
    "Cleaned up": "Bereinigt",
    "Click map to add stop": "Karte klicken, um Halt hinzuzufuegen",
    "Client Mode": "Kundenmodus",
    "Clients exported successfully.": "Kunden erfolgreich exportiert.",
    "Clipboard unavailable": "Zwischenablage nicht verfuegbar",
    "Col Cost": "Sp. Kosten",
    "Col Date": "Sp. Datum",
    "Col Km": "Sp. KM",
    "Col Notes": "Sp. Notizen",
    "Col Provider": "Sp. Anbieter",
    "Col Type": "Sp. Typ",
    "Comment": "Kommentar",
    "Complete driver database": "Vollstaendige Fahrerdatenbank",
    "Configuration": "Konfiguration",
    "Confirm Archive": "Archivierung bestaetigen",
    "Confirm Delete": "Loeschen bestaetigen",
    "Confirm Status": "Status bestaetigen",
    "Connected:": "Verbunden:",
    "Consignee": "Empfaenger",
    "Consignee Copy": "Empfaengerexemplar",
    "Consignment Parties": "Frachtparteien",
    "Consignor / Shipper": "Versender / Absender",
    "Contact Person": "Ansprechpartner",
    "Contact Type": "Kontakttyp",
    "Contact:": "Kontakt:",
    "Continue to Email": "Weiter zu E-Mail",
    "Convention on the Contract for the International Carriage of Goods by Road (CMR)": "CMR-Uebereinkommen",
    "Copy path": "Pfad kopieren",
    "Cost Type": "Kostenart",
    "Cost per Month": "Kosten pro Monat",
    "Cost per Year": "Kosten pro Jahr",
    "Country": "Land",
    "Create Contract": "Vertrag erstellen",
    "Create and edit professional invoices": "Professionelle Rechnungen erstellen",
    "Create and manage proforma invoices": "Proforma-Rechnungen verwalten",
    "Create an international CMR waybill": "Internationalen CMR-Frachtbrief erstellen",
    "Credit Limit (EUR)": "Kreditlimit (EUR)",
    "Critical": "Kritisch",
    "Current (0-30d)": "Aktuell (0-30d)",
    "Custom Dashboards": "Benutzerdefinierte Dashboards",
    "Customer": "Kunde",
    "Customer Payment": "Kundenzahlung",
    "DATA MANAGEMENT": "DATENVERWALTUNG",
    "DB Engine:": "DB-Engine:",
    "DB Path": "DB-Pfad",
    "Daily Activity": "Taegliche Aktivitaet",
    "Danger": "Gefahr",
    "Data Safety": "Datensicherheit",
    "Database Inspector": "Datenbank-Inspektor",
    "Database error: {}": "Datenbankfehler: {}",
    "Date:": "Datum:",
    "Deactivate User": "Benutzer deaktivieren",
    "Debug Mode:": "Debug-Modus:",
    "Default Rate/km": "Standardsatz/km",
    "Delete this contact?": "Diesen Kontakt loeschen?",
    "Delete this pipeline run and its processed file?": "Diesen Durchlauf und Datei loeschen?",
    "Delivery Location": "Lieferort",
    "Departing Today": "Heute abfahrend",
    "Departure": "Abfahrt",
    "Deposit": "Anzahlung",
    "Diagnostics": "Diagnose",
    "Digital Archive": "Digitales Archiv",
    "Digital Proof of Delivery": "Digitaler Liefernachweis",
    "Discount Type": "Rabattart",
    "Discount Value": "Rabattwert",
    "Dispatch & Operations": "Disposition & Betrieb",
    "Dispatcher": "Disponent",
    "Distribution & Insights": "Verteilung & Erkenntnisse",
}

print(f"DE supplementary: {len(SUPP_DE)} entries")

SUPP_ES = {
    " km": " km",
    " months": " meses",
    " seconds": " segundos",
    " l": " l",
    "30 derniers jours": "30 derniers jours",
    "31-60 days": "31-60 d-as",
    "61-90 days": "61-90 d-as",
    "90+ days": "90+ d-as",
    "ADR Dangerous Goods": "ADR Mercanc_as Peligrosas",
    "AI-Powered OCR": "OCR Impulsado por IA",
    "API Token": "Token API",
    "API Version": "Versi_n API",
    "ATTACHMENTS": "ADJUNTOS",
    "About - Operion ERP": "Acerca de - Operion ERP",
    "About Operion": "Acerca de Operion",
    "Access denied": "Acceso denegado",
    "Accommodation": "Alojamiento",
    "Account / Subdomain": "Cuenta / Subdominio",
    "Account created successfully": "Cuenta creada exitosamente",
    "Acme Inc.": "Acme S.A.",
    "Action Maint": "Acci_n Mantenimiento",
    "Action Remind": "Acci_n Recordatorio",
    "Action Resolve": "Acci_n Resolver",
    "Action Trip": "Acci_n Viaje",
    "Action Truck": "Acci_n Cami_n",
    "Active Clients Trend": "Tendencia Clientes Activos",
    "Active Drivers": "Conductores Activos",
    "Active Tasks": "Tareas Activas",
    "Active Trucks": "Camiones Activos",
    "Active vs Inactive": "Activo vs Inactivo",
    "Active:": "Activo:",
    "Activity Timeline": "Cronolog_a de Actividad",
    "Actual Uploads": "Subidas Reales",
    "Add Contact": "A_adir Contacto",
    "Add Country": "A_adir Pa_s",
    "Add Entry": "A_adir Entrada",
    "Add Loading Stop": "A_adir Parada Carga",
    "Add Record": "A_adir Registro",
    "Add Row": "A_adir Fila",
    "Add Unloading Stop": "A_adir Parada Descarga",
    "Add tag...": "A_adir etiqueta...",
    "Add to Dispatch": "A_adir a Despacho",
    "Admin Login": "Inicio Sesi_n Admin",
    "Admin Panel": "Panel Admin",
    "Admin authentication required": "Autenticaci_n admin requerida",
    "Administration": "Administraci_n",
    "Administrative Copy": "Copia Administrativa",
    "Advance Payment": "Pago Anticipado",
    "Advanced": "Avanzado",
    "Advanced Analytics": "Anal_ticas Avanzadas",
    "Advanced algorithms optimize": "Algoritmos avanzados optimizan",
    "Alert Days Ahead": "D_as Antelaci_n Alerta",
    "Alert Email Recipients": "Destinatarios Alerta Email",
    "Alert Plural": "Alertas (Pl.)",
    "Alert S": "Alerta (Sg.)",
    "Alerts & Ops": "Alertas y Operaciones",
    "All Countries": "Todos los Pa_ses",
    "All Files": "Todos los Archivos",
    "All alerts have been resolved": "Todas las alertas resueltas",
    "All copies generated": "Todas las copias generadas",
    "All systems nominal": "Todos los sistemas nominales",
    "All time": "Todo el tiempo",
    "All trips are fully assigned": "Todos los viajes asignados",
    "All trips assigned": "Todos asignados",
    "All trips, invoices, contacts": "Todos viajes, facturas, contactos",
    "Already have an account": "Ya tienes cuenta",
    "Already linked.": "Ya vinculado.",
    "Amount in Words": "Importe en Letras",
    "Analytics & Reporting": "Anal_ticas e Informes",
    "Application Settings": "Configuraci_n Aplicaci_n",
    "Apply Filters": "Aplicar Filtros",
    "Archive these routes": "Archivar estas rutas",
    "Archived:": "Archivado:",
    "Are you sure you want to cancel trip": "Seguro de cancelar viaje",
    "Arriving Today": "Llegando Hoy",
    "Assign Both": "Asignar Ambos",
    "Assign Driver Only": "Asignar Solo Conductor",
    "Assign Truck + Driver": "Asignar Cami_n + Conductor",
    "Assign Truck Only": "Asignar Solo Cami_n",
    "Assign Truck & Driver": "Asignar Cami_n y Conductor",
    "Assign jobs automatically": "Asignar trabajos autom_ticamente",
    "Assigned to {count} trips": "Asignado a {count} viajes",
    "Assignment Summary": "Resumen Asignaci_n",
    "At least 8 characters": "Al menos 8 caracteres",
    "Attach Files": "Adjuntar Archivos",
    "Attachment Type": "Tipo Adjunto",
    "Attachment:": "Adjunto:",
    "Attachments Empty": "Sin Adjuntos",
    "Auto-Fill": "Auto-Rellenar",
    "Auto-Fill from Doc": "Auto-Rellenar desde Doc",
    "Auto-calculated": "Auto-calculado",
    "Auto-generated": "Auto-generado",
    "Automated Invoicing": "Facturaci_n Automatizada",
    "Automated Job Assignment": "Asignaci_n Autom_tica Trabajos",
    "Automation": "Automatizaci_n",
    "Avg Profit/Trip": "Beneficio Medio/Viaje",
}

print(f"ES supplementary: {len(SUPP_ES)} entries")

SUPP_FR = {
    " km": " km",
    " months": " mois",
    " seconds": " secondes",
    "ADR Dangerous Goods": "ADR Marchandises Dangereuses",
    "AI-Powered OCR": "OCR Pilot_ par IA",
    "API Version": "Version API",
    "ATTACHMENTS": "PI_ECES JOINTES",
    "About - Operion ERP": "_ propos - Operion ERP",
    "About Operion": "_ propos d'Operion",
    "Access denied": "Acc_s refus_",
    "Accommodation": "H_bergement",
    "Account created successfully": "Compte cr__ avec succ_s",
    "Acme Inc.": "Acme SA",
    "Action Maint": "Action Maintenance",
    "Action Remind": "Action Rappel",
    "Action Resolve": "Action R_soudre",
    "Action Trip": "Action Trajet",
    "Action Truck": "Action Camion",
    "Actions": "Actions",
    "Active Tasks": "T_ches Actives",
    "Activity Timeline": "Chronologie Activit_s",
    "Add Contact": "Ajouter Contact",
    "Add Entry": "Ajouter Entr_e",
    "Add Loading Stop": "Ajouter Arr_t Chargement",
    "Add Record": "Ajouter Enregistrement",
    "Add Row": "Ajouter Ligne",
    "Add Unloading Stop": "Ajouter Arr_t D_chargement",
    "Add tag...": "Ajouter _tiquette...",
    "Admin Login": "Connexion Admin",
    "Admin Panel": "Panneau Admin",
    "Admin authentication required": "Authentification admin requise",
    "Administration": "Administration",
    "Administrative Copy": "Copie Administrative",
    "Advance Payment": "Paiement Anticip_",
    "Advanced": "Avanc_",
    "Advanced algorithms optimize": "Algorithmes avanc_s optimisent",
    "Alert Plural": "Alertes (Pl.)",
    "Alert S": "Alerte (Sg.)",
    "All Files": "Tous les fichiers",
    "All copies generated": "Toutes les copies g_n_r_es",
    "All systems nominal": "Tous les syst_mes nominaux",
    "All trips, invoices, contacts": "Tous trajets, factures, contacts",
    "Already have an account": "D_j_ un compte",
    "Already linked.": "D_j_ li_.",
    "Amount": "Montant",
    "Amount in Words": "Montant en Lettres",
    "Amount is required and must be positive.": "Montant requis et doit _tre positif.",
    "Analytics & Reporting": "Analytique et Rapports",
    "Apply Filters": "Appliquer Filtres",
    "At least 8 characters": "Au moins 8 caract_res",
    "Attach Files": "Joindre Fichiers",
    "Attachment Type": "Type Pi_ce Jointe",
    "Attachment:": "Pi_ce jointe :",
    "Attachments Empty": "Pi_ces jointes vides",
    "Auto-Fill": "Auto-remplissage",
    "Auto-Fill from Doc": "Auto-remplissage depuis doc",
    "Auto-calculated": "Auto-calcul_",
    "Auto-generated": "Auto-g_n_r_",
    "Automated Invoicing": "Facturation automatis_e",
    "Automated Job Assignment": "Attribution automatis_e des t_ches",
    "Automation": "Automatisation",
    "Avg Profit/Trip": "B_n_fice moyen/trajet",
}

print(f"FR supplementary: {len(SUPP_FR)} entries")

# ===========================================================================
# MAIN TRANSLATION LOGIC
# ===========================================================================
def translate_file(lang_code, supp_dict):
    en_path = os.path.join(TRANS_DIR, "en.json")
    tgt_path = os.path.join(TRANS_DIR, f"{lang_code}.json")
    
    en = load_json(en_path)
    tgt = load_json(tgt_path)
    
    # Build bootstrap from existing translations
    boot = build_bootstrap(tgt, en)
    
    # Combine bootstrap + supplementary (supplementary overrides)
    combined = dict(boot)
    combined.update(supp_dict)
    
    # Also add bootstrap values from OTHER languages as fallback hints
    # (We'll use the bootstrap from this language directly)
    
    count_translated = 0
    for path, en_val in iter_leaves(en):
        if not should_translate(en_val):
            continue
        try:
            tgt_val = get_at(tgt, path)
        except (KeyError, IndexError, TypeError):
            continue
        
        if isinstance(tgt_val, str) and tgt_val == en_val:
            translation = combined.get(en_val)
            if translation:
                set_at(tgt, path, translation)
                count_translated += 1
    
    save_json(tgt_path, tgt)
    return count_translated

def count_untranslated(lang_code):
    en_path = os.path.join(TRANS_DIR, "en.json")
    tgt_path = os.path.join(TRANS_DIR, f"{lang_code}.json")
    en = load_json(en_path)
    tgt = load_json(tgt_path)
    boot = build_bootstrap(tgt, en)
    total = 0
    untranslated = 0
    for path, en_val in iter_leaves(en):
        if not should_translate(en_val):
            continue
        total += 1
        try:
            tgt_val = get_at(tgt, path)
        except:
            continue
        if isinstance(tgt_val, str) and tgt_val == en_val:
            untranslated += 1
    return total, untranslated

if __name__ == "__main__":
    results = {}
    for code, supp in [("de", SUPP_DE), ("es", SUPP_ES), ("fr", SUPP_FR)]:
        total, before = count_untranslated(code)
        translated = translate_file(code, supp)
        total2, after = count_untranslated(code)
        cov_before = round((1 - before/total) * 100, 1) if total else 0
        cov_after = round((1 - after/total) * 100, 1) if total else 0
        results[code] = (before, after, translated, cov_before, cov_after, total)
        print(f"{code}.json: {before} -> {after} untranslated ({translated} translated)")
        print(f"  Coverage: {cov_before}% -> {cov_after}%")
    
    print()
    print("=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)
    for code in ["de", "es", "fr"]:
        b, a, t, cb, ca, tot = results[code]
        print(f"  {code}.json: {ca}% coverage ({tot - a} of {tot} strings, {a} untranslated)")
