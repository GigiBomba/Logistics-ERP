#!/bin/bash
sed -i 's/aF!81YYU2b>zLw5eJW7sGXM7Ri6Q7,Y3:zGzd^!ddMnjxkAHkcgduf}?w9tg*]N@sg]tN)Fy0k.q843}!d2_xZpW?MkCKPUC4qA7/CHANGE_ME/g' tests/test_api/test_api_auth.py tests/test_api/test_api_admin.py tests/e2e/test_e2e_api_flows.py 2>/dev/null || true
