# NerveCenter AWS Platform — Phased Plan

**Spec:** [spec.md](./spec.md) · **Tasks:** [tasks.md](./tasks.md)

Phases are ordered by **dependency**: contracts before core, core (registry + PDP + events) before durable runtime, runtime before connector sprawl, connectors before experience surfaces, integration last. Workstreams run **in parallel within a phase** — gated by the file-ownership rule below, not by sequence.

> Ordering note: the tasking lists Phase 7 (integration) before Phase 6 (LocalStack lab); this plan keeps the **numbering** from the tasking (6 = LocalStack lab, C7; 7 = integration/fault sim, C17) and executes 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7, with Phase 6 able to start early in parallel (rule R4).

---

## Phase 0 — Discovery *(C0: NC-WS-000 — done)*

C0 is **complete** (T001 records it). Its outputs live under `docs/architecture/` — produced/consolidated by C0; referenced here, not reproduced:

- `docs/architecture/nervecenter-aws-platform-gap.md` — evidence-based gap analysis with file/route/test references (Zoo's first deliverable).
- Inventory of existing subsystems, ADR inputs, and contract evidence consumed by Phase 1.

Phase 0 exit: the C0 gap doc exists and every Phase 1 contract decision cites it.

---

## Phase 1 — Contracts Freeze *(C1: NC-WS-001)*

Goal: freeze the four things every later workstream imports, so parallel work can start without contract drift.

| Step | Deliverable | Task |
|---|---|---|
| 1.1 `nc://` URI grammar freeze (versioned production; deterministic parse; registry-resolvable without live connector contact) | NC-REQ-001, spec §3 | T002 |
| 1.2 v1 schema pack — all 18 mandatory entities (spec §3 table) | NC-REQ-001/005/006 | T003 |
| 1.3 ADR set, incl. **Cedar-or-auditable-language** policy decision and **Temporal-primary** runtime decision | NC-REQ-002/003 | T004 |
| 1.4 Automation DSL (`apiVersion nervecenter.dev/v1alpha1`, `kind Automation`) + **validator written by Zoo** (CEL-like safe expression language — no arbitrary Python) | NC-CAP-004 | T005 |
| 1.5 Dependency DAG (workstream → file ownership) + **file-ownership map** | rule R1 below | T006 |

**Gate (NC-MS-000):** grammar, schema pack, ADRs, ownership DAG, and the LocalStack probe (first step of T029, run early per R4) all exist; the API group list (NC-API-001…NC-API-018) is frozen as the `/api/v1` surface. Phase 2–5 work may not start until this gate passes.

---

## Phase 2 — Core *(C2 registry, C4 PDP, C3 events)*

Goal: the three pillars every later feature depends on — canonical identity, the single policy boundary, and the event fabric. The three workstreams are **parallel** (disjoint file ownership).

| Step | Deliverable | Task |
|---|---|---|
| 2.1 Resource registry: namespaces, resources, aliases, relations, snapshots, capabilities; NC-API-001/002/003/004; **stable canonical identity across restart** | NC-REQ-001 | T007 |
| 2.2 PDP: `principal + action + resource + context → ALLOW/DENY + reason`; default DENY; explicit deny precedence; re-check at execution | NC-REQ-002 | T008 |
| 2.3 Policy documents + versions (NC-API-012) and **policy-simulations** (NC-API-013) | NC-REQ-002 | T009 |
| 2.4 Principals + **hashed scoped service tokens**, no wildcard issuance (NC-API-011) | NC-REQ-002 | T010 |
| 2.5 Event normalizer: CloudEvents-in-spirit envelope; event-time vs observed-time; partition keys; idempotency keys; opaque raw payload in encrypted object storage; sensitivity class + provenance | NC-CAP-003 | T011 |
| 2.6 Durable event bus: **at-least-once only, idempotent consumers**; **DLQ / quarantine / replay / redaction mandatory** | NC-CAP-003 | T012 |
| 2.7 Events API incl. publish/query/replay/quarantine/DLQ operations (NC-API-005) | NC-REQ-005/006 | T013 |

**Gate (NC-MS-001 core):** registry + PDP + events green in integration; an unauthorized workflow action is DENIED and audited; two synthetic identities (stand-in until the Gmail connector lands, T022) do not leak state.

---

## Phase 3 — Runtime *(C5 workflows, C6 functions)*

| Step | Deliverable | Task |
|---|---|---|
| 3.1 Temporal-primary workflow engine: DAG, join, timers, bounded retries, cancellation, compensation; executions API (NC-API-008) | NC-REQ-003 | T014 |
| 3.2 Human approval gates + **approval/provenance contract** (NC-CAP-015) + approvals API (NC-API-014); approval scoped to immutable payload + expiry | NC-REQ-004/005 | T015 |
| 3.3 Versioned WorkflowDefinitions (NC-API-007), **durable migration**, restore after restart, OTel traces on executions | NC-MS-003 | T016 |
| 3.4 Functions: **K3s Jobs MVP** — OCI images, nonroot, seccomp, read-only rootfs, egress policies, deadline, quotas, minimal secret mounts; function principal + policy re-check; functions API (NC-API-009) | NC-CAP-006 | T017 |

**Gate (NC-MS-003):** queue → join → approval → bounded-retry workflow survives a process restart; a function runs with restricted egress; crash recovery does not duplicate an external mutation (shared evidence with NC-MS-002).

---

## Phase 4 — Connectors *(C8–C12)*

Connector sprawl is gated on Phase 2 (Zoo directive: **registry + PDP + events before connector sprawl**). All connectors implement the SDK protocol (T018) and obey the verbatim per-connector rules in spec §11.

| Step | Workstream | Tasks |
|---|---|---|
| 4.0 Connector SDK protocol — capabilities/discover/snapshot/subscribe/execute/health; read-only discover first; outage → stale status, not deletion | all connectors | T018 |
| 4.1 **M1 slice first** (the four connectors named by NC-MS-001): Home Assistant (T019), OmniRoute (T020), Gmail (T022), NFS (M1 portion of T023) | C8, C9, C10, C11 | T019, T020, T022, T023 |
| 4.2 Remaining home/telemetry: Prometheus (**raw samples NOT events**), InfluxDB2 (query cost budgets), Grafana (signed webhooks; alert feed, not duplicate TSDB) | C8 | T019 |
| 4.3 Remaining sync/storage: Nextcloud (user-approved writes), S3 local + AWS (**never conflated**) | C9 | T021 |
| 4.4 Remaining comms: IMAP fallback (IDLE/polling, UIDVALIDITY) | C10 | T022 |
| 4.5 Remaining compute/local: NFS (read-only default, no blind scans; **M1 portion first**, see 4.1), ComfyUI (approved enqueue/cancel, model allowlist, GPU quotas), Echo/Alexa (supported integrations only) | C11 | T023 |
| 4.6 Sensitive personal: iPhone Photos (PhotoKit, opt-in; local-only pHash/EXIF/embeddings/face clustering; suggest→preview→approve→apply→undo), HealthKit (user-permitted metrics, observer-only) | C12 | T024 |

**Gate (NC-MS-001/002 connector evidence):** HA devices + OmniRoute routes + NFS metadata registered with stable IDs; two Gmail identities do not leak; HA light changes, Grafana webhooks, Gmail events are normalized / deduped / replayed / dry-run-able; outage → stale status, not deletion.

---

## Phase 5 — Experience *(C13 attention, C14 ideas, C15 web, C16 iOS)*

Built **against mocks** in parallel with Phases 2–4 (rule R2); rewired to live APIs in Phase 7.

| Step | Deliverable | Task |
|---|---|---|
| 5.1 Attention: NOW/TODAY/SOON/WAITING_ON/FYI/SUPPRESSED; **explainable rank**; Done/Snooze/Not important/Draft response; no guilt/streak punishments; **wake-assist** (durable clock trigger, non-binding HealthKit hint, Apple primary alarm, fallback/max attempts/quiet days/test mode, **never claims guaranteed waking**); attention API (NC-API-016) | NC-MS-005/006 | T025 |
| 5.2 Ideas: Goal resource; time-sliced bounded research; budgets; checkpoints; weekly briefings; ideas API (NC-API-017) | NC-MS-007 | T026 |
| 5.3 Web console: Today page friendly, AWS-style consoles underneath; full nav list (spec §NC-CAP-014); **user-visible rule health** | NC-CAP-014 | T027 |
| 5.4 iOS: approvals/attention surfaces; PhotoKit/HealthKit clients; **mobile recovery controls** (pause agents/mutations/automation; replay from checkpoint) | NC-REQ-004 | T028 |

**Gate (NC-MS-005/006/007):** noisy comms distilled into ranked items with explanations; a deadline produces a draft/task, not an auto-send; quiet hours honored; incremental authorized photo sync where the original survives failure; wake-assist fires on clock without HealthKit; a Goal researches under budget with checkpoints and a weekly briefing.

---

## Phase 6 — LocalStack Lab *(C7: NC-WS-007)*

LocalStack is strictly the **sandbox** (NC-CAP-010): never system of record / production event store / primary S3 / durable scheduler / real IAM / backup.

| Step | Deliverable | Task |
|---|---|---|
| 6.1 Paid-plan discovery at deployment; `ENFORCE_IAM=1` where supported | T029 |
| 6.2 Bootstrap / snapshot / reset / destroy / replay / export lifecycle (NC-API-015) | T029 |
| 6.3 CDK smoke: `S3 → EventBridge → Lambda → SQS → StepFunctions` | T029 |
| 6.4 Migration mapping with **explicit unsupported markers**; conformance/safety test suite incl. IAM denies | T029 |

**Gate (NC-MS-004):** full sandbox lifecycle plus CDK chain passes; **removing the sandbox leaves production unaffected** (fault-sim executed with T030).

---

## Phase 7 — Integration / Fault Simulation *(C17: NC-WS-017)*

| Step | Deliverable | Task |
|---|---|---|
| 7.1 Cross-workstream integration: rewire UI from mocks to live APIs; end-to-end correlation IDs across connectors → registry → events → rule → workflow → approval → policy → action | T030 |
| 7.2 Fault simulations: connector outage (stale-not-delete), process crash (no duplicate external mutation), sandbox removal (production unaffected), backup/restore test | T030 |
| 7.3 **Canonical demo** (NC-MS-008): the full guiding-model path, fully audited | T030 |

---

## Milestone → Phase Map

| Milestone | Phases | Exit evidence (tasks) |
|---|---|---|
| NC-MS-000 (M0) | 0 + 1 | C0 gap doc (T001); grammar/schema/ADRs/ownership DAG frozen (T002–T006); LocalStack probe (T029 step 1) |
| NC-MS-001 (M1) | 2 + 4 (M1 slice) | HA + OmniRoute + NFS + Gmail registered (T019/T020/T022/T023); stable IDs across restart (T007); two Gmail identities no leak (T022); unauthorized workflow action → DENY + audit (T008/T014) |
| NC-MS-002 (M2) | 2 + 3 + 4 | HA/Grafana/Gmail events normalized/deduped/replayed/dry-run (T011–T013, T019); crash recovery w/o duplicate mutation (T014/T016); outage → stale status (T018) |
| NC-MS-003 (M3) | 3 | queue/join/approval/bounded-retry workflow restored after restart (T014–T016); traces; function with restricted egress (T017) |
| NC-MS-004 (M4) | 6 | secret auth; plan discovery; CDK chain; IAM denies; replay; sandbox removal, production unaffected (T029, T030) |
| NC-MS-005 (M5) | 5 | noisy comms distilled; deadline → draft/task; quiet hours (T025) |
| NC-MS-006 (M6) | 5 | incremental authorized sync; local face clustering opt-in; original survives; wake-assist on clock without HealthKit (T024/T025) |
| NC-MS-007 (M7) | 5 | bounded research on idle GPU; checkpoints; budgets (T026) |
| NC-MS-008 (M8) | 7 | canonical demo end-to-end (T030) |

---

## Plan Rules

- **R1 — Parallel-by-file-ownership.** Two workstreams never edit the same file. T006's ownership map (Phase 1, step 1.5) is authoritative; the parent/orchestrator assigns any contested path before work starts. Conflicts are resolved by the parent, not by the workers.
- **R2 — UI-against-mocks.** C15 (web, T027) and C16 (iOS, T028) build against **mocks derived from the Phase 1 frozen schema pack** in parallel with Phases 2–4; they must not block on live APIs. Rewiring to live endpoints happens in Phase 7. No mock field may later be "silently removed" — contract drift is a Phase 1 gate violation.
- **R3 — Preserve existing working code.** The platform lands in **new file ownership** per the ownership map (T006); existing working code (current `backend/`, `web/`, `apple/`, `mcp/`, `cli/`, `sdk/`) is extended, not rewritten, except where the C0 gap doc records a verified defect.
- **R4 — LocalStack lab early-start.** C7's probe (paid-plan discovery, CDK smoke) runs as soon as Phase 1 contracts freeze; the full lab (Phase 6) completes before Phase 7 fault-sim, which depends on it.
- **R5 — No placeholder API fields or invented tool responses.** Any capability a connector does not have surfaces as an explicit `capabilities` gap with a safe/manual fallback (NC-CAP-002).
