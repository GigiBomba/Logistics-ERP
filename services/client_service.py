"""Client service — business logic for client management."""
import logging
import warnings
from typing import Any, Optional

from repositories.client_repository import ClientRepository
from repositories.contact_repository import ContactRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.tag_repository import TagRepository
from services.operations.event_bus import EventBus

from models.client_models import (
    ClientContact,
    ClientCreate,
    ClientCreateResult,
    ClientListResult,
    ClientResult,
    ClientUpdate,
)
from models.common import ErrorDetail, ServiceResult
from services.permission_service import PermissionService

logger = logging.getLogger(__name__)

CLIENT_MERGED = "CLIENT_MERGED"

ClientUpdateResult = ServiceResult[ClientResult]


class ClientService:
    def __init__(self, db):
        self.db = db
        self._repo = ClientRepository(db)
        self._inv_repo = InvoiceRepository(db)
        self._contact_repo = ContactRepository(db)
        self._tag_repo = TagRepository(db)
        self._event_bus = EventBus()

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _dict_to_client_result(d: Optional[dict]) -> Optional[ClientResult]:
        """Convert a raw repo dict to a typed ClientResult (or None)."""
        if d is None:
            return None
        return ClientResult(**d)

    def _check_permission(self, perm_check: str, user_id: int) -> None:
        """Resolve a PermissionService method by name and raise on denial."""
        perm = PermissionService(self.db)
        method = getattr(perm, perm_check, None)
        if method is None:
            raise ValueError(f"Unknown permission check: {perm_check}")
        result = method(user_id)
        if not result.allowed:
            raise PermissionError(result.reason)

    # ── New typed CRUD methods ──────────────────────────────────────────────

    def create(self, request=None, user_id=None, company_id=None, **kwargs):
        """Create a new client.

        New API (preferred)::

            svc.create(ClientCreate(name="…"), user_id=42) -> ClientCreateResult

        Legacy API (deprecated)::

            svc.create(name, **fields) -> int
        """
        if isinstance(request, ClientCreate):
            # ── New typed path ──────────────────────────────────────────
            if user_id is None:
                raise ValueError("user_id is required for the typed create() API")
            self._check_permission("can_create_client", user_id)

            data = request.model_dump()  # includes defaults for all optional fields
            client_id = self._repo.create(data)
            client_dict = self._repo.get_by_id(client_id)
            return ClientCreateResult(
                success=True,
                data=self._dict_to_client_result(client_dict),
            )

        # ── Legacy backward-compat path ─────────────────────────────────
        warnings.warn(
            "create(name, **kwargs) is deprecated — "
            "use create(ClientCreate(...), user_id=...)",
            DeprecationWarning,
            stacklevel=2,
        )
        name = request or kwargs.pop("name", None)
        if name is None:
            raise ValueError("name is required for legacy create()")
        data: dict[str, Any] = {"name": name}
        # Only pass columns the repository supports (the Pydantic schema may
        # contain fields like ``city`` and ``company_code`` that are not in
        # the DB table — see ClientCreateRequest/ClientRepository.COLUMNS).
        allowed = set(self._repo.COLUMNS) if hasattr(self._repo, "COLUMNS") else set()
        if allowed:
            data.update((k, v) for k, v in kwargs.items() if k in allowed)
        else:
            data.update(kwargs)
        return self._repo.create(data)

    def update(self, client_id, request=None, user_id=None, company_id=None, **kwargs):
        """Update an existing client.

        New API (preferred)::

            svc.update(1, ClientUpdate(phone="…"), user_id=42) -> ClientUpdateResult

        Legacy API (deprecated)::

            svc.update(client_id, **fields) -> None
        """
        if isinstance(request, ClientUpdate):
            # ── New typed path ──────────────────────────────────────────
            if user_id is None:
                raise ValueError("user_id is required for the typed update() API")
            self._check_permission("can_update_client", user_id)

            data = request.model_dump(exclude_unset=True, exclude_none=True)
            if not data:
                return ClientUpdateResult(
                    success=False,
                    errors=[ErrorDetail(message="No fields to update", code="EMPTY_UPDATE")],
                )
            self._repo.update(client_id, data)
            client_dict = self._repo.get_by_id(client_id)
            return ClientUpdateResult(
                success=True,
                data=self._dict_to_client_result(client_dict),
            )

        # ── Legacy backward-compat path ─────────────────────────────────
        warnings.warn(
            "update(client_id, **kwargs) is deprecated — "
            "use update(client_id, ClientUpdate(...), user_id=...)",
            DeprecationWarning,
            stacklevel=2,
        )
        all_kwargs: dict[str, Any] = {}
        if request is not None:
            all_kwargs.update(request.__dict__ if hasattr(request, "__dict__") else request)
        all_kwargs.update(kwargs)
        self._repo.update(client_id, all_kwargs)

    def get(self, client_id: int) -> ClientCreateResult:
        """Get a single client by ID, returning a typed result.

        For the raw dict variant use :meth:`get_by_id` (legacy).
        """
        client_dict = self._repo.get_by_id(client_id)
        if client_dict is None:
            return ClientCreateResult(
                success=False,
                errors=[ErrorDetail(message="Client not found", code="NOT_FOUND")],
            )
        return ClientCreateResult(
            success=True,
            data=self._dict_to_client_result(client_dict),
        )

    def list_all(self, include_inactive: bool = False) -> ClientListResult:
        """List all clients as a typed result.

        For the raw list-of-dicts variant use :meth:`get_all` (legacy).
        """
        clients = self._repo.get_all(include_inactive=include_inactive)
        return ClientListResult(
            success=True,
            data=[self._dict_to_client_result(c) for c in clients],
        )

    def delete(self, client_id: int, user_id: int) -> ClientCreateResult:
        """Deactivate a client (soft-delete). Admin only."""
        self._check_permission("can_delete_client", user_id)

        client_dict = self._repo.get_by_id(client_id)
        if client_dict is None:
            return ClientCreateResult(
                success=False,
                errors=[ErrorDetail(message="Client not found", code="NOT_FOUND")],
            )
        self._repo.deactivate(client_id)
        client_dict["is_active"] = 0
        return ClientCreateResult(
            success=True,
            data=self._dict_to_client_result(client_dict),
        )

    # ── Contact management ─────────────────────────────────────────────────

    def add_contact(self, client_id, contact=None, user_id=None, company_id=None, **kwargs):
        """Add a contact to a client.

        New API (preferred)::

            svc.add_contact(1, ClientContact(name="…"), user_id=42) -> ClientCreateResult

        Legacy API (deprecated)::

            svc.add_contact(client_id, **fields) -> int
        """
        if isinstance(contact, ClientContact):
            # ── New typed path ──────────────────────────────────────────
            if user_id is None:
                raise ValueError("user_id is required for the typed add_contact() API")
            self._check_permission("can_update_client", user_id)

            # Verify the client exists
            client_dict = self._repo.get_by_id(client_id)
            if client_dict is None:
                return ClientCreateResult(
                    success=False,
                    errors=[ErrorDetail(message="Client not found", code="NOT_FOUND")],
                )

            contact_data = contact.model_dump()
            contact_data["client_id"] = client_id
            self._contact_repo.create(contact_data)

            # Return the updated client
            client_dict = self._repo.get_by_id(client_id)
            return ClientCreateResult(
                success=True,
                data=self._dict_to_client_result(client_dict),
            )

        # ── Legacy backward-compat path ─────────────────────────────────
        warnings.warn(
            "add_contact(client_id, **kwargs) is deprecated — "
            "use add_contact(client_id, ClientContact(...), user_id=...)",
            DeprecationWarning,
            stacklevel=2,
        )
        data: dict[str, Any] = dict(contact) if contact else {}
        data.update(kwargs)
        data["client_id"] = client_id
        return self._contact_repo.create(data)

    # ── Existing methods (kept as-is) ───────────────────────────────────────

    def get_by_id(self, client_id: int, company_id=None) -> Optional[dict[str, Any]]:
        """Legacy: returns a raw dict. Prefer :meth:`get` for typed results."""
        return self._repo.get_by_id(client_id)

    def get_all(self, include_inactive: bool = False, company_id=None) -> list[dict[str, Any]]:
        """Legacy: returns raw dicts. Prefer :meth:`list_all` for typed results."""
        return self._repo.get_all(include_inactive=include_inactive)

    def get_all_with_revenue(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        return self._repo.get_all_with_revenue(include_inactive=include_inactive)

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._repo.search(query, limit=limit)

    def search_advanced(self, query: str, include_inactive: bool = False, limit: int = 200, company_id=None) -> list[dict[str, Any]]:
        return self._repo.search_advanced(query, include_inactive=include_inactive, limit=limit)

    def deactivate(self, client_id: int, company_id=None) -> None:
        self._repo.deactivate(client_id)

    def get_trip_count(self, client_id: int, company_id=None) -> int:
        return self._repo.get_trip_count(client_id)

    def get_top_clients(self, limit: int = 5) -> list[dict[str, Any]]:
        return self._repo.get_top_by_revenue(limit=limit)

    def get_or_create(self, name: str) -> Optional[int]:
        name = name.strip()
        if not name:
            return None
        existing = self._repo.get_by_name(name)
        if existing:
            return existing["id"]
        return self.create(name)

    def resolve_client_id(self, name: str) -> Optional[int]:
        name = name.strip()
        if not name:
            return None
        existing = self._repo.get_by_name(name)
        return existing["id"] if existing else None

    # ── Dashboard & queries ─────────────────────────────────────────────

    def get_client_dashboard(self, client_id: int, company_id=None) -> dict[str, Any]:
        client = self._repo.get_by_id(client_id)
        if not client:
            return {}
        dashboard_data = self._repo.get_dashboard_data(client_id)
        recent_trips = self._repo.get_trips(client_id, limit=5)
        outstanding_invoices = self._repo.get_outstanding_invoices(client_id)
        contacts = self._contact_repo.get_by_client(client_id)
        tags = self._tag_repo.get_by_client(client_id)
        return {
            "client": client,
            "total_revenue": dashboard_data["total_revenue"],
            "total_profit": dashboard_data["total_profit"],
            "avg_profit": dashboard_data["avg_profit"],
            "total_trips": dashboard_data["total_trips"],
            "total_km": dashboard_data["total_km"],
            "last_trip_date": dashboard_data["last_trip_date"],
            "outstanding_balance": dashboard_data["outstanding_balance"],
            "trips_last_30_days": dashboard_data["trips_last_30_days"],
            "recent_trips": recent_trips,
            "outstanding_invoices": outstanding_invoices,
            "status_counts": dashboard_data["status_counts"],
            "contacts": contacts,
            "tags": tags,
        }

    def get_client_trips(self, client_id: int, company_id=None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self._repo.get_trips(client_id, limit=limit, offset=offset)

    def get_client_invoices(self, client_id: int, company_id=None, limit: int = 100) -> list[dict[str, Any]]:
        return self._repo.get_invoices(client_id, limit=limit)

    def get_client_revenue_history(self, client_id: int, company_id=None, months: int = 12) -> list[dict[str, Any]]:
        return self._repo.get_revenue_history(client_id, months=months)

    def get_outstanding_invoices(self, client_id: int) -> list[dict[str, Any]]:
        return self._inv_repo.get_outstanding_by_client(client_id)

    def get_outstanding_balance(self, client_id: int) -> float:
        return self._inv_repo.get_outstanding_balance(client_id)

    # ── Contact management (legacy) ─────────────────────────────────────

    def get_contacts(self, client_id: int, company_id=None) -> list[dict[str, Any]]:
        return self._contact_repo.get_by_client(client_id)

    def update_contact(self, contact_id: int, **kwargs) -> None:
        self._contact_repo.update(contact_id, kwargs)

    def delete_contact(self, contact_id: int) -> None:
        self._contact_repo.delete(contact_id)

    def set_primary_contact(self, client_id: int, contact_id: int) -> None:
        self._contact_repo.set_primary(client_id, contact_id)

    # ── Tag management ─────────────────────────────────────────────────

    def get_tags(self, client_id: int, company_id=None) -> list[str]:
        rows = self._tag_repo.get_by_client(client_id)
        return [r["tag"] for r in rows]

    def add_tag(self, client_id: int, tag: str, company_id=None) -> None:
        self._tag_repo.add(client_id, tag)

    def remove_tag(self, client_id: int, tag: str) -> None:
        self._tag_repo.remove(client_id, tag)

    def get_all_tags(self) -> list[str]:
        return self._tag_repo.get_all_tags()

    # ── Payment tracking ────────────────────────────────────────────────

    def get_payment_summary(self, client_id: int, company_id=None) -> dict[str, Any]:
        row = self._inv_repo.get_payment_summary(client_id)
        if not row:
            return {
                "total_billed": 0, "total_paid": 0,
                "unpaid": 0, "overdue": 0, "invoice_count": 0,
            }
        inv_count = self._inv_repo.get_invoice_count(client_id)
        return {
            "total_billed": row.get("total_billed", 0) or 0,
            "total_paid": row.get("total_paid", 0) or 0,
            "unpaid": row.get("unpaid", 0) or 0,
            "overdue": row.get("overdue", 0) or 0,
            "invoice_count": inv_count,
        }

    # ── Merge ───────────────────────────────────────────────────────────

    def merge_clients(self, from_id: int, to_id: int, user_id: Optional[int] = None) -> dict[str, int]:
        """Merge source client into target client.

        Orchestrates the business logic of merging (reassign all related
        entities, deactivate source) using primitive repository operations
        inside a single transaction.

        New API (preferred)::

            svc.merge_clients(from_id, to_id, user_id=42) -> dict

        Legacy API (deprecated)::

            svc.merge_clients(from_id, to_id)  # no permission check
        """
        if user_id is not None:
            self._check_permission("can_merge_clients", user_id)
        else:
            warnings.warn(
                "merge_clients(from_id, to_id) without user_id is deprecated — "
                "add user_id for permission checking",
                DeprecationWarning,
                stacklevel=2,
            )

        logger.info("Merging client %s into %s — reassigning trips, invoices, contacts, tags", from_id, to_id)
        if not self.db:
            logger.error("ClientService: no database, cannot merge")
            return {"trips": 0, "invoices": 0, "contacts": 0}

        try:
            self._repo.begin_transaction()

            moved_trips = self._repo.reassign_trips(from_id, to_id)
            logger.debug("Reassigned %d trip(s) from client %s to %s", moved_trips, from_id, to_id)

            moved_invoices = self._repo.reassign_invoices(from_id, to_id)
            logger.debug("Reassigned %d invoice(s)", moved_invoices)

            moved_contacts = self._repo.reassign_contacts(from_id, to_id)
            logger.debug("Reassigned %d contact(s)", moved_contacts)

            self._repo.reassign_tags(from_id, to_id)
            logger.debug("Reassigned tags")

            # Deactivate source client (no commit — part of the transaction)
            self._repo.deactivate(from_id, commit=False)
            logger.debug("Deactivated source client %s", from_id)

            self._repo.commit_transaction()

            result = {"trips": moved_trips, "invoices": moved_invoices, "contacts": moved_contacts}
            logger.info("Merge complete: %s", result)

            self._event_bus.publish(CLIENT_MERGED, {
                "from_id": from_id,
                "to_id": to_id,
                "trips": moved_trips,
            })
            return result
        except (ValueError, LookupError):
            self._repo.rollback_transaction()
            logger.exception("merge_clients failed for client %s → %s", from_id, to_id)
            return {"trips": 0, "invoices": 0, "contacts": 0}

    # ── Export ──────────────────────────────────────────────────────────

    def export_clients_csv(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        return self._repo.get_all_with_revenue(include_inactive=include_inactive)
