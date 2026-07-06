from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 0
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    total_pages: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
