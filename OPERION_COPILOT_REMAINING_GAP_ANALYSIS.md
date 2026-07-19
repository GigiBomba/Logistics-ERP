# Operion AI Co-Pilot — Remaining Gap Analysis & Implementation Phases

## Blueprint Version: V4 (1589 lines) — Updated
## Current Status: 67 tools, ~780 tests, Phases 0-4 "done" against old blueprint

---

## GAP ANALYSIS: IMPLEMENTED vs BLUEPRINT

### ✅ Fully Implemented (67 tools, all phases 0-4 core)

| Area | Status |
|---|---|
| Data contracts (schemas.py §4, §5.2, §8) | ✅ All models |
| BaseTool interface + registry (§9) | ✅ 67 registered tools |
| LLM Provider interface + GoogleProvider (§23.2) | ✅ Interface + 1 provider |
| Phase 1 — Level 0 tools (14 SAFE) | ✅ All 14 |
| Phase 2 — Level 1-2 tools (16 INFO + 18 BUS) | ✅ Mostly (see gaps) |
| Phase 3 — Level 3 tools (9 DESTRUCTIVE) | ✅ 8 implemented, 1 from Phase 2 |
| Phase 4 — World Model (§6) | ✅ Service class built |
| Phase 4 — Freight tools (§17) | ✅ 9 tools |
| Phase 4 — Insight jobs (§18) | ✅ 3 jobs + migration |
| Phase 5 — Circuit breaker (§23.1) | ✅ Wired to executor |
| Phase 5 — Human handoff (§23.7) | ✅ Complete |
| Phase 5 — Data retention (§24) | ✅ 2 Celery tasks |
| Phase 5 — Golden regression suite (§23.4) | ✅ 10 scenarios |
| Test infrastructure | ~780 tests |

---

### 🟡 PARTIALLY Implemented

| Area | What's Missing | Blueprint § |
|---|---|---|
| Voice pipeline | **NEVER BUILT** — STT/TTS/wake word models, voice API, mic capture all absent. Only interface stubs exist. Blueprint moved voice to Phase 2 per item 4: "Voice pipeline (§3), full build-out, on both clients" | §3, §21 Phase 2 item 4 |
| Kill switch (§26) | Stub only — no Redis connection, no plan cancellation, no toggle mechanism | §26 |
| Cost guardrails (§23.3) | MAX_TOOL_CALLS enforced but MAX_REASONING_GRAPH_NODES and MAX_LLM_TOKENS_PER_TURN are dead constants | §23.3 |
| `execute_with_fallback()` | Defined but NEVER CALLED anywhere — dead code | §23.5 |
| Circuit breaker (§23.1) | `check_circuit_breaker_and_block()` is dead code; `_states` dict not thread-safe; no audit log trip event | §23.1 |
| Insight jobs (§18) | Only 3 of 6 specified jobs implemented — missing `fuel_cost_trend_job`, `return_load_matcher_job`, `driver_hours_forecast_job` | §18 |
| Autonomous Mode (§23.1) | Pre-approved workflow execution, per-workflow opt-in, autonomous execution path — NOT BUILT | §21 Phase 4 item 4 |
| `payment.generate_bulk_csv` | Tool NOT CREATED — missing from tool inventory | §9.1 |
| `correlation_id` tracing | Not implemented — needed for per-phase latency tracking | §23.6 |
| i18n across all 22 languages | Keys only in en.json/ro.json — the other 20 language files are empty for copilot.* namespace | §20 |

---

### ❌ NOT Implemented (Major gaps)

| Category | What's Missing | Blueprint § |
|---|---|---|
| **NEW SECTION: §32 Flutter Mobile Client** | Entire mobile app — Bloc state, Dio client, offline cache, voice mode, push notifications, confirmation UX, all mobile tests | §32 (entirely new) |
| **NEW SECTION: §30 Full API Surface** | POST /copilot/voice, GET /copilot/conversations, GET /copilot/conversations/{id}, POST /copilot/plans/{id}/undo, GET /copilot/insights | §30 |
| **NEW API endpoints (9 missing)** | Voice input, conversation history (list+detail), plan undo, insights queue | §30 |
| **Voice pipeline** | 3 engine integrations: STT (faster-whisper), TTS (piper-tts), wake word. 4 voice mode states UI. Mic capture on desktop. Voice API. | §3.2-§3.5 |
| **Observability panel (§23.6)** | Dev toolkit panel, per-phase latency tracking, LLM provider health dashboard, alerting thresholds | §23.6 |
| **Technical tracing** | Correlation IDs across all pipeline phases, structured metrics per phase | §23.6 |
| **Application logging (§29)** | Structured logging, PII exclusion rules, log level enforcement, retention | §29 |
| **Error handling taxonomy (§28)** | test_error_taxonomy.py, per-category test fixtures | §28 |
| **All Security tests (§15)** | test_authentication.py (JWT rejection, cross-company isolation), permission mid-session revocation test | §15 |
| **Freshness validation test** | test_freshness_validation.py — §7 pre-execution re-check | §7 |
| **Tool versioning test** | test_tool_versioning.py — §9.2 deprecation behavior | §9.2 |
| **Audit completeness test** | test_copilot_audit_completeness.py — §14 crash reconciliation | §14 |
| **GDPR erasure test** | test_copilot_erasure.py — §24 anonymization proof | §24 |
| **All reasoning graph tests** | test_reasoning_graph.py (§5.4) and test_reasoning_graph_persistence.py (§5.5) — only basic round-trip exists | §27.1 |
| **World Model accuracy test** | test_world_model.py — real data accuracy against fixture DB | §6 |
| **Observability tracing test** | test_observability_tracing.py — conversation_id trace reconstructability | §23.6 |
| **Error taxonomy test** | test_error_taxonomy.py — all 7 categories | §28 |
| **Application logging test** | test_application_logging.py — structured fields, PII scan | §29 |

---

## PROPOSED NEW PHASES

### Phase 5 — Voice Pipeline & API Surface Completion

**Goal:** Deliver the voice pipeline (moved from Phase 2 in the updated blueprint) and complete the missing API endpoints.

| Item | Effort | Depends On |
|---|---|---|
| 5.1 | **STT engine integration** — Add faster-whisper/CTranslate2 dependency, create `WhisperSTTProvider` | — |
| 5.2 | **TTS engine integration** — Add piper-tts dependency, create `PiperTTSProvider` | — |
| 5.3 | **Voice API endpoint** — POST /copilot/voice (§30), wire through same pipeline as /chat | 5.1, 5.2 |
| 5.4 | **Voice mode states** — 4-state widget (Idle/Listening/Processing/Responding) in PySide6 desktop (§3.5) | 5.1 |
| 5.5 | **Desktop mic capture** — Audio capture via sounddevice/pyaudio in CoPilotPanel | 5.4 |
| 5.6 | **Voice language tier population** — Test STT/TTS models against all 22 languages, populate VOICE_LANGUAGE_TIER | 5.1, 5.2 |
| 5.7 | **Wake word engine** — Enterprise-tier continuous listening with Porcupine/OpenWakeWord | — |
| 5.8 | **payment.generate_bulk_csv tool** — Level 1 tool wrapping payment_export_service.generate_batch() | — |
| 5.9 | **Conversation history API** — GET /copilot/conversations, GET /copilot/conversations/{id} (§11, §30) | — |
| 5.10 | **Plan undo API** — POST /copilot/plans/{id}/undo (§30) | — |
| 5.11 | **Insights queue API** — GET /copilot/insights for review queue (§30) | — |
| 5.12 | **Voice tests** — test_voice_language_tiers.py, test_voice_mode_states.py (§3.4, §3.5) | 5.1-5.4 |

**Gate:** All voice tests green, POST /voice returns CoPilotResponse, conversation history returns correct data.

---

### Phase 6 — Hardening, Observability & Compliance

**Goal:** Ship the production hardening specified in §§23-29 with full test coverage.

| Item | Effort | Depends On |
|---|---|---|
| 6.1 | **Kill switch (Redis)** — Wire `_check_kill_switch()` to Redis boolean per-company + platform-wide, cancel in-flight plans | — |
| 6.2 | **Cost guardrails enforcement** — Wire MAX_REASONING_GRAPH_NODES and MAX_LLM_TOKENS_PER_TURN into executor, add graceful clarification on hit | Phase 5 |
| 6.3 | **Tool-level timeouts** — Add timeout/result-cap for fan-out tools (freight, health_score) | — |
| 6.4 | **execute_with_fallback wiring** — Actually CALL it from the planner's LLM provider invocations | — |
| 6.5 | **Circuit breaker audit logging** — Write trip events to copilot_audit_log | — |
| 6.6 | **Correlation ID propagation** — Thread conversation_id through every log line, LLM call, and tool execution (§23.6) | — |
| 6.7 | **Per-phase latency tracking** — Emit timing for REASONING/EXECUTE/LLM phases as structured metrics (§23.6) | 6.6 |
| 6.8 | **Observability panel** — Dev toolkit panel with confidence distribution, abandonment rate, tool failure rate, CB trips (§23.6) | 6.7 |
| 6.9 | **Application logging (§29)** — Structured log format, PII exclusion per log level, log level enforcement | — |
| 6.10 | **Additional insight jobs** — fuel_cost_trend_job, return_load_matcher_job, driver_hours_forecast_job | — |
| 6.11 | **Autonomous Mode** — Pre-approved workflow table, per-workflow opt-in, autonomous execution path in executor | Phase 5 |
| 6.12 | **Tests** — test_authentication.py, test_freshness_validation.py, test_tool_versioning.py, test_copilot_audit_completeness.py, test_copilot_erasure.py, test_error_taxonomy.py, test_application_logging.py, test_observability_tracing.py, test_reasoning_graph.py, test_reasoning_graph_persistence.py, test_world_model.py | All above |

**Gate:** All above test files green in CI, kill switch functional, observability panel renders.

---

### Phase 7 — Mobile Client (Flutter)

**Goal:** Build the Flutter mobile Co-Pilot client matching desktop parity.

| Item | Effort | Depends On |
|---|---|---|
| 7.1 | **Bloc/Riverpod state** — CopilotState sealed class mirroring backend state machine (§32.1) | — |
| 7.2 | **Dio API client** — CopilotApiClient with JWT, CancelToken, retry/backoff (§32.2) | Phase 5 |
| 7.3 | **Chat screen UI** — CopilotScreen/Sheet widget rendering timeline, input, voice button | 7.1, 7.2 |
| 7.4 | **WebSocket stream** — Dart Stream wrapping WSS timeline updates | 7.2 |
| 7.5 | **Offline caching** — Isar/Hive cache for conversation history, read-only results (§32.3) | 7.1 |
| 7.6 | **Mobile voice mode** — Push-to-talk + foreground wake word, mic permission flow, audio capture (§32.4) | Phase 5 |
| 7.7 | **Mobile confirmation UX** — Bottom sheet with typed confirmation for Level 3 (§32.6) | 7.1 |
| 7.8 | **Push notifications** — Event subscriptions for background task completion, insights, CB trips (§32.5) | Phase 6 |
| 7.9 | **Mobile tests** — test_state_parity.dart, test_offline_cache_boundaries.dart, test_voice_background_behavior.dart, test_dio_retry_policy.dart | All above |

**Gate:** All mobile tests pass, Flutter app renders same CoPilotResponse as desktop, voice mode works with foreground wake word.

---

## Effort Summary

| Phase | Focus | Estimated Agent-Days | Key Deliverables |
|---|---|---|---|
| **Phase 5** | Voice Pipeline + API Surface | 15-22 | STT/TTS/wake word engines, voice API, conversation history, voice tests |
| **Phase 6** | Hardening + Observability | 12-18 | Kill switch, guardrails, observability panel, 11 new test files |
| **Phase 7** | Flutter Mobile Client | 18-28 | Full mobile Co-Pilot + all mobile tests |
| **Total Remaining** | | **45-68** | |

---

## Critical Note: Blueprint Changed

The updated blueprint (V4, 1589 lines) contains **major structural changes** from the original (2768 lines):

1. **Voice moved to Phase 2** (was Phase 4) — §21 Phase 2 item 4 explicitly says "Voice pipeline (§3), full build-out, on both clients — not deferred to Phase 4"
2. **New §32 — Flutter Mobile Client** — Entirely new section, 90 lines of specification
3. **New §28 — Error Handling Taxonomy** — 7 error categories with retry policies
4. **New §29 — Application Logging** — Structured logging with strict PII rules
5. **New §15 — Authentication** — Formalized JWT auth rules for the Co-Pilot
6. **Expanded §30 — API Surface** — 11 endpoints (we have ~5)
7. **Expanded §27 — Tests** — 18 test files specified (we have ~20 but ~8 are missing/placeholder)
8. **`voice_activation_mobile`** — New tier feature key in TIER_FEATURES
9. **3 new insight jobs** — fuel_cost_trend, return_load_matcher, driver_hours_forecast
