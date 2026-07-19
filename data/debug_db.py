"""Debug script to check database state."""
import os
import bcrypt
import sqlite3
from datetime import datetime, timezone

TEST_DB = os.path.join(os.path.dirname(__file__), "test_mobile_api.db")
# Clean it
for s in ("", "-wal", "-shm"):
    p = TEST_DB + s
    if os.path.isfile(p):
        os.remove(p)

# Set env
os.environ["OPERION_DB_PATH"] = TEST_DB
os.environ["OPERION_ENV"] = "test"
os.environ["OPERION_JWT_SECRET_KEY"] = "test-secret-key-32-chars-for-testing-only!!"

from database.db_manager import DatabaseManager

db = DatabaseManager(TEST_DB)
now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

admin_hash = bcrypt.hashpw(b"test-admin-pw-123", bcrypt.gensalt(rounds=4)).decode()
disp_hash = bcrypt.hashpw(b"dispatcher-pw-456", bcrypt.gensalt(rounds=4)).decode()
driver_hash = bcrypt.hashpw(b"driver-pw-789", bcrypt.gensalt(rounds=4)).decode()

# Companies
db.execute(
    "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier, is_active, created_at, updated_at) "
    "VALUES (1, 'Test Company', 'professional', 1, ?, ?)",
    (now, now),
)

# Users
db.execute(
    "INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id, is_active, created_at) "
    "VALUES (1, 'admin@test.com', ?, 'admin', 1, 1, ?)",
    (admin_hash, now),
)
db.execute(
    "INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id, is_active, created_at) "
    "VALUES (2, 'dispatcher@test.com', ?, 'dispatcher', 1, 1, ?)",
    (disp_hash, now),
)
db.execute(
    "INSERT OR IGNORE INTO users (id, email, password_hash, role, company_id, is_active, created_at) "
    "VALUES (3, 'driver@test.com', ?, 'driver', 1, 1, ?)",
    (driver_hash, now),
)

db.conn.commit()

# Verify users exist
rows = db.execute("SELECT id, email, role, is_active FROM users").fetchall()
print("Users in DB:")
for r in rows:
    d = dict(r)
    print(f"  id={d['id']} email={d['email']} role={d['role']} is_active={d['is_active']}")

# Check password verification
from backend.security import verify_password

for r in rows:
    u = dict(r)
    stored_hash = db.execute("SELECT password_hash FROM users WHERE id=?", (u["id"],)).fetchone()[0]
    valid = verify_password("dispatcher-pw-456", stored_hash)
    print(f"  {u['email']} pw check (dispatcher-pw-456): {valid}")

# Check admin pw
for r in rows:
    u = dict(r)
    if u["role"] == "admin":
        stored_hash = db.execute("SELECT password_hash FROM users WHERE id=?", (u["id"],)).fetchone()[0]
        valid = verify_password("test-admin-pw-123", stored_hash)
        print(f"  {u['email']} pw check (test-admin-pw-123): {valid}")

# Verify with new connection
print("\nVerifying with sqlite3 directly:")
conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT id, email, role, is_active FROM users").fetchall()
for r in rows:
    d = dict(r)
    print(f"  id={d['id']} email={d['email']} role={d['role']} is_active={d['is_active']}")
conn.close()

db.close()
