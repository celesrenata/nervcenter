# Tasks: NerveCenter AWS Platform

**Spec:** [`spec.md`](./spec.md) · **Plan:** [`plan.md`](./plan.md)

IDs are stable: **T001–T030**. Acceptance criteria are stable per task (`T0nn.AC#`) so plan/spec and reviews can cross-reference them.

> **Target-file note (no invented repo facts):** the platform lands in **new file ownership** per the ownership map produced by **T006** (plan rule R3/R1). Target paths below are the *intended* ownership areas; where a path overlaps an existing directory (`backend/`, `web/`, `apple/`, `mcp/`, `cli/`, `sdk/`, `schemas/`), C0's gap doc (`docs/architecture/nervecenter-aws-platform-gap.md`) records which existing files are extended vs replaced. Final exact filenames are fixed by T006 and each task's AC, not assumed here.

## Task Board

| ID | Workstream | Title | Phase | Deps |
|----|-----------|-------|-------|------|
| T001 | C0 | Discovery record (gap doc) — done | 0 | — |
| T002 | C1 | `nc://` URI grammar freeze | 1 | T001 |
| T003 | C1 | v1 schema pack (18 entities) | 1 | T002 |
| T004 | C1 | ADR set (Cedar, Temporal) | 1 | T001 |
| T005 | C1 | Automation DSL + Zoo validator | 1 | T002, T003 |
| T006 | C1 | Dependency DAG + file-ownership map | 1 | T002, T003, T004 |
| T007 | C2 | Resource registry | 2 | T002, T003 |
| T008 | C4 | PDP (single policy boundary) | 2 | T002, T003, T004 |
| T009 | C4 | Policy docs + simulations | 2 | T008 |
| T010 | C4 | Principals + scoped tokens | 2 | T008 |
| T011 | C3 | Event normalizer | 2 | T002, T003 |
| T012 | C3 | Durable event bus (DLQ/quarantine/replay/redaction) | 2 | T011 |
| T013 | C3 | Events API | 2 | T012 |
| T014 | C5 | Temporal workflow engine | 3 | T003, T008 |
| T015 | C5 | Approval gates + provenance contract + approvals API | 3 | T008, T014 |
| T016 | C5 | Versioned defs + durable migration + traces | 3 | T014 |
| T017 | C6 | Functions (K3s Jobs MVP) | 3 | T008, T010 |
| T018 | C8–C12 | Connector SDK protocol | 4 | T002, T003, T007, T008 |
| T019 | C8 | Home & telemetry connectors (HA, Prometheus, InfluxDB2, Grafana) | 4 | T018 |
| T020 | C9 | OmniRoute connector | 4 | T018 |
| T021 | C9 | Nextcloud + S3 (local + AWS) | 4 | T018 |
| T022 | C10 | Gmail (N accounts) + IMAP fallback | 4 | T018 |
| T023 | C11 | NFS + ComfyUI + Echo/Alexa | 4 | T018 |
| T024 | C12 | iPhone Photos + HealthKit | 4 | T018, T026 |
| T025 | C13 | Attention (+ wake-assist) | 5 | T014, T015, T026 |
| T026 | C14 | Ideas (Goal, budgets, checkpoints) | 5 | T014, T016 |
| T027 | C15 | Web console (against mocks) | 5 | T003 (mocks), T006 |
| T028 | C16 | iOS (approvals/attention, recovery controls) | 5 | T027 (patterns), T025, T026 |
| T029 | C7 | LocalStack lab | 6 | T006, T012 |
| T030 | C17 | Integration / fault sim / canonical demo | 7 | T007–T029 |

---

## C0 — Discovery

### T001 — Discovery record (gap doc)
- **Workstream:** NC-WS-000 · **Phase:** 0 · **Status:** DONE
- **Acceptance criteria**
  - T001.AC1: `docs/architecture/nervecenter-aws-platform-gap.md` exists and is evidence-based, citing file/route/test references (no invented facts).
  - T001.AC2: Records which existing subsystems (`backend/`, `web/`, `apple/`, `mcp/`, `cli/`, `sdk/`) are extended vs replaced, and the contract evidence feeding Phase 1.
- **Target files:** `docs/architecture/nervecenter-aws-platform-gap.md` (owned by C0).
- **Dependencies:** —
- **Verification:** manual review of the gap doc; spot-check ≥5 cited file/route/test references against the repo.

## C1 — Contracts & schema pack

### T002 — `nc://` URI grammar freeze
- **Workstream:** NC-WS-001 · **Phase:** 1
- **Acceptance criteria**
  - T002.AC1: A versioned, deterministic BNF/EBNF production for `nc://` exists and parses `nc://personal/homeassistant/home/devices/bedroom-lamp`.
  - T002.AC2: Grammar enforces case-sensitivity and a single canonical URI per resource (NC-REQ-001); aliases/relations are not second identities.
  - T002.AC3: URIs resolve from registry data without live connector contact.
- **Target files:** `schemas/` (URI grammar module), `docs/architecture/` grammar ADR.
- **Dependencies:** T001
- **Verification:** unit tests parse/round-trip a corpus of valid + invalid URIs; lint fails on non-canonical forms.

### T003 — v1 schema pack (18 entities)
- **Workstream:** NC-WS-001 · **Phase:** 1
- **Acceptance criteria**
  - T003.AC1: All 18 mandatory entities (spec §3) have versioned v1 schemas.
  - T003.AC2: Every `Resource` carries exactly one sensitivity class (spec §3); `SecretReference` never carries secret material (NC-CAP-008).
  - T003.AC3: Provenance fields present on `Event`, `WorkflowExecution`, `AuditEntry` (NC-REQ-005/006).
- **Target files:** `schemas/` (entity schema pack).
- **Dependencies:** T002
- **Verification:** schema-validation test suite over fixtures for all 18 entities; CI lint passes.

### T004 — ADR set (Cedar, Temporal)
- **Workstream:** NC-WS-001 · **Phase:** 1
- **Acceptance criteria**
  - T004.AC1: ADR for policy language — **Cedar or an auditable language** (NC-REQ-002) — with rationale and auditability argument.
  - T004.AC2: ADR for **Temporal-primary** durable workflow runtime (NC-REQ-003).
  - T004.AC3: ADR set records every Phase 1 contract decision with a citation to the C0 gap doc (T001).
- **Target files:** `docs/architecture/` ADR folder.
- **Dependencies:** T001
- **Verification:** manual review; each ADR has context/decision/consequences and a C0 citation.

### T005 — Automation DSL + Zoo validator
- **Workstream:** NC-WS-001 · **Phase:** 1
- **Acceptance criteria**
  - T005.AC1: `apiVersion nervecenter.dev/v1alpha1`, `kind Automation` schema with `match` / `controls` / `workflow.steps` (`inference`, `attention.create`, `notification.dispatch`, `resource.action`, `human.wait`).
  - T005.AC2: **Validator written by Zoo** rejects arbitrary Python and any non-CEL-like safe expression (NC-CAP-004); recursion/cycle detection present.
  - T005.AC3: `controls` enforces debounce, cooldown, max firing rates, DST-safe schedules; dry-run/preview supported.
- **Target files:** `schemas/` (Automation schema), validator module (path per T006).
- **Dependencies:** T002, T003
- **Verification:** validator test suite with valid/invalid/injection Attempt fixtures; DST schedule fuzz tests.

### T006 — Dependency DAG + file-ownership map
- **Workstream:** NC-WS-001 · **Phase:** 1
- **Acceptance criteria**
  - T006.AC1: DAG maps NC-WS-000…017 → owned file paths, with no path owned by >1 workstream (rule R1).
  - T006.AC2: Contested/legacy paths flagged for parent assignment before work starts.
  - T006.AC3: Extends `docs/dependency-graph.yaml` rather than duplicating it.
- **Target files:** `docs/dependency-graph.yaml`, `docs/architecture/` ownership map.
- **Dependencies:** T002, T003, T004
- **Verification:** script asserts single-owner-per-path; parent review signs off.

## C2 — Resource registry

### T007 — Resource registry
- **Workstream:** NC-WS-002 · **Phase:** 2
- **Acceptance criteria**
  - T007.AC1: NC-API-001/002/003/004 implemented: namespaces, connectors, resources (CRUD/lookup, aliases, relations, snapshots, capabilities).
  - T007.AC2: **Stable canonical identity across restart** — re-registration of the same connector is idempotent, same `nc://` URI (NC-REQ-001).
  - T007.AC3: Read-only discover first; discover has no mutation side effects (NC-CAP-002).
- **Target files:** registry module + API handlers (path per T006), `schemas/` (entity pack reuse).
- **Dependencies:** T002, T003
- **Verification:** integration test: register → restart → re-discover yields identical IDs; API contract tests for all four groups.

## C4 — PDP / IAM

### T008 — PDP (single policy boundary)
- **Workstream:** NC-WS-004 · **Phase:** 2
- **Acceptance criteria**
  - T008.AC1: Single PDP answers `principal + action + resource + context → ALLOW/DENY + reason` (NC-REQ-002).
  - T008.AC2: **Default DENY**; **explicit deny precedence** over allow.
  - T008.AC3: **Re-check at execution** — authorization re-evaluated per action, including mid-workflow; no component evaluates policy for itself.
- **Target files:** PDP module (path per T006).
- **Dependencies:** T002, T003, T004
- **Verification:** decision-table tests (allow/deny/explicit-deny/default-deny); test asserts an unauthorized action is DENIED and an `AuditEntry` is written.

### T009 — Policy docs + simulations
- **Workstream:** NC-WS-004 · **Phase:** 2
- **Acceptance criteria**
  - T009.AC1: NC-API-012 serves versioned Cedar-style policy documents.
  - T009.AC2: NC-API-013 `policy-simulations` performs dry-run evaluation returning `ALLOW/DENY + reason` without side effects.
- **Target files:** policy API handlers (path per T006).
- **Dependencies:** T008
- **Verification:** API tests: version bump changes evaluation; simulation is read-only.

### T010 — Principals + scoped tokens
- **Workstream:** NC-WS-004 · **Phase:** 2
- **Acceptance criteria**
  - T010.AC1: NC-API-011 manages principals and issues **hashed scoped service tokens** only (NC-REQ-002).
  - T010.AC2: **No wildcard issuance** to agents/functions; token scope is verifiable and revocable.
- **Target files:** principal/token modules (path per T006).
- **Dependencies:** T008
- **Verification:** token tests: wildcard request rejected; scoped token honored only within scope; revocation propagates.

## C3 — Event fabric

### T011 — Event normalizer
- **Workstream:** NC-WS-003 · **Phase:** 2
- **Acceptance criteria**
  - T011.AC1: CloudEvents-in-spirit envelope: `id`, `source` (canonical `nc://` URI), `type`, `subject`, `time` (event-time), `observed` (observed-time), `datacontenttype`, partition key, idempotency key, sensitivity class, provenance (connector instance + raw payload hash).
  - T011.AC2: Raw payload stored **opaque, in encrypted object storage**; never inlined in the bus (NC-CAP-003).
  - T011.AC3: Dedupes across connectors (two Gmail identities → no cross-account leak).
- **Target files:** normalizer module (path per T006).
- **Dependencies:** T002, T003
- **Verification:** fixture-driven normalization tests incl. two-identity dedup; encryption-at-rest assertion.

### T012 — Durable event bus
- **Workstream:** NC-WS-003 · **Phase:** 2
- **Acceptance criteria**
  - T012.AC1: **At-least-once only, with idempotent consumers** (NC-CAP-003).
  - T012.AC2: **DLQ, quarantine, replay, redaction all present** and exercised.
  - T012.AC3: Crash recovery does not duplicate an external mutation (shared evidence with NC-MS-002).
- **Target files:** bus module (path per T006).
- **Dependencies:** T011
- **Verification:** consumer-crash/restart test shows no duplicate external mutation; DLQ/quarantine/replay/redaction each have a passing test.

### T013 — Events API
- **Workstream:** NC-WS-003 · **Phase:** 2
- **Acceptance criteria**
  - T013.AC1: NC-API-005 exposes publish/query, replay, quarantine/DLQ operations, redaction.
  - T013.AC2: Every operation is policy-checked and audit-logged (NC-REQ-002/006).
- **Target files:** events API handlers (path per T006).
- **Dependencies:** T012
- **Verification:** API contract tests for each sub-operation; unauthorized replay attempt DENIED + audited.

## C5 — Durable workflows

### T014 — Temporal workflow engine
- **Workstream:** NC-WS-005 · **Phase:** 3
- **Acceptance criteria**
  - T014.AC1: Temporal-primary engine supports DAG, join, timers, **bounded** retries, cancellation, compensation (NC-CAP-005).
  - T014.AC2: NC-API-008 start/status/cancel/compensate; **durable execution** — restart recovers state (NC-REQ-003).
  - T014.AC3: Each action in an execution triggers a PDP re-check (NC-REQ-002).
- **Target files:** workflow engine + execution API (path per T006).
- **Dependencies:** T003, T008
- **Verification:** queue→join→approval→retry workflow survives a process restart (restore test); unauthorized action mid-flow → DENY.

### T015 — Approval gates + provenance contract + approvals API
- **Workstream:** NC-WS-005 · **Phase:** 3
- **Acceptance criteria**
  - T015.AC1: Human `human.wait` gate blocks execution until approval; approval **scoped to an immutable payload with expiry** (NC-REQ-004).
  - T015.AC2: NC-API-014 create/approve/deny enforces expiry; provenance contract carries all NC-CAP-015 JSON fields.
  - T015.AC3: Every approval state transition writes an `AuditEntry` (NC-REQ-006).
- **Target files:** approval module + API (path per T006).
- **Dependencies:** T008, T014
- **Verification:** approval-expiry test (expired approval no longer valid); provenance-contract field-coverage test.

### T016 — Versioned defs + durable migration + traces
- **Workstream:** NC-WS-005 · **Phase:** 3
- **Acceptance criteria**
  - T016.AC1: NC-API-007 serves **versioned** WorkflowDefinitions; **durable migration** of in-flight executions across versions.
  - T016.AC2: **OTel correlation** on executions (NC-CAP-009); traces retrievable as audit evidence.
- **Target files:** versioning/migration module + tracing (path per T006).
- **Dependencies:** T014
- **Verification:** version-bump migration test with a live execution; trace-capture assertion.

## C6 — Functions

### T017 — Functions (K3s Jobs MVP)
- **Workstream:** NC-WS-006 · **Phase:** 3
- **Acceptance criteria**
  - T017.AC1: **K3s Jobs** run OCI images with `nonroot`, `seccomp`, read-only rootfs, egress policies, deadline, quotas, **minimal secret mounts** (NC-CAP-006).
  - T017.AC2: A function is a policy principal; execution re-checked by PDP (NC-REQ-002); no wildcard token (NC-REQ-002).
  - T017.AC3: NC-API-009 exposes spec/job/egress/quota/secret-mount config.
- **Target files:** function runtime + API (path per T006).
- **Dependencies:** T008, T010
- **Verification:** **function with restricted egress** test (blocked egress logged + denied); secret-mount minimality assertion.

## C8–C12 — Connectors

### T018 — Connector SDK protocol
- **Workstream:** all connector workstreams · **Phase:** 4
- **Acceptance criteria**
  - T018.AC1: SDK exposes `capabilities` / `discover` / `snapshot` / `subscribe` / `execute` / `health` (NC-CAP-002).
  - T018.AC2: **Read-only discover first**; `execute` only for declared service calls; mutation approval-gated with scope-aware policy check at each action.
  - T018.AC3: **Outage → stale status, not deletion** (NC-REQ-008); unhealthy connectors degrade to read-only/stale.
- **Target files:** SDK protocol layer + base adapter (path per T006); reuses `sdk/` patterns.
- **Dependencies:** T002, T003, T007, T008
- **Verification:** SDK conformance harness run by each connector; simulated-outage test asserts stale-not-delete.

### T019 — Home & telemetry connectors (HA, Prometheus, InfluxDB2, Grafana)
- **Workstream:** NC-WS-008 · **Phase:** 4
- **Acceptance criteria**
  - T019.AC1: Home Assistant — WebSocket events; declared service calls only; **HA light changes** produce normalized events.
  - T019.AC2: Prometheus — Alertmanager/webhook; **raw samples NOT events**.
  - T019.AC3: InfluxDB2 — orgs/buckets/measurements/tasks; **query cost budgets**.
  - T019.AC4: Grafana — **signed webhooks**; **alert feed, not duplicate TSDB**.
- **Target files:** C8 connector adapters (path per T006).
- **Dependencies:** T018
- **Verification:** per-connector integration tests (light-change event, webhook signature, query budget enforced, sample-not-event assertion).

### T020 — OmniRoute connector
- **Workstream:** NC-WS-009 · **Phase:** 4
- **Acceptance criteria**
  - T020.AC1: Exposes routes/models/telemetry as governed resources; **propose routing policy** (proposal, never silent change).
  - T020.AC2: OmniRoute routes registered in M1 slice with stable IDs.
- **Target files:** C9 OmniRoute adapter (path per T006); reuses `backend/inference/`.
- **Dependencies:** T018
- **Verification:** route-registration stability test; routing-policy proposal is recorded as a proposal, not applied.

### T021 — Nextcloud + S3 (local + AWS)
- **Workstream:** NC-WS-009 · **Phase:** 4
- **Acceptance criteria**
  - T021.AC1: Nextcloud — WebDAV; **user-approved writes** only.
  - T021.AC2: S3 local + AWS as **separate** connectors; **never conflated** (NC-REQ-009); emulator never primary S3.
- **Target files:** C9 sync adapters (path per T006).
- **Dependencies:** T018
- **Verification:** unauthorized-write test DENIED; local-vs-AWS S3 isolation test (no cross-namespace access).

### T022 — Gmail (N accounts) + IMAP fallback
- **Workstream:** NC-WS-010 · **Phase:** 4
- **Acceptance criteria**
  - T022.AC1: Gmail — watch + **bounded polling**; drafts; **send only with approval** (NC-REQ-004).
  - T022.AC2: **Two Gmail identities, no leak** between them (NC-MS-001).
  - T022.AC3: IMAP fallback — IDLE/polling; **UIDVALIDITY** handled.
- **Target files:** C10 comms adapters (path per T006).
- **Dependencies:** T018
- **Verification:** two-identity isolation test; send-without-approval DENIED; UIDVALIDITY-change test.

### T023 — NFS + ComfyUI + Echo/Alexa
- **Workstream:** NC-WS-011 · **Phase:** 4
- **Acceptance criteria**
  - T023.AC1: NFS — **read-only default; no blind scans**; NFS metadata registered in M1 slice.
  - T023.AC2: ComfyUI — **enqueue/cancel approved**; **model allowlist**; **GPU quotas**.
  - T023.AC3: Echo/Alexa — **supported integrations only**; unsupported surfaces explicit capability gap.
- **Target files:** C11 adapters (path per T006).
- **Dependencies:** T018
- **Verification:** NFS read-only assertion; unapproved ComfyUI enqueue DENIED + allowlist/quota test; Echo unsupported-op → capability-gap response.

### T024 — iPhone Photos + HealthKit
- **Workstream:** NC-WS-012 · **Phase:** 4
- **Acceptance criteria**
  - T024.AC1: Photos — **PhotoKit, opt-in**; Apple ingest via PhotoKit/Photos Picker; **incremental authorized sync**; **original survives failure** (NC-REQ-007).
  - T024.AC2: Local pHash/EXIF/embeddings/face clustering; **user labels only**; ops `suggest→preview→approve→apply→undo`; **never publish face embeddings remotely**.
  - T024.AC3: HealthKit — **user-permitted metrics; observer queries** (no write).
- **Target files:** C12 adapters (path per T006); `apple/` clients.
- **Dependencies:** T018, T026 (local storage/processing primitives)
- **Verification:** failed-sync test leaves original intact; no-remote-embedding egress assertion; HealthKit observer-only test.

## C13 / C14 — Attention & Ideas

### T025 — Attention (+ wake-assist)
- **Workstream:** NC-WS-013 · **Phase:** 5
- **Acceptance criteria**
  - T025.AC1: NC-API-016 items in NOW/TODAY/SOON/WAITING_ON/FYI/SUPPRESSED with **explainable rank**; actions Done/Snooze/Not important/Draft response; **no guilt/streak punishments**.
  - T025.AC2: **Deadline → draft/task, not auto-send**; quiet hours honored (NC-MS-005).
  - T025.AC3: **Wake-assist** — durable clock trigger; HealthKit hint **non-binding**; **primary alarm stays Apple's**; fallback/max attempts/quiet days/test mode; **never claims guaranteed waking**; fires on clock without HealthKit (NC-MS-006).
- **Target files:** attention service + API (path per T006).
- **Dependencies:** T014, T015, T026
- **Verification:** noisy-comms distillation test; draft-not-send assertion; wake-assist fires without HealthKit (deterministic-scheduling test).

### T026 — Ideas (Goal, budgets, checkpoints)
- **Workstream:** NC-WS-014 · **Phase:** 5
- **Acceptance criteria**
  - T026.AC1: NC-API-017: idea = **Goal resource**; **time-sliced bounded research** across idle capacity.
  - T026.AC2: **Budgets** (time/compute/spend) enforced at the workflow boundary; **checkpoints** persisted durably; **weekly briefings** produced.
- **Target files:** ideas service + API (path per T006); reuses `schemas/goals.py` patterns.
- **Dependencies:** T014, T016
- **Verification:** over-budget research stops at checkpoint; weekly-briefing test.

## C15 / C16 — Web & iOS

### T027 — Web console (against mocks)
- **Workstream:** NC-WS-015 · **Phase:** 5 (rule R2)
- **Acceptance criteria**
  - T027.AC1: **Today page friendly, AWS-style consoles underneath**; full nav list (spec §NC-CAP-014).
  - T027.AC2: Built **against mocks** derived from the frozen schema pack (no dependency on live APIs in Phase 5); mock fields match Phase 1 schema exactly (no silent drift, R2).
  - T027.AC3: **User-visible rule health** view (firing state, DLQ/quarantine counts, dry-run preview).
- **Target files:** `web/src/` (new console areas per T006; extends existing `web/`).
- **Dependencies:** T003 (mocks), T006
- **Verification:** `cd web && npm run build` green; mock↔schema parity test; visual inspection of nav + rule-health at desktop/mobile widths.

### T028 — iOS (approvals/attention, recovery controls)
- **Workstream:** NC-WS-016 · **Phase:** 5
- **Acceptance criteria**
  - T028.AC1: Approvals + attention surfaces consistent with web patterns (T027); PhotoKit/HealthKit clients per T024.
  - T028.AC2: **Mobile recovery controls**: pause agents / pause mutations / pause automation; **replay from checkpoint** (spec §10.9).
  - T028.AC3: **Deterministic scheduling** works without iPhone/Watch/LocalStack/OmniRoute (spec §10.10) — the app is an optional surface, not a scheduler dependency.
- **Target files:** `apple/` app targets (per T006; extends `apple/Shared/`).
- **Dependencies:** T027 (patterns), T025, T026
- **Verification:** build on M5 Max host; recovery-control toggle tests; build succeeds with LocalStack/OmniRoute absent.

## C7 — LocalStack lab

### T029 — LocalStack lab
- **Workstream:** NC-WS-007 · **Phase:** 6 (early-start per R4)
- **Acceptance criteria**
  - T029.AC1: **Paid plan discovered at deployment**; `ENFORCE_IAM=1` where supported (NC-CAP-010).
  - T029.AC2: Lifecycle **bootstrap / snapshot / reset / destroy / replay / export** (NC-API-015).
  - T029.AC3: **CDK smoke** `S3 → EventBridge → Lambda → SQS → StepFunctions` passes.
  - T029.AC4: **Migration mapping with explicit unsupported markers**; conformance/safety suite incl. IAM denies.
  - T029.AC5: LocalStack is **never** system of record / production event store / primary S3 / durable scheduler / real IAM / backup (NC-REQ-009).
- **Target files:** sandbox module + API (path per T006); `deployments/` LocalStack manifests.
- **Dependencies:** T006, T012
- **Verification:** CDK-chain test; lifecycle round-trip test; secret-auth + IAM-deny tests; explicit-unsupported-marker lint.

## C17 — Integration / fault simulation

### T030 — Integration / fault sim / canonical demo
- **Workstream:** NC-WS-017 · **Phase:** 7
- **Acceptance criteria**
  - T030.AC1: UI rewired from mocks to live APIs (completes R2); end-to-end **OTel correlation** across connectors→registry→events→rule→workflow→approval→policy→action.
  - T030.AC2: Fault sims pass — connector outage (stale-not-delete), process crash (no duplicate external mutation), **sandbox removal while production unaffected**, **backup/restore test**.
  - T030.AC3: **Canonical demo (NC-MS-008)**: full guiding-model path, fully audited.
- **Target files:** integration test harness (path per T006); `deployments/`.
- **Dependencies:** T007–T029
- **Verification:** fault-sim suite green; canonical-demo run recorded with complete audit trail.
