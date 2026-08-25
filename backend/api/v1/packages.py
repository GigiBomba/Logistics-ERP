"""Customer package API router — pipeline package row persistence.

Remote-mode counterpart of ``PipelineRepository``'s package methods
(``create_package`` / ``update_package`` / ``get_package_by_id``) used by
the email composer modal.
"""
from __future__ import annotations


from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_db
from backend.dependencies_security import require_dispatcher
from database.db_manager import DatabaseManager
from repositories.pipeline_repository import PipelineRepository
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/packages", tags=["packages"])


class PackageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: Optional[int] = None
    package_uuid: Optional[str] = None


class PackageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    email_message_id: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/", response_model=Dict[str, int])
def create_package(
    data: PackageCreateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    package_id = PipelineRepository(db).create_package(
        trip_id=data.trip_id,
        package_uuid=data.package_uuid,
    )
    return {"id": package_id}


@router.get("/{package_id}")
def get_package(
    package_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    row = PipelineRepository(db).get_package_by_id(package_id)
    if not row:
        raise HTTPException(status_code=404, detail="Package not found")
    return row


@router.put("/{package_id}")
def update_package(
    package_id: int,
    data: PackageUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    db: DatabaseManager = Depends(get_db),
):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    PipelineRepository(db).update_package(package_id, **fields)
    return {"status": "updated"}
