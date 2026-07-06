========================================================================================

TASK: COMPREHENSIVE ARCHITECTURAL SYSTEM REMEDIATION \& REDESIGN PROTOCOL

TARGET RUNTIME ENVIRONMENT: Python 3.9 (Strict Backward Compatibility Constraints)

OUTPUT ARTIFACT: REWORKPLAN.md (Exhaustive, Multi-Phase Engineering Blueprint)

========================================================================================



CONTEXT:

Our logistics ERP platform is near its final MVP release milestone with 2,021 unit and integration tests passing. However, internal stack isolation is structurally compromised: 22 backend services execute over 140 raw SQL operations via 'conn.execute()', and 19 UI views instantiate repositories directly in memory.



To transform this system into a distributed, multi-platform enterprise infrastructure capable of serving our PySide6 Desktop Client, a future iOS/Android driver mobile tracking app, and a cloud web dashboard, you must completely decouple the core backend into an independent, distributed API engine.



YOUR OBJECTIVE:

Act as a Principal Systems Architect and Senior DevOps Engineer. Generate an exhaustive, line-by-line, un-truncated technical implementation blueprint document and save it to the workspace as 'REWORKPLAN.md'.



DO NOT use placeholders. DO NOT use high-level summaries or say "insert code here". Plan out every single detail, explicit directory path, file layout, syntax exception rule, and deployment configuration string required to execute this transition while keeping all 2,021 existing tests green.



========================================================================================

1\. DEFINITIVE PRODUCTION TECH STACK \& ARCHITECTURE MATRIX

========================================================================================

The entire plan, routing topology, and containerized deployment infrastructure must conform strictly to these technical selections:

\- Language Runtime: Python 3.9 (Enforce strict backward compatibility)

\- API Routing Gateway: FastAPI (Asynchronous microservice loop utilizing async/await)

\- Schema Serialization: Pydantic v2 (Strict typing primitives and data contracts)

\- Production Server Gateway: Uvicorn (ASGI worker) managed via Gunicorn process clustering

\- Primary Production Data Store: PostgreSQL (Relational storage with strict ACID compliance)

\- Development Data Fallback: SQLite (Asynchronous WAL-mode connection pools via connection\_pool.py)

\- Asynchronous Task Queue: Celery (For offloading document OCR vision parsing and heavy PDF builds)

\- Distributed In-Memory Engine: Redis (Acting simultaneously as the Celery message broker, enterprise data cache, and real-time fleet GPS telemetry stream ingestion buffer)

\- Dependency Pipeline: 'uv' (Rust-backed package engine ensuring ultra-fast, immutable environment builds)



========================================================================================

2\. PYTHON 3.9 COMPLIANCE \& SYNTAX GUARDRAILS

========================================================================================

To eliminate compiler exceptions during runtime, enforce these precise generation constraints across all code blocks:

\- BANNED: Native collection type hints (e.g., list\[str], dict\[str, int]).

&#x20; MANDATORY: Explicit uppercase collection imports from the typing module (e.g., typing.List\[str], typing.Dict\[str, int]).

\- BANNED: The pipe operator (|) for Union or Optional types.

&#x20; MANDATORY: Explicit usage of typing.Union or typing.Optional (e.g., typing.Optional\[str], typing.Union\[int, float]).

\- All Pydantic models must be engineered using core schemas fully native to a Python 3.9 interpreter.



========================================================================================

3\. PHASE-BY-PHASE TECHNICAL ROADMAP REQUIREMENTS FOR REWORKPLAN.md

========================================================================================

The generated 'REWORKPLAN.md' file must provide complete, exhaustive operational steps for the following phases:



PHASE 1: PURE BACKEND DECOUPLING (THE CORE BRAIN ISOLATION)

\- Detailed protocol to systematically scrub all raw 'conn.execute()' statements, manual SQL strings, and raw transaction loops out of the 22 service files (starting with cmr\_generator.py, alert\_manager.py, and document\_grouper.py).

\- Precise mapping strategies to encapsulate those queries inside dedicated, reusable methods in the 'repositories/' layer using 'BaseRepository' parent wrappers (\_execute, \_fetchone, \_fetchall).

\- Define the architectural boundary: Services consume Repositories via constructor dependency injection; Repositories never know about upper layers or raw connection leak bypasses.



PHASE 2: DEFINING THE API SCHEMA LAYER (THE DATA CONTRACTS)

\- Comprehensive design of Pydantic v2 input/output serialization structures for core entities (Trips, Documents, Clients, OCR Extracted Payloads).

\- A complete asynchronous FastAPI router matrix mapped cleanly by resource path (e.g., /api/v1/trips, /api/v1/documents, /api/v1/ocr).



PHASE 3: DISTRIBUTED INFRASTRUCTURE INTEGRATION (THE HEAVY STACK ADDITIONS)

\- Setup details for a Redis caching layer to intercept slow relational database lookup queries for static/frequent logistics data (zip geolocations, carrier company info).

\- Architecture blueprint for a Celery task framework that offloads heavy OCR extractions (Gemma 3 vision parsing) and multi-page document generations into background worker loops.

\- Design an ingestion pipeline where high-frequency mobile GPS streaming logs write to volatile Redis memory first to protect the PostgreSQL storage layer from disk I/O locking.



PHASE 4: DECOUPLING THE PYSIDE6 DESKTOP UI

\- Protocol for eliminating direct repository instantiations out of the 19 UI views (e.g., PipelineRepository(self.db)).

\- Blueprint for implementing a centralized, asynchronous network client engine inside the PySide6 client (using httpx or QNetworkAccessManager) to query the backend API via HTTP/JSON instead of local RAM functions.



PHASE 5: CONTAINERIZED DEPLOYMENT \& DEVOPS PIPELINE CONFIGURATIONS

\- Provide the complete, un-truncated multi-stage Python 3.9 Dockerfile running as a secure non-root system user using the 'uv' builder package manager.

\- Provide the complete production-grade 'docker-compose.yml' grouping the app nodes ('api', 'worker', 'redis', 'db' with persistent volume mounts, environment variables, and healthchecks).

\- Provide the complete security-hardened reverse-proxy 'nginx.conf' layout providing SSL termination, request rate-limiting, and error logging configurations.



========================================================================================

4\. ACTIONABLE IMPLEMENTATION BLUEPRINTS REQUIRED

========================================================================================

Include extensive, non-placeholder code verification blocks mapping out explicit "BEFORE vs. AFTER" architectural refactoring examples for:

1\. A service logic routine handling unmanaged inline SQL transactions transformed into a clean, decoupled service utilizing an injected Repository abstraction with correct Python 3.9 type hinting.

2\. A PySide6 UI view component executing local repository write operations transformed into a clean client UI view communicating over an asynchronous web transport layer.



========================================================================================

5\. TEST INTEGRATION PROTOCOL

========================================================================================

Detail a testing roadmap using pytest to ensure that all 2,021 tests pass flawlessly. Show how service logic unit testing remains green by feeding mock repositories with return dictionary sets, and demonstrate how new API endpoints are checked instantly using the in-memory 'fastapi.testclient.TestClient' pipeline without binding a real physical port during test runs.



Do not halt execution, do not emit ellipses (...), and do not output a partial guide. Generate the complete, production-ready 'REWORKPLAN.md' document now.

