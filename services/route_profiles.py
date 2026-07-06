"""GraphHopper profile name mapping for Route Planner UI.

Retained for backward compatibility. New code should import from
``utils.labels`` directly.
"""

from utils.labels import (  # noqa: F401
    GRAPHHOPPER_PROFILES,
    gh_profile_for_ui_label,
    ui_label_for_profile,
)
