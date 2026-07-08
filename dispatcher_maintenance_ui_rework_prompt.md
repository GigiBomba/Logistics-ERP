# PROMPT: Dispatcher Board & Maintenance Panel — Visual Rework

## Context

`Panou Dispecerat` (tabs: Panou / Alerte / Planificare) and `Control Întreținere` currently render functionally but with almost no visual structure: KPI numbers float directly on the black background with no container, there's excessive unstyled empty space, empty/loading states are raw text, and filter controls use default OS styling instead of the app's dark/indigo theme. This prompt fixes structure and hierarchy — it does NOT change data logic, routes, or business rules unless explicitly noted in Step 6 (loading state bug).

Read `design_tokens.py` and the global QSS stylesheet before starting. Reuse existing tokens (colors, spacing, radius, font) — do not hardcode new hex values if an equivalent token already exists. If a token you need doesn't exist, add it to `design_tokens.py` rather than inlining it in a widget file.

All new/changed user-facing strings MUST go through `t()` backed by `ro.json` / `en.json`. Do not hardcode any Romanian or English string directly in a widget.

---

## STEP 1 — Build a reusable `StatCard` component

Currently stat values (Sanatate Medie, Due for Service, Overdue, Cost 30d, Total Cost, Plecari Astazi, Sosiri Astazi, Critic, Necesita Atentie, Total Active, Complet Alocate, Partial, Nealocate) render as bare label+number pairs with no container, inconsistent spacing, and no visual grouping.

Create `components/stat_card.py` (or equivalent existing components folder) with a `StatCard(QWidget)`:

- Background: `#1A1A24` (or nearest existing surface token, e.g. `TOKENS.surface_elevated`)
- Border: `1px solid rgba(255,255,255,0.08)`
- Border-radius: `12px`
- Padding: `16px 20px`
- Fixed min-height: `88px`
- Layout (vertical):
  - Label: `11px`, uppercase, letter-spacing `0.5px`, color `rgba(255,255,255,0.55)`, font-weight `500`
  - Value: `26px`, font-weight `700`, color `#FFFFFF` (Inter)
  - Optional trend/status dot: `8px` circle, colored per severity (`#22C55E` good / `#F59E0B` warning / `#EF4444` critical / `#6366F1` neutral-info), positioned top-right of the card via `QGridLayout` or absolute overlay
- Hover state: border brightens to `rgba(255,255,255,0.16)`, background `#1F1F2C` — use existing QSS hover pattern from buttons/cards elsewhere in the app for consistency

Replace every bare stat display across all 4 screens with this `StatCard`, arranged in a `QHBoxLayout` with `12px` spacing between cards, wrapping to a new row if the window is narrower than the sum of card min-widths (use a flow layout if one already exists in the codebase; otherwise a simple fixed 2-row breakpoint at a defined width is acceptable).

## STEP 1B — StatCard row flow/wrap behavior on wide monitors

On wide/ultrawide monitors, a row of 4-5 `StatCard`s sized to their content will either (a) leave a large empty gap on the right if using fixed widths, or (b) stretch each card individually into an ugly, over-wide card if using naive equal-stretch. Neither is acceptable. Implement the following:

- Each `StatCard` gets a `min-width: 200px` and `max-width: 320px` (not unbounded stretch)
- The row container distributes available width evenly among cards **up to their max-width**, then any leftover space beyond `sum(max-width) + gaps` is added as **outer margin/padding on the row container** (e.g. centering the whole card group), not stretched into individual cards
- Gap between cards stays fixed at `12px` regardless of window width — do not let the gap grow to fill space
- Wrap rule: if available width < `(min-width × card_count) + (gap × (card_count - 1))`, wrap to a second row rather than shrinking cards below `min-width`. Use a flow layout if one exists in the codebase; otherwise implement a simple width-check on resize that switches the row's `QHBoxLayout` to two rows of a `QGridLayout`
- On very wide monitors (window width > ~1600px) where 5 cards at max-width still leave significant leftover space, do NOT just center the group with dead space on both sides as the only fix — increase the row's horizontal padding/margins proportionally (e.g. row container gets `padding: 0 5%` at that breakpoint) so cards feel intentionally framed rather than small and adrift in the top-left. A simple approach: cap the row container's own `max-width` at `1400px` and center that container within the available window width.
- Test at three window widths minimum: ~1280px (should show cards near max-width, little dead space), ~1920px (should show the capped/centered container, not stretched cards), and a narrowed window ~900px (should wrap to two rows cleanly, no horizontal scrollbar)
- Apply this same flow/wrap rule to every `StatCard` row across all 4 screens (Panou status bar, Alerte's two stat rows, Control Întreținere's top 5 KPIs) — one shared row-container class, not per-screen reimplementation

Add to verification checklist: confirm via screenshot at 1280px, 1920px, and ~900px window widths that no StatCard row looks sparse/adrift or produces a horizontal scrollbar.

## STEP 2 — Fix the Panou tab status bar (Image 1)

Current: 5 thin colored line segments with tiny counts below, floating with no card wrapper, huge dead space beneath.

- Wrap the whole status-bar row in a single card container (same background/border/radius as `StatCard`, padding `20px`)
- Replace the thin line + label-below layout with 5 `StatCard` instances (reusing Step 1), one per status: Planificat / Incarcare / In Tranzit / Livrat / Anulat
- Each card's status dot color: Planificat `#6B7280` (grey), Incarcare `#F59E0B`, In Tranzit `#3B82F6`, Livrat `#22C55E`, Anulat `#6B7280` (or `#EF4444` if cancelled should read as negative — confirm with existing color convention in `design_tokens.py`)
- Keep the search input and filter checkboxes above it, but restyle checkboxes per Step 4
- Below the status card row, if `0 curse` (no results), render the shared `EmptyState` component from Step 5 instead of a blank canvas — do not leave a large dead area

## STEP 3 — Fix Alerte tab layout (Image 2)

Current: "Rezumatul Zilei" stats float bare; "Alerte Operationale" and "Curse Nealocate" are plain centered text with a huge surrounding void; "Sumar Alocari" stats also float bare.

- Wrap `Rezumatul Zilei` and `Sumar Alocari` stat rows using `StatCard` (Step 1), each section in its own titled card container (section title `14px`, font-weight `600`, color `#FFFFFF`, `12px` bottom margin before the card row)
- For `Alerte Operationale` and `Curse Nealocate`: when empty, use the shared `EmptyState` component (Step 5) instead of plain centered text — this replaces "Nicio alerta activa" / "Toate cursele sunt alocate" with a proper empty-state layout (icon + message), not just floating text
- Reduce excess vertical whitespace: each section container should size to content (`QSizePolicy.Preferred` vertically), not stretch to fill remaining window height unless it's the last section

## STEP 4 — Restyle filter controls (checkboxes, dropdowns, inputs)

Visible in Image 1 (Planned/Loading/In Transit/Delivered/Cancelled checkboxes) and Image 4 (Critical/Warning/Info checkboxes, Toate dropdown, Filter inputs):

- Checkboxes: `18px × 18px`, unchecked = `1px solid rgba(255,255,255,0.2)` border, `4px` radius, transparent fill; checked = background `#6366F1`, white checkmark, same radius. Remove default OS checkbox rendering via QSS.
- Text labels next to checkboxes: `13px`, color `rgba(255,255,255,0.75)`, `8px` left margin from checkbox
- Dropdown (`Toate`) and text filter inputs: height `36px`, background `#14141C`, border `1px solid rgba(255,255,255,0.1)`, border-radius `8px`, padding `0 12px`, focus state border `#6366F1`
- Apply this styling once as a shared QSS class/selector (e.g. `.filter-checkbox`, `.filter-input`) so it's reused across both screens instead of styled per-instance

## STEP 5 — Build a shared `EmptyState` component

Create `components/empty_state.py` — used wherever a list/section has no data (Planificare tab "Nicio cursa programata", Alerte sections, Panou "0 curse" state):

- Vertically and horizontally centered within its parent container (not the whole window)
- Icon: `48px`, muted color `rgba(255,255,255,0.25)`, contextual (calendar icon for scheduling, checkmark for "all good" states, alert icon for alerts)
- Primary message: `15px`, font-weight `500`, color `rgba(255,255,255,0.7)` — via `t()`
- Optional secondary hint line: `13px`, color `rgba(255,255,255,0.45)` — via `t()`
- Optional CTA button (e.g. "Adaugă cursă" on Planificare empty state) using existing primary button QSS style (`#6366F1` background)
- Max-width `320px`, so text doesn't stretch full window width on large monitors

Apply to Planificare tab's "Nicio cursa programata" (Image 3) with a calendar icon and a "Planifică o cursă" CTA button, and to the two Alerte empty sections from Step 3.

## STEP 6 — Fix stuck loading state on Control Întreținere (Image 4)

The 5 top KPI cards (Sanatate Medie, Due for Service, Overdue, Cost 30d, Total Cost) show a permanent `...` instead of resolving to real values.

1. Locate the data-fetch call feeding these 5 KPIs and add a print/log statement confirming whether the call returns, errors silently, or is never triggered
2. If the call succeeds but the UI never updates: check the signal/slot connection binding the fetched value to the label — confirm the label `setText()` call is actually reached (add a temporary log line, run the app, confirm in console, then remove the log line)
3. If the call fails or the underlying query/table doesn't exist yet: report this back before making UI guesses — do not fake a static number to make the "..." disappear
4. Once real values render, apply the `StatCard` component from Step 1 to these 5 cards (they already have a card background — just replace the internal layout structure and the `...` placeholder with a proper skeleton-loading shimmer state while data is in flight, and the real formatted value once resolved)
5. Do the same stuck-state check for the `STATUS TAHOGRAF` panel and `Preturi Combustibil` section — both currently render as empty containers with no visible content or empty-state message. Apply `EmptyState` (Step 5) if these are legitimately empty, or fix the data binding if they're stuck.

## STEP 7 — Section header consistency (all 4 screens)

Standardize every section title (`Rezumatul Zilei`, `Alerte Operationale`, `Curse Nealocate`, `Sumar Alocari`, `STATUS TAHOGRAF`, `Preturi Combustibil`, `FILTER BY SEVERITY` group, etc.):

- `14px`, font-weight `600`, color `#FFFFFF`, `0.3px` letter-spacing if uppercase
- `16px` bottom margin before content
- Any right-aligned action link in the same row (`Rezolva Tot`, `Importa Acum`) styled as a proper button/link: color `#6366F1`, `13px`, font-weight `500`, hover underline — not plain floating text

---

## MANDATORY VERIFICATION CHECKLIST (complete before reporting done)

- [ ] `StatCard` component created and used in ALL 4 screens (Panou status bar, Alerte's 2 stat rows, Control Întreținere's top 5 KPIs) — no bare label+number pairs remain anywhere
- [ ] StatCard rows tested at ~1280px, ~1920px, and ~900px window widths — no sparse/adrift card groups, no stretched-out individual cards, no horizontal scrollbar (see Step 1B)
- [ ] `EmptyState` component created and applied to: Planificare tab, both empty Alerte sections, and Panou's zero-results state
- [ ] Checkboxes and filter inputs restyled and visually confirmed (screenshot comparison before/after) on both the Panou tab and Control Întreținere
- [ ] Control Întreținere's `...` loading bug root-caused and either fixed or reported with the specific error/log output — NOT masked with a fake static value
- [ ] `STATUS TAHOGRAF` and `Preturi Combustibil` sections show either real content, a proper empty state, or a loading skeleton — never a blank void
- [ ] Every new/changed string passes through `t()` — grep the changed files for any raw Romanian/English string literals and confirm zero matches outside `ro.json`/`en.json`
- [ ] No hardcoded hex values were added outside `design_tokens.py`
- [ ] App launches without errors/warnings in console after changes
- [ ] Take a screenshot of each of the 4 reworked screens and confirm visually against the spec above before committing
- [ ] `git add -A && git commit -m "UI rework: dispatcher board + maintenance panel — StatCard/EmptyState components, fixed loading states, restyled filters"` run at the end

Do not report this task as complete until every checkbox above is genuinely verified, not assumed.
