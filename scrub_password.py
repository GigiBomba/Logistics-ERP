import os
import sys

# The password to remove
PASSWORD = "aF!81YYU2b>zLw5eJW7sGXM7Ri6Q7,Y3:zGzd^!ddMnjxkAHkcgduf}?w9tg*]N@sg]tN)Fy0k.q843}!d2_xZpW?MkCKPUC4qA7"

# Files to clean
FILES = [
    "tests/test_api/test_api_auth.py",
    "tests/test_api/test_api_admin.py",
    "tests/e2e/test_e2e_api_flows.py",
]

for filepath in FILES:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        if PASSWORD in content:
            content = content.replace(PASSWORD, "CHANGE_ME")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Cleaned: {filepath}")
        else:
            print(f"No match: {filepath}")
    else:
        print(f"Not found: {filepath}")
