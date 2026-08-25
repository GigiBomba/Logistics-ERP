"""Check what tables and columns the test DB has."""
from __future__ import annotations

import sys
sys.path.insert(0, '.')
from tests.test_helpers import make_db
db = make_db()
tables = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('Tables:', [t[0] for t in tables])
for tbl in ['clients', 'trips', 'documents', 'trucks', 'drivers', 'companies', 'users']:
    cols = db.conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    print(f'{tbl} columns:', [(c[1], c[2]) for c in cols])
db.close()
