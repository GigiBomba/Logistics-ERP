# Romanian Invoice & E-Factura Compliance Audit Report
**Operion ERP** — July 2026

---

## Executive Summary

A comprehensive compliance audit of Operion ERP's invoice subsystem for Romanian fiscal
requirements and e-Factura readiness has been completed. The system has a solid foundation
with basic invoice generation, proforma handling, receipt generation, and CMR generation.
However, **critical gaps exist** in the database schema (missing columns referenced by the
repository), invoice data model completeness, numbering safety, and Romanian-specific
features. These must be addressed before production launch.

---

## A. Compliance Status

### Invoice Data Completeness — ❌ NOT COMPLIANT

| Requirement | Status | Notes |
|---|---|---|
| Seller: legal_company_name | ✅ | In company config |
| Seller: cui_vat_number | ✅ | `cui` in company config |
| Seller: trade_registry_number | ✅ | `reg_number` in company config |
| Seller: full_address | ✅ | `address` in company config |
| Seller: county | ❌ **MISSING** | Not stored |
| Seller: city | ❌ **MISSING** | Not stored |
| Seller: country | ⚠️ | Not explicitly on company config |
| Seller: iban | ❌ **MISSING** | Not stored — PDF cannot show IBAN |
| Seller: bank_name | ❌ **MISSING** | Not stored |
| Seller: email | ✅ | In company config |
| Seller: phone | ✅ | In company config |
| Buyer (company): legal_company_name | ✅ | `name` on client |
| Buyer: cui_vat_number | ✅ | `vat_number` on client |
| Buyer: full_address | ✅ | `address` on client |
| Buyer: county | ❌ **MISSING** | Not on client model |
| Buyer: city | ⚠️ | `city` exists on create model but rarely used |
| Buyer: country | ⚠️ | `country` exists on client |
| EU Buyer: vat_number | ✅ | `vat_number` on client |
| EU Buyer: country_code | ⚠️ | `country` on client but no ISO code validation |
| Individual Buyer: full_name | ❌ **MISSING** | No individual buyer support |
| Individual Buyer: address | ❌ **MISSING** | — |
| Invoice Header: invoice_type | ❌ **MISSING** | No `invoice_type` field |
| Invoice Header: exchange_rate | ❌ **MISSING** | Not on invoice model or schema |
| Line Items: description | ✅ | |
| Line Items: quantity | ✅ | |
| Line Items: unit_of_measure | ❌ **MISSING** | Not in InvoiceLineItem model |
| Line Items: unit_price_without_vat | ⚠️ | `unit_price` exists but ambiguous re VAT |
| Line Items: discount | ❌ **MISSING** | Only on proforma, not on invoice line items |
| Line Items: taxable_amount | ❌ **MISSING** | |
| Line Items: vat_rate | ✅ | |
| Line Items: vat_amount | ⚠️ | `total_vat` per line item |
| Line Items: line_total | ⚠️ | `total_gross` serves this |
| Totals: subtotal_without_vat | ⚠️ | `subtotal_net` exists |
| Totals: total_vat | ✅ | |
| Totals: grand_total | ✅ | |
| Totals: amount_paid | ❌ **MISSING** | No payment tracking on invoice |
| Totals: amount_remaining | ❌ **MISSING** | — |

### PDF Compliance — ⚠️ PARTIALLY COMPLIANT

| Requirement | Status | Notes |
|---|---|---|
| Seller name + CUI | ✅ | |
| Buyer name + CUI | ✅ | |
| Invoice number | ✅ | |
| Invoice date | ✅ | |
| Due date | ✅ | |
| Line items | ⚠️ | Basic generator: single "Transport fee" line only. Rich generator good. |
| VAT breakdown | ❌ | Only total_vat shown, not breakdown by VAT rate |
| Total amount | ✅ | |
| Currency | ✅ | |
| IBAN | ❌ **MISSING** | Never shown on PDF |
| Payment instructions | ❌ **MISSING** | Never shown |

### XML Readiness — ❌ NOT IMPLEMENTED

- No XML export layer exists for invoices
- `cmr_efti.py` generates eFTI XML for CMRs only
- No UBL invoice schema defined anywhere
- Invoice domain lacks stable field mapping for XML serialization

### Audit Trail Readiness — ⚠️ PARTIALLY COMPLIANT

- `AuditService` logs events to `operation_events` table
- No immutable archival mechanism for finalized invoices
- Soft delete exists via `deleted_at` but does not prevent mutation
- Status history tracked only via audit events, not a dedicated status_history table

### CMR Readiness — ✅ COMPLIANT

- Full 24-box CMR layout with all required parties, cargo, transport details
- eFTI XML embedding
- 4-copy generation with color coding
- Successive carriers, ADR, financial grid
- Digital signatures and stamps

### Proforma Safety — ✅ COMPLIANT

- Separate numbering series (PROF-)
- Separate table (`proforma_invoices`)
- PDF watermark "PROFORMA"
- Explicit disclaimer: "This is a proforma invoice and does not constitute a tax invoice"
- Explicit conversion action required
- Status changes to "Converted" after conversion

### Receipt Traceability — ⚠️ PARTIALLY COMPLIANT

- Receipt number (RCT-/REC- series)
- Date
- Payer (`received_from_name`)
- Amount and currency
- Payment method stored
- `invoice_reference` links to invoices
- Missing: explicit `payment_method` in ReceiptResult model
- Missing: audit timestamp on receipt creation

---

## B. Missing Requirements — All Items

### CRITICAL

| # | Item | Location | Impact |
|---|---|---|---|
| C1 | **Invoices table columns missing from schema** | `database/schema.py` — TABLE_INVOICES only has 7 columns; repository expects 20+ | Code will **fail at runtime** trying to INSERT/UPDATE columns that don't exist (client_id, currency, notes, line_items_json, subtotal_net, total_vat, total_gross, pdf_path, created_at, updated_at) |
| C2 | **Race condition in invoice numbering** | `invoice_repository.py:232-235` uses `MAX(id) + 1` outside a transaction | Two concurrent requests can generate the same invoice number |
| C3 | **Price precision - no discount/taxable_amount on invoice line items** | `models/invoice_models.py:7-14` | Cannot generate Romanian-compliant line-level VAT/discount details |

### HIGH

| # | Item | Location | Impact |
|---|---|---|---|
| H1 | **No IBAN/bank_name on seller config or PDF** | `config_manager.py`, `generator.py` | Romanian invoices legally require IBAN |
| H2 | **No invoice_type field** | `models/invoice_models.py` | Cannot distinguish invoice types (factura, storno, etc.) |
| H3 | **No amount_paid / amount_remaining tracking** | `models/invoice_models.py` | Cannot track partial payments |
| H4 | **No E-Factura status fields** | Schema, models, repository | No path to e-Factura integration |
| H5 | **No immutable archival for finalized invoices** | `service.py` (finalize method) | Finalized invoices can still be deleted; no archive |
| H6 | **Status enum incomplete** | `service.py` | Only draft/finalized/cancelled — missing 6 e-Factura states |
| H7 | **No county/city on client for Romanian buyers** | `models/client_models.py` | Romanian invoices require county |

### MEDIUM

| # | Item | Location | Impact |
|---|---|---|---|
| M1 | **No exchange_rate field** | `invoice_models.py` | Multi-currency invoices need explicit rate |
| M2 | **No transport_order_number field** | Models/schema | Romanian logistics reference |
| M3 | **No unit_of_measure on line items** | `models/invoice_models.py` | e-Factura XML requires UoM |
| M4 | **No per-rate VAT breakdown in PDF** | `generator.py` | Cannot show VAT per rate (19%, 9%, 5%) |
| M5 | **No individual buyer support** | `models/client_models.py` | Cannot invoice individuals (PF) |
| M6 | **line_items stored as JSON string** | Schema/repository | Not queryable; schema normalization needed for production |

### LOW

| # | Item | Location | Impact |
|---|---|---|---|
| L1 | **No dispatch_reference field** | Schema | Operational reference |
| L2 | **vehicle_registration stored as truck_plate, not dedicated field** | Trips table | Adequate but not normalized |
| L3 | **City in client create model but not in client result** | `client_models.py:52` | Inconsistency |
| L4 | **Proforma discounts not synced on conversion to invoice** | `proforma_service.py:464-479` | Discount info may be lost |
| L5 | **No receipt audit timestamp field** | `receipt_models.py` | No `updated_at` on receipt result |

---

## C. Severity Summary

| Severity | Count |
|---|---|
| **CRITICAL** | 3 |
| **HIGH** | 7 |
| **MEDIUM** | 6 |
| **LOW** | 5 |

---

## D. Launch Decision

### Can Operion legally launch as an invoicing ERP with XML export and external ANAF submission workflows?

**No — not in the current state.**

The system has **critical blockers** that would cause runtime failures:
1. The `invoices` database schema is missing approximately 10 columns that the repository
   code attempts to write to. The first invoice created through the typed API will fail
   with an SQLite `OperationalError`.
2. The invoice numbering system has a race condition that can produce duplicate numbers
   under concurrent access.
3. Line items lack Romanian-required fields (discount, unit_of_measure, taxable_amount).

Once these blockers are resolved, the system would be **ready for controlled launch**
with the understanding that e-Factura XML export and automatic ANAF submission are
documented as **future milestones**.

### Is automatic ANAF submission the only remaining major compliance milestone?

**No.** Before reaching that milestone, the following must also be completed:
- XML/UBL export layer
- E-Factura status state machine
- Per-rate VAT breakdown in PDF
- IBAN/bank_name on invoice
- Individual buyer support
- Immutable audit trail for finalized invoices

---

## E. Required Pre-Launch Tasks (Concrete Checklist)

### Pre-Day-1 (Must Fix Before Any Production Use)

- [ ] **C1:** Add missing columns to `invoices` table schema and corresponding migration
- [ ] **C2:** Replace `MAX(id) + 1` numbering with transaction-safe sequence
- [ ] **C1 fix:** Update `_run_column_migrations()` to add all missing invoice columns
- [ ] **C3:** Add `unit_of_measure`, `discount`, `taxable_amount`, `line_total` to `InvoiceLineItem`

### Pre-Launch (Before September)

- [ ] **H1:** Add `iban`, `bank_name` to company config and invoice PDF
- [ ] **H2:** Add `invoice_type` field to invoice model/schema
- [ ] **H3:** Add `amount_paid`, `amount_remaining` to invoice model and tracking logic
- [ ] **H4:** Add E-Factura fields to schema, models, and repository
- [ ] **H5:** Implement immutable archival — prevent delete/edit of finalized invoices
- [ ] **H6:** Implement complete status state machine with transition validation
- [ ] **H7:** Add `county` to client model and ensure it appears on invoice PDF
- [ ] **M4:** Implement VAT breakdown by rate in PDF generator
- [ ] **M1:** Add `exchange_rate` to invoice model
- [ ] **Part 10:** Implement deterministic XML export layer (UBL-ready)
- [ ] **H6 (state machine):** Add status history table with transition timestamps

### Post-Launch (Phase 2)

- [ ] XML → UBL e-Factura adapter
- [ ] ANAF gateway (optional connected service)
- [ ] Individual buyer (PF) invoice support
- [ ] Recurring invoice templates
- [ ] Automated payment reconciliation

---

## F. Detailed Findings

### F1. Schema Gap — Invoices Table (CRITICAL C1)

**Schema defines only:**
```sql
CREATE TABLE invoices (
    id, trip_id, invoice_number, issue_date, due_date, total_amount, status
);
```

**Repository expects these additional columns:**
`client_id`, `currency`, `notes`, `line_items_json`, `subtotal_net`, `total_vat`,
`total_gross`, `pdf_path`, `created_at`, `updated_at`, `company_id`

The `company_id` column is added by `_ensure_column` in `_run_column_migrations()`
but the other 10 columns are **never added**. Any call to `InvoiceRepository.create()`
or `InvoiceRepository.update()` will fail at the SQL level.

### F2. Numbering Race Condition (CRITICAL C2)

```python
# invoice_repository.py:232-235
row = self._fetchone(
    f"SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM {self.TABLE} ..."
)
nxt = int(row["nxt"]) if row else 1
```

Two concurrent requests can read the same `MAX(id)`, compute the same `nxt`, and
generate duplicate invoice numbers. Fix: use a proper sequence table with
`INSERT ... RETURNING seq` under `BEGIN IMMEDIATE`.

### F3. InvoiceLineItem Incomplete (CRITICAL C3)

Current model:
```python
class InvoiceLineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    vat_rate: float = 19.0
    total_net: Optional[float] = None
    total_vat: Optional[float] = None
    total_gross: Optional[float] = None
```

Missing for Romanian compliance:
- `unit_of_measure: str` (e.g., "buc", "kg", "km", "l")
- `discount_percent: float = 0`
- `discount_amount: float = 0`
- `taxable_amount: Optional[float]` (net after discount)
- `line_total: Optional[float]`

### F4. Status State Machine Gap (HIGH H6)

Current status values used in code: `draft`, `finalized`, `cancelled`, `Unpaid`, `Paid`

Required for e-Factura:
```
draft → finalized → xml_generated → submitted_externally → accepted
                                                          → rejected
                                                          → manual_review
```

No validation ensures `cancelled` can only come from `draft` or `finalized`.

### F5. PDF IBAN Missing (HIGH H1)

The company config (`config_manager.py`) does not store or expose IBAN or bank name.
The PDF generator (`generator.py`) never renders payment details beyond:
```html
Email: ... | Tel: ...
```

Romanian fiscal invoices must include IBAN and payment instructions.

### F6. No XML Export Layer (MEDIUM M4)

Zero XML generation code exists for invoices. The only XML code is `cmr_efti.py`
for CMR eFTI. No UBL invoice template, no field mapping, no namespace handling.

---

## G. Code Locations Reference

| Component | Primary File(s) |
|---|---|
| Invoice Models | `models/invoice_models.py` |
| Invoice DB Schema | `database/schema.py:63-74` |
| Schema Migrations | `database/db_manager.py:629-928` (column migrations) |
| Invoice Repository | `repositories/invoice_repository.py` |
| Invoice Service | `services/invoicing/service.py` |
| Invoice PDF Generator | `services/invoicing/generator.py` |
| Company Config | `services/invoicing/config_manager.py` |
| Proforma Models | `models/proforma_models.py` |
| Proforma Repository | `repositories/proforma_repository.py` |
| Proforma Service | `services/invoicing/proforma_service.py` |
| Receipt Models | `models/receipt_models.py` |
| Receipt Repository | `repositories/receipt_repository.py` |
| Receipt Generator | `services/invoicing/receipt_generator.py` |
| CMR Models | `models/cmr_models.py` |
| CMR Generator | `services/invoicing/cmr_generator.py` |
| CMR eFTI XML | `services/invoicing/cmr_efti.py` |
| Client Models | `models/client_models.py` |
| Client Repository | `repositories/client_repository.py` |
| Audit Service | `services/audit_service.py` |
| Numbering Service | `services/numbering_service.py` |
| Document Models | `models/document_models.py` |
| Base Repository | `repositories/__init__.py` |
| API Schemas (invoices) | `backend/schemas/invoice.py` |
| API Schemas (receipts) | `backend/schemas/receipt.py` |

---

*Report generated by automated compliance audit. All findings are based on static
code analysis of the current codebase at commit time. Some issues may be partially
addressed in unreviewed branches or planned work.*
