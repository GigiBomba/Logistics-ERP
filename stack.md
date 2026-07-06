\### CRITICAL TECH STACK SPECIFICATIONS

\- \*\*Language:\*\* Python 3.9

\- \*\*API Framework:\*\* FastAPI (Asynchronous endpoints using async/await)

\- \*\*Data Validation Layer:\*\* Pydantic v2 (For request/call data verification and JSON serialization)

\- \*\*Database (Current):\*\* SQLite (Utilizing the existing connection\_pool.py and WAL mode)

\- \*\*Target Database (Production):\*\* PostgreSQL (Ensure repositories remain decoupled so swapping databases requires zero service logic changes)

\- \*\*Server Gateway:\*\* Uvicorn (ASGI server runner)

\- \*\*Containerization:\*\* Docker \& Docker-Compose

