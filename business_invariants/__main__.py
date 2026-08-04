#!/usr/bin/env python3
"""
CLI entry point: python -m business_invariants <command>

Delegates to business_invariants.cli:main().
"""

from __future__ import annotations

import sys

from business_invariants.cli import main

if __name__ == "__main__":
    sys.exit(main())
