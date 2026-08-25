"""Simulate the EXACT request the browser sends during login."""
from __future__ import annotations

import os
import urllib.parse
import json
import urllib.request

# WARNING: Never hardcode production credentials. Always use env vars.
email = os.environ.get("OPERION_ADMIN_EMAIL", "admin@operionerp.xyz")
password = os.environ.get("OPERION_ADMIN_PASSWORD", "")

# Build form body like the browser does with URLSearchParams
params = urllib.parse.urlencode({
    "username": email,
    "password": password,
    "grant_type": "password",
})

print(f"URL-encoded body: {params[:100]}...")

# Send the request
req = urllib.request.Request(
    "https://api.operionerp.xyz/api/v1/auth/token",
    data=params.encode("utf-8"),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        print(f"Status: {resp.status}")
        body = resp.read().decode("utf-8")
        print(f"Body: {body}")
        data = json.loads(body)
        if "access_token" in data:
            print("\n*** LOGIN SUCCESS ***")
            print(f"Token: {data['access_token'][:50]}...")
except urllib.error.HTTPError as e:
    print(f"Status: {e.code}")
    body = e.read().decode("utf-8")
    print(f"Body: {body}")
except urllib.error.URLError as e:
    print(f"URL Error: {e.reason}")
