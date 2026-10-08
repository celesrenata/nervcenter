# Visual Auditor Review — Live Screenshot Audit

**Mode:** visual-auditor (vision on PNGs, read-only; no browser interaction, no code edits)
**Date:** 2026-10-07 (audit run), deployed revision TAG `50e4c83`, K3s ns `nervecenter`
**Evidence set:** 24 PNGs in [`web/screenshots/audit-live/`](../../web/screenshots/audit-live/) — desktop 1280px + mobile 390px per view, captured via `kubectl port-forward` (no published DNS A record for the ingress; see [`specs/web-quality-audit/gaps-walk.md`](gaps-walk.md) §1–2)
**Cross-checked against:** [`specs/web-quality-audit/spec.md`](spec.md) (AC-W01…AC-W0x, §Goals/Constraints), [`specs/web-quality-audit/gaps-walk.md`](gaps-walk.md), [`specs/web-quality-audit/gaps-interact.md`](gaps-interact.md), consolidated [`audit-gaps.md`](../../audit-gaps.md)
**Captures reviewed (24/24):** login-desktop, login-error-desktop, login-mobile, overview-desktop, overview-mobile, systems-desktop, systems-mobile, agents-desktop, agents-mobile, tasks-desktop, tasks-mobile, goals-desktop, goals-mobile, interact-login-failed-state, interact-incidents-desktop/-mobile, interact-decisions-desktop/-mobile, interact-timeline-desktop/-mobile, interact-ask-desktop-202ack / -mobile-390, interact-inference-desktop/-mobile-390. All opened successfully; none corrupt or blank.

---

## 1. Per-view one-line verdicts

| View | Desktop verdict | 390px verdict |
|---|---|---|
| Login | **FAIL** — works visually but ships "Default credentials: admin / password" hint; error state is a single non-field-associated banner | **PASS w/ defects** — stacks acceptably, but same credential hint and error pattern present |
| Overview | **PASS w/ defects** — KPI/stat cards render and hierarchy reads well, but emoji nav and unmeasured contrast persist | **FAIL** — fixed `w-64` sidebar dominates the viewport; content area compressed to ~250px |
| Systems | **FAIL** — live capture shows the `ERR_CONNECTION_REFUSED` / endpoint-not-reached error state, not the data grid (port-forward artifact, see §5) | **FAIL** — same error state plus sidebar consumption; no horizontal-overflow handling visible |
| Agents | **PASS w/ defects** — card/list layout coherent, status colors legible; secondary-text contrast unverified | **PASS w/ defects** — cards stack; padding tight, no horizontal overflow observed |
| Tasks | **PASS w/ defects** — list density acceptable, action buttons visible | **PASS w/ defects** — rows stack; control sizing adequate at 390px |
| Goals | **PASS w/ defects** — progress/ownership data visible, card grid aligned | **PASS w/ defects** — grid collapses to single column cleanly |
| Incidents | **PASS w/ defects** — severity colors and state chips legible | **PASS w/ defects** — chips wrap; no cut-off observed |
| Decisions | **PASS w/ defects** — decision rows and rationale text readable | **PASS w/ defects** — text wraps within bounds |
| Timeline | **PASS w/ defects** — event stream ordering clear, timestamps aligned | **PASS w/ defects** — vertical stream fits 390px without clipping |
| Ask | **PASS w/ defects** — 202 pending state rendered (interact-ask-desktop-202ack) — pending ≠ done, but the pending state is a visible designed state | **PASS w/ defects** — input + response area fits; no overflow |
| Inference | **PASS w/ defects** — inference output panel renders with content | **PASS w/ defects** — panel stacks; no cut-off |

Legend: PASS = no visible blocking defect in this capture; PASS w/ defects = usable, cross-cutting defects apply (below); FAIL = essential task blocked or layout broken in this capture.

---

## 2. Top defects (prioritized, with screenshot evidence)

### D-1 — Fixed sidebar consumes the 390px viewport (P0, all views)
Every mobile capture (e.g. `overview-mobile.png`, `systems-mobile.png`, `goals-mobile.png`) shows the desktop sidebar rendered at 390px width: the nav column occupies most of the screen and the content column is compressed to a narrow strip. This is the spec §8 failure ([`specs/web-quality-audit/spec.md`](spec.md) §17–18 "Fixed `w-64` sidebar, no mobile collapse"). No hamburger/collapsed state is visible in any capture. **Impact:** essential tasks (reading any list) are degraded on phones; navigation and content compete. **Recommendation:** collapse the sidebar to an icon rail or off-canvas drawer below `lg:` breakpoint; verify at 360 and 390px. **Acceptance:** at 390px, content column ≥ 70% of viewport width; nav reachable via one tap; no horizontal scroll on the page.

### D-2 — Login ships default credentials on the surface (P0, security + design)
`login-desktop.png`, `login-mobile.png`, `login-error-desktop.png` all show the "Default credentials: admin / password" hint under the form. Spec §22–23 calls this out as both a security defect (S101 removes the default user) and a design defect; [`specs/web-quality-audit/spec.md`](spec.md) Goal 2 requires the login surface to be the SSO entry point per `specs/sso-integration/spec.md` AC-S06. **Recommendation:** remove the hint entirely; add persistent labels, a field-associated error message, and a pending (disabled-button) state per spec §36–38. **Acceptance:** no default-credential text in DOM at any viewport; error text adjacent to the relevant field; button disabled while request in flight.

### D-3 — Login error is a single non-field-associated message (P1)
`login-error-desktop.png` and `interact-login-failed-state-2026-10-06T22-33-14-531Z.png` show one banner-style message above/around the form rather than per-field messaging with `aria-live` semantics implied. Spec §27–28 explicitly lists this. **Acceptance:** error appears next to the failing field; screen-reader-relevant (live region); form does not lose focus context.

### D-4 — Emoji navigation icon system (P1, all views)
Sidebar nav in every desktop capture (e.g. `overview-desktop.png`) uses emoji glyphs (📊-style) as the navigation icon system. Spec §15–16 (§5 of the rules: "emoji are not a professional navigation icon system") and AC-W02 require a consistent icon set. Beyond professionalism, emoji rendering is platform-dependent (size, weight, tint) which degrades cross-platform consistency. **Acceptance:** all 10 nav items use one icon set (inline SVG) at uniform 16–20px, with `aria-current="page"` on the active item (see §4 re: verification).

### D-5 — Systems view: live capture proves error state, not data state (P1, environment-dependent)
`systems-desktop.png` / `systems-mobile.png` show the failed-endpoint presentation (connection-refused rendering) rather than the systems grid. Per [`specs/web-quality-audit/gaps-walk.md`](gaps-walk.md) §2/§4.3, this is caused by the port-forward `Host` header producing an absolute `Location: http://nervcenter.celestium.life/...` redirect the browser cannot resolve; through the real ingress host the same endpoint returns 501 (verified in that doc via curl with `Host:` header). **What this means for the audit:** the *error presentation* is visible and is a designed state (good), but the actual Systems data layout was never captured live — treat the Systems data-grid verdict as **NOT TESTED**, not "renders fine". **Recommendation:** fix the redirect/Host handling (backend/nginx), re-capture at 1280 and 390 before the data-grid can be audited.

### D-6 — Typography/surface consistency: default-gray ad-hoc palette (P2)
Across all desktop captures the palette is the default Tailwind gray family with ad-hoc dark: variants — no semantic canvas/surface/elevation distinction beyond card border vs. background. Spec AC-W01 requires semantic tokens and [`specs/web-quality-audit/spec.md`](spec.md) §58 requires WCAG AA contrast. Secondary text (timestamps, metadata under cards) appears low-contrast in captures (e.g. `overview-desktop.png`, `tasks-desktop.png`) but **exact ratios are not measurable from screenshots** — see §5. **Acceptance:** computed contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text and control boundaries, verified with computed styles (not eyeballed from PNGs).

### D-7 — No visible focus indicators in any capture (P2, unprovable from statics)
No screenshot shows a focus ring. This is consistent with the spec §19 claim ("No visible focus indicators anywhere") but a static screenshot cannot prove absence — focus may simply not have been on an interactive element at capture time. **Status: INVESTIGATE.** Requires keyboard Tab capture (visual-debug) to confirm.

---

## 3. Per-view detail notes

**Login** — Composition is a centered card on a neutral canvas; primary action (Sign in) is visually dominant, which is correct. Flaws: D-2, D-3. The error banner in `interact-login-failed-state-2026-10-06T22-33-14-531Z.png` uses red text on the light surface — legible in the capture, ratio unmeasured. Mobile (`login-mobile.png`) keeps single-column stacking with full-width fields — acceptable.

**Overview** — Desktop: stat/KPI cards read in a clear left-to-right hierarchy; page title and section grouping are fine. Mobile: blocked by D-1; after the sidebar, the KPI strip wraps and some cards become very narrow. Content itself is not truncated in the capture.

**Systems** — See D-5. The visible error state is well-formed (message, not a stack trace), which is a positive for state design, but the data grid, empty state, and row density remain unverified.

**Agents** — Cards with status indicators; status colors (green/amber/red chips) are distinguishable at a glance. Secondary metadata text is small; contrast unmeasured (D-6). No cut-off at 390px in the capture.

**Tasks** — List rows with clear primary content + action affordances. Row density is reasonable; action buttons do not compete with row content. 390px rows stack without clipping.

**Goals** — Card grid; progress indicators present and legible. Single-column collapse at 390px is clean.

**Incidents** — Severity chips legible; state design (open/resolved) visible in desktop capture. Mobile chips wrap to two lines in dense rows — acceptable, no clipping.

**Decisions** — Row-based layout; rationale text wraps within bounds at both widths. Long-text handling appears correct in the capture (no ellipsis truncation hiding content).

**Timeline** — Vertical event stream; timestamps right/left aligned consistently; 390px fits without horizontal scroll in the capture.

**Ask** — `interact-ask-desktop-202ack-2026-10-06T22-24-51-011Z.png` shows the **pending/202 state** — this is a designed state being rendered, which is good; it does **not** prove the answer ever arrives (see §5). Mobile input area fits; response region stacks below.

**Inference** — Output panel with content at both widths; no overflow observed. Loading/empty state of this view is not captured.

---

## 4. Accessibility findings (what is visible vs. not)

- **Visible in captures:** color-dependent status chips (severity, agent status) — color is the primary channel; no visible icon/text fallback for the same state in the captures, which is an a11y risk (color-blind users) — flagged as **P2 INVESTIGATE** (a text label next to the chip would resolve it; cannot confirm absence from screenshots alone).
- **Not provable from screenshots:** focus indicators (D-7), keyboard order, ARIA labels/roles, screen-reader output, tab traps, live-region announcements, form label association beyond visual proximity, contrast ratios (D-6), 360px behavior (captures are 390px only).
- Per spec §58, WCAG AA must be verified with computed styles, not by eye.

---

## 5. What the screenshots cannot prove (explicit gaps)

1. **Backend/endpoint health.** The site was reached via `kubectl port-forward`; the Systems `ERR_CONNECTION_REFUSED` rendering is a redirect/Host artifact of that setup (documented in [`specs/web-quality-audit/gaps-walk.md`](gaps-walk.md) §2, §4.3), not proof that the endpoint is broken under the real ingress. Conversely, 200-rendering views do not prove the API works end-to-end.
2. **Ask 202 → final answer.** The pending state is captured; the completed-answer state is not. Whether an answer ever renders is unverified.
3. **Contrast ratios.** No measurement; D-6 is a hypothesis from visual density, not a computed fail.
4. **Focus/keyboard behavior.** Static captures cannot show or rule out `:focus-visible`.
5. **Loading spinners / skeleton states.** No mid-load captures; "loading state" design is NOT TESTED for most views.
6. **360px.** All mobile captures are 390px; 320–359px behavior unknown.
7. **Whole-site accessibility compliance.** This audit is visual; it does not establish WCAG compliance (no a11y tree, no screen reader, no keyboard pass).
8. **Dark mode.** Only light theme captured (captures do not show a dark variant); `dark:` variants' rendering is unverified.

## 6. Coverage matrix (named checks)

| Check | Status |
|---|---|
| Desktop 1280px, 10 views + login variants | PASS (reviewed) |
| Mobile 390px, 10 views + login | PASS (reviewed; D-1 defects) |
| Login error state | REVIEWED (D-3) |
| Ask pending (202) state | REVIEWED |
| Systems data-grid state | **NOT TESTED** (D-5 — error state captured instead) |
| Loading/skeleton states | **NOT TESTED** |
| Contrast (computed) | **NOT TESTED** |
| Focus indicators / keyboard | **NOT TESTED** (D-7 — INVESTIGATE) |
| Dark theme | **NOT TESTED** |
| 360px | **NOT TESTED** |

---

*Deliverable written by visual-auditor (parallel worker-1, task 01a112c3). Screenshot paths relative to repo root `web/screenshots/audit-live/`. No code was modified.*
