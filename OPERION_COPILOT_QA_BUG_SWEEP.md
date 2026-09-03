# Operion AI Copilot — QA Bug Sweep Report

**Date:** 2026-08-29
**Scope:** Entire AI Copilot layer — backend pipeline (planner/executor), LLM layer, 31+ tool modules, API router, Celery tasks, repositories/migrations, desktop Qt client, Flutter mobile client, business invariants.
**Method:** 5 parallel deep-review lanes (independent code reading, line-verified findings) + orchestrator spot-verification of the highest-severity claims. No runtime execution performed; findings marked with confidence (High = verified by code path, Medium = inferred/interleaving-dependent, Low = needs runtime repro).
**Coverage note:** The repo's own test suite (~3,970 copilot tests, all green) largely asserts *intended* behavior; several tests codify the bugs below (e.g. `test_copilot_isolation.py:224-242` documents the IDOR as "by design", `test_phase3_undo.py:166-189` codifies the missing typed-phrase validation, `test_desktop_mobile_parity.py:442-448` asserts the broken wire contract).

---

## CRITICAL (fix before production)

### SW-01 · Systemic tenant-isolation failure in copilot tool execution — cross-tenant read/write/delete
**Confidence:** High (mechanism verified) · **Sources:** tools lane F-01
**Where:** `backend/dependencies_security.py:94,128` · `database/db_manager.py:2296-2301` · `repositories/__init__.py:83-145` · tools: `vehicle_tools.py:65`, `vehicle_crud_tools.py:230`, `delete_tools.py:84,171,261,348,438,530`, `dispatch_tools.py:188`, `client_crud_tools.py:251`, `driver_tools.py:61`, `analytics_tools.py:104`, `export_tools.py:134`, `document_tools.py:77,155,189`, `invoice_tools.py:138,225,317`, `receipt_tools.py:130,216,300`, `proforma_tools.py:132,238,330`, `automail_tools.py:87`, `maintenance_tools.py:179,379`, `freight_tools.py` (scoped, excepted)
**What:** The HTTP auth stack sets only `backend.dependencies._current_company_id`, **never** `database.tenant_context`. Repositories derive filters from the context; when unset, `_company_filter()` returns `""` → **no company predicate at all**. The regular API passes `company_id=` explicitly on every service call; the copilot tools mostly don't. Only route/trip list tools, `conversation.recall_recent`, and freight tools are scoped. Every unscoped tool = cross-tenant read (clients, trips, analytics, documents) and cross-tenant write/delete (trip, vehicle, driver, client, invoice, route) given a guessable/sequential entity id.
**Fix:** In `executor.py` build-ctx (both paths, ~622-628 and ~860-866), wrap every tool execution in `database.tenant_context.set_request_context(ctx.company_id, ctx.role)` with restore in `finally`; add registry validation flagging tools whose service calls don't accept `company_id`.
**Test gap:** `test_planner_executor.py:2024` calls `set_company_context` inside the test itself, masking the production gap.

### SW-02 · `tracking.get_live_positions` leaks all tenants' live GPS positions
**Confidence:** High · **Source:** tools lane F-03
**Where:** `tracking_tools.py:52-57` → `services/fleet_tracking_service.py:704-728`
**What:** Tool calls `get_positions()` with no `driver_id`/`company_id`; the service singleton's cache is not tenant-filtered. Any caller with `tracking:read` (granted to driver, dispatcher, manager) gets every company's lat/lon/speed. Plus cache cross-contamination between requests.
**Fix:** Filter positions by `company_id` inside the tool; refuse when no company filter applies.

### SW-03 · LLM-controlled arbitrary file read via OCR/tacho import tools (server-side file disclosure)
**Confidence:** High · **Source:** tools lane F-02
**Where:** `ocr_tools.py:23-29,54-56,70-75` · `tacho_tools.py:25-28,102-108`
**What:** `document.ocr_import` / `tahograf.import_file` accept a free-form `file_path` from LLM arguments; validation is `os.path.isfile()` only. File is copied and OCR'd, text returned to the user. No uploads-root allowlist, no size limit. A prompt-injected/naughty utterance ("OCR backend/../.env") exfiltrates config/secrets or another tenant's stored documents — at Level 1 (no confirmation), even in driver catalogs (`documents:write` in `DRIVER_TOOL_PERMISSIONS`).
**Fix:** Path containment check against configured uploads root; size cap; raise to BUSINESS confirmation level.

### SW-04 · DESTRUCTIVE "typed confirmation" is never enforced; autonomous mode executes Level 3 with no human in the loop
**Confidence:** High · **Source:** tools lane F-04
**Where:** `delete_tools.py:61-68,148-155,238-245,325-332,415-422,506-513` · `schemas.py:25` · `llm/tool_calling.py:824-840`
**What:** All six delete tools accept `confirmation_phrase` but `validate()` only checks non-empty — never compared to anything. The phrase is LLM-generated, so the UI modal re-displays an LLM-chosen string. The real gate is plan `/confirm` — **except** the autonomous pre-approved path (`tool_calling.py:825-840`) executes BUSINESS/DESTRUCTIVE inline with zero user interaction. Contract in `schemas.py:25` ("always requires confirmation + typed phrase") is not implemented server-side. Combined with SW-01: permanent cross-tenant deletion without human approval.
**Fix:** Exclude DESTRUCTIVE from the autonomous fast-path; server-generated session-scoped typed challenge compared server-side.
**Test gap:** `test_phase3_undo.py:166-189` explicitly asserts the phrase is NOT validated — the test codifies the hole.

### SW-05 · Confirmation flow is unreachable from BOTH clients — `/chat` wire contract omits the `plan` object
**Confidence:** High (verified: `copilot_router.py:353-372` returns only `plan_id`) · **Source:** clients lane C1
**Where:** `backend/api/v1/copilot_router.py:104-113,353-372` · `mobile_app/.../copilot_models.dart:200-240`, `copilot_providers.dart:158-174` · `ui/copilot/controllers/copilot_controller.py:91-105,249-253`
**What:** `ChatResponse` serializes only `plan_id`; mobile `fromJson` parses only a `plan` key; desktop `_parse_response` gets `plan=None` → `_active_plan_id` never set in remote mode. Level 2/3 plans can never be confirmed from either client; plans sit in `_pending_plans` forever.
**Fix:** Include `plan_id` + `requires_confirmation` + steps in `ChatResponse` (or have clients fetch `GET /plans/{id}` when confirmation is needed).
**Test gap:** `test_desktop_mobile_parity.py:442-448` asserts `plan_present is False` — locks in the broken contract.

### SW-06 · WebSocket `/copilot/ws/{conversation_id}` is not company-scoped — cross-tenant live broadcast of tool results
**Confidence:** High · **Sources:** pipeline lane F-06, API lane F-01
**Where:** `copilot_router.py:1457-1496` · `1278-1294` (`_push_plan_update`) · `1357-1388` (`_poll_and_push_progress`) · `copilot_tool_tasks.py:63-81`
**What:** Handler validates the JWT but never checks conversation ownership; `_ws_connections` is keyed by client-supplied `conversation_id`; progress Redis keys are not company-scoped; payloads include full `result` data (client data, freight quotes, dispatch payloads). Any authenticated user can subscribe to another tenant's conversation.
**Fix:** Bind conversation→company at creation; reject mismatches (4403); scope progress keys per company.

### SW-07 · `GET /copilot/plans/{plan_id}` has no ownership check — cross-tenant plan data disclosure (IDOR)
**Confidence:** High · **Sources:** pipeline F-03, LLM F-01, API F-02 (3 independent lanes)
**Where:** `copilot_router.py:503-535` vs `48-57`
**What:** Every other plan op calls `_validate_plan_ownership`; `get_plan` reads `_pending_plans.get(plan_id)` directly and returns steps, parameters, results, intent, conversation_id to any authenticated user of any company.
**Fix:** Route through `_validate_plan_ownership`; 404 for foreign plans.
**Test gap:** `test_copilot_isolation.py:224-242` documents the hole as "by design for Phase 1".

### SW-08 · Undo feature is broken end-to-end: 500 on SQLite (str/datetime TypeError), audit writes fail on PostgreSQL, no enforcement
**Confidence:** High (verified) · **Sources:** pipeline F-01, tools F-06, API F-05/F-06 (3 lanes)
**Where:** `copilot_router.py:900-930` · `executor.py:77-90` · `database/schema.py:1236` · `audit.py:121` · `alembic/versions/d4e5f6a7b8c4...:22-48` · `repositories/copilot_repository.py:46-106`
**What:** (a) Audit `started_at` is stored as ISO string (SQLite TEXT); `is_undo_expired` computes `datetime.utcnow() - started_at` → TypeError → blanket handler → HTTP 500 on **every** real undo attempt; 30-min window is simultaneously dead code and a crash point. (b) On PostgreSQL the audit table declares `user_id`, `permission_checked`, `permission_granted`, `confirmation_level` NOT NULL but `log_step_execution` never writes them → IntegrityError on every step write (swallowed) → `copilot_audit_log` permanently empty on PG → undo 404s, observability aggregates empty, retention/erasure operate on nothing.
**Fix:** `datetime.fromisoformat` + tz normalization before subtraction; new migration making the four columns nullable/defaulted or extend the insert.

### SW-09 · Duplicate-execution family: concurrent confirm race, client retries of confirm/undo POSTs, resume re-dispatches Celery steps
**Confidence:** High (mechanisms verified) · **Sources:** pipeline F-02/F-08, clients C2/H1
**Where:** `executor.py:835-916` (skip set omits `running`) · `copilot_router.py:697-749` (no state check; plan popped only after execution) · `client/api_client.py:168-251` (retries 500/502/503/504 ×3 with backoff) · `mobile_app/.../copilot_providers.dart:14-28` (retry interceptor on shared app-wide Dio, no path filter, retries all POSTs) · `executor.py:654-663,736-769` (resume flips dispatched `running`→`paused`→`pending` → re-dispatch while Celery task still runs)
**What:** Three independent routes to the same failure: (1) two concurrent `/confirm` (or confirm+resume) execute the same step twice — BUSINESS/DESTRUCTIVE tools duplicate real mutations; (2) desktop `_request_with_retry` and mobile `CopilotRetryInterceptor` re-POST confirm/chat on transient 5xx/timeout — the server executes again since the plan is popped only after completion; (3) pause→resume of a long-running step re-dispatches it (export/email batches sent twice).
**Fix:** Add `running`/`paused` to the skip set + atomic plan "confirmed" claim; never auto-retry `confirm|cancel|undo` (client-side) and restrict the mobile interceptor to `/api/v1/copilot/*` GETs; on resume keep dispatched steps `running` (reconcile via progress key); server-side 409 on re-confirm of an executing/completed plan.

---

## HIGH

### SW-10 · Kill switch fails OPEN on Redis outage; `_set_kill_switch` silently no-ops
**Confidence:** High · **Source:** API lane F-04
**Where:** `copilot_router.py:163-185` · `backend/cache.py:17-46`
**What:** `RedisCache.get` swallows all exceptions → `None` → kill-switch checks pass; `connect()` attempted once (flapping Redis → permanently disabled); `set` failure ignored → admin believes switch is engaged. Docstring claims fail-closed; behavior is fail-open. Celery tools also never re-check the switch mid-run (see SW-21).
**Fix:** Treat cache errors as "killed"/503; reconnect/backoff; surface set failures.

### SW-11 · Observability endpoint leaks cross-tenant telemetry to any authenticated user (incl. drivers)
**Confidence:** High · **Source:** API lane F-03
**Where:** `copilot_router.py:1029-1178`
**What:** Circuit-breaker state (all companies, incl. ids/reasons), confidence counters, phase timings are process-global and returned unfiltered; admin id (company 0) gets unfiltered audit aggregates. Gated only by `get_current_user`.
**Fix:** Company-filter everything (or admin-gate the endpoint).

### SW-12 · Conversation history feature is dead: nothing ever writes `conversation_summary`; pagination cursor is broken
**Confidence:** High · **Source:** API lane F-11/F-10
**Where:** `copilot_router.py:754-870` (list/detail read `conversation_summary`, only tests insert rows) · `copilot_router.py:772-799` (cursor = `id` compared against `created_at`)
**What:** No production writer → list always `[]`; Redis turns TTL out after 4h → detail empty. On PG, `created_at < uuid-string` comparison raises → silent empty page. Schema drift: `id` used as conversation_id; PG table has no `conversation_id` column.
**Fix:** Persist summary rows on conversation end; keyset pagination on `(started_at, id)`; align schemas.

### SW-13 · Prompt injection defenses are ineffective: unsanitized `language` field in system prompt, tool results re-enter prompt verbatim, sanitizer is dead code
**Confidence:** High · **Sources:** LLM F-04/F-05, pipeline F-12
**Where:** `copilot_router.py:96` (`language` unvalidated) · `chat.py:189-195`, `tool_calling.py:380-387` (`SYSTEM_PROMPT.format(language_name=...)`) · `tool_calling.py:456-486,854-858` (raw tool-result data into model context) · `sanitizer.py:76-136` (imported only by tests) · `middleware/input_sanitizer.py:120-137` (ZWS-neutralization only, log-only, bypassable via homoglyphs/splitting)
**What:** (a) Client-controlled `language` is interpolated into the **system** prompt of every LLM call — highest-privilege injection position, unsanitized and not pinned by CI (constants pinned, formatted output not). (b) Tool results (OCR text, client notes) fed back to the model with only a prompt-level "results are DATA" sentence. (c) The dedicated sanitizer is never wired into `process_utterance`.
**Fix:** Validate `language` against `SUPPORTED_LANGUAGES`; neutralize tool-result envelopes structurally (role=untrusted, strip instruction-like patterns); enforce blocking + homoglyph normalization; wire `check_prompt_injection` into the pipeline core.

### SW-14 · Level-1 (INFORMATIONAL) tools perform business mutations with no confirmation — level/action mismatch
**Confidence:** High · **Source:** tools lane F-05
**Where:** `invoice_tools.py:70` (`invoice.draft` creates invoices) · `receipt_tools.py:69` · `proforma_tools.py:70,182` (`proforma.update` accepts arbitrary `status` — LLM can set "Converted", bypassing the Level-2 convert flow) · `payment_tools.py:48` (`payment.generate_bulk_csv` — real money movement when uploaded) · `document_tools.py:131` · `cmr_tools.py:69` · `tacho_tools.py:57`
**What:** Level 1 executes immediately in-loop; these all write DB state, some fiscally significant. `test_tools.py` asserts current levels (codifies rather than catches).
**Fix:** Raise to BUSINESS; restrict proforma status transitions via service allowlist.

### SW-15 · Self-hosted LLM provider is permanently skipped in the backend when configured via DB settings
**Confidence:** High (path) · **Source:** LLM lane F-02
**Where:** `chat.py:314-329` (usability check **before** `reload_settings(db)`) · `ocr_ai_provider.py:70-76` (defaults `_api_key=""`)
**What:** Fresh process: provider gate fails on the in-memory default before the DB settings (`qwen_api_key`/mode/endpoint) are ever loaded; `reload_settings` is only called for providers that already pass. Documented primary setup (settings UI) is dead on arrival; everything silently degrades to keyword fallback.
**Fix:** Reload settings for all candidate providers before the usability gate (or load once at startup).

### SW-16 · Google fallback provider likely non-functional: Gemini contents violate role alternation + system prompt duplication
**Confidence:** Medium (SDK runtime behavior) · **Source:** LLM lane F-03
**Where:** `google_provider.py:121-153` (`_build_contents` maps system→user, keeps all messages), `258-263` (system prompt also passed as `system_instruction`), `321-330` (all exceptions swallowed → `finish_reason="error"`)
**What:** Produces consecutive `user` contents (`[user, user]`, and in iteration 2 `[user, tool, user]`) — Gemini REST rejects non-alternating roles; errors swallowed → `provider_failed` → fallback is unusable exactly when the primary is down. Tests enshrine the broken shape (`test_google_provider.py:227-255`).
**Fix:** Strip system message from contents when emitting `system_instruction`; merge same-role contents; runtime-verify against the pinned SDK.
**Action required:** live-API check with pinned google-genai version.

### SW-17 · Human handoff permanently bricks a conversation after one blank/unparseable message; tracker cleanup never called
**Confidence:** High · **Source:** pipeline lane F-05
**Where:** `human_handoff.py:57-75,121-131` · `planner.py:680,887,948-958`
**What:** `failed_clarification_count >= 1` → handoff, and `handoff_triggered` never resets; `cleanup_expired()` has zero production callers → `_trackers` grows forever. After one blank message or unknown intent (offline), every subsequent deterministic intent returns `copilot.handoff.message`.
**Fix:** Schedule `cleanup_expired()`; auto-reset trigger on next successful turn.

### SW-18 · Circuit breaker is fed only by manual confirmations — autonomous/LLM path never records outcomes; 2 of 3 trip limits are dead
**Confidence:** High · **Source:** pipeline lane F-04
**Where:** `executor.py:557-695` vs `918-929` · `circuit_breaker.py:25-27,39,67-102`
**What:** `record_success/record_failure` called only in `confirm_and_execute`; the autonomous/LLM-first loop never records → runaway autonomous actions can't trip the breaker; `max_level2_actions_per_hour` (20) and `max_identical_action_repeats` (5) never enforced. Manual-path noise trips the whole company (60-min cooldown).
**Fix:** Record outcomes in `execute_plan`; implement hourly window + repeat checks.

### SW-19 · RBAC contradictions: admin is planner-denied but executor-allowed; dispatchers can cancel trips; driver catalog advertises tools the executor always denies
**Confidence:** High · **Source:** tools lane F-08/F-09
**Where:** `role_permissions.py:139-141` (no `"admin"` key → empty permitted set → planner denies everything) vs `executor.py:120-121` (admin bypass) · `dispatch_tools.py:442-453` (`dispatch.cancel` gated by `dispatch:write`, held by dispatchers; `supports_undo=False`; contradicts §8.1 "dispatchers can never delete") · `role_permissions.py:100-109` (drivers granted `documents:write`/`trips:write` but `executor.py:132-133` denies all non-read at runtime)
**What:** All-or-nothing admin posture depending on entry path; destructive cancel available to dispatcher; guaranteed-failure plans for drivers.
**Fix:** Explicit admin entry; own permission for `dispatch.cancel` (or block DESTRUCTIVE for dispatcher); align driver catalog with executor rule.

### SW-20 · In-memory plan store: unbounded growth, multi-worker inconsistency, plans lost on restart, eviction incomplete
**Confidence:** High · **Source:** pipeline F-13, tools F-17, API F-09 (3 lanes)
**Where:** `copilot_router.py:42-57,336-340,552,734,1563-1587`
**What:** `_pending_plans`/`_plan_owners` never TTL-evicted; confirm/cancel pop plans but not owners; `_company_conversations` grows forever; kill-switch cancel is per-process; >1 worker → confirm 404s for plans created on another worker.
**Fix:** Redis-backed store with TTL + owner claim; sweep terminal/stale plans; pop owners alongside.

### SW-21 · Celery long-running tasks: retries are dead code (`max_retries=1` never used), early-ack loses tasks on crash, no kill-switch/RBAC re-check in worker
**Confidence:** High · **Source:** API lane F-14
**Where:** `copilot_tool_tasks.py:292-394`
**What:** No `self.retry()` anywhere; worker crash mid-execution → no terminal progress, step stuck `running` until 1h TTL; task executes tools with snapshot permissions from dispatch time, no re-check of kill switch.
**Fix:** `acks_late` + explicit retry/idempotency; re-check kill switch + permission at task start.

### SW-22 · Retention & GDPR erasure semantics wrong: graphs hard-deleted (not anonymized), wrong clock columns, erasure is a no-op for id-only rows, raw `?` placeholders break on PG
**Confidence:** High · **Source:** API lane F-12/F-13
**Where:** `retention_tasks.py:33-34,72-96,125-174` · `copilot_repository.py:186-192,291-297`
**What:** Graphs `DELETE WHERE created_at < ?` instead of "null JSONB, keep row" from `finalized_at`; summaries use `created_at` not `ended_at`. GDPR erasure selects by loose substring (`12` matches `312`) but redacts only `personal_keys` — matched `*_id` values unchanged → no-op; UPDATE bypasses `_adapt_query` → fails on psycopg2.
**Fix:** UPDATE-null semantics with correct columns; redact matched identifier; route through `_execute`; batch.

### SW-23 · AI safety invariants (ai_argo.py) validate config dicts, not runtime enforcement — pass vacuously
**Confidence:** High · **Source:** API lane F-15
**Where:** `business_invariants/checks/ai_argo.py:55-120,212-288,465-522`
**What:** AI-001 passes when `destructive_ops` config is empty; AI-003 only checks the tag list is non-empty (it is by default) — never queries rows for missing `ai_source_tags`; AI-005/006 compare config keys against constants the code doesn't enforce or enforces differently (`executor.py:66,74` vs config).
**Fix:** Introspect live registry/executor constants; query actual rows for untagged AI writes.

### SW-24 · Tier gates inconsistent: `insight_action` ungated, plan ops never re-check tier, Pro help-mode has unlimited LLM usage
**Confidence:** High · **Source:** API lane F-17/F-23
**Where:** `tier_gate.py:19-27,84-151` · `copilot_router.py:1225-1273,503-749`
**What:** Business-tier user can mutate insights; a plan created pre-downgrade still executes post-downgrade; Pro tier has no quota at all and help-mode runs the full LLM loop.
**Fix:** Gate `insight_action`; re-validate tier in confirm; add help-mode quota.

### SW-25 · Rate limiting is bypassable via spoofed `X-Forwarded-For`; WS bypasses middleware entirely
**Confidence:** Medium (deployment-dependent) · **Source:** API lane F-08
**Where:** `middleware/rate_limit_middleware.py:123-127` · `backend/main.py:127-129`
**What:** Takes first XFF entry, no trusted-proxy validation → key rotation per request → 100 req/60s limit bypassable; combined with SW-24's unlimited Pro → unbounded LLM spend.
**Fix:** Use `request.client.host` or trusted-proxy allowlist.

### SW-26 · LLM tool loop lacks dedup: repeated tool calls execute duplicate side effects; executed step outcomes dropped from API response
**Confidence:** High · **Source:** pipeline F-10, LLM F-11
**Where:** `tool_calling.py:789-858` (`executed_calls` recorded, never consulted) · `tool_calling.py:830-834` + `planner.py:805-814` (mixed-turn responses carry only pending-plan steps; executed reads invisible)
**Fix:** Dedup by (tool, canonical args); merge `executed_steps` into the pending-plan response timeline.

### SW-27 · Desktop WebSocket never connected; latent code has double-connect race, stale-token reconnect loop, no resync. Mobile WS endpoint path is wrong (404) and never used
**Confidence:** High · **Source:** clients H3/H4
**Where:** `ui/copilot/controllers/copilot_controller.py:437-455,479-586` (zero callers) · `client/remote_copilot.py:75-83` (token captured once) · `mobile_app/.../copilot_endpoints.dart:160-189` (`/plans/{id}/timeline/ws` — backend has `/ws/{conversation_id}`) · `websocket_client.dart:65-72,161-178` (no reconnect cap)
**What:** Desktop real-time timeline absent; mobile `watchPlanTimeline` would 404 and reconnect forever with a stale token. `copilot_integration_test.dart:470-497` asserts the wrong URL.
**Fix:** Wire `_connect_ws`; rebuild URL per connect from fresh token; cap attempts; use matching endpoint + path on mobile.

### SW-28 · Mobile renders raw i18n keys and never displays LLM answers
**Confidence:** High · **Source:** clients H2
**Where:** `copilot_screen.dart:64-81,302` · `copilot_providers.dart:140`
**What:** Bubbles render `summaryKey`/`messageKey` verbatim; no translation layer; `copilot.summary.llm_chat`'s actual `answer` param is never shown (desktop special-cases it).
**Fix:** Resolve keys through app localization with params interpolation.

### SW-29 · Local (SQLite) mode parity drift: enterprise tier hardcoded, quota skipped, conversation memory lost, undo always "not available", pending plans unconfirmable
**Confidence:** High · **Source:** clients M5
**Where:** `client/local_copilot.py:36-37,211-218,297-305,355-357`
**What:** Free-tier companies get enterprise features locally; multi-turn context lost locally but not remotely; pending BUSINESS plans accumulate with no confirm UI and no eviction.
**Fix:** Derive tier/flags from local config; record usage; persist memory; wire confirm/eviction.

### SW-30 · Offline conversation cache (mobile) not scoped by company/user; corrupt entries never evictable
**Confidence:** High · **Source:** clients M4
**Where:** `copilot_conversation_cache.dart:85-93,132-154,191-196`
**What:** Global cache keys across tenants — company switch + offline = previous company's history served; malformed `cached_at` parses to `DateTime.now()` → always "newest" → eviction can't reclaim; expired entries only hidden, never deleted.
**Fix:** Namespace keys by company+user; delete on expiry; treat unparseable dates as oldest.

### SW-31 · Voice state machine wedges permanently (empty buffer → stuck `processing`; wake-word can never re-arm after error); concurrent turns allowed; PTT re-press desync
**Confidence:** High · **Source:** clients M1/M2/L4
**Where:** `ui/copilot/audio_recorder.py:92-114` · `copilot_panel.py:303-311,352-403,405-421,435-473,679-698` · `chat_input.py:203-208`
**What:** Empty-buffer stop returns None without `audio_ready` → mic stuck on "processing" with no error; `_on_recorder_error` resets visuals but not `_voice_state` → wake-word guard (`!= VOICE_IDLE`) never re-arms; mic button not disabled during processing and `ask_about_element` bypasses the lock → two in-flight turns race on shared `_conversation_id`, answers land under wrong bubbles.
**Fix:** Emit empty-capture signal; reset state in error paths; disable mic + guard `ask_about_element` while processing; stamp per-turn sequence.

### SW-32 · Rich-text injection into chat bubbles (desktop Qt AutoText + mobile), raw server error strings leak to UI
**Confidence:** High (path) · **Source:** LLM F-13, clients M6/L3
**Where:** `ui/copilot/widgets/chat_bubble.py:105` (default `Qt.AutoText`), `copilot_panel.py:518-524,591-592` · `copilot_panel.py:486-501` (raw `str(exc)` as translation key → internal detail displayed) · `chat.py:49-50,87-88` (prompt-only "no markdown" constraint)
**What:** LLM output and tool errors render as HTML in QLabel (`<img src=file://...>` etc.); 500 `detail: str(exc)` reaches end users when untranslated.
**Fix:** `Qt.PlainText`/escape; map known message_keys, never fall back to raw 5xx text.

---

## MEDIUM

### SW-33 · Pause during confirm-execution strands the plan (removed from store mid-run; resume 404s; remaining steps never run)
**Confidence:** High · **Source:** pipeline F-07 · `copilot_router.py:711-716,734`, `executor.py:838-840`

### SW-34 · Undo is neither idempotent nor journaled: repeat undo re-applies stale snapshot (erases newer data); undo actions never audited
**Confidence:** High · **Source:** pipeline F-09 · `copilot_router.py:897-957`, `dispatch_tools.py:232-306`

### SW-35 · Undo tokens are unauthenticated, company-unbound, non-expiring (`system.undo` + dispatch tokens); restore path unscoped with `user_id=0`
**Confidence:** Medium (mitigated today by broken route + no role holding the permission) · **Source:** tools F-11 · `undo_tools.py:22-65`, `dispatch_tools.py:242-276`

### SW-36 · Prompt-injection tests cover dead code: `sanitizer.py` exercised only by tests; live pipeline blocking untested; tool-result injection vector untested
**Confidence:** High · **Source:** pipeline F-12, LLM F-05 · `tests/copilot/test_prompt_injection.py`

### SW-37 · `OcrAIProvider` leaks `httpx.AsyncClient` per call (no aclose; `_close_client` has zero callers; concurrent attr race)
**Confidence:** High · **Source:** LLM F-07 · `ocr_ai_provider.py:80-101,138`

### SW-38 · `GoogleProvider` uses sync genai SDK in async handlers — blocks the event loop up to 30s per call
**Confidence:** High · **Source:** LLM F-08 · `google_provider.py:265,343,368,382`

### SW-39 · DB-stored Gemini key is dead configuration (`get_ai_api_key("gemini", None)` never reads prefs); ERROR-level log noise per client construction
**Confidence:** High · **Source:** LLM F-09 · `google_provider.py:77`, `chat.py:130-136`

### SW-40 · Routing module is dead code: hardcoded `("self_hosted", "google")` chain; data-sensitivity routing advertised but never consulted; no health-check failover
**Confidence:** High · **Source:** LLM F-06 · `routing.py:32-52`, `base.py:80`, `chat.py:235,314`

### SW-41 · 90s tool-loop budget not enforced (checked only between iterations; synthesis adds +30s; tool execution unbounded; worst case ≈150s)
**Confidence:** High · **Source:** LLM F-10 · `tool_calling.py:47-51,694-723,731-737`

### SW-42 · `attempted=True` mislabels "no provider" as `model_unreachable` after reload flip; final-synthesis failure surfaces apology instead of `provider_failed`
**Confidence:** High · **Source:** LLM F-12/F-15 · `chat.py:316-329`, `tool_calling.py:725-726,872-876`

### SW-43 · Gemini schema sanitizer silently drops unknown keys (SDK-version drift) and loses exclusive bounds when a sibling inclusive bound exists (`gt`→`ge`)
**Confidence:** High · **Source:** LLM F-14 · `google_provider.py:202-215,224-225`

### SW-44 · `world_model.get_slice()` mutates shared `db.user_company_id` without restore — stale-tenant leak for legacy readers
**Confidence:** Medium · **Source:** tools F-13 · `world_model.py:156-157`

### SW-45 · `route.delete` reports success for nonexistent routes; unscoped soft-discard + hard-delete fallback that ignores rowcount
**Confidence:** High · **Source:** tools F-07 · `delete_tools.py:526-574`, `route_history_service.py:220-224`

### SW-46 · `invoice.finalize` dead `confirm` flag (never read); `automail.schedule_reminder` sends real external email at Level 2 with unscoped recipient resolution (cross-tenant email)
**Confidence:** High · **Source:** tools F-10 · `invoice_tools.py:47-49,308-317`, `automail_tools.py:44,87,91-134`

### SW-47 · WhatsApp success-parse crash-after-send (index `[0]` assumption → duplicate messages); freight tool ids interpolated into provider URLs without validation (path injection)
**Confidence:** Medium · **Source:** tools F-12 · `whatsapp_tools.py:93`, `freight_tools.py:1095-1103,1168-1186`

### SW-48 · Tools with no `required_permission` are executable by every role (default-open); Celery path never re-checks permission
**Confidence:** High · **Source:** API F-16 · `context.py:200-206`, `executor.py:117-118`, `copilot_tool_tasks.py:216-227`

### SW-49 · Reasoning-graph upsert broken on PostgreSQL (`graph_json` column doesn't exist; NOT NULL `root_node_id`/`graph` unwritten) — silently never persisted
**Confidence:** High (path) · **Source:** API F-18 · `alembic/versions/f6a7b8c9d0e6...` vs `copilot_repository.py:282-288`

### SW-50 · Monthly quota is non-atomic RMW (get→set, no INCR; TOCTOU in check) — hard cap overrun under concurrency; fails open on cache errors
**Confidence:** High · **Source:** pipeline F-17, API F-07 · `tier_gate.py:161-207`

### SW-51 · WS auth token in query string (log/history exposure); no Origin validation
**Confidence:** Medium · **Source:** API F-22 · `copilot_router.py:1457-1479`

### SW-52 · Kill-switch 2s memo skips per-company check on fresh platform memo; per-worker staleness
**Confidence:** High · **Source:** API F-21 · `copilot_router.py:152-161`

### SW-53 · `maintenance_forecast_job` missing `set_company_context` (sibling jobs set it) — wrong/missed insights
**Confidence:** High · **Source:** API F-20 · `insight_tasks.py:61-77`

### SW-54 · Insight dedup unique index exists only in db_manager extra DDL, not in the Alembic migration — duplicates on migration-only PG deployments
**Confidence:** Low-Medium · **Source:** API F-19 · `alembic/versions/a7b8c9d0e1f7...` vs `db_manager.py:668-680`

### SW-55 · Mobile confirm failure destroys plan state (no retry without re-utterance); typed phrase never sent to server (no body model) — Level-3 gate is a UI illusion; no cancel on dispose
**Confidence:** High · **Source:** clients M3 · `copilot_providers.dart:130-155`, `copilot_endpoints.dart:79-94`

### SW-56 · Mobile notification bridge never activated (`startListening` never called); IDs reset per session; no tap deep-linking
**Confidence:** High · **Source:** clients M7 · `copilot_notification_providers.dart:31-56`

---

## LOW

### SW-57 · Confirm endpoint hardcodes `status: "completed"` regardless of outcome (failed/skipped/paused plans report success)
**Source:** pipeline F-15 · `copilot_router.py:736-749`

### SW-58 · Audit double rows per step (two inserts); abandonment metric permanently 0 (no writer for `tool_execution_start`); `log_action` company_id from contextvar can be 0/stale outside request context
**Source:** pipeline F-14 · `audit.py:126-198`, `copilot_router.py:1088-1133`

### SW-59 · Undo window: NULL `started_at` (Celery terminal rows) bypasses the check; boundary is strict `>` (undo at exactly 30:00 allowed)
**Source:** pipeline F-16 · `copilot_router.py:927`, `executor.py:89-90`

### SW-60 · Optional-entity resolution asymmetry: deterministic pre-pass and offline fallback behave differently for the same utterance
**Source:** pipeline F-18 · `planner.py:744-769` vs `851-895`

### SW-61 · Guardrail/circuit-breaker skip paths bypass `_finalize_step` — no `finished_at`, no WS push, no audit rows (timeline stalls)
**Source:** pipeline F-19 · `executor.py:571-588`

### SW-62 · All plan-mutation endpoints scope by company only, never by user — any same-tenant user can confirm/cancel/undo a colleague's plan
**Source:** pipeline F-11 · `copilot_router.py:48-57,538-749,897-957`

### SW-63 · `assert`-based param casts stripped under `python -O` → AttributeError crashes instead of clean validation
**Source:** tools F-14 · all CRUD/delete tools `_assert_params`

### SW-64 · `vehicle.search` silently ignores `status`/`fuel_type` filters (LLM reasons over unfiltered data)
**Source:** tools F-15 · `vehicle_tools.py:18-23,60-65`

### SW-65 · Unvalidated maintenance `date` string written to DB (corrupts date-based analytics)
**Source:** tools F-16 · `maintenance_tools.py:249-269,378`

### SW-66 · Non-atomic Redis append for conversation turns (last-write-wins, truncated memory history)
**Source:** pipeline F-17 · `context.py:136-144`

### SW-67 · Mobile clarification bar creates `TextEditingController` in `build` (input lost on rebuild, leak)
**Source:** clients L1 · `copilot_screen.dart:291`

### SW-68 · Mobile input stays enabled during confirmation/execution — new message orphans the pending plan
**Source:** clients L2 · `copilot_screen.dart:146-150`, `copilot_providers.dart:97-110`

### SW-69 · PTT re-press during in-flight voice turn desyncs state machine (overlapping turns, wrong conversation context)
**Source:** clients L4 · `copilot_panel.dart:352-373`

---

## Highest-risk areas needing runtime verification

1. **PostgreSQL write path of all copilot tables** — SW-08/SW-49 integrity errors are schema-vs-repo inferences; run the copilot suite against Postgres (`tests/test_postgresql_compat.py` only lists tables).
2. **Gemini role-alternation rejection (SW-16)** — depends on installed google-genai SDK behavior; test against live API with pinned SDK.
3. **Duplicate-execution interleavings (SW-09)** — needs chaos/integration test with an instrumented executor (timeout between server execution and response).
4. **Tenant isolation blast radius (SW-01)** — verify each of the ~25 unscoped tools against a two-company fixture DB; the repositories follow the context pattern, but service-layer behavior on missing context needs repro.
5. **Kill-switch Redis topology** — single shared instance for API workers + Celery? Reconnect behavior of `RedisCache` after outage.
6. **Multi-worker deployment** — in-memory plan store breaks confirm/pause/resume across workers (SW-20).
7. **Desktop local-mode SQLite thread safety** — planner runs on Qt worker thread against main-thread connection.
8. **XFF trust boundary** — whether a trusted proxy strips client-supplied `X-Forwarded-For` (SW-25).

---

## Recommended remediation order

1. **Tenant isolation closure (SW-01, SW-02, SW-03, SW-06, SW-07, SW-11)** — security-critical, single-line-per-site fixes in most cases.
2. **Confirmation/undo integrity (SW-04, SW-05, SW-08, SW-09, SW-55)** — the human-in-the-loop contract is currently non-functional end-to-end.
3. **PG compatibility (SW-08b, SW-49, SW-54, SW-22)** — audit/observability/retention silently dead on the production database engine.
4. **Prompt-injection hardening (SW-13, SW-36)** — validate `language`, neutralize tool results, wire the sanitizer.
5. **LLM layer reliability (SW-15, SW-16, SW-37, SW-38, SW-41)** — provider reachability and event-loop health.
6. **Client parity (SW-05, SW-27, SW-28, SW-29, SW-31)** — then re-run `test_desktop_mobile_parity.py` after fixing the wire contract it currently pins to the buggy shape.
7. **Cost/abuse (SW-24, SW-25, SW-50)** — quotas and rate limits.