# ADR-0007: Connectors as adapters

- **Number:** ADR-0007
- **Title:** Connectors as adapters — OmniRoute and Zoo pattern; preserve provider-native IDs; untrusted-content rule
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

The repository already contains the adapter pattern this ADR generalizes:

- The connector ABC and lifecycle (including `snapshot()` at [backend/connectors/base.py:697](../../../backend/connectors/base.py)) define the adapter contract; four concrete connectors implement it: `GitConnector` [backend/connectors/git.py:152](../../../backend/connectors/git.py), `GPUConnector` [backend/connectors/gpu.py:52](../../../backend/connectors/gpu.py), `HostConnector` [backend/connectors/host.py:64](../../../backend/connectors/host.py), `KubernetesConnector` [backend/connectors/kubernetes.py:25](../../../backend/connectors/kubernetes.py).
- The inference layer demonstrates the same shape for a third-party system: `OmniRouteAdapter` "routes inference requests to appropriate backends" — [backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py) (module docstring: "OmniRoute adapter for inference request routing… Section 28", [backend/inference/omniroute.py:1-5](../../../backend/inference/omniroute.py)) — with request/response translation to provider-neutral `InferenceRequest`/`InferenceResponse` models. The paired `InferencePolicyEngine` ([backend/inference/policy.py:95](../../../backend/inference/policy.py)) is not yet wired into the API (no call sites in `backend/api/`, grep, checked 2026-10-10).
- Connector data is, by nature, third-party and adversarial-capable (git content, host state, k8s metadata, model output). No trust boundary is currently declared for connector payloads.

## Decision

1. **Adapters, not forks.** Integrations with external systems are adapter modules over the `Connector` ABC ([backend/connectors/base.py:524](../../../backend/connectors/base.py)) — or, for inference-class systems, over the OmniRoute adapter pattern ([backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py)). Forking an upstream codebase (e.g., forking OmniRoute or Zoo to reach inside it) is prohibited: the adapter boundary is the boundary.
2. **Zoo integration follows the same rule.** Zoo (agent/tooling) is integrated as an adapter connector; its internals are not vendored or modified. Adapter responsibilities: translate to/from NerveCenter schemas, surface health/`snapshot()`, and emit connector events.
3. **Preserve provider-native IDs.** Adapter layers never rewrite the IDs a provider assigned (repo IDs, commit SHAs, pod UIDs, route keys, model/provider identifiers in `InferenceResponse.provider`/`.model` — [backend/inference/omniroute.py:40-48](../../../backend/inference/omniroute.py)). Native IDs are carried verbatim into NerveCenter records; canonical `nc://` identity is layered on top (ADR-0001), never substituted.
4. **Per-instance credentials.** Each adapter instance holds its own credentials (per provider account / per deployment target), injected per-namespace, never shared across instances and never baked into images (consistent with ADR-0005). Credential rotation is a per-instance operation.
5. **Untrusted-content rule.** All connector data is treated as untrusted input:
   - validated against schemas at the adapter boundary before entering NerveCenter state;
   - never executed or interpreted as instructions (prompt-injection surface: connector text feeding inference is labeled untrusted context, per the policy engine's context evaluation, [backend/inference/policy.py:95](../../../backend/inference/policy.py));
   - redacted/quarantined paths reuse the ADR-0002 event fabric mechanics;
   - mutation operations *through* a connector require the ADR-0003 PDP check plus an explicit human-visible decision record.

## Alternatives considered

1. **Forking upstream projects to customize.** Drifts from upstream, multiplies maintenance, and hides the seam where untrusted content enters. Rejected.
2. **Shared credential pool per provider.** Simpler wiring, but one leaked credential compromises every integration target and defeats per-tenant audit. Rejected.
3. **Rewriting provider IDs to NerveCenter UUIDs at ingest.** Loses the ability to round-trip back to the provider and breaks ADR-0001's reconciliation (which needs the native ID as input). Rejected.
4. **Trust connector data from "known" sources (e.g., our own git remote).** Source trustworthiness is not data trustworthiness; content can change. Rejected — the untrusted-content rule is unconditional.

## Consequences

- Every new integration starts from the ABC/adapter contract: a small file, a health check, a `snapshot()`, credential config — nothing else.
- Schema validation at the boundary means malformed third-party data fails fast in the adapter, not deep in the application.
- Adapter telemetry (latency, failure, untrusted-content quarantine counts) is emitted as events on the ADR-0002 fabric and is the primary integration-health signal.
- The `InferencePolicyEngine` wiring gap (no `backend/api/` call sites, grep checked 2026-10-10) is scheduled work: the policy engine must sit in front of the OmniRoute adapter path before production inference routing is enabled.

## References

- [backend/connectors/base.py:524](../../../backend/connectors/base.py), [backend/connectors/base.py:697](../../../backend/connectors/base.py)
- [backend/connectors/git.py:152](../../../backend/connectors/git.py), [backend/connectors/gpu.py:52](../../../backend/connectors/gpu.py), [backend/connectors/host.py:64](../../../backend/connectors/host.py), [backend/connectors/kubernetes.py:25](../../../backend/connectors/kubernetes.py)
- [backend/inference/omniroute.py:1-5](../../../backend/inference/omniroute.py), [backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py), [backend/inference/omniroute.py:40-48](../../../backend/inference/omniroute.py)
- [backend/inference/policy.py:95](../../../backend/inference/policy.py)
- Absence of `InferencePolicyEngine` call sites in `backend/api/`: grep, checked 2026-10-10.
