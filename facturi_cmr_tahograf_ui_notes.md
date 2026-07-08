# UI/UX Findings — Facturi / CMR / Tahograf + deeper notes on earlier screens

Format: 🐞 = likely functional bug (not just styling), 🎨 = pure UI/UX improvement. Bugs should be verified/fixed before or alongside any restyling — restyling around a bug just hides it.

---

## A. Facturi → Chitanță tab (Image 1)

- 🐞 **`receipt.editor.export_json` is rendering as a button label.** This looks like a raw internal method/config key leaking into user-facing UI instead of a translated label (e.g. should read "Exportă JSON" via `t()`). Find where this button's text is set and confirm it's not falling back to a dict key or debug string when a translation lookup fails.
- 🐞 **Header shows `CURSA: #17 2 — dad [2026-06-19]`.** `"17 2"` (with a stray space instead of a separator like `#17.2` or `#17-2`) looks like a formatting bug in the trip-label builder — likely a missing separator/format specifier between two numeric parts. (The `"dad"` portion is just a test client name you entered, not an issue — but worth double-checking that the client-name segment truncates/wraps gracefully for long real client names, since this slot will show actual company names in production.)
- 🎨 The action button row (Generează PDF / Tipărește / Salvează Ciornă / Încarcă Ciornă / Duplică / export json / Email) has no visual hierarchy beyond one indigo button. Group into **primary** (Generează PDF — indigo, as-is) and **secondary** (everything else — consistent outlined/ghost style, same height, same icon-to-text spacing). Right now icon sizes and button widths are inconsistent.
- 🎨 Left-side form (`TIP CHITANȚĂ`, `COMPLETARE RAPIDĂ DIN FACTURĂ`, `INFORMAȚII CHITANȚĂ`) runs as one continuous scroll with section labels but no card separation — apply the same section-card pattern from the dispatcher rework (title + card container, `16px` gap between sections) so the eye can parse where one group ends and the next begins.
- 🎨 `SELECTEAZĂ FACTURĂ` dropdown appears nearly black/disabled-looking compared to other inputs — confirm whether it's actually disabled (if so, add a visible disabled-state style, don't just let it look broken) or whether it's enabled but under-styled.
- 🎨 On the live preview (right pane), **"Primit de la" renders as an empty box with no placeholder**, while **"Primit de" is filled** — the empty side looks broken/unfinished rather than intentionally empty. Add a muted placeholder line (e.g. "—" or a greyed "Se completează automat") so an empty required field reads as "not yet filled" rather than "something didn't load."
- 🎨 Financiar section (`Sumă 0.00 EUR`, `Total 0.00 EUR`) — when both are genuinely zero (no line items yet), consider a small inline hint ("Adaugă o sumă mai jos") rather than just showing zeros, so it's clear this isn't a bug.

## B. Facturi → Scrisoare de Trasura CMR tab (Image 2)

- 🐞 **Date field defaults to `2034-07-07`** — 8 years in the future. This is almost certainly a hardcoded/test default rather than "today." Audit every date field across the document generator for the same issue; default should be `datetime.now()` (consistent with the existing preference already established for clocks elsewhere in the app) or left empty with a placeholder, never a fixed future date.
- 🐞 **"eschic" next to each generated-copy row** — this isn't a recognizable Romanian word. Check whether this is a truncated string (e.g. "eschivare," "renunță," or a cut-off English string like "eschew" leaking untranslated) or a typo for something like "șterge" (delete) / "anulează." Needs a source check, not a guess.
- 🎨 The **numbered box navigator (1–24)** is a nice touch for jumping around a 24-box legal form, but currently all pills look identical regardless of state. Add state coloring: filled/valid = subtle green tint, required-and-empty = amber/red tint, optional-and-empty = neutral grey (matches the severity-dot convention already used elsewhere). This turns it into a real progress/completion indicator instead of just a page index.
- 🎨 **Empty textareas** for Consignor/Consignee (boxes 1–2) and Documents Attached (box 5) have no placeholder text. Add contextual placeholders (e.g. "Nume, adresă, țară" / "Listați documentele atașate") so an empty box doesn't read as broken.
- 🎨 **Loading Country / Delivery Country** small fields at the end of the Locality/Country row are visually cramped and inconsistent in width vs. the other inputs on the same row — they read as an afterthought. Either give them proper labeled space of their own or move them into a clearly separate sub-row.
- 🎨 Right panel (`OPTIUNI`, `ACTIUNI`, `COPII GENERATE`) again lacks card grouping — same section-card treatment as elsewhere would help, especially since this panel mixes settings, actions, and a status list in one continuous column.
- 🎨 The two role-select buttons ("I am the Consignor" / "I am the Consignee") use a good pattern (filled-indigo selected vs. outlined unselected) — worth promoting this as the **standard toggle-button style** and reusing it anywhere else in the app that currently uses checkboxes for a binary either/or choice.

## C. Tahograf import screen (Image 3)

- 🎨 **`IMPORTA FISIERE` drop zone is a large dark box with just a top-left label and nothing else.** This needs standard drop-zone affordances: centered upload icon, centered hint text ("Trage fișierele aici sau apasă pentru a selecta"), and a dashed border (`1px dashed rgba(255,255,255,0.2)`) that brightens on drag-hover. Right now it doesn't visually read as interactive at all.
- 🎨 The instructions box below it (numbered steps 1–3) has the same problem — content is top-aligned in a tall box, leaving a large dead gap before the buttons. Either shrink the box to fit its content or vertically center the numbered list within it.
- 🐞/🎨 **"Importa Unitate Vehicul" (secondary button) is styled almost identically to the background** — it's hard to tell if it's a real, clickable button or a disabled/placeholder element. Confirm it's actually enabled, then give it a proper secondary-button style (visible border, hover state) so it doesn't read as broken or inactive.
- 🎨 **`ISTORIC IMPORTURI` table** has one real row and a large empty void beneath it. Size the table container to its content (or a reasonable max row count) rather than a fixed tall panel — apply the shared `EmptyState`/sizing pattern so "only 1 import so far" doesn't look like a rendering error.
- 🎨 Table truncation: `Card ...` and `C_20220715_1211_A_...` are hard-truncated with no way to see the full value. Add `QToolTip` on hover showing the untruncated filename/type, and consider eliding from the middle for filenames (`C_2022...1_A_x.ddd`) rather than only from the end, since the end of a filename is often the most distinguishing part.
- 🎨 **`STATUS` column shows plain white "OK"** — recolor as a small colored badge (green background/text for success, matching the severity-dot palette from the maintenance panel) so status is scannable at a glance across many rows, not just readable one at a time.

---

## D. Additional notes on the earlier dispatcher board / maintenance screens

Beyond what's already in the rework prompt, a second pass surfaces a few more things worth folding in:

- 🎨 **Sidebar icons** (left nav column, visible in all screenshots) have no active-state label/tooltip visible and rely purely on icon shape at a small size — consider adding a hover tooltip with the section name, since several icons (wrench, toolbox, folder, clipboard) are visually similar at this size and not self-explanatory without labels.
- 🎨 **Tab switches** (Panou/Alerte/Planificare, Factura/CMR/Chitanță/Proforma) currently just swap content instantly. A subtle fade/slide transition (150–200ms) would make the app feel less like abrupt panel-swapping and more polished — low priority, but consistent with the "vibecoded" feel you're trying to move away from.
- 🎨 **Top-right status cluster** (green dot, bell icon, clock) in every screenshot has no visible separation or grouping styling — consider a subtle vertical divider or consistent spacing so it doesn't look like three unrelated elements crammed into the corner.
- 🐞 Given the `receipt.editor.export_json` and `2034-07-07` findings above, it's worth doing a **full sweep for other leaked debug/placeholder values** across the app (dropdown defaults, generated IDs, date fields) before the visual rework — these are exactly the kind of thing that's easy to miss once the UI looks polished, because a nicely-styled card will still show a raw key name or a garbage date just as prominently as it does now.

---

## Suggested next step

These notes are organized so they can be turned into a follow-up implementation prompt (same style as the dispatcher/maintenance one — exact hex/px, numbered steps, verification checklist, `t()` compliance, git commit) covering:
1. Facturi document generator (Chitanță + CMR tabs): section cards, button hierarchy, placeholder text, box-navigator state coloring
2. Tahograf import screen: drop-zone affordance, button styling fix, table truncation/tooltips/status badges
3. A dedicated "debug string sweep" task to hunt down leaked raw keys/placeholder data (`receipt.editor.export_json`, `2034-07-07`, `eschic`) before they get buried under nicer styling

Let me know if you want me to draft that prompt now or after you've had a chance to confirm which of the remaining flagged 🐞 items (the CURSA label spacing, the CMR default date, and the "eschic" string) are real bugs vs. intentional.
