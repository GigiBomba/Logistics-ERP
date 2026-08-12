# Operion Waitlist System — Implementation Blueprint V1

**Target:** operionerp.xyz (Vite + React + TypeScript SPA, Cloudflare Pages, consuming shared FastAPI backend, PostgreSQL)
**Owner:** Cargo Dyvagri SRL
**Consumers of this document:** AI coding assistants (DeepSeek V4 Pro, Kimi, OpenCode, Claude) executing as junior engineers. Each phase below is a self-contained prompt. Do not proceed to the next phase until the verification gate for the current phase passes.

**North star metric:** Waitlist → Trial Activation Rate. Every implementation decision that trades off "more data collected" against "more friction" must resolve in favor of less friction. If a coding AI proposes adding a required field, a CAPTCHA before submit, or a multi-step form "for better lead quality," reject it — that is optimizing the wrong metric.

---

## 0. Architectural Principles (read before writing any code)

1. **Multi-tenant safety does not apply here** — the waitlist is a single-tenant, pre-launch marketing capture system. It must NOT reuse the `company_id`-scoped models or middleware from the core ERP schema. Keep it in its own schema/module (`waitlist`) so it can never accidentally cross-contaminate ERP tenant data, and so it can be deleted/archived post-launch without touching ERP tables.
2. **Public write endpoint = highest abuse surface on the whole site.** The signup endpoint is unauthenticated and internet-facing. Treat it with the same suspicion as a login endpoint: rate limiting, honeypot field, and email format + MX validation are mandatory, not optional polish.
3. **Provider-agnostic email**, same principle as the Co-Pilot LLM layer: the email-sending code must sit behind an `EmailProvider` interface, not call Resend's SDK directly from business logic. Swapping to Postmark/SendGrid later must be a one-file change.
4. **Referral fields exist in the schema from day one, unused.** Do not build referral logic in V1. Do build the columns, so no migration/backfill is needed when it ships later.
5. **Admin dashboard is internal-only.** It must sit behind the same auth system as the rest of Operion's admin/staff tooling (JWT + role check), never behind a public route, never behind a "secret URL."

---

## 1. Database Model

Table: `waitlist_entries` (own schema/module, not part of ERP tenant tables)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `company_name` | varchar(200), NOT NULL | required |
| `contact_name` | varchar(150), NULL | optional |
| `email` | varchar(320), NOT NULL, UNIQUE (case-insensitive) | required; unique constraint on `lower(email)` |
| `fleet_size` | enum: `1-5`, `6-20`, `21-50`, `51-200`, `200+`, NULL | optional |
| `company_size` | enum: `solo`, `2-10`, `11-50`, `51-200`, `200+`, NULL | optional |
| `country` | varchar(2), NULL | ISO 3166-1 alpha-2, optional |
| `source` | varchar(100), NOT NULL, default `'landing_page'` | e.g. `route_calculator`, `profit_calculator`, `blog:<slug>`, `landing_page` |
| `referral_code` | varchar(20), UNIQUE, NULL | this entry's own shareable code — generate on insert even though unused in V1 |
| `referred_by` | varchar(20), NULL, FK-like ref to another entry's `referral_code` (no hard FK to avoid delete-order issues) | NULL in V1 usage |
| `status` | enum: `joined`, `invited`, `activated`, `converted`, `churned`, `unsubscribed` | replaces separate booleans — a single state machine is easier to report on and impossible to get into a contradictory state (e.g. converted but not activated) |
| `joined_at` | timestamptz, NOT NULL, default now() | |
| `invited_at` | timestamptz, NULL | |
| `activated_at` | timestamptz, NULL | |
| `converted_at` | timestamptz, NULL | |
| `notes` | text, NULL | internal admin notes |
| `ip_hash` | varchar(64), NULL | SHA-256 of submitting IP, salted — for abuse detection, never store raw IP |
| `user_agent` | varchar(300), NULL | abuse detection only |
| `unsubscribed_at` | timestamptz, NULL | |

Indexes: unique on `lower(email)`, index on `status`, index on `joined_at`, index on `source`, unique on `referral_code`.

**Verification gate (schema):**
- [ ] Migration applies cleanly on a fresh DB and on top of the existing ERP DB without touching any `company_id`-scoped table.
- [ ] Duplicate email submission (different case, e.g. `Foo@x.com` vs `foo@x.com`) is rejected at the DB level, not just app level.
- [ ] `referral_code` is generated and unique for every row, confirmed with a 1,000-row bulk-insert test with no collisions.

---

## 2. Backend API (FastAPI)

Base path: `/api/waitlist`

### 2.1 `POST /api/waitlist/join` (public)

Request body:
```json
{
  "company_name": "string, required, 2-200 chars",
  "email": "string, required, valid email format",
  "contact_name": "string, optional",
  "company_size": "enum, optional",
  "country": "string, optional, ISO alpha-2",
  "fleet_size": "enum, optional",
  "source": "string, optional, default landing_page",
  "hp_field": "string, MUST be empty (honeypot, not shown in UI, hidden via CSS not `display:none` since some bots skip that check)"
}
```

Behavior:
- Reject if `hp_field` is non-empty — return HTTP 200 with a fake success payload (never tell a bot it was caught).
- Reject if email fails RFC-ish format check.
- Reject with a friendly, specific message (not a generic 500) if email already exists: `"You're already on the list — check your inbox for updates."` — do NOT silently create a duplicate, and do NOT leak whether the account exists via timing differences beyond what's unavoidable.
- Rate limit: max 5 submissions per IP per 10 minutes (use existing rate-limit middleware if the ERP backend has one; otherwise implement with Redis or an in-memory sliding window if Redis isn't already provisioned — confirm which before building).
- On success: insert row, generate `referral_code`, enqueue Email 1 (Welcome) send, return `{ "status": "joined", "referral_code": "..." }`.
- Must respond in under 300ms server-side (excluding email send, which is async/queued, never inline/blocking).

### 2.2 `GET /api/waitlist/admin/entries` (auth required, staff role)

Query params: `search` (matches company_name/email/contact_name), `status`, `country`, `company_size`, `fleet_size`, `source`, `date_from`, `date_to`, `page`, `page_size` (default 50, max 200).

Returns paginated list + total count + aggregate counts by status.

### 2.3 `PATCH /api/waitlist/admin/entries/{id}` (auth required, staff role)

Body: any subset of `{ status, notes }`. Updating `status` to `invited`/`activated`/`converted` auto-stamps the corresponding `*_at` timestamp server-side (never trust a client-supplied timestamp for these).

Status transitions must be validated against an explicit state machine:
`joined → invited → activated → converted`, with `unsubscribed`/`churned` reachable from any state. Reject invalid transitions (e.g. `joined → converted` skipping intermediate states) with a 400 and a clear error — but allow an explicit admin override flag if you genuinely need to backfill/correct data.

### 2.4 `DELETE /api/waitlist/admin/entries/{id}` (auth required, staff role)

Hard delete. Log the action (who, when, which row) to the existing admin audit log if one exists in the ERP backend; if it doesn't exist yet, flag this back to Gigi rather than silently skipping the audit trail.

### 2.5 `GET /api/waitlist/admin/export.csv` (auth required, staff role)

Same filters as 2.2, streams CSV (don't materialize the whole file in memory if the table could exceed a few thousand rows — use a streaming response).

### 2.6 `GET /api/waitlist/admin/stats` (auth required, staff role)

Returns:
```json
{
  "total": 0,
  "by_status": {"joined": 0, "invited": 0, "activated": 0, "converted": 0},
  "by_country": {"RO": 0, "...": 0},
  "by_company_size": {},
  "by_fleet_size": {},
  "by_source": {},
  "growth_daily": [{"date": "2026-07-01", "count": 0}],
  "conversion_rate": 0.0
}
```

**Verification gate (backend):**
- [ ] Submitting the same email twice returns a friendly 4xx, not a 500 from a broken unique-constraint violation.
- [ ] 6th submission from the same IP within 10 minutes is rejected with 429.
- [ ] Honeypot-triggered submissions never appear in `waitlist_entries`, confirmed by inspecting the DB after a scripted honeypot-filled request.
- [ ] `PATCH` with an invalid status transition (e.g. `joined` → `converted` directly, no override flag) returns 400.
- [ ] CSV export tested against 10,000+ synthetic rows without memory spike (streamed, not loaded fully).
- [ ] All four admin endpoints reject unauthenticated requests with 401 and non-staff authenticated requests with 403 — write an explicit test for both, don't just eyeball it.

---

## 3. Email Sequence (provider-agnostic)

Build an `EmailProvider` abstract interface with methods `send(to, template_id, variables)`. Implement `ResendProvider` first (or your chosen provider — confirm before building). All four emails below are templates driven by this interface; never hardcode a provider SDK call inside the sequence logic.

| # | Trigger | Timing | Content |
|---|---|---|---|
| 1 — Welcome | On `POST /join` success | Immediate | Thanks, benefits list, rough roadmap, target launch window |
| 2 — Progress update | Manual/scheduled admin trigger | Ad hoc, pre-launch | Co-Pilot preview, new features, screenshots |
| 3 — Launch approaching | Manual trigger | ~1-2 weeks pre-launch | What to prepare, migration guide, what happens on launch day |
| 4 — Launch day | Manual trigger (batch send to all `joined`/`invited` status entries) | Launch day | Download link, license activation, getting-started guide, support links |

Emails 2-4 are **admin-triggered batch sends**, not automated drip timers — you don't know the launch date precisely enough yet to schedule Email 3/4 on a timer. Build the admin dashboard (Section 4) with a "Send campaign to segment" action rather than a cron-based drip system. This avoids building complex scheduling infrastructure for a one-time launch event.

Every email must include an unsubscribe link that hits a public, unauthenticated endpoint (`GET /api/waitlist/unsubscribe/{token}`) that sets `status = unsubscribed` — required for deliverability and (if targeting EU/Romania) legally required regardless of company size.

**Verification gate (email):**
- [ ] Sending Email 1 is triggered by the join endpoint and confirmed via provider dashboard/logs, not just "the code compiles."
- [ ] Swapping `ResendProvider` for a dummy `LoggingEmailProvider` (writes to console/DB instead of sending) requires changing exactly one dependency-injection line, no changes to endpoint code — this is the actual test of "provider-agnostic," not a comment saying so.
- [ ] Unsubscribe link works and is idempotent (clicking twice doesn't error).

---

## 4. Admin Dashboard (React, part of existing Operion admin surface if one exists — confirm with Gigi where this should live; otherwise a new protected route in the operionerp.xyz SPA)

Views:
1. **Overview** — total signups, growth chart (daily, last 90 days), conversion funnel (joined → invited → activated → converted) as a funnel/bar visualization, breakdown by country/company size/fleet size/source.
2. **Entries table** — search, filters (status, country, size, source, date range), pagination, per-row actions: mark invited/activated/converted, delete (with confirm dialog), edit notes.
3. **Export** — CSV export respecting current filters.
4. **Campaign send** (Section 3) — pick a segment (by status/filters), pick a template (2/3/4), preview, send. Show a confirmation step before actually sending to N recipients — this is a real send-email-to-real-people action, treat it with the same care as any destructive/irreversible action in the ERP itself.

**Verification gate (admin dashboard):**
- [ ] Logging in as a non-staff user cannot reach this route at all (redirect, not just a hidden button).
- [ ] Deleting an entry requires an explicit confirm step.
- [ ] Campaign send shows recipient count and requires confirmation before firing.

---

## 5. Landing Page (Vite/React/TS, Cloudflare Pages)

Follow the flow already established in `operion_website_specification.md`. Waitlist-specific requirements:

### 5.1 Form
Fields: `company_name` (required), `email` (required), and a "More details (optional, helps us prioritize your onboarding)" progressive-disclosure section revealing `contact_name`, `company_size`, `country`, `fleet_size` — collapsed by default so the form *looks* like two fields. This gets you the optional data without it looking mandatory or adding visible friction. Submit must be reachable via Enter key, not just mouse click.

### 5.2 Success state
Do not show "Thanks." Show the explicit "what happens next" sequence from the spec (on the list → we'll keep building → occasional updates → on launch you get download + activation + free month + onboarding guide). This can be a simple 4-step visual (see widget note below), not a wall of text.

### 5.3 Contextual CTAs
Three placements, exact copy from the source spec (lightly editable, keep the tone):
- **Route Calculator**, after results render.
- **Profit Calculator**, after results render.
- **Blog article**, after the article body, before comments/footer.

Each CTA must carry a `source` value matching where it was triggered (`route_calculator`, `profit_calculator`, `blog:<slug>`) so the admin stats (Section 2.6/4.1) can actually show which surface drives signups — this is the whole point of tracking `source`, don't let it default to `landing_page` everywhere by accident.

### 5.4 No fake urgency
No countdowns, no fake "X spots left" counters. If a scarcity message is used, it must be the exact tone from the source spec: onboarding-quality framing, not artificial limits.

**Verification gate (frontend):**
- [ ] Submitting via keyboard-only (tab + enter), no mouse, works end to end.
- [ ] Each of the three contextual CTAs sends the correct `source` value — confirm by checking the network request payload, not just visually.
- [ ] Success state matches the "what happens next" sequence, not a generic thank-you.
- [ ] Full flow (land on page → fill form → submit → success state) completes in well under 30 seconds of user interaction time — time it yourself.
- [ ] Lighthouse/mobile check: form is usable on a 375px-wide viewport without horizontal scroll.

---

## 6. Success Metrics Wiring

Confirm before building: does Operion already have an analytics pipeline (e.g. Plausible, GA4, PostHog) on operionerp.xyz? If yes, wire these events into it rather than building a bespoke analytics table:
- `waitlist_view` (landing section seen)
- `waitlist_submit_attempt`
- `waitlist_submit_success` (with `source`)
- `waitlist_cta_click` (per surface)

The admin dashboard's own stats endpoint (2.6) covers signup/conversion-funnel metrics; visitor-level funnel metrics (visitors → view → submit) belong in the general analytics tool, not duplicated in the waitlist DB.

---

## 7. Explicit Non-Goals for V1 (do not build these yet)

- Referral link generation/sharing UI (schema only, per Section 1).
- Automated drip scheduling (Emails 2-4 are admin-triggered, per Section 3).
- A/B testing framework for CTA copy.
- Multi-language waitlist form (ship in whichever language the rest of the marketing site launches in first; `t()` i18n hookup can come later if the site itself is bilingual).

If a coding AI proposes scope beyond this list "since it's easy," reject it and flag it back — scope creep here delays the thing that actually needs to ship before launch.

---

## 8. Delivery Phases (execute and verify in order)

1. **Phase 1 — Schema + public join endpoint** (Sections 1, 2.1). Gate: all Section 1 + relevant Section 2 checks pass.
2. **Phase 2 — Admin API** (Sections 2.2–2.6). Gate: auth/authz checks pass, CSV export streams correctly.
3. **Phase 3 — Email provider abstraction + Welcome email** (Section 3, Email 1 only). Gate: provider-swap test passes.
4. **Phase 4 — Admin dashboard UI** (Section 4). Gate: non-staff access blocked, delete/send confirmations present.
5. **Phase 5 — Landing page integration** (Section 5). Gate: all frontend checks pass.
6. **Phase 6 — Campaign send UI + Emails 2-4 templates** (remaining Section 3 items). Gate: segment send with confirmation works against a test segment.

Do not let a coding AI mark a phase complete based on its own summary — require the actual verification gate evidence (test output, screenshot, or a described manual check) before moving to the next phase, same standard as the multi-tenant security fix.
