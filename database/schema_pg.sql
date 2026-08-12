-- =============================================================================
-- Operion ERP — PostgreSQL Schema
-- =============================================================================
-- Generated from database/schema.py for PostgreSQL migration (Phase 2).
-- Transformations applied:
--   INTEGER PRIMARY KEY AUTOINCREMENT → BIGINT GENERATED ALWAYS AS IDENTITY
--   datetime('now')                    → CURRENT_TIMESTAMP
--   FTS5 virtual tables                → tsvector column + GIN index (see §FTS)
--   SQLite triggers with RAISE(ABORT)   → PL/pgSQL functions with RAISE EXCEPTION
--   REAL                               → DOUBLE PRECISION
--   SUBSTR()                           → SUBSTRING()
-- =============================================================================

-- ── Schema version tracking ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);

-- ── Core: trips ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trips (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TEXT,
    truck_number TEXT,
    driver_name TEXT,
    client_name TEXT,
    distance_km DOUBLE PRECISION,
    total_price_eur DOUBLE PRECISION,
    rate_per_km DOUBLE PRECISION,
    gross_per_km DOUBLE PRECISION,
    net_profit DOUBLE PRECISION,
    start_date TEXT,
    end_date TEXT,
    payment_date TEXT,
    extra_costs DOUBLE PRECISION,
    fuel_cost DOUBLE PRECISION,
    toll_cost DOUBLE PRECISION,
    salary_cost DOUBLE PRECISION,
    currency TEXT,
    status TEXT,
    loading_country TEXT,
    delivery_country TEXT,
    driver_id INTEGER,
    truck_id INTEGER,
    client_id INTEGER,
    route_history_v2_id INTEGER,
    truck_consumption_l_per_100km DOUBLE PRECISION,
    context_json TEXT,
    price_pre_vat DOUBLE PRECISION DEFAULT 0,
    vat_percent DOUBLE PRECISION DEFAULT 0,
    cmr_number TEXT,
    cmr_sequence INTEGER,
    cargo_description TEXT,
    cargo_marks TEXT,
    package_count INTEGER,
    package_type TEXT,
    gross_weight_kg DOUBLE PRECISION,
    volume_m3 DOUBLE PRECISION,
    hs_code TEXT,
    carrier_instructions TEXT,
    carrier_reservations TEXT,
    special_agreements TEXT,
    carriage_payer TEXT,
    documents_attached TEXT,
    place_of_loading TEXT,
    place_of_loading_date TEXT,
    adr_info_json TEXT,
    cmr_status TEXT DEFAULT 'draft',
    cmr_remarks TEXT,
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_trips_date ON trips(created_at);
CREATE INDEX IF NOT EXISTS idx_trips_truck ON trips(truck_number);
CREATE INDEX IF NOT EXISTS idx_trips_client_name ON trips(client_name);
CREATE INDEX IF NOT EXISTS idx_trips_driver_name ON trips(driver_name);
CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status);
CREATE INDEX IF NOT EXISTS idx_trips_client_status ON trips(client_name, status);
CREATE INDEX IF NOT EXISTS idx_trips_start_date ON trips(start_date);
CREATE INDEX IF NOT EXISTS idx_trips_delivery_country ON trips(delivery_country);
CREATE INDEX IF NOT EXISTS idx_trips_loading_country ON trips(loading_country);
CREATE INDEX IF NOT EXISTS idx_trips_driver_id ON trips(driver_id);
CREATE INDEX IF NOT EXISTS idx_trips_client_id ON trips(client_id);
CREATE INDEX IF NOT EXISTS idx_trips_payment_date ON trips(payment_date);
CREATE INDEX IF NOT EXISTS idx_trips_cmr_status ON trips(cmr_status);
CREATE INDEX IF NOT EXISTS idx_trips_truck_id ON trips(truck_id);
CREATE INDEX IF NOT EXISTS idx_trips_company ON trips(company_id);
CREATE INDEX IF NOT EXISTS idx_trips_deleted ON trips(deleted_at);
-- Generated column: month
ALTER TABLE trips ADD COLUMN IF NOT EXISTS month TEXT GENERATED ALWAYS AS (SUBSTRING(created_at, 1, 7)) STORED;
CREATE INDEX IF NOT EXISTS idx_trips_month ON trips(month);

-- ── Invoices ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id INTEGER UNIQUE,
    invoice_number TEXT UNIQUE,
    issue_date TEXT,
    due_date TEXT,
    total_amount DOUBLE PRECISION,
    status TEXT,
    company_id INTEGER,
    deleted_at TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_invoices_issue_date ON invoices(issue_date);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_invoices_company ON invoices(company_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_deleted ON invoices(deleted_at);

-- ── Proforma invoices ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS proforma_invoices (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
    subtotal DOUBLE PRECISION DEFAULT 0,
    discount_type TEXT DEFAULT '',
    discount_value DOUBLE PRECISION DEFAULT 0,
    discount_amount DOUBLE PRECISION DEFAULT 0,
    tax_rate DOUBLE PRECISION DEFAULT 0,
    tax_amount DOUBLE PRECISION DEFAULT 0,
    grand_total DOUBLE PRECISION DEFAULT 0,
    currency TEXT DEFAULT 'EUR',
    mode TEXT DEFAULT 'client',
    status TEXT DEFAULT 'Draft',
    logo_path TEXT DEFAULT '',
    signature_path TEXT DEFAULT '',
    stamp_path TEXT DEFAULT '',
    company_color TEXT DEFAULT '#6366f1',
    created_at TEXT,
    updated_at TEXT,
    company_id INTEGER,
    deleted_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_proforma_number ON proforma_invoices(proforma_number);
CREATE INDEX IF NOT EXISTS idx_proforma_client ON proforma_invoices(client_name);
CREATE INDEX IF NOT EXISTS idx_proforma_status ON proforma_invoices(status);
CREATE INDEX IF NOT EXISTS idx_proforma_company ON proforma_invoices(company_id);

-- ── Email logs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id INTEGER,
    recipient TEXT,
    subject TEXT,
    timestamp TEXT,
    status TEXT,
    error_msg TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(id)
);
CREATE INDEX IF NOT EXISTS idx_email_logs_trip ON email_logs(trip_id);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status);

-- ── Invoice reminders ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoice_reminders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id INTEGER NOT NULL,
    trip_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL,
    days_offset INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);
CREATE INDEX IF NOT EXISTS idx_invoice_reminders_lookup ON invoice_reminders(invoice_id, reminder_type, status);

-- ── Settings ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
    key TEXT NOT NULL,
    value TEXT,
    company_id INTEGER REFERENCES companies(id),
    PRIMARY KEY (key, company_id)
);

-- ── Trucks ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trucks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plate_number TEXT UNIQUE,
    model TEXT,
    manufacturer TEXT,
    year INTEGER,
    vin TEXT,
    fuel_consumption DOUBLE PRECISION,
    mileage DOUBLE PRECISION,
    monthly_rate DOUBLE PRECISION,
    status TEXT,
    insurance_expiry TEXT,
    inspection_expiry TEXT,
    maintenance_due DOUBLE PRECISION,
    active_status INTEGER DEFAULT 1,
    tachograph_expiry TEXT,
    tracking_device_id TEXT,
    trailer_plate TEXT DEFAULT '',
    max_payload_kg DOUBLE PRECISION DEFAULT 0,
    cmr_insurance_number TEXT DEFAULT '',
    cmr_insurance_expiry TEXT DEFAULT '',
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_trucks_company ON trucks(company_id);
CREATE INDEX IF NOT EXISTS idx_trucks_deleted ON trucks(deleted_at);

-- ── Route tables ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT,
    start TEXT,
    destination TEXT,
    via TEXT,
    distance_km DOUBLE PRECISION,
    duration_min DOUBLE PRECISION,
    geometry TEXT,
    created_at TEXT,
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_routes_company ON routes(company_id);

CREATE TABLE IF NOT EXISTS route_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_id INTEGER,
    computed_at TEXT,
    distance_km DOUBLE PRECISION,
    duration_min DOUBLE PRECISION,
    fuel_cost DOUBLE PRECISION,
    toll_cost DOUBLE PRECISION,
    total_cost DOUBLE PRECISION,
    price_recommended DOUBLE PRECISION,
    company_id INTEGER,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);
CREATE INDEX IF NOT EXISTS idx_route_history_company ON route_history(company_id);

CREATE TABLE IF NOT EXISTS route_history_v2 (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_fingerprint TEXT NOT NULL UNIQUE,
    metadata_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_calculated_at TEXT NOT NULL,
    calculation_count INTEGER NOT NULL DEFAULT 1,
    stops_json TEXT NOT NULL,
    geometry_compressed BYTEA,
    geometry_encoding TEXT NOT NULL DEFAULT 'zlib-json',
    total_distance_km DOUBLE PRECISION,
    duration_min DOUBLE PRECISION,
    truck_id TEXT,
    truck_label TEXT,
    truck_json TEXT,
    profile TEXT,
    excluded_countries_json TEXT,
    toll_estimates_json TEXT,
    fuel_estimates_json TEXT,
    profit_estimates_json TEXT,
    countries_traversed_json TEXT,
    route_summary_json TEXT,
    archived_at TEXT,
    is_committed INTEGER NOT NULL DEFAULT 0,
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_route_history_v2_created ON route_history_v2(created_at);
CREATE INDEX IF NOT EXISTS idx_route_history_v2_last_calculated ON route_history_v2(last_calculated_at);
CREATE INDEX IF NOT EXISTS idx_route_history_v2_truck ON route_history_v2(truck_id);
CREATE INDEX IF NOT EXISTS idx_route_history_v2_profile ON route_history_v2(profile);
CREATE INDEX IF NOT EXISTS idx_route_history_v2_fingerprint ON route_history_v2(route_fingerprint);
CREATE INDEX IF NOT EXISTS idx_route_history_v2_company ON route_history_v2(company_id);

CREATE TABLE IF NOT EXISTS route_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_id INTEGER,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (route_id) REFERENCES route_history_v2(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_route_events_route ON route_events(route_id);
CREATE INDEX IF NOT EXISTS idx_route_events_type ON route_events(event_type);

CREATE TABLE IF NOT EXISTS truck_route_assignments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    truck_id TEXT NOT NULL,
    route_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'assigned',
    assigned_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    archived_at TEXT,
    notes TEXT,
    FOREIGN KEY (route_id) REFERENCES route_history_v2(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_truck_route_assignments_truck ON truck_route_assignments(truck_id);
CREATE INDEX IF NOT EXISTS idx_truck_route_assignments_route ON truck_route_assignments(route_id);
CREATE INDEX IF NOT EXISTS idx_truck_route_assignments_status ON truck_route_assignments(status);

-- ── Operations Engine ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT,
    message TEXT,
    truck_id TEXT,
    trip_id INTEGER REFERENCES trips(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    resolved_at TEXT,
    metadata_json TEXT,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);
CREATE INDEX IF NOT EXISTS idx_alerts_truck ON alerts(truck_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_alerts_company ON alerts(company_id);

CREATE TABLE IF NOT EXISTS operation_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    data_json TEXT,
    user_id INTEGER DEFAULT 0,
    company_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operation_events_type ON operation_events(event_type);
CREATE INDEX IF NOT EXISTS idx_operation_events_company ON operation_events(company_id);

CREATE TABLE IF NOT EXISTS trip_status_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    trigger TEXT,
    created_at TEXT NOT NULL,
    company_id INTEGER,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_trip_status_history_trip ON trip_status_history(trip_id);
CREATE INDEX IF NOT EXISTS idx_trip_status_history_company ON trip_status_history(company_id);

-- ── Fleet Maintenance ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    truck_id INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    date TEXT NOT NULL,
    km DOUBLE PRECISION,
    cost DOUBLE PRECISION,
    notes TEXT,
    service_provider TEXT,
    attachment_path TEXT,
    created_at TEXT NOT NULL,
    company_id INTEGER,
    deleted_at TEXT,
    FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_maintenance_records_truck ON maintenance_records(truck_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_records_type ON maintenance_records(maintenance_type);
CREATE INDEX IF NOT EXISTS idx_maintenance_records_date ON maintenance_records(date);
CREATE INDEX IF NOT EXISTS idx_maintenance_records_company ON maintenance_records(company_id);

CREATE TABLE IF NOT EXISTS maintenance_schedules (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    truck_id INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    interval_km DOUBLE PRECISION,
    interval_months INTEGER,
    fixed_expiry_date TEXT,
    last_done_km DOUBLE PRECISION,
    last_done_date TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    company_id INTEGER,
    deleted_at TEXT,
    FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_truck ON maintenance_schedules(truck_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_active ON maintenance_schedules(active);
CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_company ON maintenance_schedules(company_id);

CREATE TABLE IF NOT EXISTS truck_health_scores (
    truck_id INTEGER PRIMARY KEY,
    score INTEGER NOT NULL DEFAULT 100,
    compliance_pct DOUBLE PRECISION DEFAULT 100.0,
    overdue_count INTEGER DEFAULT 0,
    recurring_issues INTEGER DEFAULT 0,
    downtime_days INTEGER DEFAULT 0,
    last_updated TEXT NOT NULL,
    company_id INTEGER,
    FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_truck_health_scores_company ON truck_health_scores(company_id);

-- ── Drivers ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS drivers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    license_number TEXT,
    license_category TEXT,
    license_expiry TEXT,
    medical_expiry TEXT,
    hire_date TEXT,
    monthly_salary DOUBLE PRECISION DEFAULT 0,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    passport_number TEXT DEFAULT '',
    passport_expiry TEXT DEFAULT '',
    adr_certificate TEXT DEFAULT '',
    adr_certificate_expiry TEXT DEFAULT '',
    driver_card_number TEXT DEFAULT '',
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_drivers_active ON drivers(is_active);
CREATE INDEX IF NOT EXISTS idx_drivers_company ON drivers(company_id);
CREATE INDEX IF NOT EXISTS idx_drivers_deleted ON drivers(deleted_at);

CREATE TABLE IF NOT EXISTS driver_truck_assignments (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    driver_id INTEGER NOT NULL UNIQUE,
    truck_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
    FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dta_driver ON driver_truck_assignments(driver_id);
CREATE INDEX IF NOT EXISTS idx_dta_truck ON driver_truck_assignments(truck_id);

-- ── Tachograph ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tacho_imports (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    truck_id INTEGER REFERENCES trucks(id),
    driver_id INTEGER REFERENCES drivers(id),
    parse_status TEXT DEFAULT 'ok',
    raw_json TEXT,
    notes TEXT,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tacho_imports_hash ON tacho_imports(file_hash);
CREATE INDEX IF NOT EXISTS idx_tacho_imports_company ON tacho_imports(company_id);

CREATE TABLE IF NOT EXISTS tacho_driver_activity (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES tacho_imports(id),
    driver_id INTEGER REFERENCES drivers(id),
    activity_date DATE NOT NULL,
    driving_minutes INTEGER DEFAULT 0,
    work_minutes INTEGER DEFAULT 0,
    rest_minutes INTEGER DEFAULT 0,
    avail_minutes INTEGER DEFAULT 0,
    distance_km DOUBLE PRECISION DEFAULT 0,
    violations TEXT,
    country_codes TEXT
);
CREATE INDEX IF NOT EXISTS idx_tacho_driver_date ON tacho_driver_activity(driver_id, activity_date);

CREATE TABLE IF NOT EXISTS tacho_vehicle_data (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    import_id INTEGER NOT NULL REFERENCES tacho_imports(id),
    truck_id INTEGER REFERENCES trucks(id),
    vu_serial_number TEXT,
    calibration_date DATE,
    calibration_expiry DATE,
    odometer_km DOUBLE PRECISION,
    k_factor INTEGER,
    w_factor INTEGER,
    speed_violations INTEGER DEFAULT 0,
    recorded_from DATE,
    recorded_to DATE
);
CREATE INDEX IF NOT EXISTS idx_tacho_vehicle_truck ON tacho_vehicle_data(truck_id);

-- ── Clients ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    vat_number TEXT,
    company_code TEXT DEFAULT '',
    city TEXT DEFAULT '',
    currency_preference TEXT DEFAULT 'EUR',
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    client_type TEXT DEFAULT '',
    payment_terms_days INTEGER DEFAULT 30,
    credit_limit_eur DOUBLE PRECISION DEFAULT 0,
    default_rate_per_km DOUBLE PRECISION,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    eori_number TEXT DEFAULT '',
    country TEXT DEFAULT '',
    consignee_contact_name TEXT DEFAULT '',
    consignee_contact_phone TEXT DEFAULT '',
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE INDEX IF NOT EXISTS idx_clients_active ON clients(is_active);
CREATE INDEX IF NOT EXISTS idx_clients_company ON clients(company_id);
CREATE INDEX IF NOT EXISTS idx_clients_deleted ON clients(deleted_at);

CREATE TABLE IF NOT EXISTS client_contacts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contact_type TEXT NOT NULL DEFAULT 'operations',
    full_name TEXT NOT NULL,
    title TEXT,
    phone TEXT,
    email TEXT,
    is_primary INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    company_id INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_client_contacts_client ON client_contacts(client_id);
CREATE INDEX IF NOT EXISTS idx_client_contacts_company ON client_contacts(company_id);

CREATE TABLE IF NOT EXISTS client_tags (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    company_id INTEGER DEFAULT 0,
    UNIQUE (client_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_client_tags_client ON client_tags(client_id);
CREATE INDEX IF NOT EXISTS idx_client_tags_company ON client_tags(company_id);

-- ── Document Center ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id INTEGER,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    mime_type TEXT DEFAULT 'application/octet-stream',
    file_hash TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    is_archived INTEGER DEFAULT 0,
    uploaded_by TEXT DEFAULT '',
    uploaded_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ocr_text TEXT DEFAULT '',
    ocr_run_at TEXT DEFAULT '',
    ocr_engine TEXT DEFAULT '',
    text_content TEXT DEFAULT '',
    expiry_date TEXT DEFAULT '',
    signed_by TEXT DEFAULT '',
    signed_at TEXT DEFAULT '',
    copy_type TEXT DEFAULT '',
    cmr_number TEXT DEFAULT '',
    cmr_metadata_json TEXT DEFAULT '{}',
    is_signed INTEGER DEFAULT 0,
    extracted_data_json TEXT DEFAULT '{}',
    automation_tags TEXT DEFAULT '',
    company_id INTEGER DEFAULT 0,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_entity ON documents(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_number ON documents(doc_number);
CREATE INDEX IF NOT EXISTS idx_documents_expiry_date ON documents(expiry_date);
CREATE INDEX IF NOT EXISTS idx_documents_copy_type ON documents(copy_type);
CREATE INDEX IF NOT EXISTS idx_documents_cmr_number ON documents(cmr_number);
CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_deleted ON documents(deleted_at);

-- ── FTS: PostgreSQL full-text search replacement for documents ────────
-- Replaces SQLite FTS5 virtual table documents_fts.
-- See document_search_triggers below for automatic sync.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector;
CREATE INDEX IF NOT EXISTS idx_documents_search ON documents USING GIN (search_vector);

CREATE TABLE IF NOT EXISTS document_links (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id INTEGER NOT NULL,
    linked_entity_type TEXT NOT NULL,
    linked_entity_id INTEGER NOT NULL,
    relation_type TEXT DEFAULT 'attached',
    created_at TEXT NOT NULL,
    company_id INTEGER DEFAULT 0,
    UNIQUE (document_id, linked_entity_type, linked_entity_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_doc_links_document ON document_links(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_links_entity ON document_links(linked_entity_type, linked_entity_id);
CREATE INDEX IF NOT EXISTS idx_doc_links_company ON document_links(company_id);

CREATE TABLE IF NOT EXISTS document_versions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    file_hash TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    uploaded_by TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    company_id INTEGER DEFAULT 0,
    UNIQUE (document_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_company ON document_versions(company_id);

CREATE TABLE IF NOT EXISTS contracts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id INTEGER UNIQUE,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    contract_type TEXT NOT NULL DEFAULT 'transport',
    start_date TEXT,
    end_date TEXT,
    value_eur DOUBLE PRECISION DEFAULT 0,
    payment_terms TEXT DEFAULT '',
    auto_renewal INTEGER DEFAULT 0,
    renewal_notice_days INTEGER DEFAULT 30,
    status TEXT DEFAULT 'active',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_contracts_client ON contracts(client_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_end_date ON contracts(end_date);
CREATE INDEX IF NOT EXISTS idx_contracts_company ON contracts(company_id);
CREATE INDEX IF NOT EXISTS idx_contracts_deleted ON contracts(deleted_at);

CREATE TABLE IF NOT EXISTS document_templates (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    template_type TEXT NOT NULL DEFAULT 'pdf',
    fields_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ── CMR System ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cmr_counter (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    year INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL DEFAULT 0,
    UNIQUE (year)
);

CREATE TABLE IF NOT EXISTS successive_carriers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL DEFAULT 1,
    carrier_name TEXT NOT NULL,
    carrier_address TEXT,
    carrier_country TEXT,
    vehicle_plate TEXT,
    trailer_plate TEXT,
    driver_name TEXT,
    from_location TEXT,
    to_location TEXT,
    UNIQUE (trip_id, sequence_order)
);
CREATE INDEX IF NOT EXISTS idx_successive_carriers_trip ON successive_carriers(trip_id);

CREATE TABLE IF NOT EXISTS cmr_audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cmr_number TEXT NOT NULL,
    trip_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT DEFAULT 'system',
    timestamp TEXT NOT NULL,
    data_hash TEXT,
    metadata_json TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(id)
);
CREATE INDEX IF NOT EXISTS idx_cmr_audit_trip ON cmr_audit_log(trip_id);
CREATE INDEX IF NOT EXISTS idx_cmr_audit_number ON cmr_audit_log(cmr_number);
CREATE INDEX IF NOT EXISTS idx_cmr_audit_event_type ON cmr_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_cmr_audit_created ON cmr_audit_log(created_at);

-- ── Document Automation Pipeline ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_pipeline_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_uuid TEXT UNIQUE NOT NULL,
    source_file_path TEXT NOT NULL,
    source_file_name TEXT NOT NULL,
    source_mime_type TEXT NOT NULL,
    source_file_size INTEGER DEFAULT 0,
    source_file_hash TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'imported',
    stage TEXT NOT NULL DEFAULT 'import',
    error_message TEXT DEFAULT '',
    processed_file_path TEXT DEFAULT '',
    processed_pdf_path TEXT DEFAULT '',
    pages_count INTEGER DEFAULT 0,
    ocr_text TEXT DEFAULT '',
    extracted_data_json TEXT DEFAULT '{}',
    matched_trip_id INTEGER,
    match_confidence DOUBLE PRECISION DEFAULT 0.0,
    match_signals_json TEXT DEFAULT '{}',
    document_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_uuid ON document_pipeline_runs(run_uuid);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON document_pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_trip ON document_pipeline_runs(matched_trip_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_hash ON document_pipeline_runs(source_file_hash);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_company ON document_pipeline_runs(company_id);

CREATE TABLE IF NOT EXISTS document_package (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trip_id INTEGER,
    package_uuid TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    recipient_email TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    email_message_id TEXT DEFAULT '',
    sent_at TEXT,
    error_message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_package_trip ON document_package(trip_id);
CREATE INDEX IF NOT EXISTS idx_package_uuid ON document_package(package_uuid);
CREATE INDEX IF NOT EXISTS idx_package_status ON document_package(status);
CREATE INDEX IF NOT EXISTS idx_document_package_company ON document_package(company_id);

CREATE TABLE IF NOT EXISTS document_package_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    package_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (package_id) REFERENCES document_package(id) ON DELETE CASCADE,
    UNIQUE (package_id, document_id)
);
CREATE INDEX IF NOT EXISTS idx_package_items_package ON document_package_items(package_id);
CREATE INDEX IF NOT EXISTS idx_package_items_document ON document_package_items(document_id);

-- ── Receipts ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS receipts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    receipt_number TEXT UNIQUE NOT NULL,
    receipt_type TEXT NOT NULL DEFAULT 'customer_payment',
    issue_date TEXT,
    payment_date TEXT,
    currency TEXT DEFAULT 'EUR',
    company_name TEXT, company_address TEXT, company_vat TEXT,
    company_reg TEXT, company_phone TEXT, company_email TEXT,
    received_from_name TEXT, received_from_address TEXT,
    received_from_vat TEXT, received_from_reg TEXT, received_from_contact TEXT,
    received_by_name TEXT, received_by_address TEXT,
    received_by_vat TEXT, received_by_reg TEXT, received_by_contact TEXT,
    payment_method TEXT,
    reference_number TEXT, transaction_id TEXT,
    bank_reference TEXT, invoice_reference TEXT,
    related_trip_id INTEGER, driver_id INTEGER,
    vehicle_id INTEGER, trailer_id INTEGER,
    purpose TEXT,
    amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    vat_rate DOUBLE PRECISION DEFAULT 0,
    vat_amount DOUBLE PRECISION DEFAULT 0,
    total DOUBLE PRECISION DEFAULT 0,
    amount_words TEXT,
    notes TEXT,
    status TEXT DEFAULT 'Draft',
    logo_path TEXT, signature_path TEXT, stamp_path TEXT,
    attachments_json TEXT DEFAULT '[]',
    employee_name TEXT, department TEXT, expense_category TEXT,
    mileage DOUBLE PRECISION, fuel DOUBLE PRECISION, accommodation DOUBLE PRECISION,
    meals DOUBLE PRECISION, parking DOUBLE PRECISION, tolls DOUBLE PRECISION, other_expense DOUBLE PRECISION,
    pickup_location TEXT, delivery_location TEXT,
    route TEXT, dispatcher TEXT,
    language TEXT DEFAULT 'en',
    created_at TEXT, updated_at TEXT,
    company_id INTEGER,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_receipt_number ON receipts(receipt_number);
CREATE INDEX IF NOT EXISTS idx_receipt_type ON receipts(receipt_type);
CREATE INDEX IF NOT EXISTS idx_receipt_status ON receipts(status);
CREATE INDEX IF NOT EXISTS idx_receipt_trip ON receipts(related_trip_id);
CREATE INDEX IF NOT EXISTS idx_receipt_driver ON receipts(driver_id);
CREATE INDEX IF NOT EXISTS idx_receipts_company ON receipts(company_id);
CREATE INDEX IF NOT EXISTS idx_receipts_deleted ON receipts(deleted_at);

-- ── AutoMail / Dunner ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS automail_templates (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT DEFAULT '',
    variables_json TEXT DEFAULT '[]',
    is_default INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS automail_schedules (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT DEFAULT '',
    trigger_type TEXT NOT NULL,
    days_offset INTEGER NOT NULL,
    template_id INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    attach_invoice INTEGER DEFAULT 1,
    attach_cmr INTEGER DEFAULT 1,
    attach_all_docs INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (template_id) REFERENCES automail_templates(id)
);
CREATE INDEX IF NOT EXISTS idx_automail_schedules_template ON automail_schedules(template_id);
CREATE INDEX IF NOT EXISTS idx_automail_schedules_active_sort ON automail_schedules(is_active, sort_order);

CREATE TABLE IF NOT EXISTS automail_client_overrides (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id INTEGER NOT NULL UNIQUE,
    is_disabled INTEGER DEFAULT 0,
    custom_template_id INTEGER,
    custom_days_offset INTEGER,
    custom_trigger_type TEXT,
    skip_attachments INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_automail_client_overrides_client ON automail_client_overrides(client_id);

CREATE TABLE IF NOT EXISTS automail_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ── Multi-tenant / Auth ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companies (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_name TEXT NOT NULL,
    subscription_tier TEXT NOT NULL DEFAULT 'starter'
        CHECK (subscription_tier IN ('starter', 'professional', 'enterprise')),
    is_active INTEGER NOT NULL DEFAULT 1,
    trial_ends_at TEXT,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);

CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'dispatcher',
    company_id INTEGER REFERENCES companies(id),
    is_active INTEGER NOT NULL DEFAULT 1,
    display_name TEXT DEFAULT '',
    driver_id INTEGER REFERENCES drivers(id),
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);

-- ── Password reset tokens ─────────────────────────────────────────────
-- Single-use, time-limited password reset tokens (PostgreSQL parity for
-- database/schema.py TABLE_PASSWORD_RESET_TOKENS). Only the SHA-256 hash
-- of the raw token is persisted; the raw token lives only in the emailed
-- reset link.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id);

CREATE TABLE IF NOT EXISTS gps_telemetry (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    truck_id INTEGER NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed_kmh DOUBLE PRECISION DEFAULT 0,
    heading INTEGER DEFAULT 0,
    driver_id INTEGER,
    company_id INTEGER NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE INDEX IF NOT EXISTS idx_gps_truck ON gps_telemetry(truck_id);
CREATE INDEX IF NOT EXISTS idx_gps_recorded ON gps_telemetry(recorded_at);
CREATE INDEX IF NOT EXISTS idx_gps_truck_time ON gps_telemetry(truck_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_gps_telemetry_company ON gps_telemetry(company_id);

-- ── API Keys / OAuth2 ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    name TEXT NOT NULL,
    partner TEXT NOT NULL,
    scopes TEXT DEFAULT '[]',
    is_active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    last_used_at TEXT,
    expires_at TEXT,
    revoked_at TEXT,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_api_keys_partner ON api_keys(partner);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);

CREATE TABLE IF NOT EXISTS oauth2_clients (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id TEXT NOT NULL UNIQUE,
    client_name TEXT NOT NULL,
    partner TEXT NOT NULL,
    scopes TEXT DEFAULT '[]',
    secret_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    last_used_at TEXT,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_oauth2_clients_id ON oauth2_clients(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth2_clients_partner ON oauth2_clients(partner);

-- ── Webhook Events ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS webhook_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    partner TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT,
    signature_valid INTEGER DEFAULT 1,
    processing_status TEXT DEFAULT 'received',
    received_at TEXT,
    processed_at TEXT,
    company_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_webhook_events_partner ON webhook_events(partner);
CREATE INDEX IF NOT EXISTS idx_webhook_events_received ON webhook_events(received_at);
CREATE INDEX IF NOT EXISTS idx_webhook_events_company ON webhook_events(company_id);

-- ── Waitlist ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS waitlist_entries (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT NOT NULL,
    fleet_size TEXT,
    company_size TEXT,
    country TEXT,
    source TEXT NOT NULL DEFAULT 'landing_page',
    referral_code TEXT UNIQUE NOT NULL,
    referred_by TEXT,
    status TEXT NOT NULL DEFAULT 'joined',
    joined_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    invited_at TEXT,
    activated_at TEXT,
    converted_at TEXT,
    notes TEXT,
    ip_hash TEXT,
    user_agent TEXT,
    unsubscribed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_waitlist_email ON waitlist_entries(lower(email));
CREATE INDEX IF NOT EXISTS idx_waitlist_status ON waitlist_entries(status);
CREATE INDEX IF NOT EXISTS idx_waitlist_joined ON waitlist_entries(joined_at);
CREATE INDEX IF NOT EXISTS idx_waitlist_source ON waitlist_entries(source);

-- ── Contact form ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contact_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    source_ip TEXT,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);

-- =============================================================================
-- §FTS: PostgreSQL full-text search triggers for documents
-- Replaces the SQLite documents_fts FTS5 virtual table + triggers.
-- =============================================================================

CREATE OR REPLACE FUNCTION documents_search_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.file_name, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.tags, '')), 'C') ||
        setweight(to_tsvector('english', COALESCE(NEW.doc_number, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.text_content, '')), 'D') ||
        setweight(to_tsvector('english', COALESCE(NEW.cmr_number, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.extracted_data_json, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_documents_search_insert ON documents;
CREATE TRIGGER trg_documents_search_insert
    BEFORE INSERT ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_search_update();

DROP TRIGGER IF EXISTS trg_documents_search_update ON documents;
CREATE TRIGGER trg_documents_search_update
    BEFORE UPDATE OF title, file_name, description, tags, doc_number, text_content, cmr_number, extracted_data_json
    ON documents
    FOR EACH ROW EXECUTE FUNCTION documents_search_update();

-- =============================================================================
-- §TRIGGERS: Pipeline stage/status validation
-- Replaces SQLite triggers with RAISE(ABORT, ...)
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_pipeline_stage() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.stage NOT IN (
        'import', 'processing', 'enhance', 'ocr', 'validate', 'ai_fallback',
        'matching', 'auto_attach', 'verify', 'package', 'email',
        'complete', 'failed'
    ) THEN
        RAISE EXCEPTION 'invalid document_pipeline_runs.stage value: %', NEW.stage;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pipeline_runs_stage_check ON document_pipeline_runs;
CREATE TRIGGER trg_pipeline_runs_stage_check
    BEFORE INSERT ON document_pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION validate_pipeline_stage();

DROP TRIGGER IF EXISTS trg_pipeline_runs_stage_check_upd ON document_pipeline_runs;
CREATE TRIGGER trg_pipeline_runs_stage_check_upd
    BEFORE UPDATE OF stage ON document_pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION validate_pipeline_stage();

CREATE OR REPLACE FUNCTION validate_pipeline_status() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status NOT IN (
        'imported', 'processing', 'enhanced', 'processed',
        'ocr_done', 'validated', 'ai_done',
        'matched', 'attached', 'verified', 'packaged', 'emailed',
        'complete', 'failed'
    ) THEN
        RAISE EXCEPTION 'invalid document_pipeline_runs.status value: %', NEW.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pipeline_runs_status_check ON document_pipeline_runs;
CREATE TRIGGER trg_pipeline_runs_status_check
    BEFORE INSERT ON document_pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION validate_pipeline_status();

DROP TRIGGER IF EXISTS trg_pipeline_runs_status_check_upd ON document_pipeline_runs;
CREATE TRIGGER trg_pipeline_runs_status_check_upd
    BEFORE UPDATE OF status ON document_pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION validate_pipeline_status();

-- =============================================================================
-- §MIGRATIONS: Schema version seeds
-- =============================================================================

INSERT INTO schema_migrations (version, name)
VALUES (1, 'initial_schema')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (2, 'add_company_id_indexes')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (3, 'add_gps_telemetry_company_id')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, name)
VALUES (4, 'add_missing_company_id_and_soft_delete')
ON CONFLICT (version) DO NOTHING;
