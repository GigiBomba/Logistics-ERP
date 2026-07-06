# Proforma Invoice Generator — Technical Blueprint

---

## Overview

Implement a **proforma invoice generator** as a new tab in the Document Center, mirroring the existing invoice generator's UI and PDF output but adapted for **trip-independent** operation. All generated documents are registered in the Document Center with automatic OCR. Failed OCR is retried on next startup. Linked CMRs/invoices are only emailed alongside a proforma if the user explicitly opts in.

---

## Phase 0: Foundation — Database & Data Layer

### Objective
Create the `proforma_invoices` table and repository so all subsequent phases have persistent storage. Since proformas are **independent** (no trip FK), the table must hold all invoice data inline.

### Dependencies
- None

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 0.1 | Add `TABLE_PROFORMA_INVOICES` SQL | `database/schema.py` | Add after `TABLE_INVOICES` |
| 0.2 | Add `INDEX_PROFORMA_NUMBER` (unique index on `proforma_number`) | `database/schema.py` | Add index |
| 0.3 | Add `INDEX_PROFORMA_CLIENT` (on `client_name`) | `database/schema.py` | Add index |
| 0.4 | Register `TABLE_PROFORMA_INVOICES` in `_create_tables_and_indices()` | `database/db_manager.py:60` | Add to `exec_stmts` list |
| 0.5 | Expose `create_proforma_record()` / `update_proforma()` methods on `DatabaseManager` | `database/db_manager.py` | 2 new methods |
| 0.6 | Create `ProformaRepository` extending `BaseRepository` | `repositories/proforma_repository.py` | New file; CRUD + search + status methods |
| 0.7 | Add `PROFORMA_CREATED` event to EventBus | `services/operations/event_bus.py` | New event constant |

### Table Schema

```sql
CREATE TABLE IF NOT EXISTS proforma_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proforma_number TEXT UNIQUE,
    issue_date TEXT,
    valid_until TEXT,
    client_name TEXT,
    client_address TEXT,
    client_vat TEXT,
    client_phone TEXT,
    client_email TEXT,
    description TEXT,
    notes TEXT,
    line_items_json TEXT DEFAULT '[]',
    subtotal REAL DEFAULT 0,
    discount_type TEXT DEFAULT '',
    discount_value REAL DEFAULT 0,
    discount_amount REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0,
    grand_total REAL DEFAULT 0,
    currency TEXT DEFAULT 'EUR',
    mode TEXT DEFAULT 'client',
    status TEXT DEFAULT 'Draft',
    logo_path TEXT DEFAULT '',
    signature_path TEXT DEFAULT '',
    stamp_path TEXT DEFAULT '',
    company_color TEXT DEFAULT '#6366f1',
    created_at TEXT,
    updated_at TEXT
);
```

### Edge Cases
- **Duplicate proforma_number**: UNIQUE constraint catches it; repository catches `IntegrityError` and returns `None` with a log message.
- **Empty line_items_json**: Default to `'[]'` at DB level; service layer validates non-empty on generation.
- **Concurrent access**: Connection pool ensures single-writer safety.

### Definition of Done
- [ ] Table exists after fresh DB init
- [ ] `ProformaRepository` passes unit tests for CRUD
- [ ] All indices are created
- [ ] `PROFORMA_CREATED` event fires on record creation

---

## Phase 1: Service Layer — Proforma Business Logic

### Objective
Create `ProformaService` that orchestrates: generate PDF, save record, register in Document Center, handle drafts, send email.

### Dependencies
- Phase 0 (database + repository)
- Existing `services/invoicing/config_manager.py` (shared)
- Existing `services/invoicing/generator.py` (reused with proforma mode)
- Existing `services/document_service.py` (for `register_existing`)

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 1.1 | Create `ProformaService` class | `services/invoicing/proforma_service.py` | New file |
| 1.2 | Implement `__init__(self, db, prefs=None)` — init generator, event bus, client repo, document service | Same file | Constructor |
| 1.3 | Implement `generate(proforma_data, mode="client") -> str`: calls `InvoiceGenerator.generate_rich()` with `document_type="proforma"` flag | Same file | Generates PDF, returns filepath |
| 1.4 | Implement `generate_and_record(proforma_data) -> str`: generate PDF → create DB record → register in Document Center → publish event | Same file | Full generation pipeline |
| 1.5 | Implement `save_draft(data)`: writes to `data/proforma_drafts/{name}.json` | Same file | Draft persistence |
| 1.6 | Implement `load_draft(name) -> dict` | Same file | Draft deserialization |
| 1.7 | Implement `list_drafts() -> list[str]` | Same file | Draft listing |
| 1.8 | Implement `send_email(proforma_id, recipient, smtp_config, include_linked_docs=False)` | Same file | Email via NotificationCenter |
| 1.9 | Add proforma mode to `InvoiceGenerator.generate_rich()` — adds watermark "PROFORMA" and disclaimer "This is not a tax invoice" | `services/invoicing/generator.py:141` | Modify existing method |

### Key Design Decisions
- **Reuse `InvoiceGenerator.generate_rich()`**: Add a `document_type` parameter. When `"proforma"`: title changes to "Proforma Invoice", adds "PROFORMA" diagonal watermark, adds disclaimer footer. 95% of the PDF layout is identical. Zero risk to invoice PDF generation.
- **Proforma numbering**: `PROF-{year}-{id:04d}` computed at record creation time (after DB insert provides the `id`).
- **Registration in Document Center**: Category = `"proformas"`, tags = `["proforma", mode]`, no `entity_type`/`entity_id` (independent of trips).

### Edge Cases
- **Missing company config**: Fall back to `DEFAULT_CONFIG` from `config_manager.py`.
- **PDF file already exists**: Append counter `_2`, `_3` to filename.
- **Draft name collision**: Overwrite silently or prompt (service returns `False` if file exists, UI prompts).

### Definition of Done
- [ ] `generate_and_record` creates PDF, DB record, document center entry in one call
- [ ] Draft save/load roundtrip preserves all fields
- [ ] PDF has "PROFORMA" watermark and disclaimer
- [ ] `PROFORMA_CREATED` event fires and document center refreshes

---

## Phase 2: PDF Generator — Proforma-Specific Output

### Objective
Extend the existing `InvoiceGenerator` to produce proforma invoices with appropriate visual distinctions.

### Dependencies
- Phase 1 (service layer needs this)

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 2.1 | Add `document_type` parameter to `generate_rich()` signature | `services/invoicing/generator.py:141` | `def generate_rich(self, invoice_data, document_type="invoice") -> str:` |
| 2.2 | Conditional title: "INVOICE" vs "PROFORMA INVOICE" | Same file, header section | Branch on `document_type` |
| 2.3 | Add diagonal "PROFORMA" watermark (light gray, rotated 45°, center of page, large font) | Same file | ReportLab canvas drawing before build |
| 2.4 | Add disclaimer footer: "This is a proforma invoice and does not constitute a tax invoice." | Same file, footer section | Only when `document_type == "proforma"` |
| 2.5 | Change invoice number label to "Proforma #" in PDF header | Same file | Conditional label |
| 2.6 | Remove "Due Date" → replace with "Valid Until" | Same file, meta section | Proforma-specific field |
| 2.7 | No changes to layout, colors, fonts — inherits all existing branding | Same file | Zero structural changes |

### PDF Output Structure (Proforma vs Invoice)

| Section | Invoice | Proforma |
|---------|---------|----------|
| Title | "INVOICE" | "PROFORMA INVOICE" |
| Watermark | None | Diagonal "PROFORMA" |
| Number | INV-2026-0001 | PROF-2026-0001 |
| Due Date | present | "Valid Until" instead |
| Footer | "Thank you for your business" | + "This is not a tax invoice" |

### Edge Cases
- **Missing `valid_until`**: Omit the field from PDF (graceful).
- **Empty line items**: Still generate PDF but show "No items" row.

### Definition of Done
- [ ] Proforma PDF visually distinct from invoice PDF
- [ ] Watermark is visible but doesn't obscure content
- [ ] No regression in invoice PDF generation

---

## Phase 3: UI — Proforma Editor Widget

### Objective
Create `QtProformaEditor` — a standalone, embeddable widget mirroring `QtInvoiceEditor`'s structure but adapted for independent (non-trip) operation.

### Dependencies
- Phase 1 (service layer)
- Existing widgets: `StyledComboBox`, `StyledLineEdit`, `StyledTableWidget`, `StyledCheckBox`, `ScrollableFormContainer`, `SectionHeader`

### Architecture

```
QtProformaEditor(QWidget)
├── _build_top_bar()         → Client selector, mode checkboxes (no trip selector)
├── _build_client_section()  → FROM / BILL TO cards (from client or manual)
├── _build_details_section() → Proforma #, issue date, valid until, payment terms
├── _build_line_items_section() → Identical to invoice's StyledTableWidget
├── _build_totals_section()  → Tax, discount, currency, subtotal/grand total
├── _build_branding_section() → Logo, color, signature, stamp (same as invoice)
├── _build_notes_section()   → Free-text notes
├── _build_bottom_bar()      → Preview / Generate / Print / Email / Save Draft / Load Draft
└── _build_linked_docs_section() → NEW: Show linked documents, link/unlink button
```

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 3.1 | Create `QtProformaEditor` class with `__init__(self, parent=None, db=None, prefs=None)` | `ui/views/proforma_editor.py` | New file (~800 lines) |
| 3.2 | Implement `_build_top_bar()` — client combo, mode checkboxes (client/internal) | Same file | Mirrors invoice but without trip selector |
| 3.3 | Implement `_build_client_section()` — FROM (company config) / BILL TO (selected client) | Same file | Reuse canvas card pattern |
| 3.4 | Implement `_build_details_section()` — proforma number (read-only, auto), issue date, valid until, payment terms | Same file | "Valid Until" instead of "Due Date" |
| 3.5 | Implement `_build_line_items_section()` — identical to invoice's table | Same file | Copy table structure from invoice editor |
| 3.6 | Implement `_build_totals_section()` — tax, discount, currency controls | Same file | Copy from invoice editor |
| 3.7 | Implement `_build_branding_section()` — logo, color, signature, stamp | Same file | Copy from invoice editor |
| 3.8 | Implement `_build_notes_section()` — text edit | Same file | Copy |
| 3.9 | Implement `_build_linked_docs_section()` — list linked docs, "Link Document" button | Same file | NEW section |
| 3.10 | Implement signal connections (client selection → auto-fill, cell changed → recalc, mode toggled) | Same file | Mirror invoice editor's signal graph |
| 3.11 | Implement `_collect_proforma_data()` → dict | Same file | Data collection for PDF generation |
| 3.12 | Implement `_preview_pdf()`, `_generate_pdf()`, `_print_pdf()` | Same file | PDF lifecycle |
| 3.13 | Implement `_save_draft()`, `_load_draft()` | Same file | Draft persistence |
| 3.14 | Implement `_link_document()` — opens document picker from Doc Center, links via `DocumentService.link_document()` | Same file | NEW functionality |
| 3.15 | Implement `_on_linked_doc_clicked()` — opens linked document in detail | Same file | NEW functionality |
| 3.16 | Implement `_autofill_from_document()` — reads OCR text/extracted data from selected document to pre-fill fields | Same file | NEW functionality |
| 3.17 | Implement `wakeup()` / `shutdown()` lifecycle | Same file | i18n listener, event subscriptions |
| 3.18 | Implement `_retranslate_ui()` for i18n | Same file | Full translation support |

### Key Differences from Invoice Editor

| Feature | Invoice Editor | Proforma Editor |
|---------|---------------|-----------------|
| Trip selector | Present | **Absent** |
| Auto-fill from trip | Yes | **From document OCR text** |
| Number prefix | INV- | PROF- |
| Due date field | "Due Date" | "Valid Until" |
| Linked documents section | Not present | **Present** |
| Mode (client/internal) | Yes | Yes |

### Edge Cases
- **No client selected**: Allow manual entry in BILL TO fields.
- **Empty line items table**: Prevent PDF generation, show validation message.
- **Link document dialog cancelled**: Graceful no-op.
- **OCR text is empty for linked doc**: Show warning "No text extracted from this document".

### Definition of Done
- [ ] All UI sections render correctly
- [ ] Client selection auto-fills BILL TO from client repository
- [ ] Line items add/remove/duplicate/reorder work
- [ ] Tax and discount calculations are correct
- [ ] Draft save/load preserves all state
- [ ] Preview PDF opens correctly
- [ ] Generate PDF saves and registers in document center
- [ ] Document linking works (link/unlink, display linked docs)
- [ ] Auto-fill from document OCR text works
- [ ] i18n refresh translates all labels

---

## Phase 4: Document Center Integration — New Tab

### Objective
Add the proforma editor as a 3rd tab in the Document Center, add "Proformas" category to sidebar, wire up auto-refresh on proforma creation.

### Dependencies
- Phase 3 (proforma editor widget must exist)

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 4.1 | Add "proformas" to category labels dict | `ui/views/document_center_view.py:631` | After "invoices" entry |
| 4.2 | Add "proformas" to category button loop | `ui/views/document_center_view.py:649` | Add to `for cat_key in [...]` |
| 4.3 | Create `_proforma_page` widget in `_build_ui()` | `ui/views/document_center_view.py:403` | After automation tab |
| 4.4 | Instantiate `QtProformaEditor` (lazy import) in `_build_proforma_view()` | Same file | Mirror `_build_automation_view()` pattern |
| 4.5 | Add tab to `QTabWidget`: `self._tab_widget.addTab(self._proforma_page, "")` | Same file | Tab index 2 |
| 4.6 | Update `_refresh_tab_titles()` to set proforma tab text | Same file:472 | `t("docs.tab_proforma", default="Proforma")` |
| 4.7 | Update `_on_tab_changed()` to wake proforma editor on tab switch | Same file:481 | Mirror automation tab handling |
| 4.8 | Subscribe to `PROFORMA_CREATED` event for auto-refresh | Same file:286 | Add subscription in `__init__` |
| 4.9 | Update `_cleanup()` to unsubscribe `PROFORMA_CREATED` | Same file:329 | Cleanup |
| 4.10 | Update category loading to include proformas count | Same file (`_load_categories`) | Category count |

### Tab Layout (After Changes)

```
QtDocumentCenterView
└── QTabWidget
    ├── [0] Documents (existing 3-panel layout)
    ├── [1] Automation (existing pipeline)
    └── [2] Proforma (new QtProformaEditor)
```

### Edge Cases
- **Lazy import fails**: Return `None`, tab is empty — handle gracefully with a fallback label.
- **Proforma tab selected when no DB**: Editor shows empty/disabled state.
- **Very wide document center**: Proforma editor uses `ScrollableFormContainer` which handles overflow.

### Definition of Done
- [ ] Document Center has 3 tabs: Documents | Automation | Proforma
- [ ] "Proformas" appears in sidebar category list with count
- [ ] Switching to Proforma tab triggers `wakeup()` on editor
- [ ] Generating a proforma triggers document center refresh
- [ ] Existing functionality (Documents, Automation tabs) is unchanged

---

## Phase 5: OCR Retry on Startup

### Objective
When OCR fails mid-session (app closed before OCR thread completes), retry those documents on next startup. This applies to ALL document center documents, including newly generated proformas.

### Dependencies
- None (independent, can run in parallel with Phases 1-3)

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 5.1 | Add `_retry_pending_ocr()` to `OcrService` — queries documents where `ocr_run_at IS NULL OR ocr_run_at = ''` AND `file_path IS NOT NULL` AND file exists on disk, enqueues them | `services/document/ocr_service.py` | New method |
| 5.2 | Add `text_content IS NULL OR text_content = ''` to the query condition (only retry docs with no extracted text) | Same file | Refine query |
| 5.3 | Call `_retry_pending_ocr()` from `main.py` startup sequence, AFTER OCR service is initialized but BEFORE UI shows | `main.py:99` (after cloud OCR init) | One-line call |
| 5.4 | Add rate limiting: max 50 docs per startup to prevent queue overload | Same file | Safety guard |
| 5.5 | Log each retried document for troubleshooting | Same file | Logging |

### Edge Cases
- **File deleted after registration**: Skip (check `os.path.exists`).
- **Very large queue**: Cap at 50, remaining will retry on next restart.
- **OCR service not initialized**: Graceful skip with log warning.

### Definition of Done
- [ ] Documents with empty `ocr_run_at` and empty `text_content` are re-queued on startup
- [ ] Max 50 documents per startup
- [ ] Deleted files are skipped silently
- [ ] Does not block app startup (async thread)

---

## Phase 6: i18n & Translations

### Objective
Add all translation keys for the proforma editor to the English file and provide the structure for other languages.

### Dependencies
- Phase 3 (UI strings must be finalized)

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 6.1 | Add `proforma_editor` section to English translations | `data/translations/en.json` | New i18n section (~50 keys) |
| 6.2 | Add `docs.tab_proforma` | Same file | "Proforma" |
| 6.3 | Add `docs.cat_proformas` | Same file | "Proformas" |
| 6.4 | Add `proforma_created` event message | Same file | Toast/popup string |
| 6.5 | Add `proforma_pdf.*` section for PDF strings (title, watermark, disclaimer) | Same file | PDF strings |

### Key Translation Keys (English)

```json
"proforma_editor": {
    "title": "Proforma Invoice Editor",
    "subtitle": "Create and manage proforma invoices",
    "proforma_number": "Proforma #",
    "valid_until": "Valid Until",
    "link_document": "Link Document",
    "unlink_document": "Unlink",
    "linked_documents": "Linked Documents",
    "no_linked_docs": "No documents linked",
    "autofill_from_doc": "Auto-Fill from Document",
    "select_document": "Select a document to link",
    "document_linked": "Document linked successfully",
    "proforma_generated": "Proforma generated: {}",
    "include_linked_docs": "Include linked documents in email"
},
"proforma_pdf": {
    "title": "PROFORMA INVOICE",
    "disclaimer": "This is a proforma invoice and does not constitute a tax invoice.",
    "watermark": "PROFORMA"
}
```

### Definition of Done
- [ ] All English keys present
- [ ] All UI labels use `t()` lookup (no hardcoded English strings)
- [ ] Fallback values provided for all `t()` calls

---

## Phase 7: Automation Email Integration

### Objective
When sending a proforma via email from the automation pipeline, linked CMRs/invoices are only attached if the user explicitly opts in.

### Dependencies
- Phase 3 (linked documents section exists)
- Phase 4 (document center registration)

### Step-by-Step Tasks

| # | Task | File | Action |
|---|------|------|--------|
| 7.1 | Add `include_linked_docs` checkbox to email dialog in proforma editor | `ui/views/proforma_editor.py` | New checkbox in email flow |
| 7.2 | Pass `include_linked_docs` flag to `ProformaService.send_email()` | Same file | Wire checkbox to service |
| 7.3 | In `send_email()`, query linked documents for this proforma | `services/invoicing/proforma_service.py` | Filter by entity_type="proforma" |
| 7.4 | Only attach linked CMR/invoice documents if `include_linked_docs=True` | Same file | Conditional attachment |
| 7.5 | Log which documents were included/excluded | Same file | Audit trail |

### Edge Cases
- **Linked doc file missing on disk**: Skip with warning, still send proforma.
- **No linked documents**: Checkbox disabled/grayed out.

### Definition of Done
- [ ] Checkbox defaults to unchecked (opt-in)
- [ ] When checked, linked CMRs and invoices are attached
- [ ] When unchecked, only proforma PDF is attached
- [ ] Missing linked files don't block email send

---

## Risk Assessment & Regression Analysis

### High Risk

| Risk | Mitigation |
|------|-----------|
| Modifying `InvoiceGenerator.generate_rich()` could break invoice PDFs | Add `document_type` param with default `"invoice"` — zero behavioral change for existing callers |
| Adding tab to Document Center `QTabWidget` could shift tab indices | Use explicit tab indices (0,1,2) and defensive `hasattr` checks |

### Medium Risk

| Risk | Mitigation |
|------|-----------|
| Proforma editor shares widgets but not code with invoice editor — maintenance divergence | Document the shared patterns; if major changes needed in future, consider extraction to base class |
| OCR retry on startup could slow app launch | Run in background thread; cap at 50 documents; don't block UI |

### Low Risk

| Risk | Mitigation |
|------|-----------|
| New "proformas" category breaks sidebar layout | Category list is dynamically built — adding one more entry has no layout impact |
| Translation files missing keys | All `t()` calls include `default=` fallback |

### Zero Regression Guarantees

- **`InvoiceGenerator.generate_rich()`**: Default parameter `document_type="invoice"` → existing behavior preserved
- **`Document Center`**: Existing 2 tabs untouched; new tab is additive
- **`QtInvoiceEditor`**: No changes to this file
- **`InvoiceService`**: No changes to this file
- **`GeneratorsView`**: Unchanged
- **Invoice repository/table**: Unchanged

---

## File Change Summary

| File | Action | Lines (est.) |
|------|--------|--------------|
| `database/schema.py` | Add table + indices | +30 |
| `database/db_manager.py` | Register table, add methods | +30 |
| `repositories/proforma_repository.py` | **New file** | ~150 |
| `services/invoicing/proforma_service.py` | **New file** | ~200 |
| `services/invoicing/generator.py` | Modify `generate_rich()` | +30 |
| `services/operations/event_bus.py` | Add `PROFORMA_CREATED` | +2 |
| `ui/views/proforma_editor.py` | **New file** | ~800 |
| `ui/views/document_center_view.py` | Add tab, category, event subscription | +50 |
| `services/document/ocr_service.py` | Add `_retry_pending_ocr()` | +30 |
| `main.py` | Call OCR retry on startup | +3 |
| `data/translations/en.json` | Add proforma i18n keys | +50 |
| **Total** | **10 files modified, 3 new** | **~1,375 lines** |

---

## Execution Order (Critical Path)

```
Phase 0 (DB) ──► Phase 1 (Service) ──► Phase 2 (PDF Gen) ──► Phase 3 (UI Editor)
                                                                      │
                                                                      ▼
                                            Phase 4 (Doc Center Tab) ──► Phase 7 (Email)

Phase 5 (OCR Retry) — independent, can run in parallel with Phase 1-3
Phase 6 (i18n) — can run in parallel with Phase 3
```
