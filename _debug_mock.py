"""Debug: check how MagicMock creates child mocks and what method to override."""
from __future__ import annotations

from unittest.mock import MagicMock
import inspect

# Check the actual _mock_call signature
print("_mock_call signature:", inspect.signature(MagicMock._mock_call))

# Check what type child mocks are
m = MagicMock()
child = m.method
print(f"Child mock type: {type(child).__name__}")
print(f"Child mock is MagicMock: {isinstance(child, MagicMock)}")

# Check if type(self) is used for children
class MyMock(MagicMock):
    pass

m2 = MyMock()
child2 = m2.method
print(f"Custom child mock type: {type(child2).__name__}")
print(f"Custom child is MyMock: {isinstance(child2, MyMock)}")

# Check __call__ source
print("\n__call__ method:")
print(inspect.getsource(MagicMock.__call__))
