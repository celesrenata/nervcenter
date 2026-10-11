# NerveCenter — File Ownership Map

**Spec:** NC-SPEC-2026-010 · **Deliverable:** C0-D3a · **Companion:** [dependency-dag.md](./dependency-dag.md)

Per-workstream ownership of repo paths. Markers:
**NEW** = path does not exist yet · **REFACTOR** = restructure existing code ·
**INTEGRATE** = extend existing infra/registration points (no restructure).
Every path has **exactly one** owning workstream. The no-overlap proof is in
[§5](#5-no-overlap-verification).

Baseline facts (verified in this worktree, 2026-10-10):
- Existing backend subpackages: `agents api connectors context events evidence
  goals inference knowledge observability orchestration persistence policy
  scheduler services storage tasks`.
- `backend/connectors/` contains: `base.py git.py gpu.py host.py kubernetes.py
  registry.py` (+ `__init__.py`). **Absent:** `nix.py omniroute.py s3.py
  nfs.py comfyui.py homeassistant.py prometheus.py influxdb.py grafana.py
  gmail.py imap.py nextcloud.py zoo.py`.
- `migrations/` is empty (`.gitkeep` only). `tools/` does not exist.
- Dead-import block: [`backend/connectors/registry.py:497-503`](../../backend/connectors/registry.py#L497)
  (`git gpu host kubernetes nix omniroute zoo` — `nix/omniroute/zoo` have no
  module). No-op enforcer:
  [`backend/policy/permissions.py:93-95`](../../backend/policy/permissions.py#L93)
  (`_get_subject_level` returns `default_level` unconditionally).
- `apple/` contains existing `Watch/ Widgets/ Shared/ Tests/ Package.swift
  build_and_test.sh` and iOS scaffold `iOS/App/`.

---

## 1. Ownership table

### C0 — Baseline audit (**done**)
| Path | Marker | Note |
|---|---|---|
| `docs/architecture/dependency-dag.md` | NEW | This deliverable |
| `docs/architecture/file-ownership-map.md` | NEW | This deliverable |
| (all pre-existing paths) | read-only | Baseline is the audit source of truth; C0 edits nothing else |

### C1 — Contracts freeze (Phase 1)
| Path | Marker | Note |
|---|---|---|
| `schemas/**` | REFACTOR | Extend existing contract modules; **freeze** all NC tables/models (ADR-0001 record types incl. `Connector`, `ModelDescriptor`, `InferenceRoute`) |
| `migrations/**` | NEW | Empty dir; C1 creates the numbered migration scheme (see [§3](#3-migrations-numbering-allocation)) |
| `docs/architecture/uri-grammar.md` | NEW | `nc://` grammar (ADR-0001) |
| `backend/connectors/base.py` | REFACTOR (freeze) | Connector adapter interface (ADR-0007); after freeze, **read-only** for C8–C11 |

### C2 — Registry (Phase 2, parallel w/ C3/C4)
| Path | Marker | Note |
|---|---|---|
| `backend/registry/**` | NEW | Resolution service for `nc://` URIs |
| `backend/knowledge/**` | REFACTOR | Resolve through new registry |
| `backend/connectors/registry.py` | REFACTOR | **Fix-first** `:497-503`: replace static import-and-register with ADR-0007 lazy/registry-driven registration; unresolvable modules (`nix`, `zoo`, until C10 lands `omniroute`) are skipped **without** import errors — see [§4](#4-pre-assigned-defects) |
| `schemas/registry.py` (new domain module) | NEW | Registry-specific record types not covered by C1 freeze |
| `tests/backend/test_registry_*.py` | NEW | C2 unit tests |

### C3 — Event fabric (Phase 2)
| Path | Marker | Note |
|---|---|---|
| `backend/events/**` | REFACTOR | Envelope v2 (ADR-0002) + **durable DLQ**; trace-header fields live in the envelope (fix-first) |
| `backend/api/observability.py` | REFACTOR | **Fix-first** (C3 *exception*, sole `backend/api/*` file C3 may touch): propagate trace header onto emitted events |
| `tests/backend/test_events_*.py` (incl. existing `test_events_api.py`) | REFACTOR | C3 owns event tests |

### C4 — Policy decision point (Phase 2)
| Path | Marker | Note |
|---|---|---|
| `backend/policy/**` | REFACTOR | **Fix-first** `permissions.py:93-95` → Cedar PDP (ADR-0003); `guardrails.py` stays |
| `backend/api/**` wiring | INTEGRATE | PDP enforcement hook in request lifecycle; new endpoint module `backend/api/endpoints/policy.py`; C4 is **steward of `backend/api/app.py` + `backend/api/wiring.py`** (see [§2](#2-shared-http-registration-points)) |
| `mcp/auth.py` | REFACTOR | **Fix-first**: MCP auth → PDP-gated |
| `schemas/policy.py` (new domain module) | NEW | Policy decision record types |
| `tests/backend/test_policy_*.py`, `tests/mcp/*` (auth-related) | NEW/REFACTOR | C4 unit tests |

### C5 — Workflows / Temporal (Phase 3, after C1+C3+C4)
| Path | Marker | Note |
|---|---|---|
| `backend/workflows/**` | NEW | Temporal adapter (ADR-0004); every activity consults C4 PDP before side effects |
| `schemas/workflows.py` (new domain module) | NEW | Workflow run/attempt records |
| `tests/backend/test_workflows_*.py` | NEW | C5 unit tests |

### C6 — Functions / K3s (Phase 3, after C4+C5)
| Path | Marker | Note |
|---|---|---|
| `backend/functions/**` | NEW | Function runtime service (ADR-0005) |
| `deployments/kubernetes/**` | INTEGRATE | New manifests in existing kustomize tree (`base/` + new `functions/` overlay); **C6 is sole editor** of this tree |
| `schemas/functions.py` (new domain module) | NEW | Function spec/invocation records |
| `tests/backend/test_functions_*.py` | NEW | C6 unit tests |

### C7 — LocalStack sandbox lab (Phase 6)
| Path | Marker | Note |
|---|---|---|
| `tools/localstack/**` | NEW | ADR-0006 provisioning (creates `tools/`); emulated AWS services + Cedar-against-emulated checks |
| `deployments/sandbox/**` | NEW | Sandbox compose/manifests (separate tree from C6's `deployments/kubernetes/`) |

### C8 — Home/observability connectors (Phase 4, after C1+C2+C3)
| Path | Marker |
|---|---|
| `backend/connectors/homeassistant.py` | NEW |
| `backend/connectors/prometheus.py` | NEW |
| `backend/connectors/influxdb.py` | NEW |
| `backend/connectors/grafana.py` | NEW |
| `schemas/connectors_home.py` (new domain module) | NEW |
| `tests/backend/test_connector_home_*.py` | NEW |

### C9 — Productivity connectors (Phase 4)
| Path | Marker |
|---|---|
| `backend/connectors/gmail.py` | NEW |
| `backend/connectors/imap.py` | NEW |
| `backend/connectors/nextcloud.py` | NEW |
| `schemas/connectors_productivity.py` (new domain module) | NEW |
| `tests/backend/test_connector_productivity_*.py` | NEW |

### C10 — AI/storage connectors (Phase 4)
| Path | Marker |
|---|---|
| `backend/connectors/omniroute.py` | NEW — **satisfies** the `registry.py:502` import once C2's lazy registration is live |
| `backend/connectors/comfyui.py` | NEW |
| `backend/connectors/s3.py` | NEW |
| `backend/connectors/nfs.py` | NEW |
| `schemas/connectors_ai.py` (new domain module) | NEW |
| `tests/backend/test_connector_ai_*.py` | NEW |

### C11 — Apple photos/health connectors (Phase 4; ADR-0008 local-first)
| Path | Marker | Note |
|---|---|
|---|---|---|
| `apple/Watch/**` | REFACTOR | Existing watch app: photos/health sources (local-first) |
| `apple/Widgets/**` | REFACTOR | Existing widget bundle + `WidgetSnapshot` data source |
| `apple/Shared/**` | REFACTOR | Local-first data services (App Group stores) |
| `apple/Package.swift` | INTEGRATE | **Sole owner** of the SPM manifest (existing targets) |
| `apple/Tests/**` | REFACTOR | Existing `NerveAppsTests` / `NerveSharedTests` targets |
| `schemas/photos_local.py` (new domain module) | NEW | Local-first photo/health records shared by C12/C13/C16 serialization |

### C12 — Photo intelligence (Phase 4, after C10+C11)
| Path | Marker |
|---|---|
| `backend/photos/**` | NEW |
| `schemas/photos.py` (new domain module) | NEW |
| `tests/backend/test_photos_*.py` | NEW |

### C13 — Attention engine (Phase 5, after C5+C9+C11; ADR-0009)
| Path | Marker |
|---|---|
| `backend/attention/**` | NEW |
| `schemas/attention.py` (new domain module) | NEW |
| `tests/backend/test_attention_*.py` | NEW |

### C14 — Ideas engine (Phase 5, after C5+C10)
| Path | Marker |
|---|---|
| `backend/ideas/**` | NEW |
| `schemas/ideas.py` (new domain module) | NEW |
| `tests/backend/test_ideas_*.py` | NEW |

### C15 — Web console (Phase 5; can run against mocks from Phase 1)
| Path | Marker |
|---|---|
| `web/**` | REFACTOR (existing views in `web/src/views/` wired to frozen C1 contract; contract gaps in `web/CONTRACT_GAPS.md` closed against C1 schemas) |

### C16 — iOS / watchOS app (Phase 5; can run against mocks from Phase 1)
| Path | Marker | Note |
|---|---|
|---|---|---|
| `apple/iOS/**` | NEW | App targets built on the existing Phase-0 scaffold (`NervePhoneApp.swift` scaffold included) |
| `apple/build_and_test.sh` | INTEGRATE | Adds iOS/watch build+test invocation |

### C17 — Integration & fault simulation (Phase 7, after C3+C5+C7)
| Path | Marker | Note |
|---|---|
|---|---|---|
| `tests/e2e/**` | NEW | End-to-end scenarios over the full stack |
| `tests/integration/**` | NEW | Fault-injection harness (PDP deny, DLQ replay, function crash) against LocalStack lab (C7) |
| `tests/**` (existing files) | REFACTOR | **C17 is sole editor of pre-existing test files in Phase 7** — no sibling overlap because C17 runs last (see §2 rule R4) |

---

## 2. Shared HTTP registration points

`backend/api/app.py` and `backend/api/wiring.py` are the **only** files where
> one workstream per phase must append a registration line.

- **R1 (steward):** C4 owns both files for their *lifetime*. All other
  workstreams may contribute **append-only** changes (router/service
  registration for their own endpoint module) applied as single-line edits.
- **R2 (serialization):** appends are applied in strict phase order and by
  exactly **one** workstream at a time: C4 (Phase 2) → C5 → C6 (Phase 3) →
  C12 (Phase 4) → C13 → C14 (Phase 5). C8–C11 are never-HTTP: they register
  only into the **lazy connector registry** (C2's `registry.py` pattern),
  which requires **no** `app.py` edit. C15/C16 are clients — no backend edits.
- **R3 (each its own endpoint module):** a workstream's routes live in
  `backend/api/endpoints/<its-module>.py` owned by that workstream (e.g. C2:
  none today, C4: `policy.py` as stated).
- **R4 (tests):** pre-existing `tests/**` files map to their source's
  owning workstream (e.g. `test_events_api.py` → C3, `test_auth_sso.py`/
  `test_proxy_headers.py` → C4 via the MCP-auth/trace pre-assignments,
  `test_persistence.py`/`test_app_wiring.py` → C2 as registry/persistence
  integrator); C17 may edit them **only** in Phase 7, when no sibling
  workstream is active.

## 3. `migrations/` numbering allocation

`NNNN_name.sql`; C1 owns the directory plus the numbering convention.
Pre-assigned ranges make collisions structurally impossible:

| Workstream | Range | | Workstream | Range |
|---|---|---|---|---|
| C1 | 0001–0009 | | C5 | 0040–0049 |
| C2 | 0010–0019 | | C6 | 0050–0059 |
| C3 | 0020–0029 | | C12 | 0060–0069 |
| C4 | 0030–0039 | | C13/C14 | 0070–0099 |

## 4. Pre-assigned defects (fix-first, two workers, one file)

| Defect | Owner | Location | Mechanism |
|---|---|---|---|
| Dead-import block | **C2** | `backend/connectors/registry.py:497-503` | Convert to ADR-0007 lazy registration; missing modules skipped cleanly now, `omniroute` auto-resolves when C10 lands its module — C10 does **not** edit `registry.py` |
| Inference wiring | **C4/C10** (split by file) | C4: PDP gate on `backend/inference/` calls; C10: `backend/connectors/omniroute.py` | One file each; no shared line |
| MCP auth | **C4** | `mcp/auth.py` | PDP-gated authz |
| Trace header | **C3** | envelope fields in `backend/events/**` + `backend/api/observability.py` (C3's R1-authorized exception) | end-to-end propagation |
| No-op enforcer | **C4** | `backend/policy/permissions.py:93-95` | Cedar PDP decision path |

## 5. No-overlap verification

| Contested area | Partition | Verdict |
|---|---|---|
| `schemas/` | Existing modules → C1 (freeze, sole editor); new domain modules → owning domain per §1 (all different filenames) | ✅ disjoint files |
| `migrations/` | Number ranges §3, unique per workstream | ✅ disjoint files |
| `backend/connectors/` | `registry.py` → C2 · `base.py` → C1-frozen (read-only to C8–C11) · 4+3+4 new module files → C8/C9/C10 (12 distinct filenames) · `git/gpu/host/kubernetes` → frozen baseline | ✅ disjoint files |
| `backend/api/` | `app.py`+`wiring.py` → C4 steward (R1–R2 serialized single-line appends) · each `endpoints/<module>.py` → that workstream · `observability.py` → C3 (sole exception) | ✅ one editor at a time |
| `apple/` | C11: `Watch Widgets Shared Package.swift Tests` · C16: `iOS build_and_test.sh` | ✅ disjoint subpaths |
| `deployments/` | C6: `kubernetes/**` · C7: `sandbox/**` · C1: none | ✅ disjoint trees |
| `tests/` | `tests/<domain>_*.py` → owning domain · pre-existing → source owner, C17 override only in Phase 7 | ✅ serialized |
| `docs/` | C0: architecture pair · C1: `uri-grammar.md` · ADRs → parent integration (read-only here) | ✅ disjoint |

**Rule:** two workers never edit the same file. The only sanctioned multi-
editor files (`app.py`, `wiring.py`) are serialized per R2 and steward-owned
by C4; every other path above has exactly one owner.
