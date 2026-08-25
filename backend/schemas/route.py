from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class RouteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = ""
    total_km: float = 0.0


class RouteResponse(RouteBase):
    model_config = ConfigDict(extra="ignore")

    id: int
    profile: str = ""
    created_at: str = ""


class RouteCalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: List[Union[Dict[str, float], str]] = Field(
        ..., min_length=2,
        description="At least 2 points: each can be a dict with 'lat'/'lng' or a place name string"
    )
    profile: str = Field(default="truck", max_length=50)
    excluded_countries: Optional[List[str]] = Field(
        default=None,
        description="ISO-3166-1 alpha-2 country codes to exclude from the route",
    )
