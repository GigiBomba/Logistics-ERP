from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = 0
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    items: List[T]
    total: int
    total_pages: int


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    error_code: Optional[str] = None
