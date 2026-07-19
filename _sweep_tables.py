import sqlite3
conn = sqlite3.connect('data/cashflow.db')

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for t in tables:
    print(f'=== {t[0]} ===')
    cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
    for c in cols:
        print(f'  {c[1]:30s} {c[2]:15s}')
    print()
conn.close()
