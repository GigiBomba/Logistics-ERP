from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class CmrGenerateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    trip_data: Dict[str, Any] = Field(..., description="Trip data used for CMR generation")
