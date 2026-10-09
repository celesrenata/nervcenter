# Live Interaction Audit (r2) — Incidents / Decisions / Timeline / Ask / Inference

**Worker:** visual-debug (gap-closure round re-run, [interact] pass)
**Date:** 2026-10-08 (19:36–20:15 UTC)
**Target:** live deployment, K3s ns `nervecenter`, deployed image TAG `85a9e1a` (web + api). All pods Ready; migrate-job Completed.
**Companion file:** this is the interaction/live-evidence half; `gaps-walk-r2.md` (sibling worker) covers the static 6-view walk. r1 sibling: `gaps-interact.md`.

## URL used

- Same ingress `nervcenter-celestium` → `nervcenter.celestium.life` (NXDOMAIN from this host; not re-tested).
- Fallback used: `kubectl -n nervecenter port-forward svc/web 18321:80` → **`http://127.0.0.1:18321`** (nginx reverse proxy; `GET /` → 200, `GET /api/health` → 200). Port-forward started with a `nohup` background kubectl, log at `/tmp/pf-web-18321.log`, killed after the pass.

## Pre-walk API smoke (live, via port-forward)

| Endpoint | HTTP | Body note |
|---|---|---|
| `GET /api/health` | 200 | db ok / nats connected / jetstream available |
| `GET /api/incidents` | 200 | `{"data":[]}` (before probing) → **`total:2` after** (see IN-1) |
| `GET /api/decisions` | **501** | `{"detail":"Decisions list endpoint requires the decisions service to be wired via app.state.services."}` |
| `GET /api/events` | **307** → `http://127.0.0.1/api/events/` | FastAPI `redirect_slashes`; port dropped (see TL-1) |
| `GET /api/events/` (slash) | 200 | `{"data":[],...,"total":0}` — the healthy shape |
| `GET /api/compute` | 200 | empty list |
| `GET /api/routes` | 200 | empty list |
| `GET /api/models/history` | 200 | empty list |
| `POST /api/incidents` | **500** | body `Internal Server Error` (plain text, no JSON detail) — D-4, known |
| `POST /api/incidents/{id}/resolve` | **500** | body `Internal Server Error`; row stays `active` — D-4 on the UPDATE path |
| `POST /api/context/ask` | **202** | `{"accepted":true,"executed":false,"detail":"No 'context' service is configured; mutation accepted but not executed.","result":null}` |

**Auth state:** all 5 views walked **unauthenticated** (Guest / No roles), matching r1 and the walk pass. `GET /api/auth/sso/config` → `{"enabled":false,"local_admin_enabled":false,...}` (no credential path on live; login not re-probed this pass — out of [interact] scope).

## Live vs mock

Deployed bundle is **LIVE** mode: `VITE_API_BASE=/api` baked at build ([`web/Dockerfile:29`](../../web/Dockerfile)); `useMockMode=false` ([`client.ts:11`](../../web/src/api/client.ts)). Mock fixtures are never used. Per view: Incidents → live `GET/POST /api/incidents`; Decisions → live `GET /api/decisions`; Timeline → live `GET /api/events`; Ask → live `POST /api/context/ask`; Inference → live `GET /api/compute`, `/api/routes`, `/api/models/history`.

## Old-gap disposition (vs `gaps-interact.md`)

| Gap | r1 state | r2 result | Evidence |
|---|---|---|---|
| **IN-1** create incident, 500 surfaces as `500 — <detail>` in `role=alert`, form stays usable | FAIL (dead button) | **PASS (UI)** — form opens, `POST /api/incidents` → 500, `role="alert"` `[data-testid="incident-form-error"]` shows verbatim **`500 — Internal Server Error`**; form stays open/usable after the failure (title retained, description typeable, severity reselectable). **BUT see NEW-N1/N2:** the 500 is a *false failure* (row persisted) and the list only refreshes on success. | [interact-incidents-form-error-desktop…](web/screenshots/audit-live-r2/interact-incidents-form-error-desktop-2026-10-08T19-48-54-008Z.png) |
| **IN-2** empty-state guidance copy | FAIL (none) | **PASS** — `GET /api/incidents` empty → `role=alert`-free empty card `[data-testid="incidents-empty"]`: "No incidents recorded." + "Use '+ Report Incident' … or wait for the event bus to surface one. Incidents are append-only and never deleted." | [interact-incidents-desktop…](web/screenshots/audit-live-r2/interact-incidents-desktop-2026-10-08T19-46-59-679Z.png) |
| **DC-1** error banner (status+detail) instead of silent empty list | FAIL (silent) | **PASS** — live `GET /api/decisions` returns a *real* **501**, so the error renders without interception: `role="alert"` `[data-testid="decisions-error"]` = "Failed to load decisions: **501 — Decisions list endpoint requires the decisions service to be wired via app.state.services.**". No `decisions-empty` shown; row list suppressed. (Interception not needed since the endpoint is a live 501.) | [interact-decisions-error-desktop…](web/screenshots/audit-live-r2/interact-decisions-error-desktop-2026-10-08T19-50-18-139Z.png), […mobile](web/screenshots/audit-live-r2/interact-decisions-error-mobile-2026-10-08T20-12-00-010Z.png) |
| **TL-1** no hardcoded sample events; live GET empty → guidance; real event renders | r1 was FAIL (hardcoded sample; no API) | **PARTIAL / NEW DEFECT (N1/N2)** — hardcoded sample removed; `GET /api/events` (slash) is genuinely empty → guidance copy "No events recorded yet." renders. **However** `client.ts` fetches `/api/events` *without* a trailing slash, which 307-redirects to `http://127.0.0.1/api/events/` (port 80, dead under port-forward) → the browser fetch **throws**, so the view *simultaneously* renders the empty-state copy **and** a `role="alert"` "Failed to load timeline: **0 — Request failed (network error)**". A real event could not be published (no NATS publish route; only GET endpoints exist). **Repo fix applied** (see below). | [interact-timeline-error-desktop…](web/screenshots/audit-live-r2/interact-timeline-error-desktop-2026-10-08T19-55-00-243Z.png), [interact-timeline-mobile…](web/screenshots/audit-live-r2/interact-timeline-mobile-2026-10-08T20-12-41-416Z.png) |
| **ASK** POST `/api/context/ask` works (200 answer or 202 pending) | r1 kept ✅ | **PASS** — `POST /api/context/ask` → **202** `{accepted:true, executed:false, ...}`; UI renders "Request accepted (execution: pending). No 'context' service is configured; mutation accepted but not executed." (the 202-pending shape, not a crash). Confirmed via curl + in-browser. | [interact-ask-desktop…](web/screenshots/audit-live-r2/interact-ask-desktop-2026-10-08T20-01-18-338Z.png), […mobile](web/screenshots/audit-live-r2/interact-ask-mobile-2026-10-08T20-13-18-147Z.png) |
| **INF-1** empty-state guidance in compute/routes/model-history; live data renders when present | r1 kept | **PASS** — all three sections (`Physical Nodes`, `OmniRoute Routes`, `Historical Model Performance`) show honest empty-state copy; no error banner; live 200-empty fetches; clean console. "No compute nodes reported." / "No OmniRoute routes configured." / "No model history recorded." (each with "…this is an honest empty state, not a failed fetch"-class body). | [interact-inference-desktop…](web/screenshots/audit-live-r2/interact-inference-desktop-2026-10-08T20-01-51-879Z.png), […mobile](web/screenshots/audit-live-r2/interact-inference-mobile-2026-10-08T20-13-54-955Z.png) |

## New defect register

### N1 (NEW) — Incidents `POST` is a false failure: row persists but API returns 500
- **Repro:** `POST /api/incidents` → HTTP **500** `Internal Server Error`. But `GET /api/incidents` immediately returns the row: `total:2`, `{"id":"…","title":"…","status":"active",...}`. Two such rows were created during this pass ("Live r2 interact probe — D-4 regression check" @ 19:47:58Z, "r2 curl probe" @ 19:48:54Z), both `active`.
- **Impact:** the UI form shows a red `role=alert` "500 — Internal Server Error" and does **not** refresh the list (refresh is success-only, [`IncidentsView.tsx:127-131`](../../web/src/views/IncidentsView.tsx)), so the user sees a failure — yet the incident **was created**. On next navigation the row appears. This is a data-integrity/trust defect layered on top of D-4.
- **Root cause (hypothesis, needs backend confirm):** the create INSERT throws (D-4 `datetime→varchar`) *after* the row is committed/autocommitted, so the side effect persists while the response is 500. NOT re-litigating D-4 here.
- **Layer:** backend persistence/transaction handling (out of [interact] fix scope — record only).
- **Evidence:** `curl POST /api/incidents` → 500, then `curl GET /api/incidents` → `total:2`; screenshot [interact-incidents-form-error-desktop…](web/screenshots/audit-live-r2/interact-incidents-form-error-desktop-2026-10-08T19-48-54-008Z.png).

### N2 (NEW) — Timeline `role=alert` "network error" contradicts the empty-state (port-forward / trailing-slash 307)
- **Repro (in-browser, discriminating):** on the live Timeline, `fetch('/api/events')` (the exact path [`client.ts:422`](../../web/src/api/client.ts) uses) → `TypeError: Failed to fetch`; `fetch('/api/events/')` → **200** `{"data":[],...}`. The no-slash request 307-redirects to `Location: http://127.0.0.1/api/events/` (port 80, dead under `port-forward 18321:80`), so the browser redirect follow fails.
- **Impact:** the Timeline renders **both** the `timeline-empty` guidance card **and** the `role=alert` "Failed to load timeline: **0 — Request failed (network error)**" banner at the same time — a contradictory, dishonest state. It also emits a `net::ERR_CONNECTION_REFUSED` console error. Under the real ingress (port 80 served) the Location would resolve and the banner would not appear — so this is *partly* a port-forward/absolute-Location artifact, but the client-side robustness gap (trailing-slash parity with `getSystems`) is real and repo-fixable.
- **Fix applied (repo, NOT deployed):** [`web/src/api/client.ts` `getEvents`](../../web/src/api/client.ts) now calls `apiFetch('/events/')` with a trailing slash (mirrors the existing `getSystems` fix at `client.ts:435`), with a comment. This makes the live fetch resolve to the 200-empty and removes the spurious alert. **Not redeployed** per brief; a rebuild + redeploy of the web image is required to observe it live.
- **Evidence:** in-browser fetch probe (above); [interact-timeline-error-desktop…](web/screenshots/audit-live-r2/interact-timeline-error-desktop-2026-10-08T19-55-00-243Z.png); [interact-timeline-mobile…](web/screenshots/audit-live-r2/interact-timeline-mobile-2026-10-08T20-12-41-416Z.png).
- **Related (not fixed, noted):** the backend's absolute 307 `Location` dropping the port is a separate robustness concern for any port-forward/proxy-with-port setup; the canonical fix is the client trailing-slash (done) or a backend `redirect_slashes=False`/relative-Location. Left as a note.

### N3 (NEW, observed) — resolve/close actions are not exposed in the Incidents UI
- `POST /api/incidents/{id}/resolve` and `/close` exist ([`backend/api/endpoints/incidents.py:176,182`](../../backend/api/endpoints/incidents.py)) but the Incidents view renders **no per-row action controls** ([`IncidentsView.tsx:303-374`](../../web/src/views/IncidentsView.tsx) shows title/severity/status/createdAt/description/tags only). The only buttons are "Logout" and "+ Report Incident". So the requested resolve/close probe could not be exercised **from the UI**.
- **Probe (via API on a real active row):** `POST /api/incidents/79bd875b-…/resolve` → **500** `Internal Server Error`, row still `active` (same D-4 persistence bug on the UPDATE path).
- **Classification:** user-action / product decision (UI should surface resolve/close) + backend D-4 (resolve 500). Recorded, not fixed in this pass.

### N4 (NEW, cosmetic) — Decisions "0 total decisions" + error banner coexist
- With the live 501, the header still shows "0 total decisions" while the `role=alert` error banner is present. Minor: the count implies success when the fetch failed. Low priority; no fix made (behavior is honest enough — the banner is authoritative).

## Per-view interaction results (desktop 1280 + mobile 390)

### Incidents
- **Desktop:** baseline empty → IN-2 guidance copy present; "+ Report Incident" opens form; submit → 500 → `role=alert` `500 — Internal Server Error`; **form remains usable** (title retained, description typed, severity reselected to `critical`); no phantom row in the list until next load (N1). Console: single expected `500 (Internal Server Error)`.
- **Mobile 390:** no horizontal scroll (`scrollWidth:390`); `main` = **100%** width (≥70% ✓); hamburger `aria-label="Open navigation"` present and **one-tap opens** the drawer (`aria-expanded:false→true`, 9 view links visible); after the D-4 probes the list shows the 2 persisted rows (N1), rows stack cleanly, no overflow. Focus indicator: Tab → 2px solid `rgb(37,99,235)` outline on hamburger and on "+ Report Incident".
- **Resolve/close:** NOT TESTED from UI (N3 — no controls exist).
- Screenshots: [incidents-desktop](web/screenshots/audit-live-r2/interact-incidents-desktop-2026-10-08T19-46-59-679Z.png), [incidents-form-error-desktop](web/screenshots/audit-live-r2/interact-incidents-form-error-desktop-2026-10-08T19-48-54-008Z.png), [incidents-mobile](web/screenshots/audit-live-r2/interact-incidents-mobile-2026-10-08T20-07-49-524Z.png), [incidents-mobile-nav-open](web/screenshots/audit-live-r2/interact-incidents-mobile-nav-open-2026-10-08T20-08-50-214Z.png).

### Decisions
- **Desktop:** live 501 → `role=alert` banner with status+detail (DC-1 ✓); no silent empty list; "New decision" button correctly disabled (`title="No decision-create route is exposed by the backend yet."`). Console: single expected `501 (Not Implemented)`.
- **Mobile 390:** banner fits (342px < 390, no overflow), no h-scroll, main 100%.
- Screenshots: [decisions-error-desktop](web/screenshots/audit-live-r2/interact-decisions-error-desktop-2026-10-08T19-50-18-139Z.png), [decisions-error-mobile](web/screenshots/audit-live-r2/interact-decisions-error-mobile-2026-10-08T20-12-00-010Z.png).

### Timeline
- **Desktop:** empty bus → guidance copy renders, **but** the spurious `role=alert` "0 — Request failed (network error)" also renders (N2). Console: `net::ERR_CONNECTION_REFUSED` from the broken redirect. Real-event render **NOT TESTED** (no NATS publish path; only GET endpoints; bus has 0 events).
- **Mobile 390:** same N2 state at mobile width; banner fits, no h-scroll, main 100%.
- Screenshots: [timeline-error-desktop](web/screenshots/audit-live-r2/interact-timeline-error-desktop-2026-10-08T19-55-00-243Z.png), [timeline-mobile](web/screenshots/audit-live-r2/interact-timeline-mobile-2026-10-08T20-12-41-416Z.png).

### Ask
- **Desktop:** initial assistant greeting present; typed question + "Send" → `POST /api/context/ask` → **202** pending shape rendered ("Request accepted (execution: pending)…"). No crash on the 202 (no `answer` field). Console clean on a fresh reload (the two `ERR_CONNECTION_REFUSED` seen mid-session were the Timeline `/events` redirect leaking through the *shared* console buffer, not Ask's own fetch — Ask opens no WebSocket).
- **Mobile 390:** no h-scroll, main 100%, input + 3 quick-question chips present/tappable.
- Screenshots: [ask-desktop](web/screenshots/audit-live-r2/interact-ask-desktop-2026-10-08T20-01-18-338Z.png), [ask-mobile](web/screenshots/audit-live-r2/interact-ask-mobile-2026-10-08T20-13-18-147Z.png).

### Inference
- **Desktop:** three honest empty states (INF-1 ✓); no error banner; live 200-empty; clean console.
- **Mobile 390:** all three empty states stack; no h-scroll; main 100%. (Console 501 + `ERR_CONNECTION_REFUSED` seen here are the shared buffer's Decisions/Timeline leftovers, not Inference fetches — all three Inference GETs are 200.)
- Screenshots: [inference-desktop](web/screenshots/audit-live-r2/interact-inference-desktop-2026-10-08T20-01-51-879Z.png), [inference-mobile](web/screenshots/audit-live-r2/interact-inference-mobile-2026-10-08T20-13-54-955Z.png).

## Mobile + focus (all five views)

| Check | Result |
|---|---|
| Horizontal scroll at 390px | **None** on all 5 views (`documentElement.scrollWidth === 390`) |
| Content width ≥70% at 390px | **100%** (`<main>` full-width) on all 5 views |
| Hamburger one-tap | **Yes** — `aria-label` toggle `Open navigation` → `Close navigation`, `aria-expanded:false→true`, drawer shows 9 view links |
| Focus indicator on Tab | **Yes** — 2px solid `rgb(37,99,235)` outline on focused controls (hamburger, "+ Report Incident") |

## Console/network errors per view (expect zero except known D-4 500s)

- **Incidents:** expected `500 (Internal Server Error)` from the D-4 create (known). No unexpected errors.
- **Decisions:** expected `501 (Not Implemented)` (real live stub; DC-1). No unexpected errors.
- **Timeline:** `net::ERR_CONNECTION_REFUSED` from the `/api/events` port-80 redirect (NEW N2 — addressed by the client.ts fix).
- **Ask:** clean on fresh load.
- **Inference:** clean (three 200 empties).
- Note: the Playwright console buffer is *shared across same-context navigations*, so errors from one view can persist into the next view's capture. Per-view attribution above was done by reloading each view fresh and re-capturing; the residual shared-buffer entries (501 + ERR_CONNECTION_REFUSED) are annotated where they appeared.

## Repo fixes made (NOT redeployed)

- [`web/src/api/client.ts` `getEvents`](../../web/src/api/client.ts): `apiFetch('/events')` → `apiFetch('/events/')` (trailing slash) with a comment, mirroring the existing `getSystems` fix. Resolves N2's client-side robustness gap. Requires a web rebuild + redeploy to take effect live.

## User-action / not-repo-fixable (record only)

- **N1** (Incidents create persists-but-500) → backend transaction/persistence (D-4 family).
- **N2 backend half** → consider `redirect_slashes=False` or a relative `Location` in the API for port-forward/ported-proxy setups (the client trailing-slash is already applied).
- **N3** → product decision to expose resolve/close in the Incidents UI + D-4 on the resolve UPDATE path.
- **TL real-event render** → blocked by no NATS publish path / empty bus; NOT TESTED end-to-end.

## Verification status

Reproduced + diagnosed live; client.ts fix made **in source only** (not built, not redeployed, not re-verified in the browser). IN-1/IN-2/DC-1/ASK/INF-1 + mobile + focus were verified directly in the live browser. N2 is expected to clear after the web image is rebuilt and redeployed; retest condition: `GET /api/events` in-browser returns 200-empty and the `timeline-error` alert is absent while `timeline-empty` copy shows.
