import os
os.environ["OPERION_API_KEY"] = "test"
os.environ["OPERION_ENCRYPTION_KEY"] = "test-key-32-chars-long-for-test!!"
os.environ["OPERION_ENV"] = "test"
from backend.main import app
from fastapi.routing import _IncludedRouter

print("=== app.routes ===")
for r in app.routes:
    name = type(r).__name__
    path = getattr(r, "path", "N/A")
    print(f"  {name}: {path}")
    if isinstance(r, _IncludedRouter):
        print(f"    effective_route_contexts:")
        for ctx in r.effective_route_contexts():
            sr = ctx.starlette_route
            print(f"      {type(sr).__name__}: {getattr(sr, 'path', 'N/A')} (methods: {getattr(sr, 'methods', 'N/A')})")
            or_ = ctx.original_route
            print(f"        original: {type(or_).__name__}: {getattr(or_, 'path', 'N/A')}")
