#!/usr/bin/env python3
"""
Translate ALL remaining English values in cs.json to Czech.
Compares cs.json against en.json - if a value is still English, translate it.
"""
import json
import os
import re

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data', 'translations')

with open(os.path.join(data_dir, 'en.json'), 'r', encoding='utf-8') as f:
    en_data = json.load(f)

with open(os.path.join(data_dir, 'cs.json'), 'r', encoding='utf-8') as f:
    cs_data = json.load(f)

ACRONYMS = {'ID', 'KM', 'VIN', 'EUR', 'N/A', 'CSV', 'PDF', 'OCR', 'GPS', 'API',
            'CMR', 'KPI', 'SMTP', 'DSO', 'SLA', 'SOC', 'GDPR', 'CUI', 'VAT',
            'ETA', 'SMS', 'GBP', 'USD', 'RON', 'JSON', 'BOM', 'UTF-8'}

CZECH_CHARS = set('ěščřžýáíéúůďťňóĚŠČŘŽÝÁÍÉÚŮĎŤŇÓ')

# Comprehensive English -> Czech translation map
T = {
    # ===== STATUS VALUES =====
    "Planned": "Plánováno", "Loading": "Nakládka", "In Transit": "Na cestě",
    "Delivered": "Doručeno", "Cancelled": "Zrušeno", "Invoiced": "Fakturováno",
    "Paid": "Zaplaceno", "Overdue": "Po splatnosti", "Completed": "Dokončeno",
    "Archived": "Archivováno", "unknown": "Neznámý", "Unknown": "Neznámý",
    "planned": "Plánováno", "loading": "Nakládka", "in_transit": "Na cestě",
    "delivered": "Doručeno", "cancelled": "Zrušeno", "invoiced": "Fakturováno",
    "paid": "Zaplaceno", "Active": "Aktivní", "active": "Aktivní",
    "All": "Vše", "": "",

    # ===== PERIODS =====
    "All history": "Celá historie", "Last week": "Minulý týden",
    "Current month": "Aktuální měsíc", "Specific year": "Konkrétní rok",
    "Custom": "Vlastní",

    # ===== NAV =====
    "Overview": "Přehled", "Calculator": "Kalkulačka",
    "Dispatcher Board": "Dispečerský panel", "Driver Manager": "Správce řidičů",
    "Maintenance Analytics": "Analytika údržby",
    "Maintenance Control": "Správa údržby", "Tachograph": "Tachograf",
    "Operations": "Operace", "Fleet": "Vozový park", "Finance": "Finance",
    "Live Tracking": "Živé sledování", "Maintenance": "Údržba",
    "Route Planner": "Plánovač tras", "Clients": "Klienti",
    "Document Center": "Centrum dokumentů", "Does Not Exist": "Neexistuje",
    "Team": "Tým", "Migration Center": "Centrum migrace",
    "Tools": "Nástroje", "Administration": "Administrativa",
    "Generators": "Generátory",

    # ===== MIGRATION =====
    "Import and export your data": "Import a export dat",
    "Import from Software": "Import ze softwaru",
    "Physical Archive": "Fyzický archiv",
    "Export Data": "Export dat",

    # ===== TEAM =====
    "Team Management": "Správa týmu", "Add User": "Přidat uživatele",
    "Invite a new team member": "Pozvat nového člena týmu",
    "Team Members": "Členové týmu",
    "Manage existing users": "Správa stávajících uživatelů",
    "EMAIL": "EMAIL", "PASSWORD": "HESLO", "ROLE": "ROLE",
    "LINK DRIVER": "PROPOJIT ŘIDIČE", "Dispatcher": "Dispečer",
    "Driver": "Řidič", "Email": "Email", "Role": "Role", "Status": "Stav",
    "Created": "Vytvořeno", "Actions": "Akce", "Deactivate": "Deaktivovat",
    "Email is required.": "Email je povinný.",
    "Password is required.": "Heslo je povinné.",
    "User added successfully.": "Uživatel úspěšně přidán.",
    "Failed to add user: {}": "Nepodařilo se přidat uživatele: {}",
    "Failed to deactivate user: {}": "Nepodařilo se deaktivovat uživatele: {}",
    "Are you sure you want to deactivate {email}?":
        "Opravdu chcete deaktivovat {email}?",
    "Deactivate User": "Deaktivovat uživatele", "Validation": "Ověření",
    "Email is required.": "Email je povinný.",
    "Password is required.": "Heslo je povinné.",
    "Deactivate User": "Deaktivovat uživatele", "Deactivate": "Deaktivovat",
    "Error": "Chyba", "No API client or database available.":
        "Není k dispozici API klient ani databáze.", "Success": "Úspěch",
    "User added successfully.": "Uživatel úspěšně přidán.",
    "Failed to add user: {error}": "Nepodařilo se přidat uživatele: {error}",
    "Failed to deactivate user: {error}":
        "Nepodařilo se deaktivovat uživatele: {error}",

    # ===== MAIN =====
    "Add VAT": "Přidat DPH", "Price (before VAT):": "Cena (bez DPH):",
    "Price (after VAT):": "Cena (s DPH):",
    "CALCULATION RESULT": "VÝSLEDEK VÝPOČTU",
    "Fill in the form to calculate profit":
        "Vyplňte formulář pro výpočet zisku",
    "Enter trip data and press Calculate.":
        "Zadejte údaje o jízdě a stiskněte Vypočítat.",
    "Gross Revenue": "Hrubý výnos", "Total Cost": "Celkové náklady",
    "Net Profit": "Čistý zisk", "Rate / km": "Sazba / km",
    "Margin": "Marže", "VAT %": "DPH %",

    # ===== HISTORY =====
    "Cancel Status": "Zrušit stav", "Confirm Status": "Potvrdit stav",
    "No Engine": "Žádný motor", "No Transitions": "Žádné přechody",
    "Status Prompt": "Výzva ke stavu", "Transition Failed": "Přechod selhal",
    "Load More": "Načíst více", "Documents": "Dokumenty",
    "Date": "Datum", "Truck": "Vozidlo", "Driver": "Řidič",
    "Client": "Klient", "Distance (km)": "Vzdálenost (km)",
    "€/km": "€/km", "Profit": "Zisk", "Status": "Stav",
    "Emailed": "Odesláno emailem",
    "Trip emailed successfully": "Jízda úspěšně odeslána emailem",
    "Invoice generated successfully": "Faktura úspěšně vygenerována",
    "Search trips...": "Hledat jízdy...",
    "Export PDF": "Export PDF", "Export Excel": "Export Excel",
    "Email Invoice": "Odeslat fakturu emailem",
    "Operations management and invoicing": "Správa provozu a fakturace",
    "Trip #{}": "Jízda #{}", "INV-": "FAK-",

    # ===== FLEET =====
    "Select a truck first.": "Nejprve vyberte vozidlo.",
    "General": "Obecné", "Unassigned": "Nepřiřazeno",
    "No engine data": "Žádná data motoru", "Open Alerts": "Aktivní upozornění",
    "Cost/Month": "Náklady/měsíc", "Last Service": "Poslední servis",
    "Next Due": "Příští servis", "Odometer": "Kilometrovník",
    "Tracking Device ID": "ID sledovacího zařízení",
    "Truck {}": "Vozidlo {}",
    "Alerts": "Upozornění",
    "Export CSV": "Export CSV",

    # ===== RESULT =====
    "day": "den", "hour": "hodina", "minute": "minuta",
    "Routing server is off. Check that GraphHopper is running.":
        "Routing server je vypnutý. Zkontrolujte, zda GraphHopper běží.",

    # ===== EMAIL =====
    "Documents for Trip #{}": "Dokumenty k jízdě #{}",

    # ===== SETTINGS =====
    "MAINTENANCE THRESHOLDS": "PRAHY ÚDRŽBY",
    "Save": "Uložit", "Reset": "Resetovat",
    "Application Settings": "Nastavení aplikace",
    "SMTP Server:": "SMTP server:", "SMTP Port:": "SMTP port:",
    "SMTP User:": "SMTP uživatel:", "SMTP Password:": "SMTP heslo:",
    "Alert Email Recipients:": "Příjemci výstražných emailů:",
    "Alert Days Ahead:": "Počet dní předem:",
    "Tacho Warning Days:": "Varování tachografu (dny):",
    "Tacho Critical Days:": "Kritické dny tachografu:",
    "Test Connection": "Test připojení", "Email Logs": "Logy emailů",
    "Connection successful": "Připojení úspěšné",
    "Test failed: {}": "Test selhal: {}",
    "BRANDING": "BRANDING", "Company Logo:": "Logo společnosti:",
    "Color": "Barva", "Signature Image:": "Podpisový obrázek:",
    "Stamp Image:": "Razítko:", "Dark": "Tmavý", "Light": "Světlý",
    "Field Ai Vision": "AI Vision",
    "Body template:": "Šablona těla:",
    "Field Email Importer": "Importér emailů",
    "Field Folder Watcher": "Sledovač složek",
    "PaddleOCR advanced settings:": "Pokročilá nastavení PaddleOCR:",
    "Cloud OCR credentials:": "Přihlašovací údaje Cloud OCR:",
    "Field Ocr Gpu": "OCR GPU",
    "Set at least one provider": "Nastavte alespoň jednoho poskytovatele",
    " seconds": " sekund",

    # ===== INVOICE =====
    "Button Email": "Odeslat emailem", "Default Client": "Výchozí klient",
    "Email Body": "Tělo emailu", "Email Failed": "Email selhal",
    "Email Subject": "Předmět emailu", "Email Success": "Email odeslán",
    "Smtp Not Configured": "SMTP není nakonfigurováno",
    "Field {Key}": "Pole {Key}",

    # ===== EMAIL LOGS =====
    "Recipient": "Příjemce", "Subject": "Předmět", "Sent": "Odesláno",
    "No logs found": "Žádné záznamy nenalezeny",

    # ===== ALERTS =====
    "Critical": "Kritické", "Warning": "Varování", "Info": "Info",
    "None Active": "Žádné aktivní",

    # ===== COMMON =====
    "Search...": "Hledat...", "Search": "Hledat", "Confirm": "Potvrdit",
    "Warning": "Varování", "Error": "Chyba", "Schedule": "Rozvrh",
    "No activity recorded": "Žádná zaznamenaná aktivita",
    "No revenue data yet": "Zatím žádná data o výnosech",
    "Ops not available": "Operace nejsou k dispozici",
    "No signature": "Žádný podpis",
    "Signature accepted": "Podpis přijat",
    "Cleaned up": "Vyčištěno",
    "Select Signature Image": "Vybrat obrázek podpisu",
    "Open calendar": "Otevřít kalendář",
    "Select date": "Vybrat datum",
    "Show alerts": "Zobrazit upozornění",
    "Cancel": "Zrušit",
    "↓ Down": "↓ Dolů",
    "Refresh": "Obnovit",
    "↑ Up": "↑ Nahoru",
    "Truck": "Vozidlo",

    # ===== TRACKING =====
    "Fleet Tracking": "Sledování vozového parku",
    "Configure fleet tracking credentials in Settings.":
        "Nakonfigurujte přihlašovací údaje pro sledování v Nastavení.",
    "Tracking Platform": "Sledovací platforma",
    "Platform not configured": "Platforma není nakonfigurována",
    "API Token": "API token", "Server URL": "URL serveru",
    "Username": "Uživatelské jméno", "Password": "Heslo",
    "Test Connection": "Test připojení",
    "Connection test incomplete": "Test připojení neúplný",
    "Connection test failed": "Test připojení selhal",
    "Stopped": "Zastaveno", "Account / Subdomain": "Účet / subdoména",
    "ID Field": "Pole ID", "Latitude Field": "Pole zeměpisné šířky",
    "Longitude Field": "Pole zeměpisné délky",
    "Not Configured": "Není nakonfigurováno",
    "Positions JSON Path": "Cesta JSON pozic",

    # ===== ANALYTICS =====
    "Invalid Date Format": "Neplatný formát data",
    "Top Trucks by Revenue": "Nejlepší vozidla dle výnosů",
    "Revenue vs Expenses": "Výnosy vs Náklady",
    "Driver Profit": "Zisk řidiče", "Profit Margin": "Zisková marže",
    "From": "Od", "To": "Do", "Apply": "Použít",
    "Revenue": "Výnosy", "Expenses": "Náklady", "Profit": "Zisk",
    "Chart Error": "Chyba grafu", "Invalid date range": "Neplatný rozsah dat",
    "Fleet performance analytics and KPIs":
        "Analytika výkonnosti vozového parku a KPI",
    "Financial": "Finanční", "Fleet": "Vozový park", "Routes": "Trasy",
    "Clients": "Klienti", "Drivers": "Řidiči", "Documents": "Dokumenty",
    "Revenue, profit, margin, and cash flow trends":
        "Trendy výnosů, zisku, marže a cash flow",
    "Truck utilization, fuel efficiency, and maintenance alerts":
        "Využití vozidel, spotřeba paliva a upozornění na údržbu",
    "Route profitability and country corridor analysis":
        "Ziskovost tras a analýza zemských koridorů",
    "Client revenue, payment behavior, and growth":
        "Výnosy klientů, platební chování a růst",
    "Driver performance, efficiency, and compliance":
        "Výkonnost řidičů, efektivita a soulad",
    "Document volume, trends, and expiration tracking":
        "Objem dokumentů, trendy a sledování expirace",
    "Total Revenue": "Celkové výnosy", "Total Profit": "Celkový zisk",
    "Current Margin": "Aktuální marže", "Top Client": "Nejlepší klient",
    "Active Trucks": "Aktivní vozidla", "Total KM": "Celkem KM",
    "Avg Consumption": "Prům. spotřeba", "Maint. Alerts":
        "Upozornění na údržbu", "Invoices": "Faktury", "CMRs": "CMR",
    "Total Docs": "Dokumenty celkem", "Expiring": "Končící",
    "months": "měsíce",
    "Truck Profitability": "Ziskovost vozidel",
    "Fuel Efficiency (L/100km)": "Účinnost paliva (L/100km)",
    "Truck Utilization (Trips)": "Využití vozidel (jízdy)",
    "Revenue by Client": "Výnosy dle klienta",
    "Profit by Client": "Zisk dle klienta",
    "Average Payment Delay (Days)": "Průměrné zpoždění plateb (dny)",
    "Revenue Concentration": "Koncentrace výnosů",
    "Last quarter": "Minulé čtvrtletí",
    "No data available": "Žádná data",
    "Rest": "Ostatní",
    "New Clients per Month": "Noví klienti za měsíc",
    "Trips Completed": "Dokončené jízdy",
    "Profit per Driver": "Zisk na řidiče",
    "Efficiency (Profit/km)": "Efektivita (zisk/km)",
    "Tacho Violations (90 days)": "Porušení tachografu (90 dní)",
    "Most Profitable Routes": "Nejziskovější trasy",
    "Profit per KM": "Zisk na KM",
    "Fuel Cost per KM": "Náklady na palivo na KM",
    "Country Profit per KM": "Zisk na KM dle země",
    "Document Distribution": "Rozložení dokumentů",
    "Monthly Uploads": "Měsíční nahrávání",
    "CMR Generation Trend": "Trend generování CMR",
    "Other": "Ostatní",
    "Revenue by Country": "Výnosy dle země",
    "Financial Trends": "Finanční trendy",
    "Financial Performance": "Finanční výkonnost",
    "Client & Geographic": "Klient a geografie",
    "Volume & Cost": "Objem a náklady",
    "Fleet Performance": "Výkonnost vozového parku",
    "Fleet Composition": "Složení vozového parku",
    "Cost & Maintenance": "Náklady a údržba",
    "Volume & Efficiency": "Objem a efektivita",
    "Compliance & Safety": "Shoda a bezpečnost",
    "Distribution & Insights": "Rozložení a poznatky",
    "Trip Distance Distribution": "Rozložení vzdáleností jízd",
    "Trips by Month x Driver": "Jízdy dle měsíce x řidiče",
    "Profit Breakdown (Top Driver)": "Rozklad zisku (nejlepší řidič)",
    "Driving vs Rest Hours": "Hodiny řízení vs odpočinku",
    "Driver Utilization Score": "Skóre využití řidiče",
    "Avg Profit per Trip": "Prům. zisk na jízdu",
    "Total costs": "Celkové náklady", "Top Route": "Nejlepší trasa",
    "Avg Profit/km": "Prům. zisk/km", "Total Routes": "Trasy celkem",
    "Top Country": "Nejlepší země",
    "Route Performance": "Výkonnost trasy",
    "Geographic Analysis": "Geografická analýza",
    "Correlation & Distribution": "Korelace a rozložení",
    "Volume & Trends": "Objem a trendy",
    "Top Countries by Volume": "Nejlepší země dle objemu",
    "Top Countries by Profit": "Nejlepší země dle zisku",
    "Cost Breakdown": "Rozklad nákladů",
    "Distance (km)": "Vzdálenost (km)",
    "Net Profit (€)": "Čistý zisk (€)",
    "Distance Distribution": "Rozložení vzdáleností",
    "Route Length Trend": "Trend délky trasy",
    "Net Profit Trend": "Trend čistého zisku",
    "Monthly Trip Volume": "Měsíční objem jízd",
    "Trucks": "Vozidla", "Idle": "Nečinný", "Inactive": "Neaktivní",
    "Client Performance": "Výkonnost klienta",
    "Client Composition": "Složení klientů",
    "Client Trends": "Trendy klientů",
    "Client Insights": "Poznatky o klientech",
    "Document Overview": "Přehled dokumentů",
    "Document Breakdown": "Rozklad dokumentů",
    "Expiry & Aging": "Exspirace a stárnutí",
    "Growth & Trends": "Růst a trendy",
    "Document Type Breakdown": "Rozklad dle typu dokumentu",
    "Category Distribution": "Rozložení kategorií",
    "Upload by Quarter": "Nahrávání dle kvartálu",
    "Expiry Timeline": "Časová osa expirace",
    "Document Aging": "Stárnutí dokumentů",
    "Expiring by Type": "Končící dle typu",
    "Document Growth": "Růst dokumentů",
    "Volume vs Revenue": "Objem vs výnosy",
    "Total Documents Trend": "Trend celkových dokumentů",
    "Revenue per Client Trend": "Trend výnosů na klienta",
    "Trip Count Trend": "Trend počtu jízd",
    "Profit Margin per Client": "Zisková marže na klienta",
    "Revenue vs Profit": "Výnosy vs zisk",
    "Active Clients Trend": "Trend aktivních klientů",
    "Total Clients": "Klienti celkem",
    "Avg Payment Delay": "Prům. zpoždění plateb",
    "Concentration": "Koncentrace",
    "Route Performance": "Výkonnost trasy",
    "Safety Score": "Skóre bezpečnosti",
    "Active vs Inactive": "Aktivní vs neaktivní",
    "Net": "Čistý", "Total": "Celkem", "Relevant": "Relevantní",
    "Top 3": "Top 3", "Others": "Ostatní", "Trips": "Jízdy",
    "Period": "Období", "Last 30 days": "Posledních 30 dní",
    "Last 90 days": "Posledních 90 dní",
    "Last 6 months": "Posledních 6 měsíců", "Last year": "Minulý rok",
    "All time": "Celé období",
    "Daily Activity": "Denní aktivita", "Year": "Rok",
    "Client Retention": "Retence klientů",
    "Cost Per Truck": "Náklady na vozidlo",
    "Country Corridors": "Zemské koridory",
    "Driver Distance": "Vzdálenost řidiče",
    "Driver Driving Hours": "Hodiny řízení řidiče",
    "Driver Ranking": "Pořadí řidičů",
    "Driver Rest Hours": "Hodiny odpočinku řidiče",
    "Efficiency Trend": "Trend efektivity",
    "Extra Costs": "Dodatečné náklady", "Fuel": "Palivo",
    "Fuel Cost Trend": "Trend nákladů na palivo",
    "Fuel Efficiency Trend": "Trend účinnosti paliva",
    "Idle Vs Active": "Nečinný vs aktivní",
    "Invoiced Vs Paid": "Fakturováno vs zaplaceno",
    "Kpi Avg Trips": "Prům. jízdy", "Kpi Top Driver": "Nejlepší řidič",
    "Kpi Total Drivers": "Řidiči celkem",
    "Kpi Total Violations": "Porušení celkem",
    "Maintenance Cost": "Náklady na údržbu",
    "Mileage Ranking": "Pořadí dle najetých km",
    "Profit Vs Distance": "Zisk vs vzdálenost",
    "Quarterly Revenue": "Čtvrtletní výnosy",
    "Revenue Per Client Trend": "Trend výnosů na klienta",
    "Revenue Vs Profit Scatter": "Rozptyl výnosů vs zisku",
    "Salary": "Plat",
    "Section Driver Metrics": "Metriky řidiče",
    "Section Driver Performance": "Výkonnost řidiče",
    "Section Volume Safety": "Objem a bezpečnost",
    "Toll": "Mýtné", "Total Distance": "Celková vzdálenost",
    "Trip Status Distribution": "Rozložení stavů jízd",
    "Truck Age Distribution": "Rozložení stáří vozidel",
    "31-60 days": "31-60 dní", "61-90 days": "61-90 dní",
    "Current (0-30d)": "Aktuální (0-30 dní)", "90+ days": "90+ dní",
    "All Countries": "Všechny země", "KM": "KM", "Profit/KM": "Zisk/KM",
    "Route": "Trasa", "Actual Uploads": "Skutečná nahrávání",
    "Expected (Trips)": "Očekávané (jízdy)",
    "No documents expiring within 30 days":
        "Žádné dokumenty nekončí do 30 dnů",
    "See all ({count})": "Zobrazit vše ({count})",
    "Document Uploads vs Expected":
        "Nahrávání dokumentů vs očekávání",
    "Insufficient data for chart — add more trips":
        "Nedostatek dat pro graf — přidejte více jízd",
    "Outstanding Invoices by Age": "Neuhrazené faktury dle stáří",
    "Active Drivers": "Aktivní řidiči",
    "Avg Profit/Driver": "Prům. zisk/řidič",
    "Avg Profit/Route": "Prům. zisk/trasa",
    "Avg Trips/Driver": "Prům. jízdy/řidič",
    "Avg Cost/km": "Prům. náklady/km",
    "Avg collection period": "Prům. doba inkasa",
    "DSO (Days)": "DSO (dny)", "Most Frequent": "Nejčastější",
    "New Clients": "Noví klienti",
    "Unassigned Trips": "Nepřiřazené jízdy",
    "Unique Routes": "Unikátní trasy",
    "No assigned driver data for this period.":
        "Žádná data přiřazeného řidiče za toto období.",
    "Outstanding": "Neuhrazeno", "Target 30d": "Cíl 30 dní",
    "Refresh data": "Obnovit data",
    "Revenue vs Profit Trend": "Trend výnosů vs zisku",
    "Route Frequency": "Frekvence tras",
    "Driver Activity Timeline": "Časová osa aktivity řidiče",
    "Invoice Aging": "Stárnutí faktur",
    "Payment Behavior": "Platební chování",
    "Revenue & Profit Trend": "Trend výnosů a zisku",
    "Expires": "Končí",
    "Insufficient data for chart - add more trips":
        "Nedostatek dat pro graf - přidejte více jízd",

    # ===== ROUTE =====
    "Add to Dispatch": "Přidat na panel",
    "Send to Calculator": "Odeslat do kalkulačky",
    "Client Name": "Název klienta", "No saved route ID":
        "Žádné ID uložené trasy", "Select Driver": "Vybrat řidiče",
    "Start Date": "Datum zahájení", "Destination": "Cíl",
    "Stop {n}": "Zastávka {n}", "Start": "Start",
    "Trip Created": "Jízda vytvořena",
    "Recommended": "Doporučený", "Fastest": "Nejrychlejší",
    "Cheapest": "Nejlevnější", "Safest": "Nejbezpečnější",
    "Shortest": "Nejkratší",
    "Click map to add stop": "Klikněte na mapu pro přidání zastávky",
    "Route loaded": "Trasa načtena", "Route Options": "Možnosti trasy",
    "Plan multi-stop routes with cost estimation":
        "Plánujte vícedenní trasy s odhadem nákladů",
    "Route Planner": "Plánovač tras", "OPTIONS": "MOŽNOSTI",
    "EXCLUDED COUNTRIES": "VYLOUČENÉ ZEMĚ",
    "ROUTE RESULT": "VÝSLEDEK TRASY", "Add Country": "Přidat zemi",
    "Share Route": "Sdílet trasu",
    "Share this route with others so they can load it in Operion.":
        "Sdílejte tuto trasu s ostatními, aby ji mohli načíst v Operion.",
    "Share link": "Sdílet odkaz", "Copy": "Kopírovat",
    "Export File": "Exportovat soubor", "Google Maps": "Google Maps",
    "Save & Open Folder": "Uložit a otevřít složku",
    "Copied!": "Zkopírováno!",
    "Clipboard unavailable": "Schránka není dostupná",
    "Saved: {path}": "Uloženo: {path}",
    "Calculate Route": "Vypočítat trasu",
    "Distance": "Vzdálenost", "Duration": "Trvání",
    "Calculate a route to see details.":
        "Vypočítejte trasu pro zobrazení podrobností.",
    "SMART ROUTE": "CHYTRÁ TRASA",

    # ===== ROUTE HISTORY =====
    "Recalculate": "Přepočítat", "Archive": "Archivovat",
    "Export JSON": "Export JSON",
    "Delete": "Odstranit", "Compare": "Porovnat",
    "Loading map...": "Načítání mapy...",
    "Filter by truck": "Filtrovat dle vozidla",
    "Filter by Truck": "Filtrovat dle vozidla",
    "Confirm Archive": "Potvrdit archivaci",
    "Archive these routes?": "Archivovat tyto trasy?",
    "Confirm Delete": "Potvrdit odstranění",
    "Delete these routes?": "Odstranit tyto trasy?",
    "Exported": "Exportováno",
    "Routes exported successfully.": "Trasy úspěšně exportovány.",
    "Recalculated": "Přepočítáno",
    "Routes recalculated successfully.": "Trasy úspěšně přepočítány.",
    "Search routes...": "Hledat trasy...",
    "Select truck...": "Vybrat vozidlo...",
    "Review and manage saved routes":
        "Prohlížet a spravovat uložené trasy",
    "Route History": "Historie tras",
    "Total:": "Celkem:", "Active:": "Aktivní:",
    "Archived:": "Archivováno:", "Date:": "Datum:",
    "Truck:": "Vozidlo:", "Distance:": "Vzdálenost:",
    "Duration:": "Trvání:",

    # Comparison results (with format strings)
    "None": "Žádný",

    # ===== DISPATCH BOARD =====
    "Board": "Panel", "Resources": "Zdroje",
    "Alerts & Ops": "Upozornění a provoz", "Timeline": "Časová osa",
    "Clear": "Vymazat", "Filter by status": "Filtrovat dle stavu",
    "No matching trips": "Žádné odpovídající jízdy",
    "Driver Availability": "Dostupnost řidičů",
    "Truck Availability": "Dostupnost vozidel",
    "Available": "Dostupné", "Returning": "Vracející se",
    "On Trip": "Na jízdě", "Blocked": "Blokováno",
    "No active drivers": "Žádní aktivní řidiči",
    "No active trucks": "Žádná aktivní vozidla",
    "License Expired": "Platnost ŘP vypršela",
    "Medical Expired": "Platnost lékařské prohlídky vypršela",
    "Hours Exceeded": "Překročené hodiny",
    "Maint. Due": "Splatná údržba",
    "Insurance Expired": "Pojištění vypršelo",
    "Inspection Expired": "STK vypršela",
    "In Service": "V servisu", "Trip": "Jízda",
    "ETA": "ETA", "Next free": "Příští volný",
    "Operational Alerts": "Provozní upozornění",
    "No active alerts": "Žádná aktivní upozornění",
    "All alerts have been resolved":
        "Všechna upozornění byla vyřešena",
    "Unassigned Trips": "Nepřiřazené jízdy",
    "All trips assigned": "Všechny jízdy přiřazeny",
    "All trips are fully assigned": "Všechny jízdy plně přiřazeny",
    "No Truck": "Žádné vozidlo", "No Driver": "Žádný řidič",
    "No Truck or Driver": "Žádné vozidlo ani řidič",
    "Quick Assign": "Rychlé přiřazení",
    "Assignment Summary": "Souhrn přiřazení",
    "Total Active": "Celkem aktivních",
    "Fully Assigned": "Plně přiřazeno", "Partial": "Částečné",
    "Resolve All": "Vyřešit vše",
    "Trip Details": "Podrobnosti jízdy", "Edit Trip": "Upravit jízdu",
    "Close": "Zavřít", "Trip ID": "ID jízdy",
    "Departure": "Odjezd", "Distance": "Vzdálenost",
    "Price": "Cena", "Currency": "Měna", "Notes": "Poznámky",
    "No alerts for this trip": "Žádná upozornění pro tuto jízdu",
    "Resource Conflict": "Konflikt zdrojů",
    "The following conflicts were detected:":
        "Byly zjištěny následující konflikty:",
    "Drivers Free": "Volní řidiči", "Trucks Free": "Volná vozidla",
    "Schedule Timeline": "Časová osa plánu",
    "No scheduled trips to display":
        "Žádné plánované jízdy k zobrazení",
    "No trips scheduled for the selected period":
        "Pro vybrané období nejsou naplánovány žádné jízdy",
    "Plan a Trip": "Naplánovat jízdu", "NOW": "NYNÍ",
    "Assign Truck + Driver": "Přiřadit vozidlo + řidiče",
    "Quick Assign Truck & Driver":
        "Rychlé přiřazení vozidla a řidiče",
    "Cancel Trip": "Zrušit jízdu",
    "Are you sure you want to cancel trip {trip_id}?":
        "Opravdu chcete zrušit jízdu {trip_id}?",
    "Today's Brief": "Dnešní přehled",
    "Departing Today": "Odjíždí dnes",
    "Arriving Today": "Přijíždí dnes",
    "Needs Attention": "Vyžaduje pozornost",
    "Assign Truck": "Přiřadit vozidlo",
    "Assign Driver": "Přiřadit řidiče",
    "Assign Truck & Driver": "Přiřadit vozidlo a řidiče",
    "Select Truck": "Vybrat vozidlo",
    "Select Driver": "Vybrat řidiče",
    "Assign Both": "Přiřadit oba",
    "Assign Truck Only": "Přiřadit pouze vozidlo",
    "Assign Driver Only": "Přiřadit pouze řidiče",
    "CSV": "CSV", "PDF": "PDF",
    "Nothing to undo": "Nic k vrácení",
    "Nothing to redo": "Nic k opakování",
    "No trips found": "Nenalezeny žádné jízdy",
    "Try adjusting your search or filter criteria":
        "Zkuste upravit kritéria vyhledávání nebo filtrování",

    # ===== FLEET DASHBOARD =====
    "Activity Title": "Přehled aktivit",
    "Activity View All": "Zobrazit vše",
    "Card Avg Profit": "Prům. zisk",
    "Card Best Driver": "Nejlepší řidič",
    "Card Best Truck": "Nejlepší vozidlo",
    "Card Consumption": "Spotřeba",
    "Card Fuel Cost": "Náklady na palivo",
    "Card Highest Fuel": "Nejvyšší spotřeba",
    "Card Revenue": "Výnosy",
    "Card Trips": "Jízdy",
    "Chart Fleet Status": "Stav vozového parku",
    "Chart Trip Activity": "Aktivita jízd",
    "Charts Unavailable": "Grafy nedostupné",
    "Date": "Datum",
    "Error Msg": "Chybová zpráva",
    "Error Title": "Chyba",
    "Last Refreshed": "Naposledy obnoveno",
    "No Data": "Žádná data",
    "No Driver Data": "Žádná data řidiče",
    "No Truck Data": "Žádná data vozidla",
    "Section Activity": "Aktivita",
    "Section Fleet Health": "Stav vozového parku",
    "Section Overview": "Přehled",
    "Section Performance": "Výkonnost",
    "Title": "Název",

    # format-string-containing entries that must match exactly
    "{module}\n(Module not yet migrated)":
        "{module}\n(Modul ještě nepřenesen)",
}


def is_acronym_or_allowed(val):
    """Check if a string value should NOT be translated (acronym, number, etc.)."""
    if not isinstance(val, str):
        return True
    s = val.strip()
    if not s:
        return False  # empty string, still count as needing translation? No, skip.
    
    # Single acronym
    if s in ACRONYMS:
        return True
    
    # All words are acronyms/digits/symbols
    words = re.findall(r'[A-Z0-9.+/%-]+', s)
    clean_words = [w.strip('.:;()[]{}!?/%-') for w in s.split()]
    non_empty = [w for w in clean_words if w]
    if non_empty and all(w in ACRONYMS or w.isdigit() or not any(c.isalpha() for c in w) for w in non_empty):
        # Check if there's actual English text mixed in
        has_real_text = any(any(c.islower() for c in w) and w not in ACRONYMS for w in clean_words if w)
        if not has_real_text:
            return True
    
    return False


def looks_czech(val):
    """Check if val already contains Czech-specific characters."""
    if not isinstance(val, str):
        return False
    return bool(CZECH_CHARS & set(val))


def is_english_text(val):
    """Check if string looks like untranslated English."""
    if not isinstance(val, str):
        return False
    if not val.strip():
        return False
    if is_acronym_or_allowed(val):
        return False
    if looks_czech(val):
        return False
    # Contains mostly Latin letters = likely English
    letters = re.findall(r'[a-zA-Z]', val)
    if not letters:
        return False
    return True


def deep_translate(obj, en_obj):
    """Recursively translate all string values in obj using en_obj as reference."""
    changes = 0
    skipped = 0  # count values we explicitly skip
    
    if isinstance(obj, dict) and isinstance(en_obj, dict):
        for key in list(obj.keys()):
            if key in en_obj:
                c, s = deep_translate(obj[key], en_obj[key])
                changes += c
                skipped += s
            else:
                # Key in cs but not en - keep as-is
                pass
    elif isinstance(obj, list) and isinstance(en_obj, list):
        for i in range(min(len(obj), len(en_obj))):
            c, s = deep_translate(obj[i], en_obj[i])
            changes += c
            skipped += s
    elif isinstance(obj, str) and isinstance(en_obj, str):
        # This is a leaf string value
        if is_english_text(obj) and obj == en_obj:
            # Still English and matches English source -> translate
            if obj in T:
                obj = T[obj]
                changes += 1
            # Also check for format-string versions
            # Try matching against format-variant patterns
            elif '{' in obj and '}' in obj:
                # Try direct lookup
                pass  # We handle this via the dict
        # Even if cs differs from en, if it still looks English, translate
        elif is_english_text(obj) and obj != en_obj:
            # cs value is different from en but still English - might need translation
            if obj in T:
                obj = T[obj]
                changes += 1
    
    return changes, skipped


# First pass: standard recursive translation
changes1, _ = deep_translate(cs_data, en_data)
print(f"Pass 1 translations: {changes1}")

# Second pass: force-translate any value in cs_data that still equals en_data
# and contains no Czech characters
def force_pass(cs_obj, en_obj):
    """Second aggressive pass - match en values and translate."""
    count = 0
    if isinstance(cs_obj, dict) and isinstance(en_obj, dict):
        for key in en_obj:
            if key in cs_obj:
                count += force_pass(cs_obj[key], en_obj[key])
    elif isinstance(cs_obj, list) and isinstance(en_obj, list):
        for i in range(min(len(cs_obj), len(en_obj))):
            count += force_pass(cs_obj[i], en_obj[i])
    elif isinstance(cs_obj, str) and isinstance(en_obj, str):
        if cs_obj == en_obj and is_english_text(cs_obj):
            if cs_obj in T:
                # Need to update the parent - tricky
                pass  # We'll handle this differently
    return count

# Instead, let's just walk the en_data and compare directly
def walk_and_fix(cs_obj, en_obj, path=""):
    """Walk en_obj, compare with cs_obj, translate any remaining English strings."""
    count = 0
    if isinstance(en_obj, dict) and isinstance(cs_obj, dict):
        for key in en_obj:
            if key in cs_obj:
                count += walk_and_fix(cs_obj[key], en_obj[key], f"{path}.{key}")
    elif isinstance(en_obj, list) and isinstance(cs_obj, list):
        for i in range(min(len(en_obj), len(cs_obj))):
            count += walk_and_fix(cs_obj[i], en_obj[i], f"{path}[{i}]")
    elif isinstance(en_obj, str) and isinstance(cs_obj, str):
        # If cs value matches en value AND is English
        if cs_obj == en_obj and en_obj in T:
            cs_obj = T[en_obj]
            count += 1
        elif cs_obj != en_obj and is_english_text(cs_obj) and cs_obj in T:
            cs_obj = T[cs_obj]
            count += 1
    return count

# We need a different approach - mutate in-place
def mutate_fix(target, source, path=""):
    """Mutate target dict/list, fixing any English values by looking up in T."""
    changes = 0
    if isinstance(target, dict) and isinstance(source, dict):
        for key in list(target.keys()):
            if key in source:
                changes += mutate_fix(target[key], source[key], f"{path}.{key}")
    elif isinstance(target, list) and isinstance(source, list):
        for i in range(min(len(target), len(source))):
            changes += mutate_fix(target[i], source[i], f"{path}[{i}]")
    elif isinstance(target, str) and isinstance(source, str):
        if target == source and target in T:
            # Direct match - replace in-place (can't do this directly in recursion)
            pass
    return changes

# Ok, the cleanest approach: walk en_data and cs_data together,
# and whenever cs value == en value and en value is in T, replace cs value

def final_fix(cs_obj, en_obj):
    """Deep mutate cs_obj in place - whenever cs value equals en value and is in T, translate."""
    changes = 0
    if isinstance(cs_obj, dict) and isinstance(en_obj, dict):
        for key in list(cs_obj.keys()):
            if key in en_obj:
                changes += final_fix(cs_obj[key], en_obj[key])
    elif isinstance(cs_obj, list) and isinstance(en_obj, list):
        for i in range(min(len(cs_obj), len(en_obj))):
            changes += final_fix(cs_obj[i], en_obj[i])
    elif isinstance(cs_obj, str) and isinstance(en_obj, str):
        if cs_obj == en_obj and en_obj in T:
            # Replace in parent - but we can't do this from here
            # Instead, we'll use a container approach
            pass
    return changes

# Cleanest approach: just walk the tree and return translated trees
def translate_tree(cs_obj, en_obj):
    """Return a new tree with all English values translated."""
    if isinstance(cs_obj, dict) and isinstance(en_obj, dict):
        result = {}
        for key in en_obj:
            if key in cs_obj:
                result[key] = translate_tree(cs_obj[key], en_obj[key])
            else:
                result[key] = translate_tree(en_obj[key], en_obj[key])
        # Add any extra keys in cs but not in en
        for key in cs_obj:
            if key not in en_obj:
                result[key] = cs_obj[key]
        return result
    elif isinstance(cs_obj, list) and isinstance(en_obj, list):
        result = []
        for i in range(max(len(cs_obj), len(en_obj))):
            if i < len(cs_obj) and i < len(en_obj):
                result.append(translate_tree(cs_obj[i], en_obj[i]))
            elif i < len(cs_obj):
                result.append(cs_obj[i])
            else:
                result.append(en_obj[i])
        return result
    elif isinstance(cs_obj, str) and isinstance(en_obj, str):
        # If cs already has Czech, keep it
        if looks_czech(cs_obj):
            return cs_obj
        # If cs == en and en is translatable
        if cs_obj == en_obj and en_obj in T:
            return T[en_obj]
        # If cs is different from en but still looks English and is in T
        if cs_obj != en_obj and is_english_text(cs_obj) and cs_obj in T:
            return T[cs_obj]
        # Keep as-is
        return cs_obj
    else:
        return cs_obj


new_cs = translate_tree(cs_data, en_data)

# Write the result
cs_output_path = os.path.join(data_dir, 'cs.json')
with open(cs_output_path, 'w', encoding='utf-8') as f:
    json.dump(new_cs, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Count remaining
def count_remaining(cs_obj, en_obj):
    """Count how many values are still English (should be translated)."""
    eng = 0
    total = 0
    if isinstance(cs_obj, dict) and isinstance(en_obj, dict):
        for key in en_obj:
            if key in cs_obj:
                e, t = count_remaining(cs_obj[key], en_obj[key])
                eng += e
                total += t
    elif isinstance(cs_obj, list) and isinstance(en_obj, list):
        for i in range(min(len(cs_obj), len(en_obj))):
            e, t = count_remaining(cs_obj[i], en_obj[i])
            eng += e
            total += t
    elif isinstance(cs_obj, str) and isinstance(en_obj, str):
        total += 1
        if cs_obj == en_obj and en_obj != '' and not is_acronym_or_allowed(en_obj) and not looks_czech(cs_obj) and not all(c in '─ ' for c in en_obj):
            # Still English
            eng += 1
        elif cs_obj != en_obj and is_english_text(cs_obj) and not looks_czech(cs_obj) and cs_obj not in ACRONYMS:
            eng += 1
    return eng, total

eng_rem, eng_total = count_remaining(new_cs, en_data)
print(f"Pass 2 (translate_tree):")
print(f"  Remaining English: {eng_rem}")
print(f"  Total strings: {eng_total}")
print(f"  Translated: {eng_total - eng_rem}")
print(f"  Coverage: {(eng_total - eng_rem) / eng_total * 100:.1f}%")

# Show what's still English
if eng_rem > 0:
    print("\n--- Still English values ---")
    def show_remaining(cs_obj, en_obj, path=""):
        if isinstance(cs_obj, dict) and isinstance(en_obj, dict):
            for key in en_obj:
                if key in cs_obj:
                    show_remaining(cs_obj[key], en_obj[key], f"{path}.{key}")
        elif isinstance(cs_obj, list) and isinstance(en_obj, list):
            for i in range(min(len(cs_obj), len(en_obj))):
                show_remaining(cs_obj[i], en_obj[i], f"{path}[{i}]")
        elif isinstance(cs_obj, str) and isinstance(en_obj, str):
            if cs_obj == en_obj and en_obj != '' and not is_acronym_or_allowed(en_obj) and not looks_czech(cs_obj) and not all(c in '─ ' for c in en_obj):
                print(f"  {path}: '{cs_obj}'")
    show_remaining(new_cs, en_data)
