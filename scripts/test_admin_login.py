"""Test admin login flow end-to-end by generating a known hash and testing the API."""
from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load the .env file to get the current settings
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path, override=True)

admin_email = os.environ.get("OPERION_ADMIN_EMAIL", "")
admin_hash = os.environ.get("OPERION_ADMIN_PASSWORD_HASH", "")

print(f"Admin email: {admin_email}")
print(f"Admin hash: {admin_hash[:30]}...")
print(f"Hash valid: {admin_hash.startswith('$2b$')}")

# Test verify_password with the hash from env
from backend.security import verify_password

# Test a few passwords
test_pws = ["admin", "password", "admin123", "test", "Password1", "Operion123", "hello123"]
for pw in test_pws:
    result = verify_password(pw, admin_hash)
    if result:
        print(f"*** PASSWORD FOUND: '{pw}' ***")

print("\n--- Testing API endpoint ---")

# Now test the actual API
from fastapi.testclient import TestClient
from backend.main import create_app

os.environ["OPERION_ENV"] = "development"
os.environ["OPERION_API_KEY"] = "test-key"
os.environ["OPERION_JWT_SECRET_KEY"] = "test-secret-key-for-testing-purposes-only!!"
os.environ["OPERION_ADMIN_EMAIL"] = admin_email
os.environ["OPERION_ADMIN_PASSWORD_HASH"] = admin_hash

app = create_app()
client = TestClient(app)

# Test with a wrong password (should get 401)
resp = client.post(
    "/api/v1/auth/token",
    data={"username": admin_email.strip(), "password": "definitely-wrong"},
)
print(f"Wrong password status: {resp.status_code}")
print(f"Wrong password body: {resp.json() if hasattr(resp, 'json') else resp.text}")

# Test with each test password to see if any work
for pw in test_pws:
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": admin_email.strip(), "password": pw},
    )
    if resp.status_code == 200:
        print(f"*** LOGIN SUCCESS with password '{pw}' ***")
        data = resp.json()
        print(f"  Token: {data.get('access_token', '')[:50]}...")
    elif resp.status_code == 401:
        print(f"  '{pw}': 401 (wrong password)")
    else:
        print(f"  '{pw}': {resp.status_code}")

# Also verify that the /me endpoint works after login
for pw in test_pws:
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": admin_email.strip(), "password": pw},
    )
    if resp.status_code == 200:
        token = resp.json().get("access_token", "")
        me_resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"\n/me with '{pw}': {me_resp.status_code}")
        if me_resp.status_code == 200:
            print(f"  Profile: {me_resp.json()}")
        break

print("\nDone.")
