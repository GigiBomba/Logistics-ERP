import sqlite3
conn = sqlite3.connect('data/cashflow.db')

# Check vehicle_documents table
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%vehicle%' ORDER BY name").fetchall()
print("=== Vehicle-related tables ===")
for t in tables:
    print(t[0])
    cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
    for c in cols:
        print(f"  {c[1]:30s} {c[2]:15s}")
    print()

conn.close()
