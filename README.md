# Operion ERP

**Logistics ERP & Calculator** — route planning, fleet management, dispatch board, CMR/eFTI document generation, and analytics for transport companies.

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Configure environment
cp .env.example .env
# Edit .env with your GraphHopper URL, fleet tracking credentials, etc.

# 4. Run the application
python main.py
```

## Core Project Structure

```
.
├── main.py                  # Entry point — initializes DB, i18n, theme, opens MainWindow
├── config.py                # App-wide constants (paths, API URLs, cost defaults)
├── pyproject.toml           # Project metadata, linter (ruff), pytest, coverage config
├── requirements.txt         # Production + dev dependencies
│
├── ui/                      # PySide6 (Qt) UI layer
│   ├── app_shell.py         # Sidebar + topbar + stacked view container layout
│   ├── main_window.py       # MainWindow controller — module registry, navigation, services
│   ├── theme.py             # Design tokens: COLORS, FONTS, S (spacing), radii, chart palette
│   ├── theme_engine.py      # QtTheme class — generates and applies QSS stylesheet globally
│   ├── styles.py            # Theme compatibility class (Bridge to old ui.styles API)
│   ├── icons.py             # Unicode icon glyphs and iconed() helper
│   ├── views/               # View widgets (one per sidebar nav item)
│   │   ├── calculator_view.py       # Trip cost/profit calculator
│   │   ├── route_planner_view.py    # Multi-stop route planning with map
│   │   ├── dispatch_board_view.py   # Kanban board for trip dispatch
│   │   ├── fleet_tracking_view.py   # GPS fleet map + status
│   │   ├── fleet_tab.py             # Fleet/vehicle management
│   │   ├── driver_manager.py        # Driver CRUD + document linking
│   │   ├── client_workspace.py      # Client CRM workspace
│   │   ├── document_center_view.py  # Centralized document management
│   │   ├── generators_view.py       # CMR/invoice/document generator launcher
│   │   ├── cmr_form_view.py         # CMR form with UN/CEFACT boxes
│   │   ├── invoice_editor.py        # Invoice editor + PDF generation
│   │   ├── analytics_view.py        # Revenue/fleet analytics charts
│   │   ├── dashboard.py             # Fleet dashboard (KPI cards + charts)
│   │   ├── overview_view.py         # Home page — KPIs, recent activity, alerts
│   │   ├── history_view.py          # Trip history list
│   │   ├── route_history_view.py    # Route history with map preview
│   │   ├── settings_view.py         # Preferences, language, SMTP, tracking config
│   │   ├── maintenance_analytics_view.py  # Maintenance analytics
│   │   ├── maintenance_control_panel.py  # Maintenance work orders + schedules
│   │   └── tacho_import_view.py     # Tachograph file import
│   ├── widgets/              # Reusable widgets
│   │   ├── __init__.py              # StyledLineEdit, ActionButton, KpiCard, etc.
│   │   ├── nav_panel.py             # Sidebar navigation
│   │   ├── top_bar.py               # Top bar (breadcrumb, clock, alerts bell, fuel)
│   │   ├── toast.py                 # Toast notifications
│   │   ├── alert_panel.py           # Alert dropdown panel
│   │   ├── dispatch_*.py            # Dispatch sub-widgets (search, tabs, timeline, kanban)
│   │   ├── fuel_panel.py            # Fuel price panel
│   │   └── trip_card.py             # Trip card widget for kanban
│   ├── dialogs/              # Modal dialogs
│   │   ├── edit_window.py
│   │   ├── maintenance_view.py
│   │   ├── dispatch_detail_panel.py
│   │   └── paired_assignment_dialog.py
│   └── map/                  # Map subsystem (folium + QWebEngineView)
│       ├── map_widget.py            # MapWidget with JS bridge
│       ├── map_helpers.py           # Overlay/route helpers
│       └── route_renderer.py        # Route drawing on map
│
├── services/                # Business logic layer
│   ├── trip_service.py      # Trip CRUD + status transitions
│   ├── route_service.py     # GraphHopper routing client + caching
│   ├── fleet_service.py     # Fleet/vehicle management
│   ├── client_service.py    # Client CRM logic
│   ├── document_service.py  # Document upload/download/tag/link
│   ├── export_service.py    # PDF/Excel export
│   ├── fuel_price_service.py    # Fuel price scraping
│   ├── exchange_rate_service.py # Currency exchange rates
│   ├── calculator.py        # Trip cost/profit calculation engine
│   ├── country_exclusion.py # Country routing exclusions
│   ├── geocode_nominatim.py # OSM Nominatim geocoding
│   ├── graphhopper_network.py   # GraphHopper HTTP helpers
│   ├── fleet_tracking_service.py # Wialon/Frotcom/Navixy GPS adapters
│   ├── conflict_service.py  # Trip conflict detection
│   ├── i18n.py              # Internationalization (22 languages)
│   ├── preferences.py       # Centralized user preferences
│   ├── invoicing/           # CMR/eFTI document generation
│   │   ├── cmr_generator.py     # CMR PDF generation
│   │   ├── cmr_efti.py          # eFTI XML validation
│   │   └── generator.py         # Invoice PDF generator
│   └── operations/          # Operational intelligence
│       ├── operations_engine.py  # Central orchestrator
│       ├── event_bus.py         # Pub/sub event system
│       ├── alert_manager.py     # Alert creation/resolution
│       ├── maintenance_engine.py # Maintenance prediction
│       └── notification_center.py # Email/SMS notifications
│
├── repositories/            # Data access layer (SQLite)
│   ├── trip_repository.py
│   ├── fleet_repository.py
│   ├── client_repository.py
│   ├── driver_repository.py
│   ├── document_repository.py
│   └── ...
│
├── database/
│   └── db_manager.py        # SQLite connection + schema migrations
│
├── utils/
│   ├── helpers.py           # General helpers
│   ├── formatting.py        # Number/date formatting
│   ├── validation.py        # Input validation
│   └── logger.py            # Logging setup
│
├── data/
│   ├── translations/        # 22 locale JSON files (en, ro, de, fr, ...)
│   ├── company_config.json  # Company name/address/CUI
│   └── cashflow.db          # SQLite database (gitignored)
│
└── tests/                   # Pytest test suite
    ├── conftest.py          # Root config: registers Qt fixtures
    ├── test_conftest.py     # QApplication fixture, webengine setup
    ├── test_calculator.py   # Qt calculator view tests
    ├── test_overview.py     # Qt overview dashboard tests
    ├── test_trip_service.py # Service-layer unit tests
    └── ...
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Purpose |
|----------|---------|
| `OPERION_GRAPHHOPPER_URL` | GraphHopper routing server (default: `http://localhost:8989`) |
| `OPERION_DB_PATH` | SQLite database path |
| `OPERION_SMTP_*` | Email server for invoice/report delivery |
| `OPERION_FLEET_TRACKING` | Enable GPS fleet tracking integrations |

See `.env.example` for all options.

## Running Tests

```bash
pytest tests/ -q
```

## Code Quality

```bash
# Lint
ruff check .

# Format
ruff format .

# Both
ruff check --fix . && ruff format .
```

## Tech Stack

- **UI**: PySide6 (Qt 6) with QSS theming
- **Maps**: folium + QWebEngineView
- **Charts**: Plotly (Kaleido SVG → QPixmap)
- **Database**: SQLite via raw connections
- **PDF**: reportlab + pypdf
- **Routing**: GraphHopper
- **i18n**: 22 languages via JSON translation files
