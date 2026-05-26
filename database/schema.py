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

# Actualizăm tabelul TRIPS pentru a lega cursa de un camion din baza de date
# (Aceasta se face prin adăugarea coloanei truck_id dacă doriți integritate totală)
