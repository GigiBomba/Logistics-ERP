# trips table — financial/business entity (Trip History).
# Linked to route_history_v2 via route_history_v2_id FK when the trip
# originates from a route calculation.
TABLE_TRIPS = """
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    truck_number TEXT,
    driver_name TEXT,
    client_name TEXT,
    distance_km REAL,
    total_price_eur REAL,
    rate_per_km REAL,
    gross_per_km REAL,
    net_profit REAL,
    start_date TEXT,
    end_date TEXT,
    payment_date TEXT,
    extra_costs REAL,
    fuel_cost REAL,
    toll_cost REAL,
    salary_cost REAL,
    currency TEXT,
    status TEXT,
    loading_country TEXT,
    delivery_country TEXT,
    driver_id INTEGER
    -- route_history_v2_id INTEGER REFERENCES route_history_v2(id),  (added by migration)
    -- truck_consumption_l_per_100km REAL,                          (added by migration)
    -- context_json TEXT                                             (added by migration)
);
"""

INDEX_TRIPS_DATE = "CREATE INDEX IF NOT EXISTS idx_trips_date ON trips(created_at);"
INDEX_TRIPS_TRUCK = "CREATE INDEX IF NOT EXISTS idx_trips_truck ON trips(truck_number);"
INDEX_TRIPS_CLIENT_NAME = "CREATE INDEX IF NOT EXISTS idx_trips_client_name ON trips(client_name);"
INDEX_TRIPS_DRIVER_NAME = "CREATE INDEX IF NOT EXISTS idx_trips_driver_name ON trips(driver_name);"
INDEX_TRIPS_STATUS = "CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status);"
INDEX_TRIPS_CLIENT_STATUS = "CREATE INDEX IF NOT EXISTS idx_trips_client_status ON trips(client_name, status);"
ALTER_TRIPS_ADD_MONTH = "ALTER TABLE trips ADD COLUMN month TEXT GENERATED ALWAYS AS (SUBSTR(created_at, 1, 7)) STORED"
INDEX_TRIPS_MONTH = "CREATE INDEX IF NOT EXISTS idx_trips_month ON trips(month);"

INDEX_TRIPS_START_DATE = "CREATE INDEX IF NOT EXISTS idx_trips_start_date ON trips(start_date);"
INDEX_TRIPS_DELIVERY_COUNTRY = "CREATE INDEX IF NOT EXISTS idx_trips_delivery_country ON trips(delivery_country);"
INDEX_TRIPS_LOADING_COUNTRY = "CREATE INDEX IF NOT EXISTS idx_trips_loading_country ON trips(loading_country);"
INDEX_TRIPS_DRIVER_ID = "CREATE INDEX IF NOT EXISTS idx_trips_driver_id ON trips(driver_id);"



# Adaugă tabelul de facturi în schema.py
TABLE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER UNIQUE,
    invoice_number TEXT UNIQUE,
    issue_date TEXT,
    due_date TEXT,
    total_amount REAL,
    status TEXT, -- 'Unpaid', 'Paid'
    FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
);
"""

# Proforma invoices — independent of trips (manual line items, no trip FK)
TABLE_PROFORMA_INVOICES = """
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
"""

INDEX_PROFORMA_NUMBER = "CREATE UNIQUE INDEX IF NOT EXISTS idx_proforma_number ON proforma_invoices(proforma_number);"
INDEX_PROFORMA_CLIENT = "CREATE INDEX IF NOT EXISTS idx_proforma_client ON proforma_invoices(client_name);"
INDEX_PROFORMA_STATUS = "CREATE INDEX IF NOT EXISTS idx_proforma_status ON proforma_invoices(status);"

# Re-definim statusurile permise pentru trips (logică internă):
# 'Planned', 'Loading', 'In Transit', 'Delivered', 'Invoiced', 'Paid'

# Adaugă la finalul fișierului schema.py existent:
# Adauga asta in database/schema.py daca nu este deja

TABLE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

TABLE_EMAIL_LOGS = """
CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER,
    recipient TEXT,
    subject TEXT,
    timestamp TEXT,
    status TEXT,
    error_msg TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips (id)
);
"""

TABLE_INVOICE_REMINDERS = """
CREATE TABLE IF NOT EXISTS invoice_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    trip_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL,
    days_offset INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);
"""

INDEX_INVOICE_REMINDERS_LOOKUP = (
    "CREATE INDEX IF NOT EXISTS idx_invoice_reminders_lookup "
    "ON invoice_reminders(invoice_id, reminder_type, status)"
)

# Adăugați la schema.py existent:

TABLE_TRUCKS = """
CREATE TABLE IF NOT EXISTS trucks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_number TEXT UNIQUE,
    model TEXT,
    manufacturer TEXT,
    year INTEGER,
    vin TEXT,
    fuel_consumption REAL, -- L/100km standard
    mileage REAL,
    monthly_rate REAL, -- Leasing/Finantare
    status TEXT, -- 'Active', 'In Service', 'Inactive'
    insurance_expiry TEXT,
    inspection_expiry TEXT,
    maintenance_due REAL, -- KM la care trebuie service
    active_status INTEGER DEFAULT 1
);
"""

TABLE_MAINTENANCE = """
-- DEPRECATED: Replaced by TABLE_MAINTENANCE_RECORDS below.
-- Data is migrated automatically on startup; no app code should reference this table.
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    truck_id INTEGER,
    date TEXT,
    type TEXT, -- 'Oil Change', 'Tires', 'Repair', 'Inspection'
    description TEXT,
    km_at_service REAL,
    cost REAL,
    FOREIGN KEY (truck_id) REFERENCES trucks (id)
);
"""

# Routes and history for route planner
TABLE_ROUTES = """
CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    start TEXT,
    destination TEXT,
    via TEXT,
    distance_km REAL,
    duration_min REAL,
    geometry TEXT,
    created_at TEXT
);
"""

TABLE_ROUTE_HISTORY = """
CREATE TABLE IF NOT EXISTS route_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    computed_at TEXT,
    distance_km REAL,
    duration_min REAL,
    fuel_cost REAL,
    toll_cost REAL,
    total_cost REAL,
    price_recommended REAL,
    FOREIGN KEY(route_id) REFERENCES routes(id)
);
"""

TABLE_ROUTE_HISTORY_V2 = """
CREATE TABLE IF NOT EXISTS route_history_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_fingerprint TEXT NOT NULL UNIQUE,
    metadata_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_calculated_at TEXT NOT NULL,
    calculation_count INTEGER NOT NULL DEFAULT 1,
    stops_json TEXT NOT NULL,
    geometry_compressed BLOB,
    geometry_encoding TEXT NOT NULL DEFAULT 'zlib-json',
    total_distance_km REAL,
    duration_min REAL,
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
    is_committed INTEGER NOT NULL DEFAULT 0
);
"""

INDEX_ROUTE_HISTORY_V2_CREATED = "CREATE INDEX IF NOT EXISTS idx_route_history_v2_created ON route_history_v2(created_at);"
INDEX_ROUTE_HISTORY_V2_LAST_CALCULATED = "CREATE INDEX IF NOT EXISTS idx_route_history_v2_last_calculated ON route_history_v2(last_calculated_at);"
INDEX_ROUTE_HISTORY_V2_TRUCK = "CREATE INDEX IF NOT EXISTS idx_route_history_v2_truck ON route_history_v2(truck_id);"
INDEX_ROUTE_HISTORY_V2_PROFILE = "CREATE INDEX IF NOT EXISTS idx_route_history_v2_profile ON route_history_v2(profile);"
INDEX_ROUTE_HISTORY_V2_FINGERPRINT = "CREATE INDEX IF NOT EXISTS idx_route_history_v2_fingerprint ON route_history_v2(route_fingerprint);"

TABLE_ROUTE_EVENTS = """
CREATE TABLE IF NOT EXISTS route_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(route_id) REFERENCES route_history_v2(id) ON DELETE SET NULL
);
"""

TABLE_TRUCK_ROUTE_ASSIGNMENTS = """
CREATE TABLE IF NOT EXISTS truck_route_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    truck_id TEXT NOT NULL,
    route_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'assigned',
    assigned_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    archived_at TEXT,
    notes TEXT,
    FOREIGN KEY(route_id) REFERENCES route_history_v2(id) ON DELETE CASCADE
);
"""

INDEX_ROUTE_EVENTS_ROUTE = "CREATE INDEX IF NOT EXISTS idx_route_events_route ON route_events(route_id);"
INDEX_ROUTE_EVENTS_TYPE = "CREATE INDEX IF NOT EXISTS idx_route_events_type ON route_events(event_type);"
INDEX_TRUCK_ROUTE_ASSIGNMENTS_TRUCK = "CREATE INDEX IF NOT EXISTS idx_truck_route_assignments_truck ON truck_route_assignments(truck_id);"
INDEX_TRUCK_ROUTE_ASSIGNMENTS_ROUTE = "CREATE INDEX IF NOT EXISTS idx_truck_route_assignments_route ON truck_route_assignments(route_id);"
INDEX_TRUCK_ROUTE_ASSIGNMENTS_STATUS = "CREATE INDEX IF NOT EXISTS idx_truck_route_assignments_status ON truck_route_assignments(status);"

# Operations Engine tables
TABLE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT,
    message TEXT,
    truck_id TEXT,
    trip_id INTEGER,
    created_at TEXT NOT NULL,
    resolved INTEGER DEFAULT 0,
    resolved_at TEXT,
    metadata_json TEXT
);
"""

TABLE_OPERATION_EVENTS = """
CREATE TABLE IF NOT EXISTS operation_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    data_json TEXT,
    created_at TEXT NOT NULL
);
"""

TABLE_TRIP_STATUS_HISTORY = """
CREATE TABLE IF NOT EXISTS trip_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    trigger TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(id)
);
"""

# Fleet Maintenance tables
TABLE_MAINTENANCE_RECORDS = """
CREATE TABLE IF NOT EXISTS maintenance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    truck_id INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    date TEXT NOT NULL,
    km REAL,
    cost REAL,
    notes TEXT,
    service_provider TEXT,
    attachment_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (truck_id) REFERENCES trucks(id)
);
"""

TABLE_MAINTENANCE_SCHEDULES = """
CREATE TABLE IF NOT EXISTS maintenance_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    truck_id INTEGER NOT NULL,
    maintenance_type TEXT NOT NULL,
    interval_km REAL,
    interval_months INTEGER,
    fixed_expiry_date TEXT,
    last_done_km REAL,
    last_done_date TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (truck_id) REFERENCES trucks(id)
);
"""

TABLE_TRUCK_HEALTH_SCORES = """
CREATE TABLE IF NOT EXISTS truck_health_scores (
    truck_id INTEGER PRIMARY KEY,
    score INTEGER NOT NULL DEFAULT 100,
    compliance_pct REAL DEFAULT 100.0,
    overdue_count INTEGER DEFAULT 0,
    recurring_issues INTEGER DEFAULT 0,
    downtime_days INTEGER DEFAULT 0,
    last_updated TEXT NOT NULL,
    FOREIGN KEY (truck_id) REFERENCES trucks(id)
);
"""

INDEX_MAINTENANCE_RECORDS_TRUCK = "CREATE INDEX IF NOT EXISTS idx_maintenance_records_truck ON maintenance_records(truck_id);"
INDEX_MAINTENANCE_RECORDS_TYPE = "CREATE INDEX IF NOT EXISTS idx_maintenance_records_type ON maintenance_records(maintenance_type);"
INDEX_MAINTENANCE_RECORDS_DATE = "CREATE INDEX IF NOT EXISTS idx_maintenance_records_date ON maintenance_records(date);"
INDEX_MAINTENANCE_SCHEDULES_TRUCK = "CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_truck ON maintenance_schedules(truck_id);"
INDEX_MAINTENANCE_SCHEDULES_ACTIVE = "CREATE INDEX IF NOT EXISTS idx_maintenance_schedules_active ON maintenance_schedules(active);"

INDEX_ALERTS_TYPE = "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type);"
INDEX_ALERTS_TRUCK = "CREATE INDEX IF NOT EXISTS idx_alerts_truck ON alerts(truck_id);"
INDEX_ALERTS_RESOLVED = "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);"
INDEX_OPERATION_EVENTS_TYPE = "CREATE INDEX IF NOT EXISTS idx_operation_events_type ON operation_events(event_type);"
INDEX_TRIP_STATUS_HISTORY_TRIP = "CREATE INDEX IF NOT EXISTS idx_trip_status_history_trip ON trip_status_history(trip_id);"

# ── Drivers table ────────────────────────────────────────────────────────

TABLE_DRIVERS = """
CREATE TABLE IF NOT EXISTS drivers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    license_number TEXT,
    license_category TEXT,
    license_expiry TEXT,
    medical_expiry TEXT,
    hire_date TEXT,
    monthly_salary REAL DEFAULT 0,
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

INDEX_DRIVERS_ACTIVE = "CREATE INDEX IF NOT EXISTS idx_drivers_active ON drivers(is_active);"

TABLE_DRIVER_TRUCK_ASSIGNMENTS = """
CREATE TABLE IF NOT EXISTS driver_truck_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_id INTEGER NOT NULL UNIQUE,
    truck_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL,
    FOREIGN KEY (driver_id) REFERENCES drivers(id),
    FOREIGN KEY (truck_id) REFERENCES trucks(id)
);
"""

INDEX_DTA_DRIVER = "CREATE INDEX IF NOT EXISTS idx_dta_driver ON driver_truck_assignments(driver_id);"
INDEX_DTA_TRUCK = "CREATE INDEX IF NOT EXISTS idx_dta_truck ON driver_truck_assignments(truck_id);"

# ── Column additions (migrations) ────────────────────────────────────────

ALTER_TRUCKS_ADD_TACHOGRAPH = "ALTER TABLE trucks ADD COLUMN tachograph_expiry TEXT"
ALTER_TRUCKS_ADD_TRACKING_DEVICE_ID = "ALTER TABLE trucks ADD COLUMN tracking_device_id TEXT"
ALTER_TRIPS_ADD_DRIVER_ID = "ALTER TABLE trips ADD COLUMN driver_id INTEGER REFERENCES drivers(id)"
ALTER_TRIPS_ADD_TRUCK_ID = "ALTER TABLE trips ADD COLUMN truck_id INTEGER REFERENCES trucks(id)"
INDEX_TRIPS_TRUCK_ID = "CREATE INDEX IF NOT EXISTS idx_trips_truck_id ON trips(truck_id)"

# ── Tachograph tables ────────────────────────────────────────────────────

TABLE_TACHO_IMPORTS = """
CREATE TABLE IF NOT EXISTS tacho_imports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_name       TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    truck_id        INTEGER REFERENCES trucks(id),
    driver_id       INTEGER REFERENCES drivers(id),
    parse_status    TEXT DEFAULT 'ok',
    raw_json        TEXT,
    notes           TEXT
);
"""

TABLE_TACHO_DRIVER_ACTIVITY = """
CREATE TABLE IF NOT EXISTS tacho_driver_activity (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id       INTEGER NOT NULL REFERENCES tacho_imports(id),
    driver_id       INTEGER REFERENCES drivers(id),
    activity_date   DATE NOT NULL,
    driving_minutes INTEGER DEFAULT 0,
    work_minutes    INTEGER DEFAULT 0,
    rest_minutes    INTEGER DEFAULT 0,
    avail_minutes   INTEGER DEFAULT 0,
    distance_km     REAL DEFAULT 0,
    violations      TEXT,
    country_codes   TEXT
);
"""

TABLE_TACHO_VEHICLE_DATA = """
CREATE TABLE IF NOT EXISTS tacho_vehicle_data (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id           INTEGER NOT NULL REFERENCES tacho_imports(id),
    truck_id            INTEGER REFERENCES trucks(id),
    vu_serial_number    TEXT,
    calibration_date    DATE,
    calibration_expiry  DATE,
    odometer_km         REAL,
    k_factor            INTEGER,
    w_factor            INTEGER,
    speed_violations    INTEGER DEFAULT 0,
    recorded_from       DATE,
    recorded_to         DATE
);
"""

INDEX_TACHO_DRIVER_DATE = "CREATE INDEX IF NOT EXISTS idx_tacho_driver_date ON tacho_driver_activity(driver_id, activity_date);"
INDEX_TACHO_VEHICLE_TRUCK = "CREATE INDEX IF NOT EXISTS idx_tacho_vehicle_truck ON tacho_vehicle_data(truck_id);"
INDEX_TACHO_IMPORTS_HASH = "CREATE INDEX IF NOT EXISTS idx_tacho_imports_hash ON tacho_imports(file_hash);"

# ── Clients ────────────────────────────────────────────────────────────
TABLE_CLIENTS = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    vat_number TEXT,
    currency_preference TEXT DEFAULT 'EUR',
    notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
"""

INDEX_CLIENTS_NAME = "CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);"
INDEX_CLIENTS_ACTIVE = "CREATE INDEX IF NOT EXISTS idx_clients_active ON clients(is_active);"

TABLE_CLIENT_CONTACTS = """
CREATE TABLE IF NOT EXISTS client_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contact_type TEXT NOT NULL DEFAULT 'operations',
    full_name TEXT NOT NULL,
    title TEXT,
    phone TEXT,
    email TEXT,
    is_primary INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);
"""

INDEX_CONTACTS_CLIENT = "CREATE INDEX IF NOT EXISTS idx_client_contacts_client ON client_contacts(client_id);"

TABLE_CLIENT_TAGS = """
CREATE TABLE IF NOT EXISTS client_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    UNIQUE(client_id, tag)
);
"""

INDEX_TAGS_CLIENT = "CREATE INDEX IF NOT EXISTS idx_client_tags_client ON client_tags(client_id);"

ALTER_CLIENTS_ADD_TYPE = "ALTER TABLE clients ADD COLUMN client_type TEXT DEFAULT ''"
ALTER_CLIENTS_ADD_PAYMENT_TERMS = "ALTER TABLE clients ADD COLUMN payment_terms_days INTEGER DEFAULT 30"
ALTER_CLIENTS_ADD_CREDIT_LIMIT = "ALTER TABLE clients ADD COLUMN credit_limit_eur REAL DEFAULT 0"
ALTER_CLIENTS_ADD_DEFAULT_RATE = "ALTER TABLE clients ADD COLUMN default_rate_per_km REAL"
ALTER_CLIENTS_ADD_RATING = "ALTER TABLE clients ADD COLUMN rating INTEGER CHECK(rating BETWEEN 1 AND 5)"

# ── Document Center ───────────────────────────────────────────────────────

TABLE_DOCUMENTS = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    ocr_engine TEXT DEFAULT ''
);
"""

TABLE_DOCUMENT_LINKS = """
CREATE TABLE IF NOT EXISTS document_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    linked_entity_type TEXT NOT NULL,
    linked_entity_id INTEGER NOT NULL,
    relation_type TEXT DEFAULT 'attached',
    created_at TEXT NOT NULL,
    UNIQUE(document_id, linked_entity_type, linked_entity_id, relation_type)
);
"""

INDEX_DOCUMENTS_CATEGORY = "CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);"
INDEX_DOCUMENTS_ENTITY = "CREATE INDEX IF NOT EXISTS idx_documents_entity ON documents(entity_type, entity_id);"
INDEX_DOCUMENTS_HASH = "CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);"
INDEX_DOCUMENTS_NUMBER = "CREATE INDEX IF NOT EXISTS idx_documents_number ON documents(doc_number);"
INDEX_DOCUMENTS_EXPIRY_DATE = "CREATE INDEX IF NOT EXISTS idx_documents_expiry_date ON documents(expiry_date);"
INDEX_DOC_LINKS_DOCUMENT = "CREATE INDEX IF NOT EXISTS idx_doc_links_document ON document_links(document_id);"
INDEX_DOC_LINKS_ENTITY = "CREATE INDEX IF NOT EXISTS idx_doc_links_entity ON document_links(linked_entity_type, linked_entity_id);"

# ── Document Center P2: FTS5, versions, contracts, templates ───────────────

ALTER_DOCUMENTS_ADD_TEXT_CONTENT = "ALTER TABLE documents ADD COLUMN text_content TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_EXPIRY_DATE = "ALTER TABLE documents ADD COLUMN expiry_date TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_SIGNED_BY = "ALTER TABLE documents ADD COLUMN signed_by TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_SIGNED_AT = "ALTER TABLE documents ADD COLUMN signed_at TEXT DEFAULT ''"

TABLE_DOCUMENTS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title, file_name, description, tags, doc_number, text_content,
    cmr_number, extracted_data_json,
    content='documents', content_rowid='id'
);
"""

MIGRATION_DOCUMENTS_FTS_V2 = """
DROP TABLE IF EXISTS documents_fts;
"""

TRIGGER_DOCUMENTS_FTS_INSERT = """
CREATE TRIGGER IF NOT EXISTS documents_fts_ai AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, title, file_name, description, tags, doc_number, text_content,
                              cmr_number, extracted_data_json)
    VALUES (new.id, new.title, new.file_name, new.description, new.tags, new.doc_number, '',
            new.cmr_number, new.extracted_data_json);
END;
"""

TRIGGER_DOCUMENTS_FTS_DELETE = """
CREATE TRIGGER IF NOT EXISTS documents_fts_ad AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, file_name, description, tags, doc_number, text_content,
                              cmr_number, extracted_data_json)
    VALUES ('delete', old.id, old.title, old.file_name, old.description, old.tags, old.doc_number, old.text_content,
            old.cmr_number, old.extracted_data_json);
END;
"""

TRIGGER_DOCUMENTS_FTS_UPDATE = """
CREATE TRIGGER IF NOT EXISTS documents_fts_au AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, title, file_name, description, tags, doc_number, text_content,
                              cmr_number, extracted_data_json)
    VALUES ('delete', old.id, old.title, old.file_name, old.description, old.tags, old.doc_number, old.text_content,
            old.cmr_number, old.extracted_data_json);
    INSERT INTO documents_fts(rowid, title, file_name, description, tags, doc_number, text_content,
                              cmr_number, extracted_data_json)
    VALUES (new.id, new.title, new.file_name, new.description, new.tags, new.doc_number, new.text_content,
            new.cmr_number, new.extracted_data_json);
END;
"""

TABLE_DOCUMENT_VERSIONS = """
CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    file_hash TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    uploaded_by TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(document_id, version_number)
);
"""

INDEX_VERSIONS_DOCUMENT = "CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(document_id);"

TABLE_CONTRACTS = """
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER UNIQUE,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    contract_type TEXT NOT NULL DEFAULT 'transport',
    start_date TEXT,
    end_date TEXT,
    value_eur REAL DEFAULT 0,
    payment_terms TEXT DEFAULT '',
    auto_renewal INTEGER DEFAULT 0,
    renewal_notice_days INTEGER DEFAULT 30,
    status TEXT DEFAULT 'active',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

INDEX_CONTRACTS_CLIENT = "CREATE INDEX IF NOT EXISTS idx_contracts_client ON contracts(client_id);"
INDEX_CONTRACTS_STATUS = "CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);"
INDEX_CONTRACTS_END_DATE = "CREATE INDEX IF NOT EXISTS idx_contracts_end_date ON contracts(end_date);"

TABLE_DOCUMENT_TEMPLATES = """
CREATE TABLE IF NOT EXISTS document_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    template_type TEXT NOT NULL DEFAULT 'pdf',
    fields_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# ── CMR System ─────────────────────────────────────────────────────────────

TABLE_CMR_COUNTER = """
CREATE TABLE IF NOT EXISTS cmr_counter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL DEFAULT 0,
    UNIQUE(year)
);
"""

TABLE_SUCCESSIVE_CARRIERS = """
CREATE TABLE IF NOT EXISTS successive_carriers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    UNIQUE(trip_id, sequence_order)
);
"""
INDEX_SUCCESSIVE_CARRIERS_TRIP = "CREATE INDEX IF NOT EXISTS idx_successive_carriers_trip ON successive_carriers(trip_id);"

TABLE_CMR_AUDIT_LOG = """
CREATE TABLE IF NOT EXISTS cmr_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cmr_number TEXT NOT NULL,
    trip_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT DEFAULT 'system',
    timestamp TEXT NOT NULL,
    data_hash TEXT,
    metadata_json TEXT,
    FOREIGN KEY (trip_id) REFERENCES trips(id)
);
"""
INDEX_CMR_AUDIT_TRIP = "CREATE INDEX IF NOT EXISTS idx_cmr_audit_trip ON cmr_audit_log(trip_id);"
INDEX_CMR_AUDIT_NUMBER = "CREATE INDEX IF NOT EXISTS idx_cmr_audit_number ON cmr_audit_log(cmr_number);"

# ── CMR column additions (migrations) ───────────────────────────────────────

ALTER_TRIPS_ADD_CMR_NUMBER = "ALTER TABLE trips ADD COLUMN cmr_number TEXT"
ALTER_TRIPS_ADD_CMR_SEQUENCE = "ALTER TABLE trips ADD COLUMN cmr_sequence INTEGER"
ALTER_TRIPS_ADD_CARGO_DESCRIPTION = "ALTER TABLE trips ADD COLUMN cargo_description TEXT"
ALTER_TRIPS_ADD_CARGO_MARKS = "ALTER TABLE trips ADD COLUMN cargo_marks TEXT"
ALTER_TRIPS_ADD_PACKAGE_COUNT = "ALTER TABLE trips ADD COLUMN package_count INTEGER"
ALTER_TRIPS_ADD_PACKAGE_TYPE = "ALTER TABLE trips ADD COLUMN package_type TEXT"
ALTER_TRIPS_ADD_GROSS_WEIGHT_KG = "ALTER TABLE trips ADD COLUMN gross_weight_kg REAL"
ALTER_TRIPS_ADD_VOLUME_M3 = "ALTER TABLE trips ADD COLUMN volume_m3 REAL"
ALTER_TRIPS_ADD_HS_CODE = "ALTER TABLE trips ADD COLUMN hs_code TEXT"
ALTER_TRIPS_ADD_CARRIER_INSTRUCTIONS = "ALTER TABLE trips ADD COLUMN carrier_instructions TEXT"
ALTER_TRIPS_ADD_CARRIER_RESERVATIONS = "ALTER TABLE trips ADD COLUMN carrier_reservations TEXT"
ALTER_TRIPS_ADD_SPECIAL_AGREEMENTS = "ALTER TABLE trips ADD COLUMN special_agreements TEXT"
ALTER_TRIPS_ADD_CARRIAGE_PAYER = "ALTER TABLE trips ADD COLUMN carriage_payer TEXT"
ALTER_TRIPS_ADD_DOCUMENTS_ATTACHED = "ALTER TABLE trips ADD COLUMN documents_attached TEXT"
ALTER_TRIPS_ADD_PLACE_OF_LOADING = "ALTER TABLE trips ADD COLUMN place_of_loading TEXT"
ALTER_TRIPS_ADD_PLACE_OF_LOADING_DATE = "ALTER TABLE trips ADD COLUMN place_of_loading_date TEXT"
ALTER_TRIPS_ADD_LOADING_COUNTRY = "ALTER TABLE trips ADD COLUMN loading_country TEXT"
ALTER_TRIPS_ADD_DELIVERY_COUNTRY = "ALTER TABLE trips ADD COLUMN delivery_country TEXT"
ALTER_TRIPS_ADD_ADR_INFO_JSON = "ALTER TABLE trips ADD COLUMN adr_info_json TEXT"
ALTER_TRIPS_ADD_CMR_STATUS = "ALTER TABLE trips ADD COLUMN cmr_status TEXT DEFAULT 'draft'"
ALTER_TRIPS_ADD_CMR_REMARKS = "ALTER TABLE trips ADD COLUMN cmr_remarks TEXT"

ALTER_CLIENTS_ADD_EORI_NUMBER = "ALTER TABLE clients ADD COLUMN eori_number TEXT DEFAULT ''"
ALTER_CLIENTS_ADD_COUNTRY = "ALTER TABLE clients ADD COLUMN country TEXT DEFAULT ''"
ALTER_CLIENTS_ADD_CONSIGNEE_CONTACT_NAME = "ALTER TABLE clients ADD COLUMN consignee_contact_name TEXT DEFAULT ''"
ALTER_CLIENTS_ADD_CONSIGNEE_CONTACT_PHONE = "ALTER TABLE clients ADD COLUMN consignee_contact_phone TEXT DEFAULT ''"

ALTER_TRUCKS_ADD_TRAILER_PLATE = "ALTER TABLE trucks ADD COLUMN trailer_plate TEXT DEFAULT ''"
ALTER_TRUCKS_ADD_MAX_PAYLOAD_KG = "ALTER TABLE trucks ADD COLUMN max_payload_kg REAL DEFAULT 0"
ALTER_TRUCKS_ADD_CMR_INSURANCE = "ALTER TABLE trucks ADD COLUMN cmr_insurance_number TEXT DEFAULT ''"
ALTER_TRUCKS_ADD_CMR_INSURANCE_EXPIRY = "ALTER TABLE trucks ADD COLUMN cmr_insurance_expiry TEXT DEFAULT ''"

ALTER_DRIVERS_ADD_PASSPORT_NUMBER = "ALTER TABLE drivers ADD COLUMN passport_number TEXT DEFAULT ''"
ALTER_DRIVERS_ADD_PASSPORT_EXPIRY = "ALTER TABLE drivers ADD COLUMN passport_expiry TEXT DEFAULT ''"
ALTER_DRIVERS_ADD_ADR_CERTIFICATE = "ALTER TABLE drivers ADD COLUMN adr_certificate TEXT DEFAULT ''"
ALTER_DRIVERS_ADD_ADR_CERTIFICATE_EXPIRY = "ALTER TABLE drivers ADD COLUMN adr_certificate_expiry TEXT DEFAULT ''"
ALTER_DRIVERS_ADD_CARD_NUMBER = "ALTER TABLE drivers ADD COLUMN driver_card_number TEXT DEFAULT ''"

ALTER_DOCUMENTS_ADD_COPY_TYPE = "ALTER TABLE documents ADD COLUMN copy_type TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_CMR_NUMBER = "ALTER TABLE documents ADD COLUMN cmr_number TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_CMR_METADATA = "ALTER TABLE documents ADD COLUMN cmr_metadata_json TEXT DEFAULT '{}'"
ALTER_DOCUMENTS_ADD_IS_SIGNED = "ALTER TABLE documents ADD COLUMN is_signed INTEGER DEFAULT 0"

INDEX_TRIPS_CMR_STATUS = "CREATE INDEX IF NOT EXISTS idx_trips_cmr_status ON trips(cmr_status);"
INDEX_DOCUMENTS_COPY_TYPE = "CREATE INDEX IF NOT EXISTS idx_documents_copy_type ON documents(copy_type);"
INDEX_DOCUMENTS_CMR_NUMBER = "CREATE INDEX IF NOT EXISTS idx_documents_cmr_number ON documents(cmr_number);"

# ── Document Automation Pipeline ────────────────────────────────────────────────

TABLE_DOCUMENT_PIPELINE_RUNS = """
CREATE TABLE IF NOT EXISTS document_pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    match_confidence REAL DEFAULT 0.0,
    match_signals_json TEXT DEFAULT '{}',
    document_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
"""

INDEX_PIPELINE_RUNS_UUID = "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_uuid ON document_pipeline_runs(run_uuid);"
INDEX_PIPELINE_RUNS_STATUS = "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON document_pipeline_runs(status);"
INDEX_PIPELINE_RUNS_TRIP = "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_trip ON document_pipeline_runs(matched_trip_id);"
INDEX_PIPELINE_RUNS_HASH = "CREATE INDEX IF NOT EXISTS idx_pipeline_runs_hash ON document_pipeline_runs(source_file_hash);"

TABLE_DOCUMENT_PACKAGE = """
CREATE TABLE IF NOT EXISTS document_package (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    updated_at TEXT NOT NULL
);
"""

INDEX_PACKAGE_TRIP = "CREATE INDEX IF NOT EXISTS idx_package_trip ON document_package(trip_id);"
INDEX_PACKAGE_UUID = "CREATE INDEX IF NOT EXISTS idx_package_uuid ON document_package(package_uuid);"
INDEX_PACKAGE_STATUS = "CREATE INDEX IF NOT EXISTS idx_package_status ON document_package(status);"

TABLE_DOCUMENT_PACKAGE_ITEMS = """
CREATE TABLE IF NOT EXISTS document_package_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (package_id) REFERENCES document_package(id) ON DELETE CASCADE,
    UNIQUE(package_id, document_id)
);
"""

INDEX_PACKAGE_ITEMS_PACKAGE = "CREATE INDEX IF NOT EXISTS idx_package_items_package ON document_package_items(package_id);"
INDEX_PACKAGE_ITEMS_DOCUMENT = "CREATE INDEX IF NOT EXISTS idx_package_items_document ON document_package_items(document_id);"

# ── Stage/status enum validation ────────────────────────────────────────────────
# SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we enforce the
# stage/status enums with triggers.  Triggers fire for both fresh and
# upgraded databases; ``IF NOT EXISTS`` makes them idempotent.

# Canonical values mirror :class:`PipelineStage` in
# ``services/document_automation/types.py`` and the ``status`` field
# semantics used by ``PipelineRepository``.
PIPELINE_STAGE_VALUES = (
    "import", "processing", "enhance", "ocr", "validate", "ai_fallback",
    "matching", "auto_attach", "verify", "package", "email",
    "complete", "failed",
)
PIPELINE_STATUS_VALUES = (
    "imported", "processing", "enhanced", "processed",
    "ocr_done", "validated", "ai_done",
    "matched", "attached", "verified", "packaged", "emailed",
    "complete", "failed",
)

_ESCAPED_STAGES = ", ".join(f"'{v}'" for v in PIPELINE_STAGE_VALUES)
_ESCAPED_STATUSES = ", ".join(f"'{v}'" for v in PIPELINE_STATUS_VALUES)

TRIGGER_PIPELINE_RUNS_STAGE_CHECK = f"""
CREATE TRIGGER IF NOT EXISTS trg_pipeline_runs_stage_check
BEFORE INSERT ON document_pipeline_runs
WHEN NEW.stage NOT IN ({_ESCAPED_STAGES})
BEGIN
    SELECT RAISE(ABORT, 'invalid document_pipeline_runs.stage value');
END;
"""

TRIGGER_PIPELINE_RUNS_STAGE_UPDATE = f"""
CREATE TRIGGER IF NOT EXISTS trg_pipeline_runs_stage_check_upd
BEFORE UPDATE OF stage ON document_pipeline_runs
WHEN NEW.stage NOT IN ({_ESCAPED_STAGES})
BEGIN
    SELECT RAISE(ABORT, 'invalid document_pipeline_runs.stage value');
END;
"""

TRIGGER_PIPELINE_RUNS_STATUS_CHECK = f"""
CREATE TRIGGER IF NOT EXISTS trg_pipeline_runs_status_check
BEFORE INSERT ON document_pipeline_runs
WHEN NEW.status NOT IN ({_ESCAPED_STATUSES})
BEGIN
    SELECT RAISE(ABORT, 'invalid document_pipeline_runs.status value');
END;
"""

TRIGGER_PIPELINE_RUNS_STATUS_UPDATE = f"""
CREATE TRIGGER IF NOT EXISTS trg_pipeline_runs_status_check_upd
BEFORE UPDATE OF status ON document_pipeline_runs
WHEN NEW.status NOT IN ({_ESCAPED_STATUSES})
BEGIN
    SELECT RAISE(ABORT, 'invalid document_pipeline_runs.status value');
END;
"""

ALTER_DOCUMENTS_ADD_EXTRACTED_DATA = "ALTER TABLE documents ADD COLUMN extracted_data_json TEXT DEFAULT '{}'"
ALTER_DOCUMENTS_ADD_AUTOMATION_TAGS = "ALTER TABLE documents ADD COLUMN automation_tags TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_OCR_TEXT = "ALTER TABLE documents ADD COLUMN ocr_text TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_OCR_RUN_AT = "ALTER TABLE documents ADD COLUMN ocr_run_at TEXT DEFAULT ''"
ALTER_DOCUMENTS_ADD_OCR_ENGINE = "ALTER TABLE documents ADD COLUMN ocr_engine TEXT DEFAULT ''"

# ── Receipt Generator ─────────────────────────────────────────────────────

TABLE_RECEIPTS = """
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    amount REAL NOT NULL DEFAULT 0,
    vat_rate REAL DEFAULT 0,
    vat_amount REAL DEFAULT 0,
    total REAL DEFAULT 0,
    amount_words TEXT,
    notes TEXT,
    status TEXT DEFAULT 'Draft',
    logo_path TEXT, signature_path TEXT, stamp_path TEXT,
    attachments_json TEXT DEFAULT '[]',
    employee_name TEXT, department TEXT, expense_category TEXT,
    mileage REAL, fuel REAL, accommodation REAL,
    meals REAL, parking REAL, tolls REAL, other_expense REAL,
    pickup_location TEXT, delivery_location TEXT,
    route TEXT, dispatcher TEXT,
    language TEXT DEFAULT 'en',
    created_at TEXT, updated_at TEXT
);
"""

INDEX_RECEIPT_NUMBER    = "CREATE INDEX IF NOT EXISTS idx_receipt_number ON receipts(receipt_number);"
INDEX_RECEIPT_TYPE      = "CREATE INDEX IF NOT EXISTS idx_receipt_type   ON receipts(receipt_type);"
INDEX_RECEIPT_STATUS    = "CREATE INDEX IF NOT EXISTS idx_receipt_status ON receipts(status);"
INDEX_RECEIPT_TRIP      = "CREATE INDEX IF NOT EXISTS idx_receipt_trip   ON receipts(related_trip_id);"
INDEX_RECEIPT_DRIVER    = "CREATE INDEX IF NOT EXISTS idx_receipt_driver ON receipts(driver_id);"

# ── AutoMail / Dunner ────────────────────────────────────────────────────

TABLE_AUTOMAIL_TEMPLATES = """
CREATE TABLE IF NOT EXISTS automail_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    body_html TEXT DEFAULT '',
    variables_json TEXT DEFAULT '[]',
    is_default INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

TABLE_AUTOMAIL_SCHEDULES = """
CREATE TABLE IF NOT EXISTS automail_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
"""

TABLE_AUTOMAIL_CLIENT_OVERRIDES = """
CREATE TABLE IF NOT EXISTS automail_client_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
"""

TABLE_AUTOMAIL_SETTINGS = """
CREATE TABLE IF NOT EXISTS automail_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

INDEX_AUTOMAIL_SCHEDULES_TEMPLATE = (
    "CREATE INDEX IF NOT EXISTS idx_automail_schedules_template "
    "ON automail_schedules(template_id)"
)
INDEX_AUTOMAIL_SCHEDULES_ACTIVE_SORT = (
    "CREATE INDEX IF NOT EXISTS idx_automail_schedules_active_sort "
    "ON automail_schedules(is_active, sort_order)"
)
INDEX_AUTOMAIL_CLIENT_OVERRIDES_CLIENT = (
    "CREATE INDEX IF NOT EXISTS idx_automail_client_overrides_client "
    "ON automail_client_overrides(client_id)"
)

TABLE_COMPANIES = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    subscription_tier TEXT NOT NULL DEFAULT 'starter'
        CHECK (subscription_tier IN ('starter', 'professional', 'enterprise')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

INDEX_COMPANIES_NAME = (
    "CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name)"
)

TABLE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'dispatcher',
    company_id INTEGER REFERENCES companies(id),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

INDEX_USERS_EMAIL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
)

INDEX_USERS_COMPANY = (
    "CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)"
)

TABLE_GPS_TELEMETRY = """
CREATE TABLE IF NOT EXISTS gps_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    truck_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    speed_kmh REAL DEFAULT 0,
    heading INTEGER DEFAULT 0,
    driver_id INTEGER,
    recorded_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

INDEX_GPS_TRUCK = (
    "CREATE INDEX IF NOT EXISTS idx_gps_truck ON gps_telemetry(truck_id)"
)
INDEX_GPS_RECORDED = (
    "CREATE INDEX IF NOT EXISTS idx_gps_recorded ON gps_telemetry(recorded_at)"
)
