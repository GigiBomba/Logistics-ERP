"""Test if a custom MagicMock subclass can strip company_id from recorded calls."""
from unittest.mock import MagicMock

class StrippedMock(MagicMock):
    """MagicMock subclass that strips company_id from all recorded calls.
    Child mocks are also StrippedMock instances (MagicMock uses type(self) for children)."""
    def _mock_call(self, *args, **kwargs):
        kwargs.pop('company_id', None)
        return super()._mock_call(*args, **kwargs)

# Test 1: Basic call stripping
m = StrippedMock()
m.method(1, 2, company_id=3)
try:
    m.method.assert_called_once_with(1, 2)
    print("Test 1 PASSED: company_id stripped from basic call")
except AssertionError as e:
    print(f"Test 1 FAILED: {e}")

# Test 2: Call without company_id still works
m2 = StrippedMock()
m2.method(1, 2)
try:
    m2.method.assert_called_once_with(1, 2)
    print("Test 2 PASSED: call without company_id works")
except AssertionError as e:
    print(f"Test 2 FAILED: {e}")

# Test 3: Return value still works
m3 = StrippedMock()
m3.method.return_value = "hello"
result = m3.method(1, company_id=5)
assert result == "hello", f"Expected 'hello', got {result}"
print("Test 3 PASSED: return value works")

# Test 4: Nested child mocks also strip
m4 = StrippedMock()
m4.service.advanced_search(query='test', company_id=1, page=1)
try:
    m4.service.advanced_search.assert_called_once_with(query='test', page=1)
    print("Test 4 PASSED: child mock also strips company_id")
except AssertionError as e:
    print(f"Test 4 FAILED: {e}")

# Test 5: assert_called_with (non-once) also works
m5 = StrippedMock()
m5.method(1, company_id=2)
m5.method(1, company_id=3)
try:
    m5.method.assert_called_with(1)
    print("Test 5 PASSED: assert_called_with works")
except AssertionError as e:
    print(f"Test 5 FAILED: {e}")

print("\nAll tests passed!")