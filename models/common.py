from pydantic import BaseModel, ConfigDict
from typing import Optional, Generic, TypeVar
from datetime import datetime

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    total_pages: int


class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str
    code: str


class ErrorResponse(BaseModel):
    success: bool = False
    errors: list[ErrorDetail]
    message: str


class UndoToken(BaseModel):
    operation_id: str
    operation_type: str
    can_undo: bool = True
    undo_description: str = ""


class ServiceResult(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    errors: list[ErrorDetail] = []
    undo_token: Optional[UndoToken] = None


class OperationLog(BaseModel):
    operation: str
    duration_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: datetime
