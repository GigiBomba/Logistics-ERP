from __future__ import annotations

import json

with open('data/translations/en.json', 'r', encoding='utf-8') as f:
    en = json.load(f)
with open('data/translations/ro.json', 'r', encoding='utf-8') as f:
    ro = json.load(f)

def find_untranslated(en_obj, ro_obj, path=''):
    untranslated = []
    if isinstance(en_obj, dict):
        for k in en_obj:
            if k in ro_obj:
                untranslated.extend(find_untranslated(en_obj[k], ro_obj[k], f'{path}.{k}' if path else k))
            else:
                untranslated.append((f'{path}.{k} (missing in ro)', en_obj[k]))
    elif isinstance(en_obj, list):
        if en_obj != ro_obj:
            for i, (ev, rv) in enumerate(zip(en_obj, ro_obj)):
                if ev != rv:
                    untranslated.extend(find_untranslated(ev, rv, f'{path}[{i}]'))
            if len(en_obj) > len(ro_obj):
                for i in range(len(ro_obj), len(en_obj)):
                    untranslated.append((f'{path}[{i}] (missing in ro)', en_obj[i]))
    elif isinstance(en_obj, str):
        if en_obj == ro_obj:
            untranslated.append((path, en_obj))
    return untranslated

# Build mapping of path -> Romanian translation
translations = {
    'app.subtitle': 'ERP',
    'nav.calculator': 'Calculator',
    'team.email_label': 'EMAIL',
    'team.col_email': 'Email',
    'team.col_status': 'Status',
    'main.separator': '\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
    'fleet.unit_km': 'km',
    'fleet.expense_default_category': 'General',
    'fleet.alert_format': '[{type}] {msg}',
    'fleet.detail_km': 'KM:',
    'fleet.detail_vin': 'VIN:',
    'fleet.expenses_table_id': 'ID',
    'fleet.form_km': 'KM:',
    'fleet.form_model': 'Model:',
    'fleet.form_vin': 'VIN:',
    'fleet.maintenance_table_id': 'ID',
    'fleet.maintenance_table_km': 'KM',
    'fleet.maintenance_table_type': 'Tip',
    'fleet.table_consumption': 'L/100km',
    'fleet.table_id': 'ID',
    'fleet.table_km': 'KM',
    'fleet.table_model': 'Model',
    'fleet.table_vin': 'VIN',
    'history.button_email': 'Email',
    'history.button_pdf': 'PDF',
    'history.button_excel': 'Excel',
    'history.col_id': 'ID',
    'history.col_client': 'Client',
    'history.col_brut_km': '\u20ac/km',
    'history.col_profit': 'Profit',
    'history.button_export_pdf': 'Export\u0103 PDF',
    'history.button_export_excel': 'Export\u0103 Excel',
    'history.table_id': 'ID',
    'history.table_km': 'KM',
    'analytics.pie_profit': 'Profit',
    'analytics.profit_label': 'Profit',
    'analytics.client_rest': 'Altele',
    'analytics.route_profit_per_km': 'Profit per KM',
    'analytics.active': 'Active',
    'analytics.waterfall_net': 'Net',
    'analytics.group_total': 'Total',
    'analytics.group_relevant': 'Relevante',
    'analytics.group_top3': 'Top 3',
    'analytics.group_others': 'Altele',
    'analytics.col_km': 'KM',
    'analytics.col_profit_km': 'Profit/KM',
    'analytics.kpi_top_client_rev': 'Top Client',
    'invoice.trip_list_format': '#{id} {truck_number} \u2014 {client_name} [{created_at}]',
    'settings.section_email': 'EMAIL \u0219i SMTP',
    'settings.section_branding': 'BRANDING',
    'edit_trip.field_client': 'Client:',
    'route.stop_n': 'Oprire {n}',
    'route.stop_start': 'Pornire',
    'route.open_in_gmaps': 'Google Maps',
    'route_history.export_json': 'Export\u0103 JSON',
    'route_history.export_csv': 'Export\u0103 CSV',
    'route_history.label_total': 'Total:',
    'result.generic_error': '{}:\n{}',
    'invoice_pdf.default_cui': 'RO12345678',
    'invoice_pdf.default_reg': 'J40/123/2023',
    'invoice_pdf.default_phone': '07xx xxx xxx',
    'invoice_pdf.default_email': 'contact@firma.ro',
    'tracking.mapview_missing': 'tkintermapview nu este instalat.\nRuleaz\u0103: pip install tkintermapview',
    'tracking.stopped': 'Oprit',
    'email_logs.col_id': 'ID',
    'email_logs.col_status': 'Status',
    'alerts.severity_info': 'Info',
    'common.currency_eur': 'EUR',
    'common.id': 'ID',
    'common.na': 'N/A',
    'dispatch_board.live': 'LIVE',
    'dispatch_board.resource_in_service': '\u00centre\u021binere',
    'dispatch_board.resource_eta': 'ETA',
    'dispatch_board.alerts_panel_total_trips': 'Total Active',
    'dispatch_board.alerts_panel_partial': 'Par\u021bial',
    'dispatch_board.detail_status': 'Status',
    'dispatch_board.detail_client': 'Client',
    'dispatch_board.detail_eta': 'ETA',
    'dispatch_board.status_bar_active': 'Active',
    'dispatch_board.driver_hours_weekly': '{hours:.1f}h/{max_h}h',
    'dispatch_board.export_csv': 'CSV',
    'dispatch_board.export_pdf': 'PDF',
    'driver_manager.col_id': 'ID',
    'driver_manager.field_email': 'Email',
    'driver_manager.field_phone': 'Telefon',
    'home.testimonial_1_author': 'Mihai Popescu',
    'home.testimonial_2_author': 'Sarah M\u00fcller',
    'home.testimonial_3_author': 'John Smith',
    'home.testimonial_3_role': 'CEO, Smith Logistics',
    'maint.severity_info': 'Info',
    'maint.section_status': 'Status',
    'maint.col_interval_km': 'Interval (km)',
    'maint.unit_km': ' km',
    'tacho.result_label': '{label}: {value}',
    'tacho.hdr_status': 'Status',
    'tacho.status_ok': 'OK',
    'maint_analytics.cost_label': 'Cost',
    'maint_analytics.month_feb': 'Feb',
    'maint_analytics.month_mar': 'Mar',
    'maint_analytics.month_apr': 'Apr',
    'maint_analytics.month_aug': 'Aug',
    'maint_analytics.month_sep': 'Sep',
    'maint_analytics.month_oct': 'Oct',
    'maint_analytics.month_dec': 'Dec',
    'maint_timeline.field_cost': 'Cost',
    'maint_timeline.km': 'KM',
    'maint_timeline.cost': 'Cost',
    'client.table_email': 'Email',
    'client.table_inv_status': 'Status',
    'client.field_email': 'Email',
    'client.field_rating': 'Rating (1-5)',
    'client.phone': '\U0001f4de',
    'client.email_icon': '\u2709',
    'docs.prev': '<',
    'docs.next': '>',
    'docs.email': 'Email',
    'docs.ocr_section': 'OCR',
    'generators.tab_cmr': 'CMR',
    'generators.cmr_generated_status': 'Generat',
    'invoice_editor.select_client': 'Client:',
    'invoice_editor.total': 'Total',
    'invoice_editor.subtotal': 'Subtotal',
    'invoice_editor.branding': 'Branding',
    'invoice_editor.logo': 'Logo',
    'invoice_editor.email': 'Email',
    'invoice_editor.net_30': 'Net 30',
    'invoice_editor.net_15': 'Net 15',
    'invoice_editor.net_60': 'Net 60',
    'proforma_editor.select_client': 'Client:',
    'proforma_editor.total': 'Total',
    'proforma_editor.subtotal': 'Subtotal',
    'proforma_editor.branding': 'Branding',
    'proforma_editor.logo': 'Logo',
    'proforma_editor.email': 'Email',
    'proforma_editor.net_30': 'Net 30',
    'proforma_editor.net_15': 'Net 15',
    'proforma_editor.net_60': 'Net 60',
    'cmr.consignor_ro': 'EXPEDITOR / EXPEDITEUR',
    'cmr.consignee_ro': 'DESTINATAR / CONSIGNATAIRE',
    'cmr.place_of_loading_ro': 'LOCUL PREDARII MARFII / LIEU DE PRISE EN CHARGE',
    'cmr.destination_ro': 'LOCUL LIVRARII MARFII / LIEU DE LIVRAISON',
    'cmr.documents_ro': 'DOCUMENTE ANEXATE / DOCUMENTS ANNEXES',
    'cmr.sender_instructions_ro': "INSTRUCTIUNILE EXPEDITORULUI / INSTRUCTIONS DE L'EXPEDITEUR",
    'cmr.carrier_reservations': 'Rezerv\u0103ri \u0219i observa\u021bii ale transportatorului',
    'cmr.carrier_reservations_ro': 'REZERVARILE TRANSPORTATORULUI / RESERVES DU TRANSPORTEUR',
    'cmr.payment_instruction_ro': 'MODALITATEA DE PLATA / INSTRUCTION DE PAIEMENT',
    'cmr.cod': 'Ramburs (COD)',
    'cmr.cod_ro': 'PLATA LA LIVRARE / REMBOURSEMENT',
    'cmr.special_agreements_ro': 'INTELEGERI SPECIALE / CONVENTIONS SPECIALES',
    'cmr.distance_ro': 'DISTANTA / DISTANCE',
    'cmr.carrier_ro': 'TRANSPORTATOR / TRANSPORTEUR',
    'cmr.eori': 'EORI:',
    'cmr.tel': 'Tel:',
    'cmr.contact': 'Contact:',
    'cmr.email': 'Email:',
    'automation.label_status': 'Status:',
    'automation.label_document': 'Doc #{}',
    'receipt.editor.email': 'Email',
    'receipt.amount_placeholder': '0.00',
    'receipt.total_label': 'Total',
    'receipt.attach_type_cmr': 'CMR',
    'receipt.attach_type_pod': 'POD',
    'receipt.attach_type_document': 'Document',
    'admin.email': 'Email',
    'admin.latency_ms': '{value} ms',
    'admin.email_placeholder': 'admin@example.com',
    'admin.password_placeholder': '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',
    'login.email_placeholder': 'admin@example.com',
    'login.password_placeholder': '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',
    'trip.speed_display': '{speed:.0f} km/h',
    'auth.login_brand': 'Operion',
    'auth.email_label': 'Email',
    'auth.register_brand': 'Operion',
}

# Apply translations to ro.json
def apply_translations(d, path=''):
    if isinstance(d, dict):
        for k in list(d.keys()):
            full_path = f'{path}.{k}' if path else k
            if full_path in translations:
                d[k] = translations[full_path]
            elif isinstance(d[k], (dict, list)):
                apply_translations(d[k], full_path)
    elif isinstance(d, list):
        for i, item in enumerate(d):
            full_path = f'{path}[{i}]'
            if full_path in translations:
                d[i] = translations[full_path]
            elif isinstance(item, (dict, list)):
                apply_translations(item, full_path)

apply_translations(ro)

# Write back
with open('data/translations/ro.json', 'w', encoding='utf-8') as f:
    json.dump(ro, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verify
with open('data/translations/ro.json', 'r', encoding='utf-8') as f:
    ro2 = json.load(f)
with open('data/translations/en.json', 'r', encoding='utf-8') as f:
    en2 = json.load(f)

unt2 = find_untranslated(en2, ro2)
print(f'Remaining untranslated: {len(unt2)}')
for p, v in unt2:
    print(f'  {p} = {repr(v)[:80]}')
