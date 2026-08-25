#!/usr/bin/env python3
"""Final pass: translate ALL remaining untranslated values in ro.json to Romanian."""
from __future__ import annotations

import json

EN_PATH = r'data/translations/en.json'
RO_PATH = r'data/translations/ro.json'

with open(EN_PATH, 'r', encoding='utf-8') as f:
    en = json.load(f)
with open(RO_PATH, 'r', encoding='utf-8') as f:
    ro = json.load(f)

# Complete mapping of dot-path -> Romanian translation
# Covers ALL 128 remaining "should translate" values
TRANSLATIONS = {
    # --- app ---
    'app.subtitle': 'ERP',

    # --- nav ---
    'nav.calculator': 'Calculator',

    # --- team ---
    'team.email_label': 'EMAIL',
    'team.col_email': 'Email',
    'team.col_status': 'Status',

    # --- main ---
    'main.separator': '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',

    # --- fleet ---
    'fleet.unit_km': 'km',
    'fleet.expense_default_category': 'General\u0103',
    'fleet.alert_format': '[{type}] {msg}',
    'fleet.form_model': 'Model:',
    'fleet.maintenance_table_type': 'Tip',
    'fleet.table_consumption': 'L/100km',
    'fleet.table_model': 'Model',

    # --- history ---
    'history.button_email': 'Email',
    'history.button_excel': 'Excel',
    'history.col_brut_km': '\u20ac/km',
    'history.col_client': 'Client',
    'history.col_profit': 'Profit',

    # --- analytics ---
    'analytics.active': 'Active',
    'analytics.col_profit_km': 'Profit/KM',
    'analytics.group_top3': 'Top 3',
    'analytics.group_total': 'Total',
    'analytics.kpi_top_client_rev': 'Top Client',
    'analytics.pie_profit': 'Profit',
    'analytics.profit_label': 'Profit',
    'analytics.route_profit_per_km': 'Profit pe KM',
    'analytics.waterfall_net': 'Net',

    # --- invoice ---
    'invoice.trip_list_format': '#{id} {truck_number} \u2014 {client_name} [{created_at}]',

    # --- settings ---
    'settings.section_branding': 'BRANDING',

    # --- edit_trip ---
    'edit_trip.field_client': 'Client:',

    # --- route ---
    'route.open_in_gmaps': 'Google Maps',

    # --- route_history ---
    'route_history.export_json': 'Export\u0103 JSON',
    'route_history.export_csv': 'Export\u0103 CSV',
    'route_history.label_total': 'Total:',

    # --- dispatch_board ---
    'dispatch_board.alerts_panel_total_trips': 'Total Active',
    'dispatch_board.detail_client': 'Client',
    'dispatch_board.detail_status': 'Status',
    'dispatch_board.driver_hours_weekly': '{hours:.1f}h/{max_h}h',
    'dispatch_board.live': 'LIVE',
    'dispatch_board.status_bar_active': 'Active',

    # --- auth ---
    'auth.email_label': 'Email',
    'auth.login_brand': 'Operion',
    'auth.register_brand': 'Operion',

    # --- admin ---
    'admin.email': 'Email',
    'admin.email_placeholder': 'admin@example.com',
    'admin.latency_ms': '{value} ms',
    'admin.password_placeholder': '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',

    # --- login ---
    'login.email_placeholder': 'admin@example.com',
    'login.password_placeholder': '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',

    # --- alerts ---
    'alerts.severity_info': 'Info',

    # --- automation ---
    'automation.label_document': 'Doc #{}',
    'automation.label_status': 'Status:',

    # --- client ---
    'client.email_icon': '\u2709',
    'client.field_email': 'Email',
    'client.field_rating': 'Rating (1-5)',
    'client.phone': '\U0001f4de',
    'client.table_email': 'Email',
    'client.table_inv_status': 'Status',

    # --- cmr ---
    'cmr.carrier_reservations_ro': 'REZERVARILE TRANSPORTATORULUI / RESERVES DU TRANSPORTEUR',
    'cmr.carrier_ro': 'TRANSPORTATOR / TRANSPORTEUR',
    'cmr.cod_ro': 'PLATA LA LIVRARE / REMBOURSEMENT',
    'cmr.consignee_ro': 'DESTINATAR / CONSIGNATAIRE',
    'cmr.consignor_ro': 'EXPEDITOR / EXPEDITEUR',
    'cmr.contact': 'Contact:',
    'cmr.destination_ro': 'LOCUL LIVRARII MARFII / LIEU DE LIVRAISON',
    'cmr.distance_ro': 'DISTANTA / DISTANCE',
    'cmr.documents_ro': 'DOCUMENTE ANEXATE / DOCUMENTS ANNEXES',
    'cmr.email': 'Email:',
    'cmr.eori': 'EORI:',
    'cmr.payment_instruction_ro': 'MODALITATEA DE PLATA / INSTRUCTION DE PAIEMENT',
    'cmr.place_of_loading_ro': 'LOCUL PREDARII MARFII / LIEU DE PRISE EN CHARGE',
    'cmr.sender_instructions_ro': "INSTRUCTIUNILE EXPEDITORULUI / INSTRUCTIONS DE L'EXPEDITEUR",
    'cmr.special_agreements_ro': 'INTELEGERI SPECIALE / CONVENTIONS SPECIALES',
    'cmr.tel': 'Tel:',

    # --- docs ---
    'docs.email': 'Email',
    'docs.next': '>',
    'docs.prev': '<',
    'docs.ocr_section': 'OCR',

    # --- driver_manager ---
    'driver_manager.field_email': 'Email',
    'driver_manager.field_phone': 'Telefon',

    # --- email_logs ---
    'email_logs.col_status': 'Status',

    # --- generators ---
    'generators.cmr_generated_status': 'Generat',

    # --- home ---
    'home.testimonial_1_author': 'Mihai Popescu',
    'home.testimonial_2_author': 'Sarah M\u00fcller',
    'home.testimonial_3_author': 'John Smith',
    'home.testimonial_3_role': 'CEO, Smith Logistics',

    # --- invoice_editor ---
    'invoice_editor.branding': 'Branding',
    'invoice_editor.email': 'Email',
    'invoice_editor.logo': 'Logo',
    'invoice_editor.net_15': 'Net 15',
    'invoice_editor.net_30': 'Net 30',
    'invoice_editor.net_60': 'Net 60',
    'invoice_editor.select_client': 'Client:',
    'invoice_editor.subtotal': 'Subtotal',
    'invoice_editor.total': 'Total',

    # --- invoice_pdf ---
    'invoice_pdf.default_cui': 'RO12345678',
    'invoice_pdf.default_email': 'contact@firma.ro',
    'invoice_pdf.default_phone': '07xx xxx xxx',
    'invoice_pdf.default_reg': 'J40/123/2023',

    # --- maint ---
    'maint.col_interval_km': 'Interval (km)',
    'maint.section_status': 'Status',
    'maint.severity_info': 'Info',
    'maint.unit_km': ' km',

    # --- maint_analytics ---
    'maint_analytics.cost_label': 'Cost',
    'maint_analytics.month_apr': 'Apr',
    'maint_analytics.month_aug': 'Aug',
    'maint_analytics.month_dec': 'Dec',
    'maint_analytics.month_feb': 'Feb',
    'maint_analytics.month_mar': 'Mar',
    'maint_analytics.month_oct': 'Oct',
    'maint_analytics.month_sep': 'Sep',

    # --- maint_timeline ---
    'maint_timeline.cost': 'Cost',
    'maint_timeline.field_cost': 'Cost',

    # --- proforma_editor ---
    'proforma_editor.branding': 'Branding',
    'proforma_editor.email': 'Email',
    'proforma_editor.logo': 'Logo',
    'proforma_editor.net_15': 'Net 15',
    'proforma_editor.net_30': 'Net 30',
    'proforma_editor.net_60': 'Net 60',
    'proforma_editor.select_client': 'Client:',
    'proforma_editor.subtotal': 'Subtotal',
    'proforma_editor.total': 'Total',

    # --- receipt ---
    'receipt.amount_placeholder': '0.00',
    'receipt.attach_type_document': 'Document',
    'receipt.attach_type_pod': 'POD',
    'receipt.editor.email': 'Email',
    'receipt.total_label': 'Total',

    # --- tacho ---
    'tacho.hdr_status': 'Status',
    'tacho.result_label': '{label}: {value}',
    'tacho.status_ok': 'OK',

    # --- trip ---
    'trip.speed_display': '{speed:.0f} km/h',

    # --- common (keys that aren't in common but in the flat list) ---
    # Note: 'common.id', 'common.na', 'common.currency_eur' are handled by should_translate
}

def apply_translation(d, path=''):
    """Recursively walk the JSON and apply translations by path."""
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
print('Written ro.json')

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

# List remaining untranslated (acronyms that are fine)
ACRONYMS = {'ID', 'KM', 'VIN', 'EUR', 'N/A', 'CSV', 'PDF', 'OCR', 'GPS', 'API',
            'CMR', 'KPI', 'SMTP', 'DSO', 'SLA', 'SOC', 'GDPR', 'CUI', 'VAT',
            'ETA', 'SMS', 'GBP', 'USD', 'RON', 'JSON', 'BOM', 'UTF-8'}

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

print(f'\nStill untranslated (acronyms - OK): {len(acronym_ok)}')
print(f'Still untranslated (needs fix): {len(need_translate)}')

if need_translate:
    print('\nNeed to translate:')
    for k, v in need_translate:
        print(f'  {k} = {repr(v)[:80]}')
