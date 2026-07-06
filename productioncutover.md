========================================================================================

TASK: FINAL PRODUCTION CUTOVER \& UI CLIENT ISOLATION PROTOCOL

TARGET RUNTIME ENVIRONMENT: Python 3.9 (Strict Syntax Enforcement)

OBJECTIVE: Convert the PySide6 Desktop Application into a Pure Remote API Client



CONTEXT:

Our modular backend refactoring was successful, and we have successfully moved core business logic and database executions into a standalone FastAPI server. However, we must now prepare the system for actual production rollout. The PySide6 desktop application must run as a lightweight, isolated user interface that communicates exclusively over secure network requests (HTTPS/JSON) with our centralized cloud backend API. The UI must contain ZERO direct SQLite database imports, zero direct local database file manipulations, and zero manual repository instantiations in the view layers.



YOUR GOAL:

Act as a Principal Software Engineer and Enterprise Desktop Architect. Write a systematic, file-by-file implementation plan and generate the necessary wrapper scripts, configurations, and core client-side network modules to transition the PySide6 application from local execution mode to pure remote client mode.



Your execution must keep our 2,021 tests green and comply strictly with Python 3.9 syntax limits.



========================================================================================



PYTHON 3.9 COMPLIANCE MANDATE (STRICT)

========================================================================================



BANNED: Native collections in type hints (e.g., list\[str], dict\[str, Any]).

MANDATORY: Explicit uppercase imports from the typing module (e.g., typing.List\[str], typing.Dict\[str, Any]).



BANNED: Union pipe operators (|) for typing.

MANDATORY: Explicit typing.Union or typing.Optional imports (e.g., typing.Optional\[str]).



All code, wrappers, and configuration classes must compile cleanly on a Python 3.9 runtime.



========================================================================================

2\. MANDATORY IMPLEMENTATION PHASES FOR THE CODE REWORK



Please plan and generate files to handle these exact phases:



PHASE 1: THE REMOTE CONFIGURATION GATEWAY



Implement a client-side environment manager ('client/config.py') that checks for 'OPERION\_API\_URL' and 'OPERION\_ENV' (e.g., 'production', 'development').



If 'OPERION\_ENV=production', automatically point all UI routing requests to your production cloud domain (e.g., 'https://api.operionerp.com') with SSL verification enabled.



Ensure the config fallback gracefully defaults to 'http://127.0.0.1:8000' for local staging.



PHASE 2: SECURING THE QT EVENT LOOP (ASYNC THREAD WRAPPERS)



Direct network calls over slow internet connections will instantly freeze the PySide6 main UI thread. You must build a reusable Qt-friendly background worker wrapper: 'client/network/network\_worker.py'.



This file must extend 'QThread' or utilize 'QRunnable' and 'QThreadPool' to offload heavy API calls (such as document upload or running OCR via the API) to background threads.



Implement explicit PySide6 Signals (e.g., 'finished(dict)', 'error(str)') to feed returned JSON payloads back to the main UI views safely once the server responds.



PHASE 3: AUDITING \& REFACTORING THE VIEW INVENTORY



Scan our 19 view files and provide the exact modifications needed to migrate local files to pure API routes.



Specifically demonstrate how to convert a local file path save in 'receipt\_editor.py' or 'document\_center\_view.py' into a secure binary multipart file upload using 'httpx' boundary streams targeting the '/api/v1/documents/upload' endpoint.



Provide a clear code transformation showing how 'on\_upload\_clicked' reads the local file stream, wraps it in a 'files' dictionary payload, runs it inside our background thread worker, and displays a clean QProgressBar while waiting for the response.



PHASE 4: LOCAL SANITIZATION \& PACKAGING PIPELINE



Write a clean build configuration script ('scripts/build\_client.py' or 'pyinstaller.spec') that packages only the 'ui/' directory, 'client/' network helpers, and localized assets/design tokens.



Explicitly exclude all 'backend/', 'repositories/', 'database/', 'tests/', and local SQLite database files ('\*.db') from the compiled build.



This ensures that when we distribute the client installer to users, it weighs less than 100MB and contains absolutely zero reverse-engineerable proprietary database queries, local business schemas, or deep routing code.



========================================================================================

3\. NON-PLACEHOLDER IMPLEMENTATION EXAMPLES REQUIRED



Do not write placeholders like "# insert logic here" or use ellipsis (...) in your generated code blocks. Write complete, copy-pasteable files for:



'client/network/network\_worker.py': Standardizing threaded API calls with PySide6 custom signals.



'ui/views/upload\_integration.py': A complete view component demonstrating how to select a local PDF, run it through the background thread worker, stream it via a multipart API request to the backend, and update the UI with the resulting OCR JSON extraction.



'scripts/verify\_client\_isolation.py': A quick automated test script that scans the client folder and flags any files importing 'sqlite3', 'database', or instantiating a local 'BaseRepository' object.



Proceed with the complete architectural finalization plan now.

