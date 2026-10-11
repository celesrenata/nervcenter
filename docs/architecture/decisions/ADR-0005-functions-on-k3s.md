# ADR-0005: Functions execution

- **Number:** ADR-0005
- **Title:** Functions — K3s Kubernetes Jobs MVP; optional Knative later
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

NerveCenter executes tasks on workers, and the production cluster type is K3s (audit notes reference the `nervecenter` K3s namespace — [specs/web-quality-audit/gaps-walk.md:6](../../../specs/web-quality-audit/gaps-walk.md)). There is no dedicated function-execution sandbox in the repository today: a search for "knative" over code, manifests, and docs finds no runtime (grep, checked 2026-10-10). The existing Kubernetes deployment base ([deployments/kubernetes/base/kustomization.yaml](../../../deployments/kubernetes/base/kustomization.yaml)) and Harbor-based image pipeline ([deployments/harbor/deploy.sh](../../../deployments/harbor/deploy.sh)) are the substrate a function runtime would sit on.

Functions (arbitrary, user- or agent-submitted code executed on the platform's behalf) need a hard sandbox: blast radius must be limited to a single execution with no network egress surprises, no privilege escalation, and a bounded lifetime.

## Decision

1. **MVP runtime: Kubernetes Jobs on the existing K3s cluster.** Each function execution is a `batch/v1 Job` in a dedicated namespace, created by the platform on behalf of the task that requested it. Jobs give the platform: declarative cleanup (ttlSecondsAfterFinished), bounded concurrency, and reuse of the existing RBAC/registry/ingress machinery.
2. **Optional Knative later.** Knative (scale-to-zero, event-driven) is explicitly deferred; it may be layered on top of the same Job/image contract without changing function semantics. Nothing in this ADR depends on Knative.
3. **OCI images as the function artifact.** Functions ship as OCI images from the Harbor registry (existing pipeline: [deployments/harbor/deploy.sh](../../../deployments/harbor/deploy.sh)); source is never executed directly on a shared node.
4. **Security posture per execution (all mandatory, enforced in the Job spec, not by convention):**
   - `runAsNonRoot` / nonroot user — no root container.
   - `seccompProfile: RuntimeDefault` (plus the cluster's AppArmor/LSM baseline).
   - `readOnlyRootFilesystem: true` with explicit emptyDir mounts for scratch space only.
   - **Egress policy:** a restrictive NetworkPolicy per function namespace; default-deny egress with explicit allow-lists (registry, object storage, ADR-0001/ADR-0002 endpoints only unless the function declares an approved egress scope).
   - **Execution deadline:** `activeDeadlineSeconds` set from the function's declared deadline; the platform kills the Pod and records a timeout event — no unbounded runs.
5. **Secrets:** function credentials are injected per-namespace and never baked into images; no shared long-lived credentials (aligns with per-instance credentials, ADR-0007).

## Alternatives considered

1. **Knative Functions from the start.** More moving parts (revisor, queue sidecars, controller) for a product that does not yet have a function traffic pattern. Deferred, not rejected.
2. **WASM sandboxes.** Excellent isolation-per-millisecond but a large ecosystem lift (runners, language toolchains, cold-start behavior) before any function value exists. Rejected for the MVP.
3. **Docker-in-Docker / plain containers on a worker node.** Weaker blast-radius control; a compromised runtime can reach the host network and sibling workloads. Rejected.
4. **Cloud serverless (Lambda-class).** Introduces a second vendor runtime, egress to the vendor network, and conflicts with the local-first/sovereign posture (see ADR-0006/ADR-0008). Rejected.

## Consequences

- New namespace(s) + NetworkPolicy set per function cohort; the base manifests gain a function job template (new files under `deployments/`, out of scope for this ADR's file ownership).
- Image build latency is on the critical path of first execution; a build cache is expected infrastructure.
- Deadlines make long-running functions a workflow (ADR-0004 Temporal) that *launches* functions, not a function that runs forever.
- Egress allow-lists require a change-management path (request → approve → policy update); ad-hoc egress is a security finding, not a feature.
- Job overhead (Pod scheduling) is acceptable at the current scale; if sub-second cold starts ever become a product requirement, that is the trigger to revisit Knative.

## References

- [specs/web-quality-audit/gaps-walk.md:6](../../../specs/web-quality-audit/gaps-walk.md)
- [deployments/kubernetes/base/kustomization.yaml](../../../deployments/kubernetes/base/kustomization.yaml)
- [deployments/harbor/deploy.sh](../../../deployments/harbor/deploy.sh)
- Absence of a function runtime (no "knative" in the repository): grep over code/manifests/docs, checked 2026-10-10.
