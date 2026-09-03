#!/usr/bin/env python
"""Operion AI Co-Pilot — no-live-call provider usability report.

Prints which LLM providers (``self_hosted``, ``google``) are usable per the
CURRENT environment: instance config (endpoint / model / api_mode), the env
signals the providers actually read (``OPERION_GEMINI_API_KEY`` /
``GOOGLE_API_KEY`` for google; ``OPERION_QWEN_API_KEY`` for self_hosted), and
the resolved tool-catalog size.

No live network calls are made — this is a static readiness report, safe to
run in CI or on a dev machine.  Runnable standalone:

    python scripts/copilot_provider_health.py

Exits 0 on a successful report (unusable providers are a valid report), 1 on
an unexpected failure to assemble it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _env_flag(name: str) -> str:
    return "set" if os.environ.get(name) else "unset"


def main() -> int:
    try:
        from backend.copilot.llm.chat import _provider_usable
        from backend.copilot.llm.registry import get_provider
        from backend.copilot.planner import _ensure_llm_providers_loaded, _ensure_tools_loaded
        from backend.copilot.tools.registry import all_tools
    except Exception as exc:  # pragma: no cover — broken install
        print(f"[FAIL] could not import copilot modules: {exc}")
        return 1

    _ensure_tools_loaded()
    _ensure_llm_providers_loaded()

    print("Operion AI Co-Pilot — Provider Usability Report")
    print("=" * 52)

    tools = all_tools()
    non_deprecated = [t for t in tools if not getattr(t, "deprecated", False)]
    print(f"Tool registry     : {len(tools)} tools ({len(non_deprecated)} non-deprecated)")

    # ── self_hosted (OcrAIProvider) ───────────────────────────────────────
    sh = get_provider("self_hosted")
    if sh is not None:
        usable = _provider_usable(sh)
        print("-" * 52)
        print("Provider: self_hosted (OcrAIProvider)")
        print(f"  usable         : {'YES' if usable else 'no'}")
        print(f"  api_mode       : {getattr(sh, '_api_mode', 'openai')}")
        print(f"  endpoint       : {getattr(sh, '_endpoint', '?')}")
        print(f"  model          : {getattr(sh, 'model_id', '?')}")
        print(f"  api_key        : {'yes' if getattr(sh, '_api_key', '') else 'no'} "
              f"(env OPERION_QWEN_API_KEY={_env_flag('OPERION_QWEN_API_KEY')})")
        print(f"  reload keys    : qwen_endpoint / qwen_model / qwen_api_mode / qwen_api_key")

    # ── google (GoogleProvider) ───────────────────────────────────────────
    ggl = get_provider("google")
    if ggl is not None:
        usable = _provider_usable(ggl)
        print("-" * 52)
        print("Provider: google (GoogleProvider)")
        print(f"  usable         : {'YES' if usable else 'no'}")
        print(f"  model          : {getattr(ggl, 'model_id', '?')}")
        print(f"  api_key        : {'yes' if getattr(ggl, '_api_key', '') else 'no'} (instance)")
        print(f"  env keys       : OPERION_GEMINI_API_KEY={_env_flag('OPERION_GEMINI_API_KEY')} / "
              f"GOOGLE_API_KEY={_env_flag('GOOGLE_API_KEY')}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("-" * 52)
    usable_count = sum(
        1
        for pid in ("self_hosted", "google")
        if get_provider(pid) is not None and _provider_usable(get_provider(pid))
    )
    print(f"Usable providers : {usable_count}/2")
    return 0


if __name__ == "__main__":
    sys.exit(main())