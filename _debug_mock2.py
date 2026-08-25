"""Debug: check _increment_mock_call and find where calls are recorded."""
from __future__ import annotations

from unittest.mock import MagicMock
import inspect

print("_increment_mock_call signature:", inspect.signature(MagicMock._increment_mock_call))
print("\n_increment_mock_call source:")
try:
    print(inspect.getsource(MagicMock._increment_mock_call))
except Exception as e:
    print(f"  Cannot get source: {e}")

# Also check _mock_check_sig
print("\n_mock_check_sig signature:", inspect.signature(MagicMock._mock_check_sig))
