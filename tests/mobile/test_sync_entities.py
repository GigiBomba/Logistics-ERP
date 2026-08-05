"""Contract tests for the delta-sync endpoint's new-entity branches.

Phase-6 audit: ``GET /mobile/sync`` supports ``entity=fleet`` (monotonic id
cursor — trucks have no timestamps), ``entity=drivers`` and ``entity=clients``
(updated_at cursors), but the existing suite only drove ``entity=transport`` /
``message``.  These parametrized cases lock down, per entity:

  1. the ``SyncResponse`` envelope (records list + cursor + has_more),
  2. cursor advancement semantics (fleet: id cursor; drivers/clients:
     updated_at cursor), and
  3. company scoping (company-2 rows seeded but excluded).

Seeding reuses the existing ``real_db`` + ``records_seed`` fixtures
(trucks/drivers/clients/trips/invoices for company 1) plus the same
``seed_records`` helper for the company-2 isolation rows.
"""
from __future__ import annotations

import pytest

from tests.mobile.conftest import seed_records

SYNC_URL = "/api/v1/mobile/sync"

# records_seed (company 1) creates exactly these rows:
#   3 trucks, 2 drivers, 2 clients — all with updated_at '2026-01-01T00:00:00Z'.
COMPANY_1_COUNTS = {"fleet": 3, "drivers": 2, "clients": 2}

_OLDER_THAN_ALL = "2000-01-01T00:00:00Z"
_NEWER_THAN_ALL = "2030-01-01T00:00:00Z"


@pytest.mark.parametrize(
    "entity,expected_count,id_cursor",
    [
        pytest.param("fleet", 3, True, id="fleet"),
        pytest.param("drivers", 2, False, id="drivers"),
        pytest.param("clients", 2, False, id="clients"),
    ],
)
def test_delta_sync_entity_contract(
    mobile_app,
    real_db,
    records_seed,
    dispatcher_client,
    entity,
    expected_count,
    id_cursor,
):
    """One parametrized contract case per new sync entity.

    Asserts the response shape, cursor advancement and the company filter.
    """
    # Make isolation observable: seed a second company alongside company 1.
    seed_records(real_db, company_id=2)

    # 1) Full sync → 200 + SyncResponse envelope + company scope.
    resp = dispatcher_client.get(f"{SYNC_URL}?entity={entity}&full=true")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["records"], list), "records must be a list"
    assert body["cursor"], "cursor must be non-empty"
    assert body["has_more"] is False, "small seed sets must not claim more"
    assert len(body["records"]) == expected_count, (
        f"expected {expected_count} company-1 {entity} records, "
        f"got {len(body['records'])}"
    )
    assert all(r["company_id"] == 1 for r in body["records"]), (
        "company-2 rows must be excluded from the delta"
    )
    if entity == "fleet":
        assert all(r["plate_number"].startswith("AB-") for r in body["records"]), (
            "company-2 trucks (OT2- prefix) leaked into the fleet delta"
        )

    # 2) Cursor advancement per entity.
    if id_cursor:
        # fleet: monotonic id cursor.  since=0 → all; since=<max id> → empty
        # with the cursor preserved (never regressing to 0 / empty string).
        r0 = dispatcher_client.get(f"{SYNC_URL}?entity=fleet&since=0")
        assert r0.status_code == 200, r0.text
        b0 = r0.json()
        assert len(b0["records"]) == expected_count, "since=0 must return the whole fleet"
        assert all(r["company_id"] == 1 for r in b0["records"])
        max_id = str(max(r["id"] for r in b0["records"]))
        assert b0["cursor"] == max_id, "fleet cursor must advance to the max id"

        r1 = dispatcher_client.get(f"{SYNC_URL}?entity=fleet&since={max_id}")
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["records"] == [], "since=<max id> must be an empty delta"
        assert b1["cursor"] == max_id, "empty fleet delta must preserve the cursor"
    else:
        # drivers/clients: updated_at cursor.  Older since → records,
        # newer since → empty.
        r_old = dispatcher_client.get(f"{SYNC_URL}?entity={entity}&since={_OLDER_THAN_ALL}")
        assert r_old.status_code == 200, r_old.text
        b_old = r_old.json()
        assert len(b_old["records"]) == expected_count, (
            f"since={_OLDER_THAN_ALL} must return all company-1 {entity}"
        )
        assert all(r["company_id"] == 1 for r in b_old["records"])
        assert all(r["updated_at"] > _OLDER_THAN_ALL for r in b_old["records"]), (
            "records must have updated_at newer than the cursor"
        )

        r_new = dispatcher_client.get(f"{SYNC_URL}?entity={entity}&since={_NEWER_THAN_ALL}")
        assert r_new.status_code == 200, r_new.text
        assert r_new.json()["records"] == [], (
            f"since={_NEWER_THAN_ALL} must be an empty {entity} delta"
        )
