import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from backend.dependencies import get_payment_batch_service
from backend.schemas.common import PaginatedResponse
from backend.schemas.payment_profile import PaymentBatchRequest
from backend.services.payment_batch_service import PaymentBatchService

from backend.dependencies_security import require_dispatcher

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/recipients", response_model=PaginatedResponse[dict])
def list_recipients(
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    query: str = Query("", description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    service: PaymentBatchService = Depends(get_payment_batch_service),
):
    """Get paginated list of payment recipients (clients + drivers + custom profiles) that have payment info."""
    try:
        company_id = current_user.get("company_id", 0)
        recipients = service.get_all_recipients(query=query, company_id=company_id)
        return PaginatedResponse.from_items(items=recipients, total=len(recipients), page=page, page_size=page_size)
    except Exception as exc:
        logger.exception("Operation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Operation failed")


@router.post("/export-csv")
def export_batch_csv(
    data: PaymentBatchRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentBatchService = Depends(get_payment_batch_service),
):
    """Export a payment batch as a banking CSV file.
    
    Accepts a list of PaymentBatchItem objects, resolves banking details from the database,
    and returns a CSV file for download.
    """
    try:
        items = [item.model_dump() for item in data.items]
        csv_content = service.build_batch_csv_from_request(items)
        filename = (data.batch_name or "payment_batch").replace(" ", "_")
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.csv",
            },
        )
    except Exception as exc:
        logger.exception("Export failed: %s", exc)
        raise HTTPException(status_code=500, detail="Export failed")


@router.post("/validate-recipient")
def validate_recipient(
    recipient_id: int = Query(...),
    recipient_type: str = Query(..., description="One of: client, driver, custom, government, supplier, contractor, other"),
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentBatchService = Depends(get_payment_batch_service),
):
    """Validate that a recipient has sufficient payment information for export."""
    try:
        company_id = current_user.get("company_id", 0)
        errors = service.validate_recipient_payment_info(recipient_id, recipient_type, company_id=company_id)
        return {"valid": len(errors) == 0, "errors": errors}
    except Exception as exc:
        logger.exception("Validation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Validation failed")


@router.post("/export-csv-direct")
def export_batch_csv_direct(
    data: PaymentBatchRequest,
    current_user: Dict[str, Any] = Depends(require_dispatcher),
    service: PaymentBatchService = Depends(get_payment_batch_service),
):
    """Export pre-resolved batch items as CSV directly (items already contain bank info).
    
    Use this when the frontend has already collected all banking details for each item
    and doesn't need backend resolution.
    """
    try:
        company_id = current_user.get("company_id", 0)
        items = [item.model_dump() for item in data.items]
        csv_content = service.build_batch_csv(items, company_id=company_id)
        filename = (data.batch_name or "payment_batch").replace(" ", "_")
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.csv",
            },
        )
    except Exception as exc:
        logger.exception("Export failed: %s", exc)
        raise HTTPException(status_code=500, detail="Export failed")
