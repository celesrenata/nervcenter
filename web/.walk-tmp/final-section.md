
---

## Final recapture — deployed fixed bundle, TAG `bee3fa8` (2026-10-09, 13:17–14:10 UTC)

FINAL [interact] pass against the FIXED live deployment (`web` + `api` image `bee3fa8`, all pods Ready; bundle `assets/index-C-6TxAyS.js` served at `http://127.0.0.1:18321` via `port-forward svc/web`). Desktop 1280×800 + mobile 390×844 (isMobile+touch). Script: [`web/.walk-tmp/interact-final.cjs`](../../web/.walk-tmp/interact-final.cjs); machine evidence: [`web/.walk-tmp/interact-final.json`](../../web/.walk-tmp/interact-final.json). Live pre-pass smoke: `/api/health` 200, `/api/incidents/` 200 (4 rows), `/api/events/` 200, `POST /api/context/ask` 202, `/api/compute/` + `/api/routes/` 200-empty, `/api/models/history/` **501**, `/api/decisions/` **501**, SSO config `enabled:false`.

### Per-gap dispositions on the deployed bundle

| Gap | Disposition | Evidence (deployed bundle) |
|---|---|---|
| **IN-1** Report Incident → 201 → row appears | **PASS** | `POST /api/incidents` **201** captured in-network; fresh row rendered (`in1CreatedRowAppears=true`); `incident-form-success` shown. [row-actions shot](web/screenshots/audit-live-r2/interact-incidents-row-actions-desktop.png) |
| **IN-1** per-row Resolve/Close per transition map | **PASS** | Fresh active row shows **both** Resolve + Close (`in1FreshRow*=true`); `smoke incident` (closed) renders **0** action buttons; after Close the row renders **0** buttons (`in1ClosedNoActions=0`). Map: active→{in-progress,resolved,closed}, resolved→{closed}, closed→∅ (`backend/services/incident_agent.py:103`). |
| **IN-1** resolve 200 / close 200 live | **PASS** | Tab-2 Resolve → row badge flips to `resolved` (`in1Resolve200=true`, 200 on wire); Close → `closed` (200 on wire). |
| **IN-1** 409 on illegal transition surfaced verbatim | **PASS** | UI button gating makes the illegal click unreachable in a single tab (correct per the map), so the 409 was reproduced with a genuine stale-view race: tab-2 resolves, stale tab-1 (still showing `active`) clicks Resolve → `POST /api/incidents/{id}/resolve` **409**, row-level `role=alert` renders the backend detail **verbatim**: *"Incident 'e505ecdb-…' cannot transition from 'resolved' to 'resolved'"*. [409 shot](web/screenshots/audit-live-r2/interact-incidents-409-desktop.png) |
| **IN-2** empty-state guidance | **PASS (code + precedence)** | `incidents-empty` block ("No incidents recorded. Use “+ Report Incident”…") present in [`web/src/views/IncidentsView.tsx`](../../web/src/views/IncidentsView.tsx); not visually exercised because live data (4 rows) was present — correct precedence: data over empty copy. |
| **DC-1** error → `role=alert` with status+detail | **PASS** | Live 501 renders the `decisions-error` alert: *"Failed to load decisions: 501 — Decisions list endpoint requires the decisions service to be wired via app.state.services."* [shot](web/screenshots/audit-live-r2/interact-decisions-error-desktop.png) + [mobile](web/screenshots/audit-live-r2/interact-decisions-error-mobile.png) |
| **DC-1/N4** no bare "0 total decisions" next to error | **PASS** | `n4NoBareCountNextToError=true` (no "total decisions" text on page while errored); amber `decisions-unavailable` banner *"Decisions currently unavailable — see the error banner above."* visible (`dc1UnavailableBanner=true`). |
| **TL-1** no hardcoded samples; live event renders | **PASS** | After seeding **one real event** on the live NATS JetStream bus (`nervcenter.system.audit.timeline.seed`, `id=tl1-seed-20261009-audit`, published from the api pod), `GET /api/events/` 200 total=1 and Timeline renders the real event (`tl1LiveEventRendered=true`; *"TL-1 audit seed event: real bus traffic for Timeline recapture (bee3fa8)"* visible). [shot](web/screenshots/audit-live-r2/interact-timeline-desktop.png) + [mobile](web/screenshots/audit-live-r2/interact-timeline-mobile.png) |
| **TL-1/N2** trailing-slash fetch; zero console errors | **PASS** | In-browser `200 GET /api/events/` (slash) on desktop **and** mobile; `timeline`/`timeline-mobile` console-error buffers: **NONE** (no 307 port-drop, no ERR). The prior N2 retest condition is met on the deployed bundle. |
| **ASK** keep ✅ 202 pending renders | **PASS** | `POST /api/context/ask` **202**; assistant bubble renders *"Request accepted (execution: pending). No 'context' service is configured; mutation accepted but not executed."* [shot](web/screenshots/audit-live-r2/interact-ask-desktop.png) + [mobile](web/screenshots/audit-live-r2/interact-ask-mobile.png) |
| **INF-1** empty-state guidance (compute/routes/model-history) | **PASS** | All three `inference-empty-*` states render (`inf1EmptyStates=[true,true,true]`); the live `/api/models/history` **501** is absorbed into guidance — **no** `role=alert` red banner (`inf1NoRedAlert=true`; per-section EmptyState design, not a fetch-error banner). [shot](web/screenshots/audit-live-r2/interact-inference-desktop.png) + [mobile](web/screenshots/audit-live-r2/interact-inference-mobile.png) |
| **Mobile 390** ≥70% content / hamburger / no h-scroll | **PASS** | `<main>` width 390/390 = **100%**; h-scroll delta **0** on Incidents, drawer-open, and Inference; hamburger opens in one tap (`aria-expanded` → true) **and stays clickable while open** — second tap closes the drawer (walk-round fix verified: `mobileHamburgerClickableWhileOpen=true`). [drawer shot](web/screenshots/audit-live-r2/interact-incidents-mobile-nav-open.png) |
| **Focus ring on Tab** | **PASS** | Programmatic focus on the Systems nav link: computed `outline: solid 2px rgb(37,99,235)` + visible in the [focus clip](web/screenshots/audit-live-r2/interact-focus-ring-desktop.png). |
| **SVG icons + aria-current** | **PASS** | 10/10 `nav#app-nav` links contain an inline `<svg>`; exactly one `[aria-current="page"]` = "Overview" on `/`. |

### Console/network per view (deployed bundle)

- Zero **JS exceptions** in every per-view console buffer (incidents, decisions, timeline, ask, inference, overview — desktop and mobile).
- Browser resource logs contain only the **expected live 501** (`GET /api/decisions`, whose UI expression is the N4 banner) and the **intentional 409** from the IN-1 stale-view probe. No 3xx port-drop, no `ERR_CONNECTION_REFUSED`, no other 4xx/5xx.
- Per-view API status captured in `interact-final.json` (`apiStatus`): each view hit only its intended endpoints with the expected codes (200/201/202/409/501).

### New defects found

- **None repo-fixable** on the deployed bundle — no `web/src` changes were required; nothing fixed in-repo, nothing redeployed.
- Non-defect observations (record only, backend scope): `/api/models/history` returns a bare 501 while sibling list endpoints return the 200 wrapper; InferenceView already degrades honestly, so no UI action. The 501 is logged by the browser as a failed resource (console noise) — acceptable under the honest-empty contract.
- Data note: the recapture added real rows to the live DB (incidents created/resolved/closed via the UI; `r2 curl probe` remains `active`) and one seeded bus event (`tl1-seed-20261009-audit`, retained in the JetStream stream). All consistent with "real data in views is fine".

### Screenshots (14, all non-blank, overwritten in `web/screenshots/audit-live-r2/`)

`interact-incidents-desktop`, `interact-incidents-row-actions-desktop`, `interact-incidents-409-desktop`, `interact-incidents-mobile`, `interact-incidents-mobile-nav-open`, `interact-decisions-error-desktop`, `interact-decisions-error-mobile`, `interact-timeline-desktop`, `interact-timeline-mobile`, `interact-ask-desktop`, `interact-ask-mobile`, `interact-inference-desktop`, `interact-inference-mobile`, `interact-focus-ring-desktop`. (Legacy timestamped `interact-*` PNGs from the 2026-10-08 run remain in the same directory; the plain-name files above are the r2-final captures.)

### Verdict

All five [interact] views on the `bee3fa8` bundle: **PASS**. Prior gaps IN-1, IN-2, DC-1, TL-1, ASK, INF-1 and the N2/N3/N4 side-fixes are verified fixed **against the deployed bundle** (live deployment via port-forward, revision `bee3fa8`, bundle `index-C-6TxAyS.js`). No retest conditions outstanding.
