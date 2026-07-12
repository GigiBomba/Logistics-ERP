from typing import Any, Dict, List, Union

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
