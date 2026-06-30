"""GraphHopper profile name mapping for Route Planner UI."""

from config import Config

GRAPHHOPPER_PROFILES = Config.GRAPHHOPPER_PROFILES


def ui_label_for_profile(gh_profile: str) -> str:
    reverse = {v: k for k, v in GRAPHHOPPER_PROFILES.items()}
    return reverse.get(gh_profile, gh_profile or "Recommended")


def gh_profile_for_ui_label(label: str) -> str:
    return GRAPHHOPPER_PROFILES.get(label, "truck")
