"""Batch replace create_app() with create_test_app() and add import in test_api files."""
from __future__ import annotations

import os, re, glob

test_api_dir = "tests/test_api"
files = sorted(glob.glob(os.path.join(test_api_dir, "test_*.py")))

# Files that use create_app()
target_files = [
    "test_api_admin.py", "test_api_auth.py", "test_api_auth_reset.py", "test_api_cache.py",
    "test_api_documents.py", "test_api_document_read.py", "test_api_gps.py", "test_api_health.py",
    "test_api_registration.py", "test_auth_e2e.py", "test_middleware_integration.py",
    "test_mobile_additional.py", "test_mobile_data_flow.py", "test_mobile_endpoints.py",
    "test_mobile_mutation.py",
]

for fname in target_files:
    fpath = os.path.join(test_api_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Replace create_app() with create_test_app()
    content = content.replace("create_app()", "create_test_app()")
    
    # Add import if we made changes and don't already have it
    if content != original and "create_test_app" not in content.split("create_test_app()")[0]:
        # Find the last import line and add after it
        lines = content.split("\n")
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                last_import_idx = i
        
        # Check if import already exists
        has_import = any("from tests.test_api.helpers import create_test_app" in line for line in lines)
        if not has_import:
            lines.insert(last_import_idx + 1, "from tests.test_api.helpers import create_test_app")
            content = "\n".join(lines)
    
    if content != original:
        with open(fpath, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"  Fixed {fname}")

print("Done!")
