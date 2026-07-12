"""OAuth2 client management (admin only)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from backend.oauth2 import OAuth2Service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth2", tags=["oauth2"])


@router.get("/clients")
async def list_clients(
    partner: str = None,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """List all registered OAuth2 clients, optionally filtered by partner."""
    service = OAuth2Service(db)
    clients = service.list_clients(partner)
    # Exclude secret_hash from the response
    safe_clients = []
    for c in clients:
        c.pop("secret_hash", None)
        safe_clients.append(c)
    return {"clients": safe_clients}


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def register_client(
    request: dict,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Register a new OAuth2 client.

    Returns the client_id and client_secret **only once**.
    The secret must be stored securely by the caller.
    """
    name = request.get("name", "").strip()
    partner = request.get("partner", "").strip()
    scopes = request.get("scopes", [])

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'name' is required.",
        )
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'partner' is required.",
        )

    service = OAuth2Service(db)
    client_id, client_secret = service.register_client(
        name=name,
        partner=partner,
        scopes=scopes,
    )

    logger.info(
        "Admin created OAuth2 client '%s' (partner=%s, id=%s)",
        name, partner, client_id,
    )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "warning": "Store this secret securely — it will not be shown again",
    }


@router.delete("/clients/{client_id}")
async def revoke_client(
    client_id: str,
    db=Depends(get_db),
    _=Depends(require_admin),
):
    """Revoke an OAuth2 client by its client_id."""
    service = OAuth2Service(db)
    service.revoke_client(client_id)
    return {"status": "revoked", "client_id": client_id}
