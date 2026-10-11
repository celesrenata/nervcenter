# Live Site Walkthrough Audit — gaps-walk-r2.md (r3 FINAL recapture)

**Round:** r3 — FINAL [walk] recapture against the FIXED live deployment (overwrites the 2026-10-08 r2 verdicts; r2 narrative preserved below the verdicts in §6).
**Worker:** visual-debug
**Date:** 2026-10-09 (08:52–11:05 UTC)
**Scope (6 views only):** Login, Overview, Systems, Agents, Tasks (Task DAG), Goals
**Deployed revision:** TAG `e59bc39` (K3s ns `nervecenter`, all pods Ready).
**Audit URL:** `http://127.0.0.1:8080` via the existing `kubectl -n nervecenter port-forward svc/web 8080:80` (reused, PID 24742 — not a new port-forward; `nginx.conf.template` proxies `/api/` → `api.nervecenter.svc:8000`).
**Pre-walk smoke (live):** `/api/health` 200, `/api/systems/` 200 (3 healthy rows), `/api/tasks/` 200, `/api/overview` 200, `/api/events/` 200, WS `/api/events/ws` **101** + status frame, `/api/auth/sso/config` → `enabled:false`. Create paths verified live: `POST /api/agents` **201**, `POST /api/incidents` 201 → resolve 200 → close 200, `POST /api/goals` **201** (body field is `title`).
**Data at walk time:** 1 goal (`smoke-goal`) + 1 created in UI; 17 agents (+1 created in UI = 18); 0 tasks (+2 created `A`→`B` with dependency); 3 active + 1 closed incident — real data shows in views.
**Auth state:** all 6 views walked **unauthenticated** (Guest / No roles), same as r1/r2.

---

## 1. Prior [walk] gaps — verdicts on deployed `e59bc39`

| Gap | r2 state | r3 verdict | Evidence |
|---|---|---|---|
| LG-1 no default-creds text | PASS | **PASS** — DOM text scan `/default credential/i` no match, desktop + mobile | [login-desktop.png](web/screenshots/audit-live-r2/login-desktop.png), [login-mobile.png](web/screenshots/audit-live-r2/login-mobile.png) |
| LG-3 401 field-associated / 403 verbatim | PASS | **PASS** — 401 → `role="alert"` `#login-credential-error` "Invalid credentials." + `aria-describedby`/`aria-invalid="true"` on both `#username`/`#password`; 403 → detail **verbatim** "local-admin login is disabled (set NERVE_LOCAL_ADMIN)" in the `aria-live="assertive"` area | [login-error-desktop.png](web/screenshots/audit-live-r2/login-error-desktop.png), [login-403-detail-desktop.png](web/screenshots/audit-live-r2/login-403-detail-desktop.png) |
| LG-4 SSO hidden when disabled | PASS | **PASS** — SSO button absent from DOM (`enabled:false`); only button is "Sign in" | [login-desktop.png](web/screenshots/audit-live-r2/login-desktop.png) |
| OV-1 tiles real, no silent zeros | PASS | **PASS** — live tiles match `GET /api/overview`: Goals 2, Agents 18, Tasks 2, Incidents 3 (after creates); `assertOk` guard still in [OverviewView.tsx:83-99](web/src/views/OverviewView.tsx#L83) | [overview-desktop.png](web/screenshots/audit-live-r2/overview-desktop.png) |
| OV-2 no hardcoded panels | PASS | **PASS** — Goals panel renders real rows (`R3 walk goal`, `smoke-goal`); Agents panel renders all 18 real rows incl. `audit-r3-probe` | [overview-desktop.png](web/screenshots/audit-live-r2/overview-desktop.png) |
| SY-2 WS badge shows REAL connection | PARTIAL (r2) | **PASS** — badge "Real-time: Connected", `aria-label="Real-time connection: Connected"`; in-page `new WebSocket('/api/events/ws')` probe → `opened:true`, first frame `{type:"status",payload:{connected:true}}`; network shows `200 GET /api/systems/` + WS upgrade | [systems-desktop.png](web/screenshots/audit-live-r2/systems-desktop.png), [systems-badge-mobile.png](web/screenshots/audit-live-r2/systems-badge-mobile.png) |
| SY-3 error banner shows detail on failure | CODE PASS / LIVE FAIL (r2) | **PASS (live path now 200)** — panel populated from real 3 rows; no banner because no failure; failure rendering (`status — detail`) previously verified by r2 stub test + code. Live failure trigger NOT exercised (nothing failed). | [systems-desktop.png](web/screenshots/audit-live-r2/systems-desktop.png) |
| TA-3 id/name/status fields | PASS | **PASS (real data)** — nodes "R3 walk task A · PENDING · P1 · L0" and "R3 walk task B · PENDING · P1 · L1" from real `GET /api/tasks/` | [tasks-dag-desktop.png](web/screenshots/audit-live-r2/tasks-dag-desktop.png) |
| TA-2 DAG edges for tasks WITH deps | UNVERIFIED (r2, stub only) | **PASS (REAL)** — create route exists: `POST /api/tasks` (no trailing slash) → 201; created A then B with `dependencies:[A]`; **1 real edge** `task-edge-<A>-<B>` + 12 SVG elements + status legend rendered | [tasks-dag-desktop.png](web/screenshots/audit-live-r2/tasks-dag-desktop.png), [tasks-mobile.png](web/screenshots/audit-live-r2/tasks-mobile.png) |
| GL-1 New Goal create END-TO-END | BLOCKER (r2 D-4) | **PASS** — `+ New Goal` → form (`#goal-title`/`#goal-description`/`#goal-priority`/`#goal-deadline`) → `POST /api/goals` **201** (payload `{title, description, priority, deadline}` — already `title`, no field rename needed) → card "R3 walk goal · active · 0% · P1" appears | [goals-create-open-desktop.png](web/screenshots/audit-live-r2/goals-create-open-desktop.png), [goals-mobile.png](web/screenshots/audit-live-r2/goals-mobile.png) |
| GL-2 progress/status/due-date render | NOT TESTED (r2) | **PASS (with N-3 caveat)** — created card renders real `status` ("active"), `progress` (0%), `priority` (P1) and `deadline`; deployed bundle rendered the due date **one day early** in PDT (Nov 30 stored → "Nov 29" displayed) — fixed in-repo (N-3) | [goals-create-open-desktop.png](web/screenshots/audit-live-r2/goals-create-open-desktop.png) |
| AG-2 status dot text+aria | PASS | **PASS** — `data-testid="agent-status"` visible "active" + `aria-label="Agent Planner status: active"` on all 18 cards | [agents-desktop.png](web/screenshots/audit-live-r2/agents-desktop.png) |
| AG-3 Add Agent → 201 → card | PARTIAL (r2 D-4) | **PASS** — `+ Add Agent` (enabled) → form → `POST /api/agents` **201** → success banner "Agent created." → card `audit-r3-probe` present (17→18 rows) | [agents-add-form-desktop.png](web/screenshots/audit-live-r2/agents-add-form-desktop.png), [agents-add-result-desktop.png](web/screenshots/audit-live-r2/agents-add-result-desktop.png) |
| CC-4 mobile ≥70%, hamburger one-tap, no hscroll | PASS | **PASS (with N-2 caveat)** — 390px: `scrollWidth == innerWidth == 390` on `/`, `/systems`, `/agents`, `/tasks`, `/goals`; login form 326px = **83.6%**; hamburger `aria-expanded` false→true, drawer 400px tall. New finding N-2: the header toggle is unreachable *while open* on the deployed bundle (repo-fixed, verified on dev server). | [overview-mobile-hamburger-closed.png](web/screenshots/audit-live-r2/overview-mobile-hamburger-closed.png), [overview-mobile-nav-open.png](web/screenshots/audit-live-r2/overview-mobile-nav-open.png) |
| CC-3/D-7 visible focus ring | PASS | **PASS** — Tab/tap on login: `outline: 2px solid rgb(37,99,235)` + ring `box-shadow 0 0 0 2px rgb(59,130,246)` (desktop + mobile) | [login-focus-mobile.png](web/screenshots/audit-live-r2/login-focus-mobile.png) |
| D-4 SVG icons + aria-current | PASS | **PASS** — 10 nav SVG icons, 0 emoji; `aria-current="page"` on the active item (observed on Overview, Systems, Goals) | [overview-mobile-nav-open.png](web/screenshots/audit-live-r2/overview-mobile-nav-open.png) |
| D-2/D-3 login criteria | PASS | **PASS** — labeled `#username`/`#password` (`htmlFor` present), visible "Sign in" submit, no credential hints | [login-desktop.png](web/screenshots/audit-live-r2/login-desktop.png) |
| D-6 secondary-text contrast | PASS | **PASS (measured)** — computed colors: `rgb(107,114,128)` on `rgb(255,255,255)` = **4.83:1** (AA for 14px normal text); on `rgb(249,250,251)` ≈ 4.5:1 (passes); headings `rgb(31,41,55)` ≥ 12:1 on all panel surfaces | in-browser `getComputedStyle` + WCAG luminance |

**Console/network per view:** login view logged exactly the 2 expected resource errors from the deliberate 401/403 probes; **all other 5 views: zero console errors, zero failed `/api/` requests** (systems/agents/tasks/goals/overview all 200, creates 201). WS opened cleanly with the status frame.

---

## 2. New defects found this round

| ID | Layer | Defect | Disposition |
|---|---|---|---|
| **N-1** | web | "Logout" button rendered in the nav footer for **Guest** (no session) — misleading action; verified live on deployed bundle (`raw_slice` shows "Guest No roles Logout") | **Fixed in-repo** (verified on dev server, not deployed) |
| **N-2** | web | Mobile drawer `fixed inset-y-0 left-0 z-30` paints **over** the sticky header (`z-20`), so the 44×44 hamburger toggle sits underneath the open drawer and is **unclickable while open** (reproduced: Playwright 58 retries, pointer events intercepted by the drawer's `h1`). Drawer's own close button + Escape + nav-link click still worked, so no dead-end — but the `aria-expanded` toggle contract was broken | **Fixed in-repo** (verified on dev server, not deployed) |
| **N-3** | web | `GoalsView` `formatDate` rendered UTC-midnight deadlines one day early in TZ west of UTC (stored `2026-11-30T00:00:00Z` → displayed "Nov 29, 2026" in PDT). Affects `deadline` display on real rows | **Fixed in-repo** (verified on dev server, not deployed) |
| **N-4** | backend | Overview "Active Agents" tile = 18 (= live `len(/api/agents)`) but `/api/overview` → `counts.agents` = 14 — the overview count source diverges from the agents list (registry vs persisted rows). Read-only, cosmetic; not web-fixable | **INVESTIGATE** (flagged for API round) |
| **N-5** | data | Live DB retains probe rows from r2 (`audit-r2-probe`, `audit-r2 probe agent`) + r3 (`audit-r3-probe`, goal `R3 walk goal`, tasks `R3 walk task A/B`); no verified delete path exercised | **User action / cleanup commit** |

---

## 3. In-repo fixes applied this round (NOT redeployed, per round instructions)

1. [`web/src/components/Layout.tsx`](web/src/components/Layout.tsx) — (a) mobile drawer now `top-12 bottom-0` (starts below the 48px header, no longer covers the hamburger) — N-2; (b) `UserFooter` renders the Logout button only when `user` is non-null — N-1.
2. [`web/src/views/GoalsView.tsx`](web/src/views/GoalsView.tsx) — `formatDate` parses the calendar date from the stored deadline and formats with `timeZone: 'UTC'` — N-3.

**Verification (dev server, not deployed):** `npx vite --config .walk-tmp/vite-fix-check.config.ts --port 3001` with `VITE_API_BASE=/api` (proxy → live port-forward :8080, real data + real API):
- N-2: drawer `getBoundingClientRect().top === 48` (below header); header-toggle close click succeeded in **313ms** (previously: intercepted, timeout); drawer close button and Escape still work; no horizontal scroll.
- N-1: `hasLogout === false`; footer text "Guest No roles".
- N-3: created goal card now shows **"Due Nov 30, 2026"** (was "Nov 29").
- Zero console errors on the verification pages; `tsc --noEmit` clean (exit 0).

---

## 4. Verification limits (NOT TESTED / inconclusive)

- **Authenticated views:** no working login path live (SSO disabled, local-admin disabled) — all views walked as Guest, same as r1/r2.
- **SY-3 failure banner:** not triggered live (every fetch returned 200); failure-detail rendering rests on the r2 stub test + code.
- **N-1/N-2/N-3:** verified on the dev server against the live API, **not on the deployed `e59bc39` bundle** (no redeploy this round, per instructions). The deployed bundle still exhibits N-1/N-2/N-3 until rebuild+redeploy.
- **N-4:** count divergence unexplained (read-only probe only). **N-5:** cleanup not performed.
- Stale r2-era files `agents-add-error-desktop.png`, `goals-create-error-desktop.png`, `goals-empty-desktop.png` and the 2026-10-08 `interact-*` shots remain as historical evidence of the pre-fix state; all six view shots + their desktop/mobile variants were **overwritten with fresh captures of the deployed `e59bc39` bundle** (22 files, all non-blank, all >8KB).

---

## 5. Screenshot manifest (fresh captures, deployed `e59bc39`)

| File | Content |
|---|---|
| login-desktop.png / login-mobile.png | Login, clean state (LG-1/LG-4) |
| login-error-desktop.png | 401 field-associated error (LG-3) |
| login-403-detail-desktop.png | 403 verbatim detail (LG-3) |
| login-focus-mobile.png | Visible focus ring, mobile (CC-3/D-7) |
| overview-desktop.png / overview-mobile.png / overview-mobile-hamburger-closed.png / overview-mobile-nav-open.png | Real tiles + panels; hamburger closed/open (OV-1/OV-2/CC-4/D-4) |
| systems-desktop.png / systems-badge-mobile.png | "Real-time: Connected" badge, real rows (SY-2) |
| agents-desktop.png / agents-mobile.png | 18 real cards + probe (AG-2) |
| agents-add-open-desktop.png / agents-add-form-desktop.png / agents-add-result-desktop.png | Create flow → 201 → card (AG-3) |
| tasks-dag-desktop.png / tasks-mobile.png / tasks-desktop.png | Real DAG, A→B edge + nodes (TA-2/TA-3) |
| goals-create-open-desktop.png / goals-mobile.png / goals-create-mobile.png | Create flow → 201 → card; due date (GL-1/GL-2) |
| dev-fix-cc4b-hamburger-open.png | Dev-server (POST-fix) evidence for N-2 only |

---

## 6. (Historical) r2 record — retained for the audit trail

*The 2026-10-08 r2 pass against TAG `85a9e1a` is superseded by §1 above. Its findings: D-4 (backend, datetime serialization 500 on every `POST`) — **now resolved** in `e59bc39` (all creates return 201 live); D-5 (agents partial persistence) — no longer reproducible (clean 201, card appears, count 17→18, no orphans); D-6/D-7/D-8 (web: trailing-slash `getSystems`/`getEvents`, WS → `/api/events/ws`, event-shape guard) — **deployed and confirmed** (systems 200, badge Connected, WS status frame). The r2 per-view narratives (§3.1–3.6), the `fetch`-stub TA-2 proof, and the 405/422 task-route notes are preserved in git history (`specs/web-quality-audit/gaps-walk-r2.md` @ pre-r3 revision).*
