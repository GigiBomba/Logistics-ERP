"""Check translation coverage across ALL 21 non-en files."""
import json, os

DIR = "data/translations"

def flat(d, p=""):
    items = {}
    for k, v in d.items():
        key = f"{p}.{k}" if p else k
        if isinstance(v, dict):
            items.update(flat(v, key))
        else:
            items[key] = str(v)
    return items

en = json.load(open(os.path.join(DIR, "en.json"), "r", encoding="utf-8-sig"))
en_f = flat(en)
total = len(en_f)

results = []
for fname in sorted(os.listdir(DIR)):
    if fname == "en.json" or not fname.endswith(".json"):
        continue
    lang = json.load(open(os.path.join(DIR, fname), "r", encoding="utf-8-sig"))
    lang_f = flat(lang)
    untrans = sum(1 for k, v in lang_f.items() if v == en_f.get(k, ""))
    translated = total - untrans
    pct = 100 * translated / total
    results.append((fname, translated, untrans, pct))

results.sort(key=lambda x: x[3])  # sort by worst first
print(f"Total keys (en.json): {total}")
print()
print(f"{'File':12s} {'Translated':>10s} {'Untranslated':>12s} {'Coverage':>10s}")
print("-" * 48)
for fname, tr, un, pct in results:
    print(f"{fname:12s} {tr:>10d} {un:>12d} {pct:>9.1f}%")
print("-" * 48)
total_tr = sum(r[1] for r in results)
total_un = sum(r[2] for r in results)
print(f"{'TOTAL':12s} {total_tr:>10d} {total_un:>12d} {100*total_tr/(total*21):>9.1f}%")
