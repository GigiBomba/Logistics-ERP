#!/usr/bin/env python3
"""Final comprehensive Romanian translation pass."""
import json

EN_PATH = r'data/translations/en.json'
RO_PATH = r'data/translations/ro.json'

with open(EN_PATH, 'r', encoding='utf-8') as f:
    en = json.load(f)
with open(RO_PATH, 'r', encoding='utf-8') as f:
    ro = json.load(f)

# --- Path-based Romanian translations for values that differ from English ---
# Only entries where the Romanian value != English value are included
TRANSLATIONS = {
    # === Status -> Stare (Romanian word for status, used in already-translated entries) ===
    'team.col_status': 'Stare',
    'email_logs.col_status': 'Stare',
    'dispatch_board.detail_status': 'Stare',
    'tacho.hdr_status': 'Stare',
    'client.table_inv_status': 'Stare',
    'maint.section_status': 'Stare',

    # === Labels ===
    'automation.label_status': 'Stare:',
    'dispatch_board.detail_client': 'Client',
    'history.col_client': 'Client',
    'edit_trip.field_client': 'Client:',
    'invoice_editor.select_client': 'Client:',
    'proforma_editor.select_client': 'Client:',

    # === Column headers consistent with existing ro.json ===
    'history.col_profit': 'Profit',
    'analytics.pie_profit': 'Profit',
    'analytics.profit_label': 'Profit',
    'analytics.route_profit_per_km': 'Profit pe KM',
    'analytics.col_profit_km': 'Profit/KM',
    'analytics.group_total': 'Total',
    'analytics.group_top3': 'Top 3',
    'analytics.waterfall_net': 'Net',
    'analytics.kpi_top_client_rev': 'Client de Top',
    'analytics.active': 'Active',
    'dispatch_board.status_bar_active': 'Active',
    'dispatch_board.alerts_panel_total_trips': 'Total Active',
    'route_history.label_total': 'Total:',

    # === Acronyms/technical terms that should NOT be translated ===
    'app.subtitle': 'ERP',
    'alerts.severity_info': 'Info',
    'maint.severity_info': 'Info',
    'tacho.status_ok': 'OK',
    'dispatch_board.live': 'LIVE',
    'fleet.unit_km': 'km',
    'fleet.table_consumption': 'L/100km',
    'maint.unit_km': ' km',
    'maint.col_interval_km': 'Interval (km)',
    'maint_analytics.cost_label': 'Cost',
    'maint_timeline.field_cost': 'Cost',
    'maint_timeline.cost': 'Cost',
    'docs.ocr_section': 'OCR',
    'generators.tab_cmr': 'CMR',
    'receipt.attach_type_cmr': 'CMR',
    'receipt.attach_type_pod': 'POD',
    'receipt.attach_type_document': 'Document',
    'invoice_editor.subtotal': 'Subtotal',
    'invoice_editor.total': 'Total',
    'proforma_editor.subtotal': 'Subtotal',
    'proforma_editor.total': 'Total',
    'receipt.total_label': 'Total',
    'receipt.amount_placeholder': '0.00',
    'receipt.attach_type_document': 'Document',
    'receipt.editor.email': 'Email',

    # === Same word in Romanian - keep as-is ===
    'nav.calculator': 'Calculator',
    'team.email_label': 'EMAIL',
    'team.col_email': 'Email',
    'auth.email_label': 'Email',
    'auth.login_brand': 'Operion',
    'auth.register_brand': 'Operion',
    'admin.email': 'Email',
    'admin.email_placeholder': 'admin@example.com',
    'login.email_placeholder': 'admin@example.com',
    'admin.password_placeholder': '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',
    'login.password_placeholder': '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',
    'admin.latency_ms': '{value} ms',
    'trip.speed_display': '{speed:.0f} km/h',
    'tacho.result_label': '{label}: {value}',
    'automation.label_document': 'Doc #{}',
    'dispatch_board.driver_hours_weekly': '{hours:.1f}h/{max_h}h',
    'fleet.alert_format': '[{type}] {msg}',
    
    # === Brand names / values that must stay ===
    'route.open_in_gmaps': 'Google Maps',
    'home.testimonial_1_author': 'Mihai Popescu',
    'home.testimonial_2_author': 'Sarah M\u00fcller',
    'home.testimonial_3_author': 'John Smith',
    'home.testimonial_3_role': 'CEO, Smith Logistics',

    # === CMR form labels (bilingual RO/FR - already Romanian) ===
    'cmr.consignor_ro': 'EXPEDITOR / EXPEDITEUR',
    'cmr.consignee_ro': 'DESTINATAR / CONSIGNATAIRE',
    'cmr.place_of_loading_ro': 'LOCUL PREDARII MARFII / LIEU DE PRISE EN CHARGE',
    'cmr.destination_ro': 'LOCUL LIVRARII MARFII / LIEU DE LIVRAISON',
    'cmr.documents_ro': 'DOCUMENTE ANEXATE / DOCUMENTS ANNEXES',
    'cmr.sender_instructions_ro': "INSTRUCTIUNILE EXPEDITORULUI / INSTRUCTIONS DE L'EXPEDITEUR",
    'cmr.carrier_reservations_ro': 'REZERVARILE TRANSPORTATORULUI / RESERVES DU TRANSPORTEUR',
    'cmr.payment_instruction_ro': 'MODALITATEA DE PLATA / INSTRUCTION DE PAIEMENT',
    'cmr.cod_ro': 'PLATA LA LIVRARE / REMBOURSEMENT',
    'cmr.special_agreements_ro': 'INTELEGERI SPECIALE / CONVENTIONS SPECIALES',
    'cmr.distance_ro': 'DISTANTA / DISTANCE',
    'cmr.carrier_ro': 'TRANSPORTATOR / TRANSPORTEUR',
    'cmr.eori': 'EORI:',
    'cmr.tel': 'Tel:',
    'cmr.contact': 'Contact:',
    'cmr.email': 'Email:',
    'cmr.carrier_reservations': 'Rezerv\u0103ri \u0219i observa\u021bii ale transportatorului',
    'cmr.cod': 'Ramburs (COD)',

    # === PDF default values ===
    'invoice_pdf.default_cui': 'RO12345678',
    'invoice_pdf.default_email': 'contact@firma.ro',
    'invoice_pdf.default_phone': '07xx xxx xxx',
    'invoice_pdf.default_reg': 'J40/123/2023',

    # === Symbols ===
    'client.phone': '\U0001f4de',
    'client.email_icon': '\u2709',
    'docs.prev': '<',
    'docs.next': '>',
    'history.col_brut_km': '\u20ac/km',

    # === Already-translated fields (keeping existing) ===
    'invoice.trip_list_format': '#{id} {truck_number} \u2014 {client_name} [{created_at}]',
    'settings.section_branding': 'BRANDING',
    'history.button_email': 'Email',
    'history.button_excel': 'Excel',
    'docs.email': 'Email',
    'client.table_email': 'Email',
    'client.field_email': 'Email',
    'driver_manager.field_email': 'Email',
    'driver_manager.field_phone': 'Telefon',
    'invoice_editor.email': 'Email',
    'invoice_editor.branding': 'Branding',
    'invoice_editor.logo': 'Logo',
    'invoice_editor.net_15': 'Net 15',
    'invoice_editor.net_30': 'Net 30',
    'invoice_editor.net_60': 'Net 60',
    'proforma_editor.email': 'Email',
    'proforma_editor.branding': 'Branding',
    'proforma_editor.logo': 'Logo',
    'proforma_editor.net_15': 'Net 15',
    'proforma_editor.net_30': 'Net 30',
    'proforma_editor.net_60': 'Net 60',

    # === Month abbreviations (keep as standard abbreviations) ===
    'maint_analytics.month_apr': 'Apr',
    'maint_analytics.month_aug': 'Aug',
    'maint_analytics.month_dec': 'Dec',
    'maint_analytics.month_feb': 'Feb',
    'maint_analytics.month_mar': 'Mar',
    'maint_analytics.month_oct': 'Oct',
    'maint_analytics.month_sep': 'Sep',

    # === Labels with format strings ===
    'fleet.form_model': 'Model:',
    'fleet.table_model': 'Model',
    'fleet.maintenance_table_type': 'Tip',
    'fleet.expense_default_category': 'General\u0103',
    'generators.cmr_generated_status': 'Generat',
    'main.separator': '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
}

def apply_translation(d, path=''):
    if isinstance(d, dict):
        for k in list(d.keys()):
            full_path = f'{path}.{k}' if path else k
            if full_path in TRANSLATIONS:
                d[k] = TRANSLATIONS[full_path]
            elif isinstance(d[k], (dict, list)):
                apply_translation(d[k], full_path)
    elif isinstance(d, list):
        for i, item in enumerate(d):
            full_path = f'{path}[{i}]'
            if full_path in TRANSLATIONS:
                d[i] = TRANSLATIONS[full_path]
            elif isinstance(item, (dict, list)):
                apply_translation(item, full_path)

apply_translation(ro)

# Write back
with open(RO_PATH, 'w', encoding='utf-8') as f:
    json.dump(ro, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(f'Written {RO_PATH}')

# Verify coverage
def flat(d, p=''):
    items = {}
    for k, v in d.items():
        key = f'{p}.{k}' if p else k
        if isinstance(v, dict):
            items.update(flat(v, key))
        elif isinstance(v, list):
            items[key] = json.dumps(v, ensure_ascii=False)
        else:
            items[key] = str(v)
    return items

with open(EN_PATH, 'r', encoding='utf-8') as f:
    en2 = json.load(f)
with open(RO_PATH, 'r', encoding='utf-8') as f:
    ro2 = json.load(f)

en_f = flat(en2)
ro_f = flat(ro2)

total = len(en_f)
untrans = sum(1 for k, v in ro_f.items() if v == en_f.get(k, ''))
pct = 100 * (total - untrans) / total
print(f'Total keys: {total}')
print(f'Untranslated: {untrans}')
print(f'Coverage: {pct:.1f}%')

# List remaining
ACRONYMS = {'ID', 'KM', 'VIN', 'EUR', 'N/A', 'CSV', 'PDF', 'OCR', 'GPS', 'API',
            'CMR', 'KPI', 'SMTP', 'DSO', 'SLA', 'SOC', 'GDPR', 'CUI', 'VAT',
            'ETA', 'SMS', 'GBP', 'USD', 'RON', 'JSON', 'BOM', 'UTF-8',
            'ERP', 'LIVE', 'OK', 'POD', 'L/100km'}

def should_translate(val):
    if not isinstance(val, str):
        return False
    words = val.split()
    clean = [w.strip('.:(),{}[]%/ \t') for w in words if w.strip('.:(),{}[]%/ \t')]
    if not clean:
        return False
    if all(w in ACRONYMS for w in clean):
        return False
    return True

still_untrans = []
for k, v in sorted(ro_f.items()):
    if v == en_f.get(k, ''):
        still_untrans.append((k, v))

acronym_ok = [s for s in still_untrans if not should_translate(s[1])]
need_translate = [s for s in still_untrans if should_translate(s[1])]

print(f'\nStill untranslated (acronyms/format - OK): {len(acronym_ok)}')
print(f'Still untranslated (needs fix): {len(need_translate)}')

if need_translate:
    print('\nNeed to translate:')
    for k, v in need_translate:
        print(f'  {k} = {repr(v)[:80]}')
