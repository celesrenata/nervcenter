# Plan: Personal Reasoning & Policy Closure (G-1)

**Feature:** personal-reasoning-policy-closure · **Spec:** [`spec.md`](./spec.md) · **Tasks:** [`tasks.md`](./tasks.md)
**Gap source:** [gaps1.md](../../gaps1.md) G-1.1–G-1.9 (Phase 1 "Personal reasoning core" + Phase 2 "Privacy & attention policy")

## Ground Truth (2026-10-14)

| Area | State | Evidence |
|------|-------|----------|
| Personal planes P0–P4 | ✅ built + tested (559 passing) | `backend/{attention,messages,email,voicemail,calendar,contacts,waiting_on,briefing}/`, `gaps1.md` §2 |
| Person/Communication/cross-channel Conversation | ❌ absent; flat VIP `Contact` + per-channel message-thread `Conversation` only | `backend/api/models.py:570` (`Contact`), `backend/api/models.py:310` (per-(peer, channel) thread); grep `Person\|Communication\|Commitment` domain classes in `backend/` → none |
| Detection (§16–§18) | ❌ absent | grep `Commitment` across `backend/` → 0 hits |
| Follow-Up objects/scheduler | ❌ absent; one-shot draft helper only | `backend/waiting_on/service.py:231` (`follow_up` drafts text, schedules nothing) |
| Drafts plane | ❌ absent; rule-based email echo only | `backend/email/service.py:254` (comment: "An LLM-backed drafter can replace this later") |
| API shape | flat top-level routers (`/api/attention`, `/api/messages`, …); §63 `/api/personal/*` undocumented | `backend/api/endpoints/attention.py:38`, `waiting_on.py:50`, `messages.py:45`, `briefing.py:25`, `email.py:43`; `gaps1.md` G-1.5 |
| MCP tools | 18 §45 tools; 0 §64 personal tools; suite hard-asserts 18 | `mcp/tools_module.py:134` (`_SPEC`), `tests/mcp/test_mcp_tools.py:59` (`assert len(ALL_TOOLS) == 18`), `tests/mcp/test_mcp_wire.py:51` |
| CLI | 12 core command groups; no §65 personal commands | `cli/main.py` `ALL_COMMANDS` |
| Policy PDP | mutation decisions only (default-deny, explicit-deny precedence, approval bindings) | `backend/policy/pdp.py:585` (`PolicyDecisionPoint`); no inference-routing decisions |
| Context compiler | no personal/engineering partition | `backend/context/compiler.py:78` (`ContextCompiler`); `ContextSource` has no partition field |
| Attention policy | deterministic `_score` with `why[]`; no budget/quiet/escalation/adaptive-escalation | `backend/attention/service.py:227` |
| Attention actions | resolve/suppress/acknowledge/snooze endpoints exist | `backend/api/endpoints/attention.py:147–167` |
| Persistence (personal) | in-memory singletons + `reset_*` hooks; no personal tables in `backend/persistence/models/` | `backend/persistence/models/*` (no attention/communication tables) |

## Architecture Decisions

1. **New packages, not new top-level API prefixes.** `backend/communications/`
   (models, resolution, detection, search, memory extraction),
   `backend/followups/`, `backend/drafts/` — mirroring the existing house
   layout (`backend/<plane>/<service>.py` + `backend/api/endpoints/<plane>.py`).
   The flat API shape is kept (G-1.5 option (a)); §63 `/api/personal/*` names
   are *mapped* in `docs/nervcenter-spec.md`, not mirrored as routes.
2. **Person is canonical, identities are links.** `Person` owns
   `ContactIdentity` records (kind ∈ email|phone|messages|voicemail|calendar,
   value, channel, source). Resolution is conservative (§6): deterministic
   match on contact value first; same-display-name + different values →
   `PROPOSED` link, never auto-merged; merge is an explicit endpoint call.
   The existing flat `Contact` (VIP registry) becomes a view: `is_vip` moves
   to `Person`, `Contact` endpoints keep working by delegating.
3. **Detection is a pure function over `Communication`.** Each extractor
   (`detect_commitments`, `detect_requests`, `detect_deadlines`) takes a
   normalized `Communication` and returns typed findings with `why[]`.
   Date parsing is a shared deterministic helper (explicit ISO, relative
   "tomorrow/next week/by Tuesday", "remind me" phrasings). A
   `InferenceAssist` interface (off by default, policy-gated per AC-R14) is
   the only extension point for model-assist; it is a *refiner*, never the
   sole detector, so the §21 deterministic+explainable contract holds with it
   off. Findings emit §8 events and become `AttentionItem` sources through
   the existing `AttentionService` (no changes to attention's `_score`).
4. **Follow-Up is a first-class timer, reusing attention as its clock.**
   `FollowUp` (target_kind/target_id/person_id/due_at/reason/created_from/
   status) → on due, the engine creates a `FollowUp`-sourced `AttentionItem`
   (§57 shape) and fires `followup.triggered`. Waiting-on items with no reply
   get a `FollowUp` at ingest (configurable default 48h). Snooze/resolve on
   the attention item propagates back to the follow-up (Wait/Forget).
5. **Drafts are objects with a status machine.** `DRAFT → SENT|DISCARDED`;
   `SENT` is reachable **only** via the relay send path (out of scope here) —
   the drafts API can create/patch/discard but not send (§13/§41). Each draft
   records `basis[]` (evidence/communication refs) and `model_used`
   (§71). The rule-based drafter stays the default; the model-assisted
   path goes through the AC-R14 inference-routing decision before any
   inference call.
6. **Policy extensions, not a second PDP.** Inference routing reuses
   `PolicyDecisionPoint` mechanics: a new decision type `INFER_ROUTE` with
   conditions on `sensitivity` + `privacy=LOCAL_ONLY` + `remote_allowed`;
   explicit DENY (confidential/PRIVATE → no remote) takes precedence over
   ALLOW (low-sensitivity → remote ok). Default deny → local-only tier.
   Context firewall (§35) is a partition flag on `ContextSource` (
   `partition: "personal" | "engineering"`): engineering compiles never read
   personal communications unless an explicit relationship link
   (`conversation ↔ goal`) grants scoped access.
7. **Attention budget/quiet/escalation live in `backend/attention/`** as
   policy wrappers around the existing service: budget caps FYI items/day
   and bundles the overflow into the briefing; quiet periods flip a
   `notify` flag (items stay in NOW); escalation is deadline-driven
   (TODAY → NOW as a deadline nears, §28) plus a per-person/channel
   adaptive-preference record (§29, user-editable).
8. **MCP + CLI are thin layers over the new endpoints.** 11 §64 tools added
   to `_SPEC` in the uniform (name, description, properties, required,
   method, path, kind) shape → 29 total; tests updated to assert the new
   count/names. CLI gains `attention`, `today`, `commitments`, `waiting`,
   `brief`, `people`, `communication` groups via `cli/client.py` +
   `cli/output.py` (table + `--json`, exit codes 0/2/127).

## Dependency Graph

```text
R101 models+resolution ──┬─► R102 ingest wiring ──┬─► R103 detection ──┬─► R104 followups
                         │                        ├─► R105 drafts      ├─► R106 followup attention wiring
                         │                        └─► R107 policy firewall/labels/routing ──┤
                         │                                                                     │
                         └─► R108 attention budget/quiet/escalation ────────────────────────────┼─► R112 MCP tools
                                                                                               │   R113 CLI
                         R109 §63 mapping docs + operational state (§52) ──► R110 search/memory ┘
R111 final evidence gate depends on R101–R110 (MCP/CLI may land as their features do)
```

Execution waves (per tasks.md):
- **Wave 1 (foundation):** R101, R107-policy (firewall+labels+inference routing are
  needed before any model-assist hook is exercised).
- **Wave 2 (reasoning core):** R102 → R103 → R104 + R105 (parallel after R102) → R108.
- **Wave 3 (surface layer):** R106, R109, R110 (parallel); R111 evidence.
- **Wave 4 (access layers):** R112 (MCP), R113 (CLI) — each tool/command lands
  when its backing endpoint exists (per G-1.6/G-1.7 in gaps1).

## File Ownership (single owner per path)

| Owner task | Paths |
|-----------|-------|
| R101–R106 (one backend worker) | `backend/communications/**`, `backend/followups/**`, `backend/drafts/**`, `backend/api/models.py` (new domain models), `backend/api/endpoints/{people,communications,conversations,commitments,requests,deadlines,followups,drafts}.py`, `backend/api/app.py` (router registration), `backend/messages/**`, `backend/email/**`, `backend/voicemail/**` (ingest hooks only), `tests/backend/test_{communications,detection,followups,drafts}.py` |
| R107 | `backend/policy/**` (inference-routing decision type), `backend/context/compiler.py` (partition), `tests/backend/test_personal_policy.py` |
| R108 | `backend/attention/**` (budget/quiet/escalation wrappers + models), `backend/briefing/service.py` (bundling hook only), `tests/backend/test_attention_policy.py` (or extend `test_attention.py`) |
| R109 | `docs/nervcenter-spec.md` (§63 mapping table), `backend/briefing/**` (operational-state rollup), `tests/backend/test_operational_state.py` |
| R110 | `backend/communications/search.py`, `backend/communications/memory.py`, `backend/api/endpoints/communications.py` (search route), entity-graph write path for extracted facts, `tests/backend/test_personal_search.py` |
| R111 | `docs/implementation-status.yaml` (workstream + evidence), `specs/personal-reasoning-policy-closure/tasks.md` (verification log) |
| R112 | `mcp/tools_module.py` (`_SPEC` + handlers), `tests/mcp/**` |
| R113 | `cli/commands/{attention,today,commitments,waiting,brief,people,communication}.py`, `cli/main.py` (`ALL_COMMANDS`) |

Cross-boundary rule: R112/R113 may *read* the endpoint contract (OpenAPI) but
not modify it; endpoint defects go back to R101–R106 as follow-ups. R107 may
read the communication models (R101) but the label field contract is owned by
R101 (single field `sensitivity` on `Communication`).

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Detection recall fails on realistic text (§72) | Deterministic extractor + labeled fixtures from day one; recall-first fixtures are hard ACs (AC-R05); synthetic-lab (G-3.3) takes over regression later |
| Identity over-merge poisons the person graph | Conservative matching (§6): value-equality auto-links, name-only stays `PROPOSED`; explicit merge endpoint; negative tests in AC-R02 |
| Personal content leaks into engineering context (§35) | Partition flag enforced in the compiler (not just by convention) + firewall tests with seeded personal data (AC-R12) |
| Rule-based drafts feel broken vs. "assistant" | Spec is explicit: rule-based is the *honest fallback* (house style); model-assist is an interface, not a v0 promise; no-impersonation keeps `sent` out of the API entirely |
| MCP test suite breakage mid-feature | Tools land in small batches; `tests/mcp/` updated in the same task as each batch; final count asserted only at R112 completion |
| In-memory services don't survive restarts (personal data loss) | Assumption: house-style in-memory is acceptable for v0 (matches P0–P4); persistence adapter is a recorded follow-up, not hidden debt |
| Real OmniRoute unavailable (gaps1 open question #4) | All model-assist paths are policy-gated interfaces with a stub client for tests; deterministic path is the contract (AC-R04) |

## Initial Todos

Derived from tasks.md; the first wave starts here:

- [ ] R101: Add `Person`/`ContactIdentity`/`Communication`/`Conversation` models + resolution service (`backend/communications/`); migrate VIP flag to `Person`; `tests/backend/test_communications.py` green (AC-R01, AC-R02)
- [ ] R107: Context firewall partition + `sensitivity` label model + `INFER_ROUTE` PDP decision type with the §37 privacy metadata; `tests/backend/test_personal_policy.py` matrix green (AC-R12, AC-R13, AC-R14)
- [ ] R102: Wire resolution + `Communication` normalization into messages/email/voicemail/calendar ingest; §62 scenario test green (AC-R03)
- [ ] R103: Commitment/request/deadline extractors + `why[]` + §8 events + attention-source feed; `tests/backend/test_detection.py` ≥15 green (AC-R04, AC-R05, AC-R06)
- [ ] R104: `FollowUp` model + engine + due→attention promotion + follow-up actions; waiting-on hook; tests green (AC-R07)
- [ ] R105: `Draft` model + drafts endpoints + rule-based fallback + policy-gated model-assist path; tests green (AC-R08)
- [ ] R108: Attention budget/quiet periods/deadline escalation/adaptive escalation; tests green (AC-R15)
- [ ] R106: Wire follow-up/detection attention items end-to-end with escalation + budget (integration tests)
- [ ] R109: §63 mapping table in `docs/nervcenter-spec.md` + `GET /api/briefing/operational` rollup; tests green (AC-R09, AC-R17)
- [ ] R110: Cross-channel search + memory extraction to entity graph with provenance; tests green (AC-R16)
- [ ] R112: 11 §64 MCP tools + `tests/mcp/` updates (29 total) (AC-R10)
- [ ] R113: §65 CLI commands (`attention`, `today`, `commitments`, `waiting`, `brief`, `people`, `communication`) (AC-R11)
- [ ] R111: Evidence gate — full pytest, MCP suite, CLI smoke, §61/§62 scenarios; `docs/implementation-status.yaml` entry (AC-R18)

## Exit Criteria (from spec)

AC-R01–AC-R18 in [`spec.md`](./spec.md) — each maps to a task's verification
section in [tasks.md](./tasks.md).
