import json

with open('data/translations/en.json', 'r', encoding='utf-8') as f:
    en = json.load(f)
with open('data/translations/ro.json', 'r', encoding='utf-8') as f:
    ro = json.load(f)

def find_untranslated(en_obj, ro_obj, path='', skip_empty=True):
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

untranslated = find_untranslated(en, ro)
print(f'Total untranslated keys: {len(untranslated)}')
for p, v in untranslated:
    safe = repr(v)[:120]
    print(f'  {p} = {safe}')

# Count how many are identical English/Romanian words vs. actual English needing translation
same_words = ['ERP', 'Calculator', 'EMAIL', 'Email', 'Status', 'km', 'General', 'KM', 'VIN', 'ID', 'Model', 
              'L/100km', 'PDF', 'Excel', 'EUR', 'Client', 'Profit', '\u20ac/km', 'Export PDF', 'Export Excel',
              'Altele', 'Net', 'Total', 'Relevante', 'Top 3', 'KM', 'Profit/KM', 'Top Client',
              'BRANDING', 'Google Maps', 'Export JSON', 'Export CSV', 'Total:', 'RO12345678',
              'J40/123/2023', '07xx xxx xxx', 'contact@firma.ro', 'Info', 'N/A', 'LIVE', 'ETA', 
              'Total Active', 'CSV', 'Telefon', 'CEO, Smith Logistics', 'Interval (km)', 'OK', 'Cost',
              'Feb', 'Mar', 'Apr', 'Aug', 'Sep', 'Oct', 'Dec', 'Rating (1-5)', 
              'Subtotal', 'Branding', 'Logo', 'Net 30', 'Net 15', 'Net 60',
              'EXPEDITOR / EXPEDITEUR', 'DESTINATAR / CONSIGNATAIRE',
              'LOCUL PREDARII MARFII / LIEU DE PRISE EN CHARGE',
              'LOCUL LIVRARII MARFII / LIEU DE LIVRAISON',
              'DOCUMENTE ANEXATE / DOCUMENTS ANNEXES',
              "INSTRUCTIUNILE EXPEDITORULUI / INSTRUCTIONS DE L'EXPEDITEUR",
              'REZERVARILE TRANSPORTATORULUI / RESERVES DU TRANSPORTEUR',
              'MODALITATEA DE PLATA / INSTRUCTION DE PAIEMENT',
              'PLATA LA LIVRARE / REMBOURSEMENT',
              'INTELEGERI SPECIALE / CONVENTIONS SPECIALES',
              'DISTANTA / DISTANCE', 'TRANSPORTATOR / TRANSPORTEUR',
              'EORI:', 'Tel:', 'Contact:', 'Email:', 'OCR', 'generated', 
              'admin@example.com', '{speed:.0f} km/h', 'Operion', 'Document',
              '{value} ms', 'POD', 'CMR', '0.00', 'Doc #{}',
              'Status:', '\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7\u00b7',
              'Mihai Popescu', 'Sarah M\u00fcller', 'John Smith']
