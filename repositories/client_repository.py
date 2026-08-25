"""Client repository — all client DB access consolidated here."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories import BaseRepository

class ClientRepository(BaseRepository):
    TABLE = "clients"
    SOFT_DELETE = True
    COLUMNS = [
        "id", "name", "contact_person", "phone", "email", "address", "vat_number",
        "currency_preference", "notes", "is_active", "created_at", "updated_at",
        "client_type", "payment_terms_days", "credit_limit_eur", "default_rate_per_km",
        "rating", "eori_number", "country", "consignee_contact_name",
        "consignee_contact_phone", "company_id",
    ]

    def get_by_id(self, client_id: int, company_id=None) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter_for(company_id)} {self._soft_delete_filter()}",
            (client_id,) + self._company_params_for(company_id),
        )

    def get_client_email_by_name(self, name: str) -> Optional[str]:
        row = self._fetchone(
            f"SELECT email FROM {self.TABLE} WHERE name = ? AND email IS NOT NULL AND email != '' {self._company_filter()} {self._soft_delete_filter()} LIMIT 1",
            (name,) + self._company_params(),
        )
        return row["email"] if row else None

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE name = ? {self._company_filter()} {self._soft_delete_filter()}", (name,) + self._company_params()
        )

    def search_by_name(self, name: str, fuzzy: bool = True, limit: int = 5) -> List[Dict[str, Any]]:
        """Exact match first, then fuzzy LIKE match.

        Used by the document automation trip-matcher to find the
        client whose name appeared in OCR text.
        """
        name = (name or "").strip()
        if not name:
            return []
        # Exact match wins.
        exact = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 AND LOWER(TRIM(name)) = LOWER(TRIM(?)) {self._company_filter()} {self._soft_delete_filter()}",
            (name,) + self._company_params(),
        )
        results: List[Dict[str, Any]] = []
        if exact:
            results.append(exact)
        if fuzzy:
            like_results = self._fetchall(
                f"SELECT * FROM {self.TABLE} "
                "WHERE is_active = 1 AND name LIKE ? ESCAPE '\\' "
                f"{self._company_filter()} {self._soft_delete_filter()} "
                "ORDER BY name ASC LIMIT ?",
                (f"%{self._escape_like(name)}%",) + self._company_params() + (limit,),
            )
            for r in like_results:
                if r["id"] not in {x["id"] for x in results}:
                    results.append(r)
        return results[:limit]

    def get_all(self, include_inactive: bool = False, limit: int = 500, company_id=None) -> List[Dict[str, Any]]:
        where = "" if include_inactive else "WHERE is_active = 1"
        if not where:
            where = "WHERE 1=1"
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} {where} {self._company_filter_for(company_id)} {self._soft_delete_filter()} ORDER BY name ASC LIMIT ?",
            self._company_params_for(company_id) + (limit,),
        )

    @staticmethod
    def _escape_like(s: str) -> str:
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE is_active = 1 AND name LIKE ? ESCAPE '\\' {self._company_filter()} {self._soft_delete_filter()} ORDER BY name ASC LIMIT ?",
            (f"%{self._escape_like(query)}%",) + self._company_params() + (limit,),
        )

    def create(self, data: Dict[str, Any]) -> int:
        self._validate_columns(data)
        from datetime import datetime
        data = dict(data)
        data = self._set_company_from_context(data)
        data.setdefault("created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
        data.setdefault("is_active", 1)
        cols = ", ".join(data.keys())
        vals = ", ".join("?" for _ in data)
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} ({cols}) VALUES ({vals})",
            tuple(data.values()),
        commit=True)

    def update(self, client_id: int, data: Dict[str, Any]) -> None:
        self._validate_columns(data)
        from datetime import datetime
        data = dict(data)
        data["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        sets = ", ".join(f"{k} = ?" for k in data)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ? {self._company_filter()}",
            tuple(data.values()) + (client_id,) + self._company_params(),
        commit=True)

    def deactivate(self, client_id: int, commit: bool = True) -> None:
        self._execute(
            f"UPDATE {self.TABLE} SET is_active = 0 WHERE id = ? {self._company_filter()}",
            (client_id,) + self._company_params(),
            commit=commit,
        )

    def soft_delete(self, client_id: int, commit: bool = True) -> None:
        """Deactivate a client AND stamp ``deleted_at`` (unified delete semantics).

        Keeps ``is_active = 0`` (the UI reads it) and adds ``deleted_at`` so
        the sync layer treats the client as deleted.  ``deactivate()`` alone
        (used by the UI's deactivate action) does NOT stamp ``deleted_at``.
        """
        from database.time_utils import utc_now_iso
        self._execute(
            f"UPDATE {self.TABLE} SET is_active = 0, deleted_at = ? WHERE id = ? {self._company_filter()}",
            (utc_now_iso(), client_id) + self._company_params(),
            commit=commit,
        )

    # ── Primitive merge operations (single-entity SQL updates, no business logic) ──

    def reassign_trips(self, source_id: int, target_id: int) -> int:
        """Reassign all trips from source client to target client."""
        return self._execute_with_count(
            f"UPDATE trips SET client_id = ? WHERE client_id = ? {self._company_filter()}",
            (target_id, source_id) + self._company_params(),
            commit=False,
        )

    def reassign_invoices(self, source_id: int, target_id: int) -> int:
        """No-op: invoices reference trips via ``trip_id``, not ``client_id``.

        After :meth:`reassign_trips` moves the trips to the target client,
        the invoice → trip linkage is already correct.
        """
        return 0

    def reassign_contacts(self, source_id: int, target_id: int) -> int:
        """Reassign all contacts from source client to target client."""
        from repositories.contact_repository import ContactRepository
        contacts = ContactRepository(self.db).get_by_client(source_id)
        for c in contacts:
            self._execute(
                "UPDATE client_contacts SET client_id = ? WHERE id = ?",
                (target_id, c["id"]),
                commit=False,
            )
        return len(contacts)

    def reassign_tags(self, source_id: int, target_id: int) -> int:
        """Reassign all tags from source client to target client."""
        return self._execute_with_count(
            f"UPDATE client_tags SET client_id = ? WHERE client_id = ? {self._company_filter()}",
            (target_id, source_id) + self._company_params(),
            commit=False,
        )

    # ── Legacy merge entrypoint (backward compat) ────────────────────────────

    def merge_client_data(self, from_id: int, to_id: int) -> dict[str, int]:
        """Backward-compatible wrapper — delegates to primitive operations."""
        self.begin_transaction()
        try:
            moved_trips = self.reassign_trips(from_id, to_id)
            moved_invoices = self.reassign_invoices(from_id, to_id)
            moved_contacts = self.reassign_contacts(from_id, to_id)
            self.reassign_tags(from_id, to_id)
            self.deactivate(from_id, commit=False)
            self.commit_transaction()
            return {"trips": moved_trips, "invoices": moved_invoices, "contacts": moved_contacts}
        except Exception:
            self.rollback_transaction()
            raise

    # ── Multi-source merge (mobile, blueprint §6.3) ─────────────────────────

    def merge_clients_multi(
        self, target_id: int, source_ids: list[int], company_id=None
    ) -> dict[str, int]:
        """Merge multiple source clients into one target — atomic.

        Moves trips, contacts and tags from every source client onto
        *target_id*, then deletes the source client rows — all inside ONE
        transaction with dialect-aware locking:

          - SQLite:      ``BEGIN IMMEDIATE`` takes the write lock up front, so a
                         concurrent merge blocks until the first commits.
          - PostgreSQL:  the transaction is implicit (``autocommit=False``); the
                         target and all source rows are locked with
                         ``SELECT ... FOR UPDATE`` before any mutation.

        The target + source rows are re-validated inside the lock, so a
        concurrently-merged (already deleted) source aborts the transaction.

        Returns ``{"merged_trip_count", "merged_invoice_count",
        "merged_contact_count"}``.
        """
        source_ids = [int(s) for s in source_ids]
        if not source_ids:
            raise ValueError("source_ids must not be empty")
        if target_id in source_ids:
            raise ValueError("target_id must not appear in source_ids")
        engine = getattr(self.db, "_engine", "sqlite")
        all_ids = [target_id] + source_ids
        all_placeholders = ", ".join(["?"] * len(all_ids))
        src_placeholders = ", ".join(["?"] * len(source_ids))
        params_all = tuple(all_ids) + self._company_params_for(company_id)

        try:
            # 1. Begin transaction + row-level locking ────────────────────────
            if engine == "postgresql":
                lock_sql = (
                    f"SELECT id FROM {self.TABLE} WHERE id IN ({all_placeholders}) "
                    f"{self._company_filter_for(company_id)} FOR UPDATE"
                )
                cur = self.db.conn.cursor()
                try:
                    cur.execute(self._adapt_query(lock_sql), params_all)
                    cur.fetchall()
                finally:
                    cur.close()
            else:
                self.db.conn.execute("BEGIN IMMEDIATE")

            # 2. Re-validate target + sources exist (inside the lock) ─────────
            rows = self._fetchall(
                f"SELECT id FROM {self.TABLE} WHERE id IN ({all_placeholders}) "
                f"{self._company_filter_for(company_id)} {self._soft_delete_filter()}",
                params_all,
            )
            found = {r["id"] for r in rows}
            missing = [i for i in all_ids if i not in found]
            if missing:
                raise ValueError(f"Clients no longer available: {missing}")

            # 3. Move trips (and count invoices linked to the moved trips) ────
            trip_rows = self._fetchall(
                f"SELECT id FROM trips WHERE client_id IN ({src_placeholders}) "
                f"{self._company_filter_for(company_id)} {self._soft_delete_filter()}",
                tuple(source_ids) + self._company_params_for(company_id),
            )
            moved_trip_ids = [r["id"] for r in trip_rows]
            moved_trips = self._execute_with_count(
                f"UPDATE trips SET client_id = ? WHERE client_id IN ({src_placeholders}) "
                f"{self._company_filter_for(company_id)} {self._soft_delete_filter()}",
                (target_id,) + tuple(source_ids) + self._company_params_for(company_id),
                commit=False,
            )
            if moved_trip_ids:
                in_trips = ", ".join(["?"] * len(moved_trip_ids))
                inv_row = self._fetchone(
                    f"SELECT COUNT(*) AS cnt FROM invoices WHERE trip_id IN ({in_trips})",
                    tuple(moved_trip_ids),
                )
                moved_invoices = inv_row["cnt"] if inv_row else 0
            else:
                moved_invoices = 0

            # 4. Move contacts ─────────────────────────────────────────────────
            # NOTE: client_contacts has no deleted_at column — no soft-delete filter.
            moved_contacts = self._execute_with_count(
                f"UPDATE client_contacts SET client_id = ? WHERE client_id IN ({src_placeholders}) "
                f"{self._company_filter_for(company_id)}",
                (target_id,) + tuple(source_ids) + self._company_params_for(company_id),
                commit=False,
            )

            # 5. Merge tags (deduplicate against the target) ───────────────────
            # NOTE: client_tags has no deleted_at column — no soft-delete filter.
            tag_rows = self._fetchall(
                f"SELECT tag FROM client_tags WHERE client_id IN ({src_placeholders}) "
                f"{self._company_filter_for(company_id)}",
                tuple(source_ids) + self._company_params_for(company_id),
            )
            for r in tag_rows:
                existing = self._fetchone(
                    "SELECT id FROM client_tags WHERE client_id = ? AND tag = ?",
                    (target_id, r["tag"]),
                )
                if existing:
                    continue
                self.db.execute(
                    "INSERT INTO client_tags (client_id, tag, company_id) VALUES (?, ?, ?)",
                    (target_id, r["tag"], company_id or 0),
                )
            self._execute(
                f"DELETE FROM client_tags WHERE client_id IN ({src_placeholders}) "
                f"{self._company_filter_for(company_id)}",
                tuple(source_ids) + self._company_params_for(company_id),
                commit=False,
            )

            # 6. Delete source client rows ────────────────────────────────────
            self._execute(
                f"DELETE FROM {self.TABLE} WHERE id IN ({src_placeholders}) "
                f"{self._company_filter_for(company_id)} {self._soft_delete_filter()}",
                tuple(source_ids) + self._company_params_for(company_id),
                commit=False,
            )

            self.db.conn.commit()
            return {
                "merged_trip_count": moved_trips,
                "merged_invoice_count": moved_invoices,
                "merged_contact_count": moved_contacts,
            }
        except Exception:
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            raise

    def get_trip_count(self, client_id: int) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ? {self._company_filter()} {self._soft_delete_filter()}",
            (client_id,) + self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_top_by_revenue(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT c.*, SUM(COALESCE(t.total_price_eur, 0)) AS total_revenue
                FROM {self.TABLE} c
                JOIN trips t ON t.client_id = c.id
                WHERE t.status NOT IN ('Cancelled')
                  {self._company_filter("c")} {self._soft_delete_filter("c")}
                GROUP BY c.id
                ORDER BY total_revenue DESC
                LIMIT ?""",
            self._company_params() + (limit,),
        )

    def get_trips(self, client_id: int, limit: int = 100, offset: int = 0, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM trips WHERE client_id = ? {self._company_filter_for(company_id)} {self._soft_delete_filter()} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (client_id,) + self._company_params_for(company_id) + (limit, offset),
        )

    def get_trips_status_counts(self, client_id: int) -> Dict[str, int]:
        rows = self._fetchall(
            f"SELECT LOWER(status) AS status, COUNT(*) AS cnt FROM trips WHERE client_id = ? {self._company_filter()} {self._soft_delete_filter()} GROUP BY LOWER(status)",
            (client_id,) + self._company_params(),
        )
        return {r["status"]: r["cnt"] for r in rows}

    def get_revenue_summary(self, client_id: int) -> Dict[str, Any]:
        row = self._fetchone(
            f"""SELECT COUNT(*) AS total_trips,
                      COALESCE(SUM(total_price_eur), 0) AS total_revenue,
                      COALESCE(SUM(net_profit), 0) AS total_profit,
                      COALESCE(AVG(net_profit), 0) AS avg_profit,
                      COALESCE(SUM(distance_km), 0) AS total_km,
                      COALESCE(MAX(created_at), '') AS last_trip_date
               FROM trips WHERE client_id = ? AND status NOT IN ('Cancelled')
               {self._company_filter()} {self._soft_delete_filter()}""",
            (client_id,) + self._company_params(),
        )
        return row or {}

    def get_revenue_history(self, client_id: int, months: int = 12) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT SUBSTRING(start_date, 1, 7) AS month,
                      COUNT(*) AS trip_count,
                      COALESCE(SUM(total_price_eur), 0) AS revenue,
                      COALESCE(SUM(net_profit), 0) AS profit,
                      COALESCE(SUM(distance_km), 0) AS km
               FROM trips
               WHERE client_id = ? AND status NOT IN ('Cancelled')
               {self._company_filter()} {self._soft_delete_filter()}
               GROUP BY month
               ORDER BY month DESC
               LIMIT ?""",
            (client_id,) + self._company_params() + (months,),
        )

    def get_outstanding_invoices(self, client_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT i.*, t.client_name, t.truck_number, t.distance_km,
                      t.total_price_eur AS trip_revenue, t.start_date
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ?
               {self._company_filter("t")} {self._soft_delete_filter("t")}
               ORDER BY i.due_date ASC
               LIMIT ?""",
            (client_id,) + self._company_params() + (limit,),
        )

    def get_outstanding_balance(self, client_id: int) -> float:
        row = self._fetchone(
            f"""SELECT COALESCE(SUM(i.total_amount), 0) AS balance
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ? AND i.status = 'Unpaid'
               {self._company_filter("t")} {self._soft_delete_filter("t")}""",
            (client_id,) + self._company_params(),
        )
        return float(row["balance"]) if row else 0.0

    def get_invoices(self, client_id: int, limit: int = 100, company_id=None) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"""SELECT i.*, t.client_name, t.truck_number, t.distance_km,
                      t.total_price_eur AS trip_revenue, t.start_date, t.status AS trip_status
               FROM invoices i
               JOIN trips t ON t.id = i.trip_id
               WHERE t.client_id = ?
               {self._company_filter_for(company_id, "t")}
               {self._soft_delete_filter("t")} {self._soft_delete_filter("i")}
               ORDER BY i.issue_date DESC
               LIMIT ?""",
            (client_id,) + self._company_params_for(company_id) + (limit,),
        )

    def get_trip_count_in_range(self, client_id: int, days: int = 30) -> int:
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM trips WHERE client_id = ? AND start_date >= ? {self._company_filter()} {self._soft_delete_filter()}",
            (client_id, since) + self._company_params(),
        )
        return row["cnt"] if row else 0

    def get_dashboard_data(self, client_id: int) -> dict:
        """Consolidated dashboard query — replaces 4 separate trip queries with 1-2."""
        from datetime import datetime, timedelta

        since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        row = self._fetchone(
            f"""SELECT
                  COUNT(*) AS total_trips,
                  COALESCE(SUM(CASE WHEN LOWER(status) != 'cancelled' THEN total_price_eur END), 0) AS total_revenue,
                  COALESCE(SUM(CASE WHEN LOWER(status) != 'cancelled' THEN net_profit END), 0) AS total_profit,
                  COALESCE(AVG(CASE WHEN LOWER(status) != 'cancelled' THEN net_profit END), 0) AS avg_profit,
                  COALESCE(SUM(CASE WHEN LOWER(status) != 'cancelled' THEN distance_km END), 0) AS total_km,
                  COALESCE(MAX(CASE WHEN LOWER(status) != 'cancelled' THEN created_at END), '') AS last_trip_date,
                  COALESCE(SUM(CASE WHEN start_date >= ? THEN 1 ELSE 0 END), 0) AS trips_last_30d,
                  COALESCE(SUM(CASE WHEN LOWER(status) = 'planned' THEN 1 ELSE 0 END), 0) AS cnt_planned,
                  COALESCE(SUM(CASE WHEN LOWER(status) = 'in transit' THEN 1 ELSE 0 END), 0) AS cnt_in_transit,
                  COALESCE(SUM(CASE WHEN LOWER(status) = 'delivered' THEN 1 ELSE 0 END), 0) AS cnt_delivered,
                  COALESCE(SUM(CASE WHEN LOWER(status) = 'invoiced' THEN 1 ELSE 0 END), 0) AS cnt_invoiced,
                  COALESCE(SUM(CASE WHEN LOWER(status) = 'paid' THEN 1 ELSE 0 END), 0) AS cnt_paid
                FROM trips
                WHERE client_id = ? {self._company_filter()} {self._soft_delete_filter()}""",
            (since, client_id) + self._company_params(),
        )

        bal_row = self._fetchone(
            f"""SELECT COALESCE(SUM(i.total_amount), 0) AS balance
                FROM invoices i
                JOIN trips t ON t.id = i.trip_id
                WHERE t.client_id = ? AND i.status = 'Unpaid'
                {self._company_filter("t")} {self._soft_delete_filter("t")}""",
            (client_id,) + self._company_params(),
        )

        status_counts = {}
        if row:
            for status_key in ['planned', 'in transit', 'delivered', 'invoiced', 'paid']:
                col = "cnt_" + status_key.replace(" ", "_")
                val = row.get(col, 0) or 0
                if val:
                    status_counts[status_key] = val

        return {
            "total_revenue": float(row["total_revenue"] or 0) if row else 0.0,
            "total_profit": float(row["total_profit"] or 0) if row else 0.0,
            "avg_profit": float(row["avg_profit"] or 0) if row else 0.0,
            "total_trips": row["total_trips"] if row else 0,
            "total_km": float(row["total_km"] or 0) if row else 0.0,
            "last_trip_date": row["last_trip_date"] if row else "",
            "trips_last_30_days": row["trips_last_30d"] if row else 0,
            "outstanding_balance": float(bal_row["balance"] or 0) if bal_row else 0.0,
            "status_counts": status_counts,
        }

    def search_advanced(self, query: str, include_inactive: bool = False, limit: int = 200, company_id=None) -> List[Dict[str, Any]]:
        q = f"%{self._escape_like(query)}%"
        active_clause = "" if include_inactive else "AND c.is_active = 1"
        return self._fetchall(
            f"""SELECT c.*
                FROM {self.TABLE} c
                WHERE (c.name LIKE ? ESCAPE '\\' OR c.contact_person LIKE ? ESCAPE '\\' OR c.phone LIKE ? ESCAPE '\\'
                       OR c.email LIKE ? ESCAPE '\\' OR c.address LIKE ? ESCAPE '\\' OR c.notes LIKE ? ESCAPE '\\')
                      {active_clause}
                      {self._company_filter_for(company_id, "c")}
                      {self._soft_delete_filter("c")}
                ORDER BY c.name ASC
                LIMIT ?""",
            (q, q, q, q, q, q) + self._company_params_for(company_id) + (limit,),
        )

    def get_all_with_revenue(self, include_inactive: bool = False, limit: int = 500) -> List[Dict[str, Any]]:
        active_clause = "" if include_inactive else "WHERE c.is_active = 1"
        if not active_clause:
            active_clause = "WHERE 1=1"
        return self._fetchall(
            f"""SELECT c.*,
                      COALESCE(SUM(CASE WHEN t.status NOT IN ('Cancelled') THEN t.total_price_eur ELSE 0 END), 0) AS total_revenue,
                      COUNT(DISTINCT t.id) AS trip_count,
                      COALESCE(SUM(CASE WHEN i.status = 'Unpaid' THEN i.total_amount ELSE 0 END), 0) AS outstanding_balance
               FROM {self.TABLE} c
               LEFT JOIN trips t ON t.client_id = c.id
               LEFT JOIN invoices i ON i.trip_id = t.id
               {active_clause}
               {self._company_filter("c")} {self._soft_delete_filter("c")}
               GROUP BY c.id
               ORDER BY c.name ASC
               LIMIT ?""",
            self._company_params() + (limit,),
        )
