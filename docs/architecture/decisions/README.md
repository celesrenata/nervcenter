# NerveCenter Architecture Decision Records

Decision records for spec **NC-SPEC-2026-010**, milestone **C0**. All ADRs are **Proposed** as of 2026-10-10 and are binding for C1 planning only after ratification.

Evidence convention: every in-repo claim cites `path:line`; every external claim cites a URL with the date it was checked (all checked 2026-10-10).

| ADR | Title | Status |
| --- | --- | --- |
| [ADR-0001](./ADR-0001-canonical-resource-identity-and-registry.md) | Canonical resource identity & registry (`nc://` + PostgreSQL registry + connector reconciliation) | Proposed |
| [ADR-0002](./ADR-0002-event-fabric.md) | Event fabric: durable NATS JetStream bus, CloudEvents-spirit envelope, encrypted payloads, durable DLQ | Proposed |
| [ADR-0003](./ADR-0003-policy-decision-point.md) | Single Cedar-style PDP, default deny, deny precedence, re-check at execution; OpenFGA as relationship complement only | Proposed |
| [ADR-0004](./ADR-0004-durable-workflow-runtime.md) | Durable workflow runtime: Temporal primary; DAG scheduler demoted to compute placement; versioned, no silent fork | Proposed |
| [ADR-0005](./ADR-0005-functions-on-k3s.md) | Functions: K3s Kubernetes Jobs MVP, optional Knative later; OCI images, nonroot, seccomp, read-only rootfs, egress policy, deadline | Proposed |
| [ADR-0006](./ADR-0006-localstack-sandbox.md) | LocalStack sandbox: emulator/conformance/safety lab only; entitlement discovered at deployment; ENFORCE_IAM=1; per-task namespaces | Proposed |
| [ADR-0007](./ADR-0007-connectors-as-adapters.md) | Connectors as adapters (OmniRoute/Zoo pattern); preserve provider-native IDs; per-instance credentials; untrusted-content rule | Proposed |
| [ADR-0008](./ADR-0008-photo-health-local-first.md) | Photo/health local-first: Immich subsystem, PhotoKit-permitted ingest, local face clustering, face embeddings never published | Proposed |
| [ADR-0009](./ADR-0009-attention-engine.md) | Attention engine: durable LLM-independent core, calm ranked queue, no guilt/streaks, wake-up clock with non-binding HealthKit hints | Proposed |

## Open items carried out of C0

- ADR-0006: LocalStack plan/licensing terms require user confirmation before procurement.
- ADR-0001: the exact `nc://` path grammar is intentionally not frozen in C0; to be ratified in C1.
- ADR-0003/0007: wiring the `InferencePolicyEngine` ([backend/inference/policy.py:95](../../../backend/inference/policy.py)) into the API is scheduled work, not an assumed capability.
