import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Response

logger = logging.getLogger(__name__)

from backend.dependencies import get_payment_profile_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.payment_profile import (
    PaymentProfileCreate,
    PaymentProfileResponse,
    PaymentProfileUpdate,
)
from services.payment_profile_service import PaymentProfileService

from backend.dependencies_security import require_dispatcher

router = APIRouter(prefix="/payment-profiles", tags=["payment-profiles"])


class PaymentProfileListResponse(PaginatedResponse[PaymentProfileResponse]):
    """Paginated list of payment profiles."""


@router.get("/", response_model=PaymentProfileListResponse)
def list_payment_profiles(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    query: str = Query("", description="Search query"),
    include_inactive: bool = Query(False),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    service: PaymentProfileService = Depends(get_payment_profile_service),
):
    """Return paginated list of payment profiles."""
    try:
        if query:
            items = service.search(query, limit=page_size)
        else:
            items = service.get_all(include_inactive=include_inactive, limit=page_size)
        return PaginatedResponse.from_items(
            items=[PaymentProfileResponse(**p) for p in items],
            total=len(items),
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")


@router.get("/{profile_id}", response_model=PaymentProfileResponse)
def get_payment_profile(
    profile_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentProfileService = Depends(get_payment_profile_service),
):
    try:
        profile = service.get_by_id(profile_id)
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")
    if not profile:
        raise HTTPException(status_code=404, detail="Payment profile not found")
    return PaymentProfileResponse(**profile)


@router.post("/", response_model=Dict[str, int], status_code=201)
def create_payment_profile(
    data: PaymentProfileCreate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentProfileService = Depends(get_payment_profile_service),
):
    try:
        profile_id = service.create(data.model_dump())
        return {"id": profile_id}
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")


@router.patch("/{profile_id}")
def update_payment_profile_partial(
    profile_id: int,
    data: PaymentProfileUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentProfileService = Depends(get_payment_profile_service),
):
    """Partially update a payment profile (PATCH)."""
    try:
        existing = service.get_by_id(profile_id)
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")
    if not existing:
        raise HTTPException(status_code=404, detail="Payment profile not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        try:
            service.update(profile_id, update_fields)
        except Exception as exc:
            logger.exception("Operation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Operation failed")
    return {"status": "updated"}


@router.put("/{profile_id}", deprecated=True)
def update_payment_profile(
    profile_id: int,
    data: PaymentProfileUpdate,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentProfileService = Depends(get_payment_profile_service),
    response: Response = None,
):
    """[DEPRECATED] Use PATCH /{profile_id} instead."""
    try:
        existing = service.get_by_id(profile_id)
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")
    if not existing:
        raise HTTPException(status_code=404, detail="Payment profile not found")
    update_fields = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_fields:
        try:
            service.update(profile_id, update_fields)
        except Exception as exc:
            logger.exception("Operation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Operation failed")
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Tue, 12 Jan 2027 00:00:00 GMT"
    return {"status": "updated"}


@router.delete("/{profile_id}")
def delete_payment_profile(
    profile_id: int,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentProfileService = Depends(get_payment_profile_service),
):
    try:
        existing = service.get_by_id(profile_id)
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")
    if not existing:
        raise HTTPException(status_code=404, detail="Payment profile not found")
    try:
        service.delete(profile_id)
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")
    return {"status": "deleted"}
