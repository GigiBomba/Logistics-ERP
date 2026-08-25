"""Batch-fix mock assertions that are missing the company_id kwarg.
This is needed because route handlers now pass company_id=... to service methods
for multi-tenant isolation.
"""
from __future__ import annotations

import os, glob, re

test_api_dir = "tests/test_api"
files = sorted(glob.glob(os.path.join(test_api_dir, "test_*.py")))

total_fixed = 0
for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Fix patterns like:
    #   mock.advanced_search.assert_called_once_with(query='test', ...)
    # Add company_id=ANY before the closing paren
    
    # Pattern 1: assert_called_once_with(...) without company_id
    # Add company_id=unittest.mock.ANY if not present
    if "company_id" not in content:
        # Add import for ANY if needed
        if "from unittest.mock import" in content or "from unittest.mock import ANY" not in content:
            # Add ANY to existing imports
            content = re.sub(
                r"(from unittest\.mock import.*?)([^)]*)\)",
                lambda m: m.group(0).rstrip(")") + ", ANY)" if "ANY" not in m.group(0) else m.group(0),
                content,
                count=1
            )
    
    if content != original:
        total_fixed += 1
        with open(fpath, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"  Fixed imports in {os.path.basename(fpath)}")

print(f"\nFixed {total_fixed} files")
