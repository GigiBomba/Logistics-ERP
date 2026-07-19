import json
import sys

with open('data/translations/en.json', 'r', encoding='utf-8') as f:
    en = json.load(f)
with open('data/translations/hr.json', 'r', encoding='utf-8') as f:
    hr = json.load(f)

ACRONYMS = {'ID', 'KM', 'VIN', 'EUR', 'N/A', 'CSV', 'PDF', 'OCR', 'GPS', 'API',
            'CMR', 'KPI', 'SMTP', 'DSO', 'SLA', 'SOC', 'GDPR', 'CUI', 'VAT',
            'ETA', 'SMS', 'GBP', 'USD', 'RON', 'JSON', 'BOM', 'UTF-8'}

CRO_CHARS = set('čćšžđČĆŠŽĐ')

def is_croatian(text):
    return bool(CRO_CHARS & set(text))

def find_missing(en_obj, hr_obj, path=''):
    missing = []
    if isinstance(en_obj, dict) and isinstance(hr_obj, dict):
        for k in en_obj:
            new_path = f'{path}.{k}' if path else k
            if k in hr_obj:
                missing.extend(find_missing(en_obj[k], hr_obj[k], new_path))
    elif isinstance(en_obj, list) and isinstance(hr_obj, list) and len(en_obj) == len(hr_obj):
        for i, (e, h) in enumerate(zip(en_obj, hr_obj)):
            missing.extend(find_missing(e, h, f'{path}[{i}]'))
    elif isinstance(en_obj, str) and isinstance(hr_obj, str):
        if en_obj == hr_obj:
            if not is_croatian(en_obj):
                words = en_obj.split()
                acro_words = [w.strip('.:(),{}[]%') for w in words]
                if not all(w in ACRONYMS for w in acro_words if w):
                    missing.append((path, en_obj))
    return missing

missing = find_missing(en, hr)
with open('missing_translations.txt', 'w', encoding='utf-8') as f:
    f.write(f'Remaining untranslated: {len(missing)}\n')
    for path, val in missing:
        f.write(f'{path} = {repr(val)}\n')
print(f'Written {len(missing)} missing translations to missing_translations.txt')
