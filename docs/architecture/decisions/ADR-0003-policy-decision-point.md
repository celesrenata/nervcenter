# ADR-0003: Policy decision point

- **Number:** ADR-0003
- **Title:** Single Cedar-style PDP for all actions; OpenFGA only as relationship complement
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

The current permission model is a non-functional scaffold:

- `PermissionEnforcer` is defined at [backend/policy/permissions.py:39](../../../backend/policy/permissions.py), but its core is a no-op: `_get_subject_level` unconditionally returns `PermissionLevel(self.default_level)` — [backend/policy/permissions.py:93-95](../../../backend/policy/permissions.py). Its docstring scopes it to "inference operations" only ([backend/policy/permissions.py:40-44](../../../backend/policy/permissions.py)).
- It is **not wired into the API layer**: a search for `PermissionEnforcer`/`enforce` across `backend/api/` finds no call sites (grep, checked 2026-10-10).
- Real authentication today is signed JWT / SSO (spec S101): "Signed-JWT auth endpoints for the NerveCenter API (spec sso-integration, S101)" — [backend/api/auth.py:1-5](../../../backend/api/auth.py).
- There is no Cedar or OpenFGA anywhere in the repository (grep over `*.py *.md *.yaml *.toml`, checked 2026-10-10).

Consequence: nothing in the system actually denies any action based on a policy. "Default allow by accident" is the operational reality.

## Decision

1. **One policy decision point (PDP) for all actions** — API mutations, task execution, connector calls, inference routes, and event consumption all consult the same PDP. No per-domain bespoke checkers.
2. **Cedar-style policy engine.** Policies are Cedar-style attribute policies (principal, action, resource, context); validation uses the Cedar policy validator (https://docs.cedarpolicy.com/policies/validation.html, checked 2026-10-10). The concrete engine binding (Cedar library or an equivalent authoring-compatible runtime) is a C1 implementation detail, not asserted to exist in the repo today.
3. **Default deny.** An action is allowed only if a matching `permit` applies. Absence of a policy means denial.
4. **Explicit deny precedence.** A matching `forbid` overrides any `permit`, regardless of scope.
5. **Re-check at execution.** Authorization is evaluated both at request admission and again immediately before the privileged operation executes (e.g., before a task run starts, before a connector mutation), because admission-time and execution-time can differ by arbitrary wall-clock time.
6. **Replace the no-op scaffold.** `PermissionEnforcer` ([backend/policy/permissions.py:39](../../../backend/policy/permissions.py)) is retired/replaced; the hierarchical `PermissionLevel` model is not extended.
7. **OpenFGA only as complement.** If relationship-based sharing (e.g., "users sharing a library") is needed, OpenFGA may be used *as a data source feeding the PDP's context*, never as the PDP itself, so decision semantics (default deny, deny precedence, re-check) stay in one place.

## Alternatives considered

1. **Extend the existing `PermissionLevel` hierarchy.** The level ladder (`read/write/execute/admin/owner`) cannot express resource attributes, conditions, or deny precedence; patching the no-op inherits its scope limitation ("inference operations"). Rejected.
2. **OpenFGA as the PDP.** OpenFGA is strong for relationship queries but is not a general attribute-policy engine; making it the PDP fragments policy semantics across two engines. Rejected as primary; allowed as complement.
3. **OPA (Rego).** Viable, but adds a second policy language ecosystem; Cedar-style syntax with built-in validation was preferred for policy authoring ergonomics. Noted as equivalent in kind.
4. **Ad-hoc per-endpoint checks.** Proven to have failed (nothing is checked today). Rejected.

## Consequences

- New runtime dependency (policy engine) and a policy authoring/distribution pipeline: policies become versioned artifacts, not code.
- Hot-path latency: two evaluations per privileged action (admission + execution); the PDP must be in-process or local-network, with a cache keyed on policy version.
- Migration risk: today everything is effectively allowed; default deny means a staged rollout (allow-all policy → deny-by-default with an explicit allow set) is mandatory to avoid outages.
- Audit: every PDP decision is emitted as an event on the ADR-0002 fabric (decision, reason, matched policy), giving a queryable authorization history.
- S101 auth ([backend/api/auth.py:1-5](../../../backend/api/auth.py)) supplies the authenticated subject; the PDP consumes it but does not replace it.

## References

- [backend/policy/permissions.py:39](../../../backend/policy/permissions.py), [backend/policy/permissions.py:40-44](../../../backend/policy/permissions.py), [backend/policy/permissions.py:93-95](../../../backend/policy/permissions.py)
- [backend/api/auth.py:1-5](../../../backend/api/auth.py)
- Cedar policy validation: https://docs.cedarpolicy.com/policies/validation.html (checked 2026-10-10)
- Absence of PDP wiring in `backend/api/` and of Cedar/OpenFGA in the repository: grep, checked 2026-10-10.
