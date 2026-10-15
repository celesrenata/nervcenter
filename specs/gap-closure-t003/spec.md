# Gap Closure T003 — Core Inference, Evaluation & Apple Closure (G-2/G-3)

**Status:** draft · **Created:** 2026-10-14
**Task ID:** T003 (gap-closure round; see §9 ID note — this is **not** the aws-platform
`T003` v1 schema pack)
**Upstream:** [gaps1.md](../../gaps1.md) §4 — T2 (Apple personal surfaces, G-2.1–G-2.5) and
T3 (prompt1 core depth, G-3.1–G-3.5), dated 2026-10-14, evidence-verified
**Standard:** `prompt1.md` (core engineering plane) and `prompt2.md` (Personal Operations,
Phases P0–P5) are the authoritative product standards. Section citations below (`§46`,
`§66`, …) refer to them.
**Companion doc:** [plan.md](./plan.md) (task IDs, dependencies, initial todos)
**Sibling style reference:** `specs/nervcenter-uplift/` · `specs/nervecenter-aws-platform/`

---

## 1. Problem Statement

The repo is in good shape (559 Python tests green, 20 web views, all Apple targets
compile) but two spec planes remain materially unbuilt:

1. **Core "brain" (G-3).** `backend/inference/omniroute.py` is a provider-injection
   framework — no real OmniRoute transport exists anywhere (grep: no `httpx`/base URL in
   the module). `POST /api/context/ask` returns `202 {accepted:true, executed:false}`
   (`backend/api/endpoints/context.py:16`) — an honest ACK stub, not an answer.
   `synthetic-lab/` is a `.gitkeep`. gRPC is undocumented, and the web e2e masks
   `['/api/systems', '/api/decisions']` as "provable dead-end 404s" even though both
   endpoints exist and are tested.
2. **Apple personal surfaces (G-2).** The iPhone app implements only the six
   *engineering* tabs (`Overview/Agents/Goals/Incidents/Systems/Ask`); the §66 personal
   views (Today/Inbox/People/Waiting/Briefing) are missing. The Watch has no personal
   experience (§27/§60/§67 "3 NEED YOU"). The Widgets are engineering-oriented — §68
   ("3 need you / 🔴 Pharmacy / Next: Dinner 6:30") and §69 (morning brief) content are
   not there. The relay captures iMessage only; the spec's relay is also the owner of
   email/voicemail/calendar capture. And none of this is verifiable on a real device or
   simulator today (G-2.5).

This spec drives one traceable closure of G-2.1–G-2.5 and G-3.1–G-3.5. Per house
practice (gaps1.md §5), T2 and T3 are two **parallel tracks**: the Apple track depends
on Phase 1 personal APIs (owned by other gap tasks — read-only dependency), while the
inference track is independent of them.

### Scope

**In scope**

- `apple/iOS/**` — personal views + tab reorganization (G-2.1).
- `apple/Watch/**` — personal experience + complications + wrist actions (G-2.2).
- `apple/Widgets/**` + `apple/Tests/**` — §68/§69 widget content + tests (G-2.3).
- `apple/Relay/**` + `apple/Tests/RelayTests/**` — email capture via the mail-connector
  plane; voicemail + calendar scoping (G-2.4).
- `apple/` dev-sign / simulator verification path, XCUITest where practical (G-2.5).
- `backend/inference/` — real OmniRoute transport, telemetry into the routes plane
  (G-3.1).
- `backend/context/` + `backend/api/endpoints/context.py` — the ask pipeline with
  provenance (G-3.2).
- `synthetic-lab/` — evaluation corpus + replay tooling + CI regression gate (G-3.3).
- `docs/` — gRPC transport decision (G-3.4, decision not build).
- `web/tests/e2e/**` — removal of the stale known-404 masks (G-3.5).

**Out of scope**

- The Phase 1 personal reasoning planes (Person/Communication/Conversation, detection
  engines, follow-ups, drafts — gaps1 G-1.1–G-1.4). T003 consumes those APIs read-only;
  it does not build them. Where a T2 view depends on a not-yet-landed personal endpoint,
  the task degrades honestly (empty state, documented gap) rather than stubbing data.
- The personal privacy/attention policy layer (G-1.8: §35 firewall, §36 labels, §58
  budget, §59 quiet) — separate gap task; T003's ask pipeline calls the PDP pre-flight
  **only if** the routing-policy decision surface already exists, else it records the
  pre-flight as an open integration point.
- Mail-connector backend tests/commits (G-0.1/G-0.2 — Phase 0 integrity work, separate
  task). The relay email capture (G-2.4) consumes that plane.
- App Store distribution; real-user biometrics; production OmniRoute contracts beyond
  what `NERVE_OMNIROUTE_URL` exposes.
- gRPC implementation (G-3.4 is a *decision and document*, explicitly not a build).
- Any change to canonical data contracts frozen by prior specs.

### Non-goals

- No new cloud dependencies; the system must remain useful without Internet.
- No simulated backend success in any view (web-quality rule; same rule applies to the
  new Apple personal views).
- No fabricated demo data in shipped views — previews/tests only.
- No guaranteed-wake claims from the watch or relay.

---

## 2. Goals

1. **G-2 closure:** the iPhone personal views, Watch personal experience, and §68/§69
   widget content exist and render against the real backend (same standard as the
   engineering views' tests), verified on a dev-sign or simulator path — not just
   compile-checked.
2. **G-3 closure:** `/api/context/ask` returns a grounded, evidence-backed answer when
   inference is available; the 202-ACK remains only as honest degradation when it is
   not. Every routed call is observable via the routes plane (`get_route_history`).
3. **Evaluation:** `synthetic-lab/` holds a versioned evaluation corpus with replay
   tooling and a CI regression gate so inference regressions are caught, not felt.
4. **Honesty in the test suite:** no stale 404 masks; e2e asserts real responses.

---

## 3. Acceptance Criteria

AC IDs are stable (`T003.AC#`). Each maps to at least one task in
[plan.md](./plan.md) (§Task Board).

### iPhone personal views (G-2.1)

- **T003.AC1** — `apple/iOS/**` adds the §66 personal views — Today, Inbox, People,
  Waiting, Briefing — and the recommended **Today | Engineering | Ask** top-level
  reorganization. Each view is a thin client over the personal APIs
  (`/api/attention`, `/api/briefing`, `/api/calendar`, `/api/messages`,
  `/api/contacts`, `/api/waiting_on` + the G-1 plane endpoints once landed) with
  loading, empty, error, and stale states; no hardcoded fixture rows; shared modules
  (`NerveAPI`, `NerveModels`) extended with the new endpoint types, not forked.
- **T003.AC2** — Each new view renders against the real backend in the verification
  path (T003.AC12): a seeded attention item, brief, and calendar event each appear in
  their view; empty state is distinct from error state; the existing six engineering
  views remain intact and green.

### Watch personal experience (G-2.2)

- **T003.AC3** — `apple/Watch/**` adds the personal attention home per §27/§67: the
  "3 NEED YOU" / "✓ CLEAR" semantics driven by `/api/attention/now` (attention *count*,
  not raw unread count), and wrist escalation actions per §60 (resolve / snooze /
  escalate) that hit the attention API (`/api/attention/{id}/resolve|snooze`); denial
  and expiry paths are visible.

### Widgets personal content (G-2.3)

- **T003.AC4** — `apple/Widgets/**` adds the §68 home-screen widget (e.g. "3 need you /
  🔴 Pharmacy / Next: Dinner 6:30") and §69 morning-brief widget fed by
  `/api/attention/now`, `/api/briefing`, and `/api/calendar`; new `WidgetSnapshot`
  fields are unit-tested; timeline entries provide the refresh cadence; the existing
  engineering widgets keep rendering.

### Relay scope beyond iMessage (G-2.4)

- **T003.AC5** — `apple/Relay/**` captures **email** via the mail-connector plane
  (`backend/connectors/mail`: registered connectors + OAuth `token_ref`), normalizes
  into the email plane with `source: "personal-relay"` provenance; the shared
  cursor/backlog/replay engine (31 existing tests) is reused, not forked.
- **T003.AC6** — Voicemail and calendar capture are **scoped in-tree** (adapter
  skeletons + explicit capability-gap errors per house rule "unsupported
  integrations must surface explicit capability gaps with safe/manual fallback", not
  silent no-ops) and their acceptance is parked behind the same integration contract
  (see §5) — or, if the provider access decision lands first, fully implemented.
  Offline behavior follows §48; raw retention follows §49.

### Real-device / simulator verification (G-2.5)

- **T003.AC7** — A dev-sign path (or simulator-based XCUITest path) is established so
  G-2.1–G-2.4 are *verified, not compile-checked*: at minimum `swift build` +
  `swift test` (all three bundles, per the G-4.1 fix) + a device/simulator run of the
  new personal views against the local backend; gaps (no signing, no live OmniRoute)
  are stated explicitly in the evidence, per house style.

### OmniRoute integration (G-3.1)

- **T003.AC8** — `backend/inference/omniroute.py` gains a real transport: env-configured
  `NERVE_OMNIROUTE_URL` + auth header, `InferenceRoute` (primary/fallback) mapped to
  fabric requests, `OmniRouteTelemetry` recorded into the routes plane
  (`models_history` / `get_route_history`). Against a real **or recorded-fixture**
  OmniRoute: an `ask` produces a routed call and `get_route_history` shows the
  telemetry; the fallback path is exercised by test. When no endpoint is configured,
  the adapter degrades to the existing injected-client path (backwards compatible).

### Ask pipeline (G-3.2)

- **T003.AC9** — `POST /api/context/ask` runs: context compiler (extending
  `backend/context/compiler.py`) → PDP pre-flight → OmniRoute (T003.AC8) → answer with
  provenance (evidence citations resolvable by id; the pattern Apple's
  `testAskAnswerProvenance` assumes). The `202 {accepted, executed:false}` shape
  remains **only** when inference is unavailable (honest degradation, house style);
  `nerve ask "what broke?"` returns a grounded answer against seeded state; MCP/e2e
  updated to match.

### Evaluation dataset (G-3.3)

- **T003.AC10** — `synthetic-lab/` holds a versioned corpus: labeled detection cases
  (for the G-1.1 engines — recall/precision per §72), attention scoring cases (§21),
  and ask QA pairs (ground-truth answers for T003.AC9); replay tooling runs the corpus
  against the planes and reports recall/precision; a CI regression gate on the corpus
  exists and fails on regression. The corpus is deterministic (fixed seeds) and
  self-contained.

### gRPC surface (G-3.4)

- **T003.AC11** — A tracked decision (ADR in `docs/architecture/decisions/`) records
  **HTTP as the v0 transport** and defers gRPC, with the rationale (single principal
  today; MCP + REST + WS already cover all clients; gRPC cost deferred until a
  latency/throughput consumer is named). No gRPC code is written.

### e2e known-404 masks (G-3.5)

- **T003.AC12** — The stale masks are removed from **three** files:
  `web/tests/e2e/ask.spec.ts`, `views.spec.ts`, and `views-a.spec.ts` (gaps2 §3.7
  delta: the third masked file was found on the evening re-pass; `views-a`'s
  mask additionally includes `/api/tasks`, which exists). All three masked
  endpoints (`/api/systems`, `/api/decisions`, `/api/tasks`) exist and are
  tested. **`views-b.spec.ts` is excluded on purpose**: its
  `KNOWN_MISSING_BACKEND_PATHS` is a deliberate non-2xx error-UI fixture
  (409/501/503 to exercise the error banner), not a stale mask. The suites now
  assert real responses for the endpoints, and the full e2e suite is green
  (`npm run e2e`) with zero console errors under the tightened policy.

---

## 4. Constraints

- **File ownership / parallel workers:** T003 does not edit sibling gap tasks' files.
  Cross-cutting files are claimed here only where the gap mapping assigns them:
  `backend/inference/**`, `backend/context/**`, `synthetic-lab/**`,
  `web/tests/e2e/**` (mask removal), `docs/architecture/decisions/ADR-*` (gRPC),
  `apple/iOS/**`, `apple/Watch/**`, `apple/Widgets/**`, `apple/Relay/**`,
  `apple/Tests/**`, `apple/Package.swift`. Anything else (personal-plane backends,
  PDP, mail-connector tests) is a **read-only dependency** — the integration contract
  is reported to the parent, not edited.
- **Build gates:** `swift build` + per-bundle `swift test` green after every Apple
  change; `pytest tests/ -m "not integration"` green after every backend change;
  `npm run e2e` green after the mask removal.
- **No fabricated data:** personal views render API data or honest empty/error states;
  preview data stays in `#Preview` closures and tests (house rule, inherited from
  `specs/mobile-apps`).
- **Honest degradation:** when `NERVE_OMNIROUTE_URL` is unset, ask returns the 202 ACK
  and nothing simulates an answer; the relay email capture surfaces explicit
  capability gaps, not silent skips.
- **Provenance:** every ask answer carries resolvable evidence ids (§71 auditability:
  source, model used, classification); telemetry rows are written on the fallback
  path too, not only on success.
- **Determinism:** the synthetic-lab corpus and replay must be reproducible (fixed
  seeds, versioned fixtures) so the CI gate is stable.
- **No gRPC code** (AC11 is a decision document); no App Store distribution; no
  production OmniRoute contract changes.
- **ID note:** task ID **T003** here belongs to the *gap-closure* round (gaps1.md
  §5 sequencing). It does not collide in practice with `specs/nervecenter-aws-platform`
  `T003` (v1 schema pack) because that pack's IDs are scoped to its own `tasks.md`;
  cross-references in this spec always say "aws-platform T003" where needed.

---

## 5. Verification & Integration Contract

Each AC maps to a task in [plan.md](./plan.md) with exact commands and evidence
paths. Verification commands (house suite, per G-4.5):

- Python: `.venv/bin/python -m pytest tests/ -m "not integration" -q`
- Web: `cd web && npm run e2e`
- Apple: `cd apple && swift build && swift test --filter NerveAppsTests && swift test
  --filter NerveRelayTests && swift test --filter NerveSharedTests` (plus the
  XCUITest/simulator run from T003.AC7)

**Integration contract reported to the parent (per worker policy — dependencies
finished in place, not requested):**

1. **Read from Phase 1 (G-1 tasks):** T2 views + watch + widgets consume
   `/api/attention*`, `/api/briefing*`, `/api/calendar`, `/api/messages`,
   `/api/contacts`, `/api/waiting_on`, and the G-1.2 person/conversation endpoints
   once landed. Contract shape: existing flat routers (`docs/nervcenter-spec.md`
   documents the mapping per G-1.5). If a G-1 endpoint is absent at T2 build time,
   the owning view ships its empty state and the gap is logged — no stub data.
2. **Read from Phase 0 (G-0.2):** relay email capture depends on the committed
   mail-connector plane (`backend/connectors/mail/*` + `endpoints/mail_connectors.py`)
   and its tests; `token_ref`-based OAuth, no secret material in the relay.
3. **Expose to G-1.8 (privacy):** the ask pipeline's PDP pre-flight is a single call
   site (`backend/context/ask.py` → PDP); when G-1.8's routing-policy decisions land,
   only that call site changes. The OmniRoute transport exposes
   `record_telemetry(route, request, outcome)` so G-1.8 can gate tiers without
   touching the ask pipeline.
4. **Expose to CI:** `synthetic-lab/` ships a `run` entry point
   (`synthetic-lab/run.py` or equivalent) + a test that wraps it, so any CI system
   (not just this repo's) can add the gate.
5. **Apple verification path (G-2.5) is shared by all T2 tasks** — it lands first and
   is the gate for AC1–AC6 evidence.

---

## 6. Explicit non-gaps (checked; no action in T003)

- Engineering iPhone tabs (§56) — all six exist; T003 reorganizes around them, does
  not rebuild them.
- Relay iMessage engine — cursor/backlog/replay/HTTP-4xx tested (31 tests); reused.
- MCP §45 18 tools — intact; only the ask-provenance surface changes shape if
  T003.AC9 alters response fields (tracked in the e2e/MCP update step).
- Event bus / DLQ / PDP / persistence — tested and wired; unchanged.

## 7. Open questions (need a decision, inherited from gaps1.md §7)

1. **OmniRoute access:** is a real OmniRoute endpoint available from this host for
   T003.AC8 (URL/auth), or do we build against recorded fixtures first? (Default:
   fixtures first; AC8 wording covers both.)
2. **Apple signing (AC7):** which dev team/credentials target the personal-surface
   UI tests — dev-sign or simulator-only? (Default: simulator + XCUITest; dev-sign
   if credentials provided.)
3. **G-2.4 voicemail/calendar provider access:** which provider/store is available
   (Apple Mail voicemail store vs provider API; EventKit on-device)? Until decided,
   AC6's "scoped in-tree" branch applies.
