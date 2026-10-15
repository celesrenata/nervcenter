# NerveCenter — Gap Review & Closure Plan (`gaps1.md`)

**Date:** 2026-10-14
**Scope:** Review of `prompt1.md` (v0.2 spec, core engineering plane) and `prompt2.md` (Personal Operations, Phases P0–P5), against the actual code, with a live test run and "poke-around" of every plane.
**Method:** read both prompts in full; surveyed `backend/`, `mcp/`, `cli/`, `web/`, `apple/`, `deployments/`; ran `pytest` (Python), `tsc && vite build` (web), `swift build` + `swift test` (Apple); traced imports; diffed spec requirements vs. implemented surfaces.

---

## 1. Executive summary

The repo is **far more complete than the last audit snapshot** (`audit-gaps.md`, 2026-10-12) suggests. The Personal Operations plane (P0–P4: attention, messages, email, voicemail, calendar, contacts, waiting-on, briefing) is built, tested, and wired into the API, web app, and relay daemon. The "crashes along the way" the user mentioned are real and were found:

- **Crash A (hard, repo-breaking):** a half-finished, *uncommitted* mail-connector plane (`backend/connectors/mail/`) re-exports `MailConnector` from the wrong module → `import backend.api.app` failed → **every** API test failed at collection (18 files). One-line fix, applied.
- **Crash B (latent time-bomb):** `test_calendar.py::test_service_reset_hook` hard-codes reference day `2026-10-14` and relies on the *default* list window `[now, now+7d)`. It passed while the real clock was before 2026-10-14 and started failing the day after. Fixed to be clock-invariant.

After both fixes: **`pytest tests/` → 559 passed, 0 failed** (was: collection error on 18 files / 1 failure).

The genuine remaining gaps are **feature gaps, not broken code**:

1. **Uncommitted half-finished work** (68 staged files): the mail-connector plane and a web theming/Downloads feature have **zero tests** and no commit. This is the highest-integrity risk right now.
2. **prompt2 Phase P3+ (the "reasoning" layer) is largely unbuilt:** commitment/request/deadline **detection engines**, the **Unified Person model** and cross-channel **conversations**, the **Follow-Up engine**, the **drafts plane**, the 11 **§64 MCP tools**, and the 8 **§65 CLI commands**.
3. **Apple personal surfaces missing:** the iPhone/Watch apps only implement the *engineering* views (Overview/Goals/Incidents/Agents/Systems/Ask); the §66 personal views (Today/Inbox/People/Waiting/Briefing), §67 "3 NEED YOU" complication, and §68/§69 personal widget content are not there. The relay captures iMessage only (no email/voicemail/calendar).
4. **prompt1 depth items:** the OmniRoute adapter is a provider-injection framework (not wired to a real OmniRoute fabric), `/api/context/ask` returns a 202 ACK rather than an answered question, and `synthetic-lab/` (evaluation datasets) is empty.
5. **Hygiene:** stale status docs, `web/dist` build artifacts tracked in git, `swift test` only runs 1 of 3 test bundles by default, `on_event` deprecation warnings, untracked `.patches/` worker artifacts.

Everything below is ordered by impact. Each item has: what's missing (with spec §), evidence in the code, the work needed, acceptance criteria, and a rough size (S ≤ ~1h, M ~half-day, L ≥ day).

---

## 2. Verified current state (evidence, 2026-10-14)

| Plane | State | Evidence |
|---|---|---|
| Backend tests | ✅ 559 passed, 0 failed (after 2 fixes) | `.venv/bin/python -m pytest tests/ -m "not integration"` → `559 passed in 3.30s` |
| Core planes (entities/events/evidence/claims/goals/tasks/agents/compute/routes/models/decisions) | ✅ built + tested | `backend/api/endpoints/*`, 30+ test files |
| Personal planes P0–P4 (attention, messages, email, calendar, voicemail, contacts, waiting-on, briefing) | ✅ built + tested + wired | `backend/{attention,messages,email,calendar,voicemail,contacts,waiting_on,briefing}/`, routers mounted in `app.py` |
| Policy PDP, event bus (NATS, DLQ, rules), persistence (Postgres/SQLAlchemy/alembic), auth (JWT + Keycloak SSO PKCE, live-verified 2026-10-12) | ✅ | `tests/backend/test_auth_sso.py`, `events/test_dlq.py`, `audit-gaps.md` SSO note |
| MCP server (§45) | ✅ all **18** tools present | `mcp/tools_module.py::_SPEC` matches §45 list exactly |
| CLI (§47, core) | ✅ 14 commands run | `python -m cli --help` |
| Web app | ✅ `tsc && vite build` clean; **20 views** incl. Now/Messages/Email/Voicemail/Calendar/Contacts/WaitingOn/Briefing | `web/src/views/` |
| Apple package | ✅ `swift build` clean | `apple/` Package.swift, all targets compile |
| Apple tests | ⚠️ pass **only per-bundle** — default `swift test` runs just `NerveAppsTests` (2 tests); `--filter NerveRelayTests` → 31 pass, `NerveSharedTests` pass too | see G-5.3 |
| Relay daemon (`nerve-personal-relay`, §46/§47) | ✅ committed (`26ff788`), 6 Swift files + CLI, cursor/backlog/HTTP tests green | `apple/Relay/`, `apple/Tests/RelayTests/` |
| Widgets | ⚠️ present (`Small/Medium/Large` + provider + snapshot) but engineering-oriented; §68/§69 personal content not implemented | `apple/Widgets/` |
| `synthetic-lab/` | ❌ empty (`.gitkeep` only) | — |
| **Uncommitted worktree** | ⚠️ **68 staged files** — mail-connector plane + web theme/Downloads; no tests, no commit | `git status` |

---

## 3. Crashes found & fixed this session (review these diffs)

### 3.1 Crash A — broken package re-export (repo-breaking)
`backend/connectors/__init__.py` (committed at `26ff788`) does:
```python
from backend.connectors.mail import (
    MailConnector,          # ← never defined/exported there
    MailConnectorService,
    get_mail_connector_service,
)
```
The `MailConnector` Pydantic model lives in `backend/api/models.py:449` (and is imported from there by `mail/service.py:23`), but the new `backend/connectors/mail/__init__.py` — a *new, uncommitted* file — exported the other names and missed `MailConnector`. Because `backend/api/app.py` imports `get_mail_connector_service` from the package, **`import backend.api.app` raised `ImportError`**, which failed collection of every test file that builds the app (18 files) and would have crashed the API server on boot.

**Fix applied** (only change needed): `backend/connectors/mail/__init__.py` now re-exports the model:
```python
from backend.api.models import MailConnector
...
__all__ = ["MailConnector", "ImapClient", ...]
```
*Design note for the commit:* a cleaner long-term fix is to move `MailConnector`/`MailAuthMethod`/`MailConnectorStatus` out of `backend/api/models.py` into `backend/connectors/mail/` (domain model owns its own module; `api.models` re-exports for the HTTP layer). Low urgency; optional.

### 3.2 Crash B — clock-dependent calendar test (latent time-bomb)
`tests/backend/test_calendar.py::test_service_reset_hook` used `start=_day()` where `_day()` is the hard-coded constant `datetime(2026,10,14)` and called `svc.list_events()` with **no window** → default window `[now, now+7d)`. Green while `now < 2026-10-14`, red after. Second trap: even with a window, the ingested event had no `end`, so its span was a *point* on the window's left boundary and the half-open overlap check (`span[0] < we and span[1] > ws`) excluded it.

**Fix applied:** the test now ingests a 09:00–10:00 event and asserts over an explicit `at(8)–at(11)` window (before/after reset), with a comment explaining why. It also now asserts the fresh instance is empty, strengthening the reset check.

---

## 4. Gap inventory

Legend: **T0** = integrity/now · **T1** = prompt2 P3+ core (the missing "brain") · **T2** = Apple personal surfaces · **T3** = prompt1 core depth · **T4** = hygiene.

### T0 — Integrity of the in-flight work

#### G-0.1 Land or finish the uncommitted mail-connector + web work (M)
68 files are staged: the mail-connector plane (`backend/connectors/mail/*`, `endpoints/mail_connectors.py`, router mount, models) and a web feature (dark/light `ThemeContext` + `ThemeSwitcher`, `DownloadsView` + `/downloads` route + `manifest.json.example`, restyled `index.css`/tailwind, touches to ~20 views).
- **Work:** write backend tests for the mail plane (below), re-verify web e2e, then commit as 2–3 logical commits (connectors / web theme / web downloads).
- **Accept:** `git status` clean (except deliberate ignores), all suites green on the commit.

#### G-0.2 Mail-connector plane has zero tests (M)
Nothing in `tests/` references `MailConnector*` (grep: empty). Untested surface:
- `imap_client.py` — `ImapImapClient`/`StubImapClient` probe mapping (CAPABILITY ok → CONNECTED; auth reject → AUTH_EXPIRED; network fail → ERROR), `ProbeResult`.
- `oauth.py` — `build_authorization_url`, `parse_callback` (state validation), `exchange_request`, `make/validate_token_ref`.
- `service.py` — registry upsert/404 semantics, `verify()` status transitions, `reset_mail_connector_service()`.
- `endpoints/mail_connectors.py` — list/create/verify/delete HTTP contract (secret never stored, only `token_ref`).
- **Accept:** mirror the pattern of `tests/backend/test_email.py`; ~20 tests green.

#### G-0.3 Stop tracking build artifacts (S)
`web/dist/` is committed and currently staged (`M web/dist/index.html`). Regenerated bundles in git cause churn and stale-ship risk.
- **Decision:** either `git rm -r --cached web/dist` + add to `.gitignore` (Dockerfile must build in-image) or keep it only if `web/Dockerfile` deliberately ships pre-built dist (check `web/Dockerfile` first). Also `.patches/` (untracked parallel-task worker output) should be gitignored.
- **Accept:** rebuild doesn't dirty the tree; CI can't depend on committed dist.

### T1 — prompt2 Phase P3+: the personal "reasoning" layer

The planes that *collect* are done; the engines that *understand* are not.

#### G-1.1 Commitment / Request / Deadline detection (§16, §17, §18) (L)
No models, services, or endpoints exist (grep `Commitment` across `backend/`: none). Today, `AttentionItem` is only produced from manual ingest/waiting-on/calendar; nothing extracts "Alice: *I'll send the contract Friday*" → commitment, "*Can you review this?*" → request, "*due Thursday*" → deadline.
- **Work:** `backend/communications/` (or extend `messages/`) with three deterministic extractors (§21 mandates deterministic + explainable — regex/date-parser + model-assisted hooks, same shape as attention scoring); models `Commitment`, `Request`, `Deadline` in `api/models.py`; endpoints per G-1.7; feed detected items into the attention engine (they become `AttentionItem` sources).
- **Accept:** ingest a batch of sample messages → correct typed items with `why[]` explanations; 15+ unit tests incl. edge cases (§72 failure principle: recall-first for deadlines/urgent requests, precision-first for noise).

#### G-1.2 Unified Person model + cross-channel conversations (§6, §7, §32) (L)
`contacts/` is a flat VIP registry; there is no person entity linking iMessage/email/voicemail/calendar sources, no `Communication` object (§7: source, channel, direction, participants, sensitivity), and no conversation thread model (§32 "cross-channel conversation understanding").
- **Work:** `Person` (canonical id + alias resolution per §6), `Communication` (normalized, channel-agnostic), `Conversation` (thread grouping across channels, §32); resolution service that maps relay `peer_identifier` / email From / voicemail caller → one person; wire into messages/email/voicemail ingest.
- **Accept:** the §62 example scenario (same person, message + email + voicemail) produces one person, three communications, one conversation; tested.

#### G-1.3 Follow-Up engine (§57) (M)
Nothing schedules follow-ups (e.g., "check in Friday if no reply"). Attention has `snooze` but no follow-up objects, timers, or due-notification path.
- **Work:** `FollowUp` model (target item/person, due, reason, created_from); creation from commitments/requests detection (G-1.1) and user action; scheduler hook (reuse goal/task machinery or a small timer service) that raises a follow-up `AttentionItem` when due; endpoints + tests.
- **Accept:** a request with no reply produces a due follow-up item; snooze/resolve interactions work.

#### G-1.4 Drafts plane (§40 Response Assistant, §63 `/api/personal/drafts`) (M)
`email/service.py:254 draft_reply` exists but is a **rule-based echo** (returns canned strings; comment admits "An LLM-backed drafter can replace this later"). No draft store, no message drafts, no drafts API.
- **Work:** `Draft` model (channel, conversation, text, basis/evidence ids, status draft/sent/discarded — sent only via relay, §13/§41 no-impersonation); drafts endpoints (list/get/update/discard); replace the rule-based email drafter with an OmniRoute-routed drafter when inference is available, keeping the rule-based path as the honest fallback.
- **Accept:** draft appears in API + (T2) Inbox view; auditability fields per §71 (source, model used, classification).

#### G-1.5 §63 API groups — reconcile shape (S)
Spec asks for `/api/personal/{people,communications,conversations,commitments,requests,deadlines,followups,attention,briefings,drafts}`. The implementation instead uses top-level `/api/attention`, `/api/messages`, … (a deliberate, documented choice per `audit-gaps.md`).
- **Work:** either (a) accept the flat shape and record the deviation in `docs/` + this file, or (b) add a thin `router = APIRouter(prefix="/api/personal")` alias layer. Recommend (a) for now — do not grow surface area while the features are still being built — and **document the mapping** in `docs/nervcenter-spec.md`.
- **Accept:** doc notes the canonical mapping; no behavior change.

#### G-1.6 §64 — 11 personal MCP tools (M)
All 18 §45 tools exist; **none of the §64 personal tools** exist (`get_attention`, `get_daily_brief`, `get_person`, `get_conversation`, `search_communications`, `get_commitments`, `get_waiting_on`, `create_followup`, `snooze_attention`, `resolve_attention`, `draft_reply`).
- **Work:** extend `mcp/tools_module.py::_SPEC` (the pattern is uniform: name, schema, method, path, kind) once G-1.1–G-1.4 + attention actions exist. `resolve_attention`/`snooze_attention` can ship immediately against existing endpoints. "Sending communications should use separately permissioned tools" (§64) → sending tools go through the PDP with a distinct permission (§55).
- **Accept:** `tests/mcp/` updated (it asserts the tool list), 29 tools total, Zoo can call each.

#### G-1.7 §65 — personal CLI commands (S, after G-1.1–G-1.4)
`cli/commands/` has 14 core commands; no `attention`, `today`, `commitments`, `waiting`, `brief`, `people`, `communication`, `attention snooze`.
- **Work:** new command modules reusing `cli/client.py`; `nerve attention` = ranked list with `why`; `nerve attention snooze <id> tomorrow`; table output via existing `output.py`.
- **Accept:** each §65 example command runs against a seeded local backend.

#### G-1.8 Personal privacy/attention policy (§35 firewall, §36 sensitivity, §37 OmniRoute policy, §58 budget, §59 quiet periods, §28/§29 escalation) (L)
- **§35 personal/engineering firewall:** no enforcement layer separates personal context from engineering context in the context compiler (`context/compiler.py`) — a personal message could leak into an engineering `ask`. **Verify + implement** a context partition (two corpora, routing-level isolation).
- **§36 sensitivity labels:** no label model on communications; add `sensitivity` enum (public/internal/confidential) driving storage + what may be routed to external inference (§37).
- **§37 OmniRoute privacy policy:** `policy/pdp.py` + `guardrails.py` exist for mutations; extend decisions to *inference routing* (e.g., confidential content → local model tier only, §38/§39 model tiering).
- **§58 attention budget / §59 quiet periods / §28–29 escalation:** no budget/quiet-hours/escalation logic in the attention service.
- **Accept:** PDP test matrix: confidential communication never routes to a cloud model tier; quiet period suppresses notifications but not NOW items; budget caps FYI items per day.

#### G-1.9 §50 search / §51 memory extraction / §52 daily operational state (M)
`/api/search` covers the core knowledge plane. Personal search across communications/people/conversations, §51 memory extraction (durable facts from conversations → entity graph), and §52 "Daily Operational State" (the rollup behind `nerve today` / Today widget) are missing.
- **Accept:** `search_communications` works across channels; a conversation yields extracted facts as entities with provenance.

### T2 — Apple personal surfaces

#### G-2.1 iPhone personal views (§66) (L)
`apple/iOS/App/Views/` = exactly the six engineering tabs (`Overview/Agents/Goals/Incidents/Systems/AskView`) matching prompt1 §56 — so the phone app is a **prompt1-only** app. Missing: **Today / Inbox / People / Waiting / Briefing** and the recommended top-level **Today | Engineering | Ask** reorganization.
- **Work:** add the personal views (thin API clients over G-1 endpoints + existing attention/briefing/calendar), restructure the tab layout per §66, keep shared modules (`NerveAPI`, `NerveModels`) — add endpoint types for the new planes.
- **Accept:** each view renders against the real backend (same standard as the engineering views' tests).

#### G-2.2 Watch personal experience (§27, §60, §67) (M)
`apple/Watch/Views/` = `WatchHomeView/WatchApprovalsView/WatchGoalViews/WatchStopView` (engineering only). Missing: personal attention home ("3 NEED YOU" / "✓ CLEAR" complication per §67), escalation actions (§60 watch escalation: resolve/snooze/escalate from the wrist).
- **Accept:** complication shows attention count semantics, not raw unread; wrist actions hit the attention API.

#### G-2.3 Widgets personal content (§68 home screen, §69 morning brief) (M)
`apple/Widgets/` exists (Small/Medium/Large, provider, `InMemoryWidgetDataSource`, `WidgetSnapshot`) but is engineering-oriented. §68 wants "3 need you / 🔴 Pharmacy / Next: Dinner 6:30"; §69 wants the morning brief widget (actions/waiting/calendar + next deadline).
- **Work:** new widget families fed by `/api/attention/now`, `/api/briefing`, `/api/calendar`; timeline entries for refresh cadence.
- **Accept:** widget snapshots show the §68/§69 examples from seeded data; `WidgetSnapshot` test updated.

#### G-2.4 Relay scope beyond iMessage (§46–§47, §9, §14, §42) (L)
`apple/Relay/` captures Messages only (`MessageStore` tails `chat.db`, normalizes, POSTs with cursor/backlog — well tested). The spec's relay is the owner of **email** (via the mail-connector plane — the connector registry + OAuth added in T0 is the setup for this), **voicemail**, and **calendar** capture.
- **Work:** phased: (1) email via IMAP using the registered connectors + `token_ref` (the new `connectors/mail` plane is exactly this foundation); (2) voicemail (Apple Mail/`voicemail` store or provider API); (3) calendar (EventKit read-only sync). Keep the cursor/backlog/replay engine shared.
- **Accept:** each source ingests into its plane with `source: "personal-relay"` provenance; offline behavior per §48; raw retention per §49.

#### G-2.5 Widget/App personal data on real device (M)
None of the above can be exercised beyond `swift build/test` on the build host without a signing config + device; `apple/Distribution/credentials/` only has a README. Establish the dev-sign path (or simulator-based UI tests via XCUITest) so T2 work is verifiable, not just compile-checked.

### T3 — prompt1 core depth

#### G-3.1 OmniRoute is a framework, not an integration (L)
`backend/inference/omniroute.py` (`OmniRouteAdapter`) accepts *injected* provider clients (`OpenAIClient`, `AnthropicClient` in the docstring) — no HTTP call to an OmniRoute service exists anywhere (grep: no `httpx`/base URL in the module). Real behavior is mocked (`NERVE_MOCK_INFER` in e2e). Spec §28 wants NerveCenter to *be a client of the OmniRoute fabric*: route decisions → fabric call → telemetry back into the routes plane (`get_route_history` MCP exists; `models_history.py` endpoint exists — but nothing feeds it from real calls).
- **Work:** add a real OmniRoute transport (env-configured `NERVE_OMNIROUTE_URL`, auth header), map `InferenceRoute` (primary/fallback models) → fabric requests, record `OmniRouteTelemetry` into `models_history`, and wire the drafts/ask/detection (G-1.4, G-1.9, T3.2) through it with the §37 privacy policy (G-1.8) as a pre-flight PDP check.
- **Accept:** against a real (or recorded-fixture) OmniRoute: `ask` → routed call → `get_route_history` shows the telemetry; fallback path exercised by test.

#### G-3.2 `/api/context/ask` is an ACK, not an answer (L, depends on G-3.1)
`context.py:16` returns `202 {accepted:true, executed:false}` — the web/CLI/e2e are all built around this honest stub. The actual "reason about the state" loop (compile context → select route → infer → evidence-backed answer) doesn't exist end-to-end.
- **Work:** implement the ask pipeline: context compiler (extend `context/compiler.py` with the firewall from G-1.8) → PDP → OmniRoute (G-3.1) → answer with provenance (`evidence` citations, the pattern the Apple tests already assume: `testAskAnswerProvenance`). Keep the 202-ACK as the *queue* semantics only when inference is unavailable (honest degradation, per house style).
- **Accept:** `nerve ask "what broke?"` returns a grounded answer against seeded state; MCP/e2e updated; provenance ids resolvable.

#### G-3.3 `synthetic-lab/` empty — evaluation dataset (M)
Spec references a synthetic-lab/eval workstream (PERSONAL-O "evaluation dataset" §73; `specs/nervcenter-uplift` mentions it). Directory is a `.gitkeep`.
- **Work:** define the corpus: synthetic people/communications/messages batches with labeled ground truth for G-1.1 detection (recall/precision per §72), attention scoring cases (§21), and ask QA pairs for G-3.2; tooling to replay them against the planes (`synthetic-lab/` scripts + `tests/` fixtures).
- **Accept:** detection engines report recall/precision from the lab; a regression gate runs on the corpus in CI.

#### G-3.4 gRPC surface (S, optional)
Spec §(architecture) says "HTTP/gRPC interface"; only HTTP exists. Recommend: document HTTP as the v0 transport, open a tracked decision instead of building gRPC now.

#### G-3.5 e2e known-404 masks re-check (S)
`web/tests/e2e/ask.spec.ts` (and `views*`) mask `['/api/systems', '/api/decisions']` as "provable dead-end 404s", but both `endpoints/systems.py` and `endpoints/decisions.py` now exist and are tested. The mask is stale — remove it and let the suites assert real responses (this either finds nothing or surfaces a real routing bug).

### T4 — Hygiene

#### G-4.1 `swift test` runs only 1 of 3 bundles by default (S)
Plain `swift test` in `apple/` executed only `NerveAppsTests` (2 tests); `NerveRelayTests` (31) and `NerveSharedTests` required `--filter`. Root-cause the `Package.swift` test-target/platform wiring (likely a platform restriction making some bundles invisible to the default runner) and fix it, or add a `scripts/test-apple.sh` that runs all three bundles explicitly and wire it into CI/docs.

#### G-4.2 `on_event` deprecation (S)
`backend/api/wiring.py:357` uses `app.on_event("shutdown")` (686 warning occurrences per run). Migrate to FastAPI lifespan handlers.

#### G-4.3 Stale status docs (M)
`docs/implementation-status.yaml`, `docs/architecture/current-state.md`, and `audit-gaps.md` predate the personal planes (the status file references paths like `backend/events/`, `backend/knowledge/` that don't match the real tree; `implementation-status` lists personal ops as pending). Refresh them to match §2 above; keep `audit-gaps.md` as history.

#### G-4.4 JWT key-length warnings in tests (S)
`test_auth_sso.py` triggers PyJWT "weak key" warnings (32-byte HS256 keys). Use ≥32-byte random keys in test fixtures to keep the signal clean.

#### G-4.5 House-test-suite doc (S)
Document the canonical commands (`pytest -m "not integration"`, `npm run e2e`, per-bundle `swift test`) in `README.md` — currently scattered across `audit-gaps.md` and specs.

---

## 5. Sequenced closure plan

### Phase 0 — Stabilize (≈0.5 day, do first)
1. **G-0.2** mail-connector tests → **G-0.1** commit the uncommitted tree (connectors / web-theme / web-downloads) → **G-0.3** untrack `web/dist`, gitignore `.patches/`.
2. Gate: `git status` clean; 559+ Python tests, web e2e, Apple per-bundle tests all green *on the commit*.

### Phase 1 — Personal reasoning core (≈1–2 weeks; the spec's P3)
Order matters — dependencies shown:
1. **G-1.2** Person/Communication/Conversation model + ingest wiring (foundation for everything).
2. **G-1.1** commitment/request/deadline detection (feeds attention + G-1.3).
3. **G-1.3** Follow-Up engine · **G-1.4** Drafts plane (uses rule-based first; LLM later).
4. **G-1.6** §64 MCP tools (the 4 attention/waiting-on tools can ship in step 1; the rest land with their features) · **G-1.7** §65 CLI.
5. **G-1.5** document the `/api/personal` mapping (flat shape kept).
6. Gate: `tests/backend/test_communications.py`, `test_followups.py`, `test_drafts.py` green; MCP suite shows 29 tools; §62 scenario passes end-to-end.

### Phase 2 — Privacy & attention policy (≈3–5 days, parallelizable with Phase 1 step 4+)
**G-1.8** (§35 firewall, §36 labels, §37/§38/§39 routing policy, §58 budget, §59 quiet, §28/§29 escalation) → **G-1.9** (§50/§51/§52).
Gate: PDP matrix tests (confidential → local-only), budget/quiet behavior tests.

### Phase 3 — Core "brain" (≈1–2 weeks, parallel track)
**G-3.1** real OmniRoute transport + telemetry → **G-3.2** ask pipeline with provenance → **G-3.3** synthetic-lab eval corpus + CI gate (starts as soon as G-1.1 lands so detection has metrics).
**G-3.4** gRPC decision · **G-3.5** remove stale 404 masks.
Gate: `nerve ask` grounded answers; route history populated; lab recall/precision report in CI.

### Phase 4 — Apple personal surfaces (≈1–2 weeks; depends on Phase 1 APIs)
**G-2.5** signing/simulator test path first (otherwise all of Phase 4 is unverified) → **G-2.1** iPhone Today/Inbox/People/Waiting/Briefing + tab reorg → **G-2.2** Watch personal + complications → **G-2.3** §68/§69 widgets → **G-2.4** relay email (uses the new connector plane) → voicemail → calendar.
Gate: XCUITest/simulator runs of each new view against the real backend; relay e2e for email ingest.

### Phase 5 — Hygiene sweep (interleaved, ~1 day total)
**G-4.1** swift test runner · **G-4.2** lifespan · **G-4.3** doc refresh · **G-4.4** JWT test keys · **G-4.5** README test commands.

**Suggested workstream mapping to §73:** PERSONAL-F (person resolution) → G-1.2; PERSONAL-G (extraction) → G-1.1; PERSONAL-I (follow-up) → G-1.3; PERSONAL-K (drafting) → G-1.4; PERSONAL-H (attention engine) → G-1.8; PERSONAL-L/M → G-2.1/2.2; PERSONAL-O (eval) → G-3.3; PERSONAL-N (privacy) → G-1.8.

---

## 6. Explicit non-gaps (checked, no action)

- **MCP §45** — all 18 tools present and wired.
- **CLI §47 core** — 14 commands functional.
- **iPhone §56 tabs** — all six engineering views exist.
- **Attention actions (§55)** — resolve/suppress/acknowledge/snooze endpoints exist (`endpoints/attention.py`).
- **SSO** — live-verified (Keycloak PKCE, 2026-10-12).
- **Relay core engine** — cursor/backlog/replay/HTTP-4xx tested (31 tests).
- **Event bus / DLQ / PDP / persistence** — tested and wired.

## 7. Open questions (need a decision, not just work)

1. **G-0.3:** is `web/dist` intentionally committed for the Docker image (check `web/Dockerfile`), or should it be untracked?
2. **G-1.5:** keep the flat personal API shape and document the deviation, or build the `/api/personal/*` alias layer?
3. **G-3.4:** is gRPC required for v0 or is HTTP sufficient (recommend documenting and deferring)?
4. **OmniRoute access:** is a real OmniRoute endpoint available from this host for G-3.1 (URL/auth), or do we build against recorded fixtures first?
5. **Apple signing (G-2.5):** which dev team/credentials target the personal-surface UI tests?
