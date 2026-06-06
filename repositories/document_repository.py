"""Document Center repository — CRUD and search for documents + links."""
from typing import Any, Dict, List, Optional

from repositories import BaseRepository


class DocumentRepository(BaseRepository):
    TABLE = "documents"
    TABLE_LINKS = "document_links"

    # ── Document CRUD ──────────────────────────────────────────────────

    def create(self, doc_number: str, title: str, category: str,
               entity_type: str, entity_id: Optional[int],
               file_path: str, file_name: str, file_size: int,
               mime_type: str, file_hash: str, tags: str,
               description: str, uploaded_by: str,
               uploaded_at: str, updated_at: str,
               copy_type: str = "", cmr_number: str = "",
               cmr_metadata_json: str = "{}", is_signed: int = 0) -> int:
        return self._execute_insert(
            f"INSERT INTO {self.TABLE} "
            f"(doc_number, title, category, entity_type, entity_id, "
            f"file_path, file_name, file_size, mime_type, file_hash, "
            f"tags, description, uploaded_by, uploaded_at, updated_at, "
            f"copy_type, cmr_number, cmr_metadata_json, is_signed) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_number, title, category, entity_type, entity_id,
             file_path, file_name, file_size, mime_type, file_hash,
             tags, description, uploaded_by, uploaded_at, updated_at,
             copy_type, cmr_number, cmr_metadata_json, is_signed),
        )

    def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ?", (doc_id,)
        )

    def get_by_doc_number(self, doc_number: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE doc_number = ?", (doc_number,)
        )

    def get_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE file_hash = ? AND is_archived = 0",
            (file_hash,),
        )

    def update(self, doc_id: int, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._execute(
            f"UPDATE {self.TABLE} SET {sets} WHERE id = ?",
            tuple(fields.values()) + (doc_id,),
        )

    def archive(self, doc_id: int) -> None:
        import datetime
        self._execute(
            f"UPDATE {self.TABLE} SET is_archived = 1, updated_at = ? WHERE id = ?",
            (datetime.datetime.now().isoformat(), doc_id),
        )

    def delete(self, doc_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE} WHERE id = ?", (doc_id,))

    def count(self) -> int:
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} WHERE is_archived = 0"
        )
        return row["cnt"] if row else 0

    def count_by_category(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT category, COUNT(*) AS cnt FROM {self.TABLE} "
            f"WHERE is_archived = 0 GROUP BY category ORDER BY cnt DESC"
        )

    def get_next_doc_number(self) -> str:
        import datetime
        year = datetime.datetime.now().year
        row = self._fetchone(
            f"SELECT MAX(doc_number) AS last_num FROM {self.TABLE} "
            f"WHERE doc_number LIKE ?",
            (f"DOC-{year}-%",),
        )
        if row and row.get("last_num"):
            try:
                seq = int(row["last_num"].split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"DOC-{year}-{seq:04d}"

    def get_ids_by_ids(self, doc_ids: list) -> List[Dict[str, Any]]:
        if not doc_ids:
            return []
        placeholders = ",".join("?" for _ in doc_ids)
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE id IN ({placeholders})",
            tuple(doc_ids),
        )

    # ── Advanced Search ────────────────────────────────────────────────

    def advanced_search(self, query: str = "", category: str = "",
                        entity_type: str = "", entity_id: Optional[int] = None,
                        date_from: str = "", date_to: str = "",
                        mime_type: str = "", tag: str = "",
                        order: str = "uploaded_at DESC",
                        limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        conditions = ["is_archived = 0"]
        params: list = []

        if query:
            conditions.append(
                "(d.title LIKE ? OR d.file_name LIKE ? OR d.description LIKE ? "
                "OR d.tags LIKE ? OR d.doc_number LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q, q, q, q])

        if category:
            conditions.append("d.category = ?")
            params.append(category)

        if entity_type:
            conditions.append("d.entity_type = ?")
            params.append(entity_type)

        if entity_id is not None:
            conditions.append("d.entity_id = ?")
            params.append(entity_id)

        if date_from:
            conditions.append("d.uploaded_at >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("d.uploaded_at <= ?")
            params.append(date_to + "T23:59:59")

        if mime_type:
            conditions.append("d.mime_type LIKE ?")
            params.append(f"{mime_type}%")

        if tag:
            conditions.append("d.tags LIKE ?")
            params.append(f'%"{tag}"%')

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        valid_orders = {
            "uploaded_at DESC", "uploaded_at ASC",
            "title ASC", "title DESC",
            "file_size DESC", "file_size ASC",
            "file_name ASC", "file_name DESC",
        }
        order_clause = order if order in valid_orders else "uploaded_at DESC"

        return self._fetchall(
            f"SELECT d.* FROM {self.TABLE} d {where} "
            f"ORDER BY {order_clause} LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )

    def advanced_search_count(self, query: str = "", category: str = "",
                              entity_type: str = "",
                              entity_id: Optional[int] = None,
                              date_from: str = "", date_to: str = "",
                              mime_type: str = "",
                              tag: str = "") -> int:
        conditions = ["is_archived = 0"]
        params: list = []

        if query:
            conditions.append(
                "(d.title LIKE ? OR d.file_name LIKE ? OR d.description LIKE ? "
                "OR d.tags LIKE ? OR d.doc_number LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q, q, q, q])

        if category:
            conditions.append("d.category = ?")
            params.append(category)

        if entity_type:
            conditions.append("d.entity_type = ?")
            params.append(entity_type)

        if entity_id is not None:
            conditions.append("d.entity_id = ?")
            params.append(entity_id)

        if date_from:
            conditions.append("d.uploaded_at >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("d.uploaded_at <= ?")
            params.append(date_to + "T23:59:59")

        if mime_type:
            conditions.append("d.mime_type LIKE ?")
            params.append(f"{mime_type}%")

        if tag:
            conditions.append("d.tags LIKE ?")
            params.append(f'%"{tag}"%')

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} d {where}",
            tuple(params),
        )
        return row["cnt"] if row else 0

    def get_distinct_entity_types(self) -> List[str]:
        rows = self._fetchall(
            f"SELECT DISTINCT entity_type FROM {self.TABLE} "
            f"WHERE entity_type != '' AND is_archived = 0"
        )
        return sorted({r["entity_type"] for r in rows})

    def get_distinct_mime_types(self) -> List[str]:
        rows = self._fetchall(
            f"SELECT DISTINCT mime_type FROM {self.TABLE} "
            f"WHERE mime_type != '' AND is_archived = 0"
        )
        return sorted({r["mime_type"] for r in rows})

    # ── Tag CRUD ──────────────────────────────────────────────────────

    def add_tag(self, doc_id: int, tag: str) -> bool:
        doc = self.get_by_id(doc_id)
        if not doc:
            return False
        import json
        try:
            tags = json.loads(doc["tags"])
            if not isinstance(tags, list):
                tags = []
        except (json.JSONDecodeError, TypeError):
            tags = []
        tag = tag.strip()
        if tag and tag not in tags:
            tags.append(tag)
            self.update(doc_id, tags=json.dumps(tags),
                        updated_at=__import__("datetime").datetime.now().isoformat())
            return True
        return False

    def remove_tag(self, doc_id: int, tag: str) -> bool:
        doc = self.get_by_id(doc_id)
        if not doc:
            return False
        import json
        try:
            tags = json.loads(doc["tags"])
            if not isinstance(tags, list):
                tags = []
        except (json.JSONDecodeError, TypeError):
            tags = []
        if tag in tags:
            tags.remove(tag)
            self.update(doc_id, tags=json.dumps(tags),
                        updated_at=__import__("datetime").datetime.now().isoformat())
            return True
        return False

    def set_tags(self, doc_id: int, tags: list) -> None:
        import json
        self.update(doc_id, tags=json.dumps(tags),
                    updated_at=__import__("datetime").datetime.now().isoformat())

    # ── Batch operations ──────────────────────────────────────────────

    def delete_batch(self, doc_ids: list) -> int:
        if not doc_ids:
            return 0
        placeholders = ",".join("?" for _ in doc_ids)
        self._execute(
            f"DELETE FROM {self.TABLE} WHERE id IN ({placeholders})",
            tuple(doc_ids),
        )
        self._execute(
            f"DELETE FROM {self.TABLE_LINKS} WHERE document_id IN ({placeholders})",
            tuple(doc_ids),
        )
        return len(doc_ids)

    # ── Search (compat wrappers) ──────────────────────────────────────

    def search(self, query: str = "", category: str = "",
               entity_type: str = "", entity_id: Optional[int] = None,
               order: str = "uploaded_at DESC",
               limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        return self.advanced_search(
            query=query, category=category,
            entity_type=entity_type, entity_id=entity_id,
            order=order, limit=limit, offset=offset,
        )

    def search_count(self, query: str = "", category: str = "",
                     entity_type: str = "",
                     entity_id: Optional[int] = None) -> int:
        return self.advanced_search_count(
            query=query, category=category,
            entity_type=entity_type, entity_id=entity_id,
        )

    def get_all_tags(self) -> List[str]:
        rows = self._fetchall(
            f"SELECT DISTINCT tags FROM {self.TABLE} WHERE is_archived = 0 "
            f"AND tags IS NOT NULL AND tags != '' AND tags != '[]'"
        )
        tag_set = set()
        import json
        for row in rows:
            try:
                parsed = json.loads(row["tags"])
                if isinstance(parsed, list):
                    for t in parsed:
                        if t:
                            tag_set.add(str(t))
            except (json.JSONDecodeError, TypeError):
                pass
        return sorted(tag_set)

    # ── Document Links ─────────────────────────────────────────────────

    def add_link(self, document_id: int, linked_entity_type: str,
                 linked_entity_id: int, relation_type: str = "attached",
                 created_at: str = "") -> int:
        return self._execute_insert(
            f"INSERT OR IGNORE INTO {self.TABLE_LINKS} "
            f"(document_id, linked_entity_type, linked_entity_id, "
            f"relation_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (document_id, linked_entity_type, linked_entity_id,
             relation_type, created_at),
        )

    def remove_link(self, link_id: int) -> None:
        self._execute(f"DELETE FROM {self.TABLE_LINKS} WHERE id = ?", (link_id,))

    def remove_all_links(self, document_id: int) -> None:
        self._execute(
            f"DELETE FROM {self.TABLE_LINKS} WHERE document_id = ?",
            (document_id,),
        )

    def get_links(self, document_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT * FROM {self.TABLE_LINKS} WHERE document_id = ? "
            f"ORDER BY id",
            (document_id,),
        )

    def get_documents_for_entity(self, entity_type: str,
                                 entity_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT d.* FROM {self.TABLE} d "
            f"JOIN {self.TABLE_LINKS} dl ON dl.document_id = d.id "
            f"WHERE dl.linked_entity_type = ? AND dl.linked_entity_id = ? "
            f"AND d.is_archived = 0 "
            f"ORDER BY d.uploaded_at DESC",
            (entity_type, entity_id),
        )

    def get_entity_types_for_document(self, document_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            f"SELECT DISTINCT linked_entity_type, linked_entity_id "
            f"FROM {self.TABLE_LINKS} WHERE document_id = ?",
            (document_id,),
        )

    # ── Primary entity link helpers ────────────────────────────────────

    def get_primary_link(self, document_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            f"SELECT * FROM {self.TABLE_LINKS} WHERE document_id = ? "
            f"ORDER BY id LIMIT 1",
            (document_id,),
        )

    # ── FTS5 Full-Text Search ───────────────────────────────────────────

    def fts_search(self, query: str, category: str = "",
                   entity_type: str = "", order: str = "uploaded_at DESC",
                   limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        conditions = ["d.is_archived = 0"]
        params: list = []

        if query:
            conditions.append("d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)")
            params.append(self._fts_query(query))

        if category:
            conditions.append("d.category = ?")
            params.append(category)

        if entity_type:
            conditions.append("d.entity_type = ?")
            params.append(entity_type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        valid_orders = {
            "uploaded_at DESC", "uploaded_at ASC", "title ASC", "title DESC",
            "file_size DESC", "file_size ASC", "file_name ASC", "file_name DESC",
        }
        order_clause = order if order in valid_orders else "uploaded_at DESC"

        return self._fetchall(
            f"SELECT d.* FROM {self.TABLE} d {where} "
            f"ORDER BY {order_clause} LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset),
        )

    def fts_search_count(self, query: str, category: str = "",
                         entity_type: str = "") -> int:
        conditions = ["d.is_archived = 0"]
        params: list = []

        if query:
            conditions.append("d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)")
            params.append(self._fts_query(query))

        if category:
            conditions.append("d.category = ?")
            params.append(category)

        if entity_type:
            conditions.append("d.entity_type = ?")
            params.append(entity_type)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        row = self._fetchone(
            f"SELECT COUNT(*) AS cnt FROM {self.TABLE} d {where}", tuple(params),
        )
        return row["cnt"] if row else 0

    def get_expiring_documents(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        import datetime
        cutoff = (datetime.datetime.now() + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE expiry_date != '' "
            f"AND expiry_date <= ? AND is_archived = 0 "
            f"ORDER BY expiry_date ASC",
            (cutoff,),
        )

    def get_overdue_documents(self) -> List[Dict[str, Any]]:
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        return self._fetchall(
            f"SELECT * FROM {self.TABLE} WHERE expiry_date != '' "
            f"AND expiry_date < ? AND is_archived = 0 "
            f"ORDER BY expiry_date ASC",
            (today,),
        )

    @staticmethod
    def _fts_query(user_query: str) -> str:
        terms = user_query.strip().split()
        return " AND ".join(f'"{t}"' for t in terms) if terms else user_query

    # ── Document Versions ───────────────────────────────────────────────

    def add_version(self, document_id: int, version_number: int,
                    file_path: str, file_size: int, file_hash: str,
                    comment: str, uploaded_by: str, created_at: str) -> int:
        return self._execute_insert(
            f"INSERT INTO document_versions "
            f"(document_id, version_number, file_path, file_size, file_hash, "
            f"comment, uploaded_by, created_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (document_id, version_number, file_path, file_size, file_hash,
             comment, uploaded_by, created_at),
        )

    def get_versions(self, document_id: int) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM document_versions WHERE document_id = ? "
            "ORDER BY version_number DESC",
            (document_id,),
        )

    def get_version_count(self, document_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM document_versions WHERE document_id = ?",
            (document_id,),
        )
        return row["cnt"] if row else 0

    def delete_versions(self, document_id: int) -> None:
        self._execute(
            "DELETE FROM document_versions WHERE document_id = ?", (document_id,),
        )

    # ── Contracts ───────────────────────────────────────────────────────

    def create_contract(self, document_id: int, client_id: int,
                        contract_type: str, start_date: str, end_date: str,
                        value_eur: float, payment_terms: str,
                        auto_renewal: int, renewal_notice_days: int,
                        notes: str, created_at: str, updated_at: str) -> int:
        return self._execute_insert(
            "INSERT INTO contracts "
            "(document_id, client_id, contract_type, start_date, end_date, "
            "value_eur, payment_terms, auto_renewal, renewal_notice_days, "
            "notes, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
            (document_id, client_id, contract_type, start_date, end_date,
             value_eur, payment_terms, auto_renewal, renewal_notice_days,
             notes, created_at, updated_at),
        )

    def get_contracts(self, client_id: Optional[int] = None,
                      status: str = "") -> List[Dict[str, Any]]:
        conditions = []
        params: list = []
        if client_id is not None:
            conditions.append("client_id = ?")
            params.append(client_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self._fetchall(
            f"SELECT * FROM contracts {where} ORDER BY end_date DESC",
            tuple(params),
        )

    def get_contract_by_id(self, contract_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM contracts WHERE id = ?", (contract_id,),
        )

    def get_contract_by_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM contracts WHERE document_id = ?", (document_id,),
        )

    def update_contract(self, contract_id: int, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._execute(
            f"UPDATE contracts SET {sets} WHERE id = ?",
            tuple(fields.values()) + (contract_id,),
        )

    def get_expiring_contracts(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        import datetime
        cutoff = (datetime.datetime.now() + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        return self._fetchall(
            "SELECT * FROM contracts WHERE end_date != '' "
            "AND end_date <= ? AND status = 'active' ORDER BY end_date ASC",
            (cutoff,),
        )

    # ── Templates ───────────────────────────────────────────────────────

    def create_template(self, name: str, description: str, category: str,
                        template_type: str, fields_json: str,
                        created_at: str, updated_at: str) -> int:
        return self._execute_insert(
            "INSERT INTO document_templates "
            "(name, description, category, template_type, fields_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, description, category, template_type, fields_json, created_at, updated_at),
        )

    def get_templates(self, category: str = "") -> List[Dict[str, Any]]:
        if category:
            return self._fetchall(
                "SELECT * FROM document_templates WHERE category = ? ORDER BY name",
                (category,),
            )
        return self._fetchall(
            "SELECT * FROM document_templates ORDER BY category, name"
        )

    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM document_templates WHERE id = ?", (template_id,),
        )

    def delete_template(self, template_id: int) -> None:
        self._execute("DELETE FROM document_templates WHERE id = ?", (template_id,))

    # ── Rebuild FTS5 index on startup ───────────────────────────────────

    def rebuild_fts_index(self) -> None:
        try:
            self._execute(
                "INSERT INTO documents_fts(documents_fts) VALUES('rebuild')"
            )
        except Exception:
            pass
