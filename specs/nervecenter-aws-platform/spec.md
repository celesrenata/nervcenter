# NerveCenter AWS Platform — Specification

**Status:** draft · **Created:** 2026-10-10
**Upstream spec:** NC-SPEC-2026-010 (condensed directive in the C0-BASE tasking; authoritative — this file is a faithful distillation with stable IDs)
**Discovery:** Phase 0 (workstream C0) outputs live under `docs/architecture/` — produced/consolidated by C0; referenced here, not reproduced. First deliverable: `docs/architecture/nervecenter-aws-platform-gap.md` (evidence-based, with file/route/test references).
**Companion docs:** [plan.md](./plan.md) · [tasks.md](./tasks.md)
**Sibling style reference:** `specs/nervcenter-uplift/`

---

## 1. Problem Statement

NerveCenter must grow from its current first-draft application into an **AWS-like control plane for a physical/digital/AI environment**. The operating model:

- **Everything discoverable = resource.**
- **Changes = events.**
- **Policies authorize.**
- **AI proposes, never silently overrules security.**

The platform provides a canonical, policy-governed identity and event surface across heterogeneous connectors (home automation, telemetry, mail, photos, health, inference, compute, storage), durable execution for automation, a single policy decision point, a LocalStack-based **sandbox** (never production), and attention/ideas experiences on top. This specification distills NC-SPEC-2026-010 into stable, cross-referenced IDs (NC-CAP / NC-REQ / NC-API / NC-MS / NC-WS) so that Spec Kit workstreams C0–C17 can proceed in parallel by file ownership.

### Scope

**In scope**

- Capability set NC-CAP-001…NC-CAP-015 (§5) and the `/api/v1` contract groups NC-API-001…NC-API-018 (§7).
- The nine invariants NC-REQ-001…NC-REQ-009 (§6) and the verbatim safety/operational rules (§10).
- Milestones NC-MS-000…NC-MS-008 (§8) and workstreams NC-WS-000…NC-WS-017 (§9).
- The 14 governed connector integrations (§11) and the connector SDK protocol (NC-CAP-002).
- LocalStack strictly as sandbox/emulator (NC-CAP-010), attention (NC-CAP-011), ideas (NC-CAP-012), photos/health (NC-CAP-013), console UX (NC-CAP-014), approvals/audit (NC-CAP-015).

**Out of scope**

- Production use of LocalStack in any role (see NC-REQ-009).
- Publishing face embeddings or biometric data to any remote system (see §10).
- Any rewrite of existing working code: **preserve existing working code**; the platform lands in new file ownership (see plan.md, Phase 1 file-ownership freeze).
- Guaranteeing wake-ups from the device (wake-assist must **never claim guaranteed waking**).
- Placeholder API fields or invented tool responses — unsupported integrations must surface **explicit capability gaps with safe/manual fallback** instead.

---

## 2. Guiding Model

The normative data-flow model (NC-SPEC-2026-010):

```text
 Connectors
    → Resource Registry
    → Event Normalizer
    → Durable Event Bus
    → Knowledge Graph + Event Rules
    → Workflow Engine
    → Functions + Zoo/Agents
    → Policy Gateway
    → Actual Resources
```

Side rails on the model:

- **LocalStack** = sandbox adapter / CDK smoke / replay / IAM tests (NC-CAP-010).
- **OmniRoute** = governed inference transport (connector, NC-WS-009).
- **Web / iPhone / Watch** = control / attention / approvals (NC-CAP-014, NC-CAP-015, C15/C16).

Every mutation path — including AI-initiated — terminates at the **Policy Gateway** (NC-CAP-007) before touching an actual resource. AI proposes; the policy decision is authoritative.

---

## 3. Canonical Resource Identity and `nc://` URI Grammar

- Canonical example: `nc://personal/homeassistant/home/devices/bedroom-lamp`.
- **Grammar requirement (frozen in Phase 1 by T002):** every resource is addressable by exactly one canonical `nc://` URI; URIs are the stable identity of a resource across connector restarts and re-discovery; the URI grammar must be deterministic to parse and resolvable **from the registry without live connector contact** (aliases, relations, and snapshots are registry data); URI scheme, authority, and path segments are case-sensitive; grammar production is versioned and its freeze is a Phase 1 gate. The exact BNF production is a C1 contracts deliverable, not invented here.
- Aliases (`ResourceAlias`) map human/connector-local names onto the single canonical URI; relations (`ResourceRelation`) link resources across connectors.
- Identity stability acceptance: **stable IDs across restart** (see NC-MS-001).

### Mandatory entities (v1 schema pack, T003)

| Entity | Notes |
|---|---|
| `Namespace` | isolation boundary; namespace isolation is an operational rule |
| `ConnectorInstance` | a deployed connector of a known kind |
| `Resource` | the canonical, policy-addressable unit; carries a sensitivity class |
| `ResourceAlias` | maps local names → canonical URI |
| `ResourceRelation` | typed relation between resources |
| `ResourceSnapshot` | point-in-time state; discover-first is read-only |
| `Capability` | what a connector/resource can do (declared, not inferred) |
| `Principal` | user, agent, function, service — policy subject |
| `Policy` | Cedar-style policy document (NC-CAP-007) |
| `Event` | normalized envelope + opaque raw payload reference (NC-CAP-003) |
| `Rule` | versioned Automation definition (NC-CAP-004) |
| `WorkflowDefinition` | versioned Temporal workflow definition (NC-CAP-005) |
| `WorkflowExecution` | durable execution instance with provenance (NC-CAP-015) |
| `Function` | K3s Job spec with egress/quota/secret constraints (NC-CAP-006) |
| `SecretReference` | reference only — never secret material (NC-CAP-008) |
| `Approval` | scoped to an immutable payload with expiry (NC-CAP-015) |
| `AttentionItem` | classified, explainably ranked item (NC-CAP-011) |
| `AuditEntry` | append-only record; every decision/action carries audit (NC-CAP-015) |

### Sensitivity classes

Every resource carries exactly one: `PUBLIC` · `HOME_PRIVATE` · `PERSONAL_PRIVATE` · `FINANCIAL` · `HEALTH_SENSITIVE` · `BIOMETRIC` · `SECRET`. Class drives storage encryption, redaction behavior, and policy context.

---

## 4. Connector SDK Protocol

NC-CAP-002. All 14 connectors (§11) implement the same protocol surface:

| Operation | Contract |
|---|---|
| `capabilities` | declare supported operations, sensitivity classes, limits; **read-only discover first** |
| `discover` | enumerate resources read-only; no mutation side effects |
| `snapshot` | bounded point-in-time read of a resource set |
| `subscribe` | stream changes (e.g., HA WebSocket); bounded, rate-quotable |
| `execute` | invoke a **declared** service call; approval-gated mutation; scope-aware policy check at each action |
| `health` | liveness + integration-loss status; outage → **stale status, not deletion** |

---

## 5. Capabilities (NC-CAP-001 … NC-CAP-015)

### NC-CAP-001 — Resource Registry

Owns namespaces, resources, aliases, relations, snapshots, capabilities. Single source of truth for canonical identity (NC-REQ-001). Survives restart with stable IDs. Exposes `NC-API-001` (namespaces), `NC-API-002` (connectors), `NC-API-003` (resources), `NC-API-004` (resources/{id}/actions).

### NC-CAP-002 — Connector SDK

Protocol in §4 plus per-connector adapters for the 14 integrations in §11. Connector sprawl is gated: **registry + PDP + events land before connector sprawl** (plan.md Phase 2 → Phase 4).

### NC-CAP-003 — Event Fabric

- **Envelope:** CloudEvents-compatible **in spirit** — `id`, `source` (canonical `nc://` URI), `type`, `subject`, `time` (event-time), `observed` (observed-time), `datacontenttype`, `data` = reference to **opaque raw payload in encrypted object storage** (raw payload never inlined in the bus), partition key, idempotency key, sensitivity class, provenance (connector instance + raw payload hash).
- **Delivery:** **at-least-once only, with idempotent consumers.**
- **Mandatory mechanisms:** DLQ, quarantine, replay, redaction — none optional.
- Normalization dedupes across connectors (e.g., multiple Gmail identities → no leak between them, NC-MS-001).

### NC-CAP-004 — Rules / Triggers

- Expression language: **CEL-like safe expression language; no arbitrary Python.**
- Safety mechanics (all mandatory): recursion/cycle detection, debounce, cooldown, max firing rates, DST-safe schedules, preview/dry-run.
- **Scope-aware permission check at EACH action** a rule fires — re-evaluated, not cached from trigger time.
- DSL shape (Zoo writes the validator — T005):

```yaml
apiVersion: nervecenter.dev/v1alpha1
kind: Automation
spec:
  match:     { … }            # event/match criteria, safe expression language
  controls:  { … }            # debounce / cooldown / max-fire / schedule (DST-safe)
  workflow:
    steps:
      - inference:            { … }   # governed inference via OmniRoute
      - attention.create:     { … }
      - notification.dispatch:{ … }
      - resource.action:      { … }   # each action re-checked against policy
      - human.wait:           { … }   # approval gate (NC-CAP-015)
```

### NC-CAP-005 — Durable Workflows

- **Temporal-primary** workflow runtime.
- Constructs: DAG, join, timers, retries (bounded), cancellation, compensation, human approvals.
- **Versioned definitions**; **durable migration** of in-flight executions across definition versions.
- **Durable execution** invariant (NC-REQ-003): restarts recover state; crash recovery must not duplicate external mutation (NC-MS-002).

### NC-CAP-006 — Functions

- **K3s Jobs MVP**; OCI images; `nonroot`; `seccomp`; read-only rootfs; egress policies; deadline; quotas; **minimal secret mounts** (references, never material; NC-CAP-008).
- Function execution is a principal for policy (NC-CAP-007); functions never hold wildcard tokens (NC-REQ-002).

### NC-CAP-007 — IAM / Policy Decision Point (PDP)

- **Single policy evaluation boundary** (NC-REQ-002): one PDP answers `principal + action + resource + context → ALLOW / DENY + reason`.
- **Default DENY**; **explicit deny precedence** over allow.
- Policy language: **Cedar or an auditable language** (C1 decision, Phase 1 ADR).
- **Re-check at execution** — authorization is re-evaluated at each action, including mid-workflow.
- Approvals are **scoped to an immutable payload with expiry**; granting one approval never grants a class of actions.
- **Hashed scoped service tokens**; **no wildcard issuance to agents/functions.**

### NC-CAP-008 — Secrets

Secrets are vaulted and referenced (`SecretReference`); never stored in resource/registry records, workflow state, or event envelopes. **No webhook secret in URL.** Access to a secret is itself a policy-checked action.

### NC-CAP-009 — Observability

**OTel correlation on everything:** events, rule firings, workflow executions, function jobs, policy decisions, approvals, and connector calls share correlation identifiers; traces are first-class evidence for audit (NC-CAP-015).

### NC-CAP-010 — LocalStack Sandbox

**Decision: LocalStack-as-sandbox-not-production.** LocalStack is a developer emulator and a conformance/safety testing surface. It is **never** the system of record, never the production event store, never primary S3, never the durable scheduler, never real IAM, never the backup target.

Required behaviors:

- Discover the **paid plan at deployment** (capability discovery, not assumption).
- `ENFORCE_IAM=1` where supported.
- Lifecycle: **bootstrap / snapshot / reset / destroy / replay / export.**
- **CDK smoke chain:** `S3 → EventBridge → Lambda → SQS → StepFunctions`.
- **Migration mapping** from production service semantics to sandbox semantics, with **explicit unsupported markers** (no silent capability collapse).
- **Sandbox failure must not stop production** (NC-REQ-009); local and AWS S3 are **never conflated**.

### NC-CAP-011 — Attention

- Bins: `NOW / TODAY / SOON / WAITING_ON / FYI / SUPPRESSED`.
- **Explainable rank** — every item carries the reasons it was ranked where it was.
- Actions: `Done / Snooze / Not important / Draft response`.
- **No guilt/streak punishments** in copy, scoring, or behavior.
- **Wake-assist:** durable clock trigger (Temporal timer, NC-CAP-005); HealthKit hint is **non-binding**; **primary alarm stays Apple's**; fallback / max attempts / quiet days / test mode; **never claim guaranteed waking**.
- Deadlines produce a **draft or task, not an auto-send** (NC-MS-005).

### NC-CAP-012 — Ideas

- An idea is a **Goal resource**.
- **Time-sliced bounded research** across idle capacity; **budgets** (time, compute, spend) enforced at the workflow boundary; **checkpoints** persisted durably; **weekly briefings** summarize progress.

### NC-CAP-013 — Photos / Health

- Photos: **prefer Immich** (faces/external libraries); Apple ingest via **PhotoKit / Photos Picker** (opt-in); local pHash / EXIF / embeddings / face clustering; **user labels only**; operations follow `suggest → preview → approve → apply → undo`; **never publish face embeddings remotely** (NC-REQ-007).
- Health: HealthKit **user-permitted metrics, observer queries only** — no write to HealthKit by the platform.
- Sync is **incremental and bounded**; **original survives failure** (NC-MS-006): a failed sync/transform never deletes or corrupts source data.

### NC-CAP-014 — Console UX

- **Today page friendly, AWS-style consoles underneath.**
- Navigation: `Today / Resources / Connections / Events / Rules / Workflows / Functions / Storage / Policies & Identity / Agents / Compute & Inference / Experiments & Ideas / Audit / Settings`.
- **User-visible rule health** (firing state, DLQ/quarantine counts, dry-run preview) is a first-class view, not a debug page.
- UI work proceeds **against mocks** in parallel with core (plan.md rule).

### NC-CAP-015 — Approvals / Audit

**Approval / provenance contract** (JSON, normative fields):

```json
{
  "execution_id": "…",
  "definition_id": "…",
  "version": "…",
  "trigger_event_id": "…",
  "principal_id": "…",
  "effective_policy": "…",
  "state": "WAITING_FOR_APPROVAL",
  "proposed_actions": [ "…" ],
  "evidence": "…",
  "budget": "…",
  "idempotency_key": "…",
  "audit_id": "…"
}
```

Approvals scope to the immutable payload + expiry; every state transition writes an `AuditEntry`. Audit is append-only and replayable; **auditability** is invariant (NC-REQ-006).

---

## 6. Invariants (NC-REQ-001 … NC-REQ-009)

These invariants are non-negotiable; quoted phrasing is preserved from NC-SPEC-2026-010 and must not be paraphrased weaker in downstream docs or code comments.

| ID | Invariant | Normative content (verbatim where quoted) |
|---|---|---|
| NC-REQ-001 | **One canonical resource identity** | Every discoverable thing is exactly one resource with exactly one canonical `nc://` URI. Aliases and relations never create second identities. Stable IDs across restart. |
| NC-REQ-002 | **One policy evaluation boundary** | A single PDP decides `principal + action + resource + context → ALLOW/DENY + reason`. Default DENY; explicit deny precedence; re-check at execution. No component may evaluate policy for itself. AI "proposes, never silently overrules security". |
| NC-REQ-003 | **Durable execution** | Workflows and attention triggers run on durable execution (Temporal-primary). Restart recovers state; crash recovery without duplicate external mutation; versioned definitions with durable migration. |
| NC-REQ-004 | **Explicit consent** | Approval-gated mutations. Send-only-with-approval for communications. User-approved writes (e.g., Nextcloud). Photos opt-in; HealthKit user-permitted metrics only. Approvals scoped to immutable payload + expiry. |
| NC-REQ-005 | **Provenance** | Every derived artifact carries its chain: trigger event → effective policy → principal → evidence → approval → audit entry (contract in NC-CAP-015). Raw payloads preserved with hash, in encrypted object storage. |
| NC-REQ-006 | **Auditability** | Append-only `AuditEntry` for every decision and action; OTel correlation on everything; audit is replayable. |
| NC-REQ-007 | **Local-first sensitive data** | Sensitive classes (`HEALTH_SENSITIVE`, `BIOMETRIC`, `SECRET`, …) stay local-first: encrypted personal/raw stores, local face clustering, **never publish face embeddings remotely**, originals survive failure. |
| NC-REQ-008 | **Graceful integration loss** | Outage → stale status, not deletion. Connectors degrade to read-only/stale; the platform keeps serving last-known state and marks it as such. |
| NC-REQ-009 | **No production coupling to emulator** | LocalStack "never the system of record / production event store / primary S3 / durable scheduler / real IAM / backup". Local and AWS S3 **never conflated**. **Sandbox failure must not stop production.** |

---

## 7. API Contract (NC-API-001 … NC-API-018)

All groups are served under `/api/v1/…`. Groups below are the freeze target for Phase 1 (contracts); operation inventories per group are C1 deliverables (T003/T004) — this table fixes the **groups**, not every verb.

| ID | Group (`/api/v1/…`) | Owns |
|---|---|---|
| NC-API-001 | `namespaces` | namespace lifecycle, isolation |
| NC-API-002 | `connectors` | connector instances, capabilities, health |
| NC-API-003 | `resources` | registry CRUD/lookup, aliases, relations, snapshots, sensitivity class |
| NC-API-004 | `resources/{id}/actions` | execute declared actions (policy re-checked; approval-gated where required) |
| NC-API-005 | `events` | publish/query events, replay, quarantine/DLQ operations, redaction |
| NC-API-006 | `event-rules` | rules (Automation DSL), dry-run/preview, rule health |
| NC-API-007 | `workflows` | WorkflowDefinition versions |
| NC-API-008 | `workflow-executions` | start/status/cancel/compensate; provenance contract fields |
| NC-API-009 | `functions` | function specs, jobs, egress/quota/secret-mount config |
| NC-API-010 | `storage` | encrypted object storage references (raw payloads, personal stores), backups |
| NC-API-011 | `principals` | principals, scoped (hashed) service token issuance — no wildcards |
| NC-API-012 | `policies` | Cedar-style policy documents, versions |
| NC-API-013 | `policy-simulations` | dry-run evaluation (`principal + action + resource + context`) |
| NC-API-014 | `approvals` | provenance contract create/approve/deny; expiry enforcement |
| NC-API-015 | `sandboxes/localstack` | bootstrap/snapshot/reset/destroy/replay/export; paid-plan discovery; migration mapping |
| NC-API-016 | `attention` | items (NOW/TODAY/SOON/WAITING_ON/FYI/SUPPRESSED), actions, wake-assist controls |
| NC-API-017 | `ideas` | goal resources, budgets, checkpoints, weekly briefings |
| NC-API-018 | `audit` | append-only query/replay of `AuditEntry` |

Contract hygiene: **no placeholder API fields or invented tool responses**; unsupported operations return explicit capability-gap responses with safe/manual fallback (NC-CAP-002 `capabilities` disclosure).

---

## 8. Milestones (NC-MS-000 … NC-MS-008)

| ID | Milestone | Acceptance (from NC-SPEC-2026-010) |
|---|---|---|
| NC-MS-000 | **M0 — Inventory / ADRs / contracts** | C0 gap doc evidence-based; v1 schemas, ADRs, ownership DAG, LocalStack probe exist; contracts frozen (Phase 1 gate). |
| NC-MS-001 | **M1 — Resources + policies** | HA devices + OmniRoute routes + NFS metadata registered; **stable IDs across restart**; **two Gmail identities, no leak** between them; **unauthorized workflow action → DENY + audit**. |
| NC-MS-002 | **M2 — Event rules** | HA light changes, Grafana webhooks, Gmail events: **normalized / deduped / replay / dry-run**; **crash recovery without duplicate external mutation**; **outage → stale status, not deletion**. |
| NC-MS-003 | **M3 — Durable runtime** | Queue workflows; join; approval; bounded retries; **restore after restart**; traces; **function with restricted egress**. |
| NC-MS-004 | **M4 — LocalStack lab** | Secret auth; plan discovery; **CDK chain** (S3→EventBridge→Lambda→SQS→StepFunctions); IAM denies; replay; **sandbox removal while production unaffected**. |
| NC-MS-005 | **M5 — Attention** | Distill noisy comms; **deadline → draft/task, not auto-send**; quiet hours honored. |
| NC-MS-006 | **M6 — Photo/health** | **Incremental authorized sync**; **local face clustering opt-in**; **original survives failure**; **wake-assist fires on clock without HealthKit**. |
| NC-MS-007 | **M7 — Ideas** | **Bounded research across idle GPU**; checkpoints; budgets enforced. |
| NC-MS-008 | **M8 — Canonical demo** | End-to-end demo of the guiding model: connector → registry → events → rule → workflow → (approval) → policy → action, fully audited. |

---

## 9. Workstreams (NC-WS-000 … NC-WS-017)

| ID | Workstream | Scope | Phase |
|---|---|---|---|
| NC-WS-000 | C0 — Discovery | inventory, gap doc, evidence gathering (done; outputs in `docs/architecture/`) | 0 |
| NC-WS-001 | C1 — Contracts & schema pack | `nc://` grammar freeze, v1 schema pack (18 entities), ADRs (incl. Cedar-or-auditable), dependency DAG, file-ownership map, Automation DSL validator | 1 |
| NC-WS-002 | C2 — Resource registry | NC-CAP-001, NC-API-001/002/003/004 | 2 |
| NC-WS-003 | C3 — Event fabric | NC-CAP-003, NC-API-005 | 2 |
| NC-WS-004 | C4 — PDP / IAM | NC-CAP-007, NC-API-011/012/013 | 2 |
| NC-WS-005 | C5 — Durable workflows | NC-CAP-005, NC-API-007/008 | 3 |
| NC-WS-006 | C6 — Functions | NC-CAP-006, NC-API-009 | 3 |
| NC-WS-007 | C7 — LocalStack lab | NC-CAP-010, NC-API-015 | 6 |
| NC-WS-008 | C8 — Home & telemetry connectors | Home Assistant, Prometheus, InfluxDB2, Grafana | 4 |
| NC-WS-009 | C9 — Inference & sync connectors | OmniRoute, Nextcloud, S3 (local + AWS) | 4 |
| NC-WS-010 | C10 — Communications connectors | Gmail (N accounts), IMAP fallback | 4 |
| NC-WS-011 | C11 — Compute & local connectors | ComfyUI, NFS, Echo/Alexa | 4 |
| NC-WS-012 | C12 — Sensitive personal connectors | iPhone Photos, HealthKit | 4 |
| NC-WS-013 | C13 — Attention | NC-CAP-011, NC-API-016 | 5 |
| NC-WS-014 | C14 — Ideas | NC-CAP-012, NC-API-017 | 5 |
| NC-WS-015 | C15 — Web console | NC-CAP-014 (against mocks) | 5 |
| NC-WS-016 | C16 — iOS | approvals/attention surfaces, mobile recovery controls, PhotoKit/HealthKit clients | 5 |
| NC-WS-017 | C17 — Integration / fault simulation | cross-workstream integration, fault sims (outage, crash, sandbox removal), canonical demo (NC-MS-008) | 7 |

> C1 is the Phase 1 contracts workstream; its scope (grammar/schema/DAG/validator) is fixed by the phase plan, and the C0–C17 numbering is taken from the tasking.

---

## 10. Safety and Operational Rules (verbatim, do not paraphrase weaker)

Preserved from NC-SPEC-2026-010:

1. Secrets **vaulted**; **no webhook secret in URL**.
2. **Incremental bounded sync** everywhere (no unbounded backfills).
3. **Rate quotas** on all connector interactions.
4. **Encrypted personal/raw stores** (raw event payloads, photos, health data).
5. **Backup/restore tests** are a gate, not an aspiration.
6. **Namespace isolation** between connector instances and identities.
7. **Read-only discover first**; **approval-gated mutations**.
8. **OTel correlation on everything.**
9. **Mobile recovery controls:** pause agents / pause mutations / pause automation; **replay from checkpoint**.
10. **Deterministic scheduling without iPhone/Watch/LocalStack/OmniRoute** — the platform must schedule and run when those are absent.
11. **User-visible rule health.**
12. **No uncontrolled background activity.**
13. **AI proposes, never silently overrules security.**
14. LocalStack: **never** system of record / production event store / primary S3 / durable scheduler / real IAM / backup; **sandbox failure must not stop production**; S3 local vs AWS **never conflated**.
15. Photos: **never publish face embeddings remotely**; user labels only.
16. Wake-assist: **never claim guaranteed waking**; primary alarm stays Apple's.
17. Gmail: **send only with approval**.
18. Rules: **no arbitrary Python**; scope-aware permission check at **each** action.
19. Delivery: **at-least-once only with idempotent consumers**.
20. MCP tools **read resources and create PROPOSALS by default; explicit mutation capabilities required.**

---

## 11. Governed Connectors (14)

Per-connector rules as fixed by NC-SPEC-2026-010 (all connectors additionally obey §10):

| Connector | Workstream | Rules |
|---|---|---|
| Home Assistant | NC-WS-008 | WebSocket events; **declared service calls** only for `execute` |
| Prometheus | NC-WS-008 | Alertmanager/webhook; **raw samples NOT events** (samples stay out of the event bus) |
| InfluxDB2 | NC-WS-008 | orgs/buckets/measurements/tasks; **query cost budgets** |
| Grafana | NC-WS-008 | **signed webhooks**; **alert feed, not duplicate TSDB** |
| OmniRoute | NC-WS-009 | routes/models/telemetry; **propose routing policy** (proposal, never silent change) |
| Nextcloud | NC-WS-009 | WebDAV; **user-approved writes** |
| S3 (local + AWS) | NC-WS-009 | **never conflate emulator** with AWS S3; separate namespaces |
| Gmail (N accounts) | NC-WS-010 | watch + **bounded polling**; drafts; **send only with approval**; identities isolated (no cross-account leak, NC-MS-001) |
| IMAP fallback | NC-WS-010 | IDLE/polling; **UIDVALIDITY** handling |
| ComfyUI | NC-WS-011 | **enqueue/cancel approved**; **model allowlist**; **GPU quotas** |
| NFS | NC-WS-011 | **read-only default; no blind scans** |
| Echo/Alexa | NC-WS-011 | **supported integrations only** (capability-gated) |
| iPhone Photos | NC-WS-012 | **PhotoKit**, **opt-in**; local processing per NC-CAP-013 |
| HealthKit | NC-WS-012 | **user-permitted metrics; observer queries** |

Unsupported integration surfaces → explicit capability gap + safe/manual fallback (NC-CAP-002 `capabilities`; §7 contract hygiene).

---

## 12. Zoo Integration Contract

- **First deliverable** (Phase 0, done): `docs/architecture/nervecenter-aws-platform-gap.md` — evidence-based, file/route/test references (C0).
- **Second** (Phase 1): v1 schemas, ADRs, ownership DAG, LocalStack probe (C1 + C7 probe).
- **Then:** parallel workstreams by file ownership; **registry + PDP + events before connector sprawl**; **UI against mocks in parallel**; **preserve existing working code**.
- MCP tools read resources and create **PROPOSALS** by default; explicit mutation capabilities required (§10.20).
- **No placeholder API fields or invented tool responses.**
