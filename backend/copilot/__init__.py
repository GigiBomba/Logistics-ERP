from __future__ import annotations

# Operion AI Co-Pilot — Natural-language interface to Operion ERP business logic.
#
# The Co-Pilot plans, validates, executes through existing services/repositories,
# and explains what happened. It never touches SQL, never manipulates widgets directly,
# and never bypasses permission or validation layers.
#
# Blueprint: Operion_AI_CoPilot_Blueprint_V4.md

# Install correlation-ID propagation on the copilot loggers at import time.
# Idempotent: install_copilot_logging() skips an already-attached filter.
from backend.copilot.telemetry import install_copilot_logging as _install_copilot_logging

_install_copilot_logging()
