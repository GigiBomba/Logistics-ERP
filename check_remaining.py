import json

with open('data/translations/en.json', 'r', encoding='utf-8') as f:
    en = json.load(f)
with open('data/translations/ro.json', 'r', encoding='utf-8') as f:
    ro = json.load(f)

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

en_f = flat(en)
ro_f = flat(ro)

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

untranslated = []
acronym_only = 0
for k, v in sorted(ro_f.items()):
    if k in en_f and v == en_f[k]:
        if should_translate(v):
            untranslated.append((k, v))
        else:
            acronym_only += 1

with open(r'C:\Users\Bonjo\AppData\Local\Temp\opencode\remaining.txt', 'w', encoding='utf-8') as f:
    f.write(f'Untranslated (should translate): {len(untranslated)}\n')
    f.write(f'Skipped (acronym only): {acronym_only}\n\n')
    for k, v in untranslated:
        f.write(f'{k} = {repr(v)}\n')
    f.write('\n\n--- Acronym-skipped ---\n\n')
    for k, v in sorted(ro_f.items()):
        if k in en_f and v == en_f[k]:
            if not should_translate(v):
                f.write(f'{k} = {repr(v)}\n')

print('Done')
