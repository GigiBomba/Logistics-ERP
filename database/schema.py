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
    status TEXT
    -- route_history_v2_id INTEGER REFERENCES route_history_v2(id),  (added by migration)
    -- truck_consumption_l_per_100km REAL,                          (added by migration)
    -- context_json TEXT                                             (added by migration)
);
"""

INDEX_TRIPS_DATE = "CREATE INDEX IF NOT EXISTS idx_trips_date ON trips(created_at);"
INDEX_TRIPS_TRUCK = "CREATE INDEX IF NOT EXISTS idx_trips_truck ON trips(truck_number);"



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
    archived_at TEXT
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
