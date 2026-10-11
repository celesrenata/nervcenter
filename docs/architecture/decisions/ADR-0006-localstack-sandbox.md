# ADR-0006: LocalStack sandbox

- **Number:** ADR-0006
- **Title:** LocalStack sandbox — developer emulator and conformance/safety lab only
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

The object-storage client is S3/MinIO-compatible with AWS SigV4 signing and "works against AWS S3, MinIO, and LocalStack without extra dependencies" ([backend/storage/s3.py:6](../../../backend/storage/s3.py)); the SigV4 path is why LocalStack is useful — it exercises the exact signing the client ships (endpoint defaults match what MinIO/LocalStack expect — [backend/storage/s3.py:25](../../../backend/storage/s3.py)). A repository-wide search for "LocalStack" finds no deployment, no compose service, and no sandbox scaffolding anywhere else — only those two docstring lines (grep, checked 2026-10-10). In other words: the code is LocalStack-compatible, but no LocalStack exists as infrastructure yet.

LocalStack's own documentation describes per-plan feature and licensing tiers, and documents AWS API conformance testing and IAM policy enforcement as developer-tool capabilities:
- Plans/licensing: https://docs.localstack.cloud/aws/licensing/ (checked 2026-10-10; paid plans Base/Ultimate/Enterprise plus a non-commercial Hobby tier).
- IAM policy enforcement for developer testing: https://docs.localstack.cloud/aws/developer-tools/security-testing/iam-policy-enforcement/ (checked 2026-10-10).
- AWS service emulation (e.g., Events): https://docs.localstack.cloud/aws/services/events/ (checked 2026-10-10).

Because the licensing terms differ by plan and the intended use (developer sandbox vs. production-adjacent service) determines entitlement, the plan/entitlement choice is a user decision, not a code decision.

## Decision

1. **Role: emulator, conformance lab, safety lab only.** Paid LocalStack is a developer/sandbox facility. It is categorically **not**:
   - the system of record for anything;
   - a production event store (the durable event bus is NATS JetStream, per ADR-0002 — LocalStack's emulated SQS/SNS/EventBridge do not replace it);
   - the primary S3/object store in production (production object storage remains a real S3/MinIO-class service with real durability semantics);
   - a durable workflow/scheduler runtime (per ADR-0004);
   - the real IAM of record (identity/authorization is the JWT/SSO system at [backend/api/auth.py:1-5](../../../backend/api/auth.py) plus the ADR-0003 PDP);
   - a backup target or backup system of record.
2. **Discover entitlement at deployment.** Sandbox bootstrap verifies which LocalStack plan/license the deployment is entitled to (license token / plan metadata) and exposes the resulting capability set to the sandbox tooling; sandbox features are enabled conditionally, never assumed.
3. **IAM simulation in enforcement mode.** Sandbox IAM simulation runs with `ENFORCE_IAM=1` (per LocalStack's IAM-policy-enforcement developer tooling, https://docs.localstack.cloud/aws/developer-tools/security-testing/iam-policy-enforcement/ , checked 2026-10-10) so that permission-denial behavior is exercised, not merely emulated permissively.
4. **Isolated per-task namespaces.** Each sandbox scenario gets its own isolated namespace/account scope (fresh keys, fresh service state, disposable lifecycle); sandbox state is never shared between tasks and never persists past the task unless explicitly snapshotted for debugging.
5. **Licensing terms to be confirmed with the user.** This ADR assumes a paid plan covering developer-environment use; the exact plan (Base/Ultimate/Enterprise vs. Hobby for non-commercial) and its terms must be confirmed by the user before procurement. No entitlement is claimed here.

## Alternatives considered

1. **LocalStack as the always-on dev "production-like" service (including event store).** Tempting for uniformity, but makes emulator durability semantics the product's durability semantics; a LocalStack restart would silently lose "production" state. Rejected.
2. **Free-tier-only sandbox with permissive IAM (ENFORCE_IAM unset).** Cheaper, but skips the very behavior (IAM denial paths) NerveCenter most needs to test before the ADR-0003 PDP rollout. Rejected.
3. **Pure AWS sandbox accounts per task.** Real AWS, but high cost, slow provisioning, and no conformance-testing convenience; overkill for a developer loop. Noted as the eventual conformance target, not the daily tool.
4. **No LocalStack at all (tests against MinIO only).** MinIO validates S3 compatibility but not IAM-policy behavior or multi-service AWS conformance. Insufficient. Rejected.

## Consequences

- New sandbox scaffolding (compose/service + entitlement probe + per-task namespace provisioning) — none exists today (evidence: grep, checked 2026-10-10).
- Conformance test suites gain an emulated-AWS lane; results are labeled "emulated" and never reported as production AWS behavior.
- Security: sandbox keys are short-lived and namespace-scoped; sandbox network access to production S3/JetStream/Postgres is blocked by policy.
- Procurement is blocked on user confirmation of plan/entitlement; until then the sandbox runs at the minimum available tier with clearly degraded capabilities.

## References

- [backend/storage/s3.py:6](../../../backend/storage/s3.py), [backend/storage/s3.py:25](../../../backend/storage/s3.py)
- [backend/api/auth.py:1-5](../../../backend/api/auth.py)
- LocalStack plans/licensing: https://docs.localstack.cloud/aws/licensing/ (checked 2026-10-10)
- LocalStack IAM policy enforcement (developer tooling): https://docs.localstack.cloud/aws/developer-tools/security-testing/iam-policy-enforcement/ (checked 2026-10-10)
- LocalStack service emulation (Events): https://docs.localstack.cloud/aws/services/events/ (checked 2026-10-10)
- Absence of LocalStack infrastructure in the repository (only the two `s3.py` docstring mentions): grep over `*.py *.md *.yaml *.yml *.toml *.json *.sh` and Dockerfiles, checked 2026-10-10.
