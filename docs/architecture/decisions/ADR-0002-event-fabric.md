# ADR-0002: Event fabric

- **Number:** ADR-0002
- **Title:** Event fabric — durable NATS JetStream bus with CloudEvents-spirit envelope
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

The event fabric is implemented on NATS JetStream:

- `EventPublisher.publish` publishes events onto the JetStream stream ([backend/events/publisher.py:126](../../../backend/events/publisher.py)).
- The wire format is a custom JSON envelope, `EventEnvelope` — "the JSON envelope sent over the wire, wrapping the event payload with delivery metadata (publish time, delivery attempts, NATS subject, etc.)" ([backend/events/models.py:7-11](../../../backend/events/models.py)).
- JetStream access is the delivery substrate: `jetstream` context property at [backend/events/nats_client.py:304](../../../backend/events/nats_client.py).
- Durable deduplication already exists in Postgres: `UniqueConstraint("idempotency_key")` on the `events` table ([backend/persistence/alembic/versions/001_initial.py:73](../../../backend/persistence/alembic/versions/001_initial.py)).
- The dead-letter queue is **in-process**: `self._dead_letter: list[dict[str, Any]] = []` on the subscriber ([backend/events/subscriber.py:125](../../../backend/events/subscriber.py)). It is lost on process restart and is not observable from outside the process.
- Production deploys a single NATS instance (`replicas: 1`, image `nats:2.10-alpine`) — [deployments/kubernetes/base/nats-deployment.yaml:15,26](../../../deployments/kubernetes/base/nats-deployment.yaml).

## Decision

1. **Keep NATS JetStream as the durable bus.** No replacement bus. Streams remain the system of record for ordered event history; Postgres remains the dedup index.
2. **Adopt a CloudEvents-spirit envelope extension of the existing custom envelope.** Add additive fields to `EventEnvelope` ([backend/events/models.py:7-11](../../../backend/events/models.py)) in the spirit of the CloudEvents spec — `id`, `source`, `type`, `time`, `subject`, `data_content_type`, `data_schema`, plus spec extension attributes — without replacing the existing envelope or breaking existing consumers. This is an evolution of the wire model, not a claim of full CloudEvents conformance, and no CloudEvents API is asserted to exist in the repo today.
3. **Encrypted raw payload in object storage.** Events whose payloads are large or sensitive store the raw payload in object storage (S3/MinIO-compatible, SigV4-signed — [backend/storage/s3.py:1](../../../backend/storage/s3.py); in-memory backend for tests — [backend/storage/memory.py](../../../backend/storage/memory.py)) encrypted at rest with a key outside the event stream; the envelope carries only an opaque content reference.
4. **Mandatory DLQ / quarantine / replay / redaction.** Every consumer path must implement all four:
   - **DLQ:** move the in-process dead letter list ([backend/events/subscriber.py:125](../../../backend/events/subscriber.py)) to a durable JetStream DLQ stream plus a Postgres row per quarantined event, so dead letters survive restarts and are queryable.
   - **Quarantine:** events failing schema/policy validation are parked, not dropped or redelivered forever.
   - **Replay:** existing replay primitives (`ReplayRequest`/`ReplayResult`, [backend/events/models.py:10-11](../../../backend/events/models.py)) remain the sole replay path; replay must honor the idempotency constraint at [backend/persistence/alembic/versions/001_initial.py:73](../../../backend/persistence/alembic/versions/001_initial.py).
   - **Redaction:** payload redaction rules are evaluated at publish time so the durable stream never holds unredacted sensitive material (see `redact_url`-style handling, [backend/api/wiring.py:29-36](../../../backend/api/wiring.py)).
5. **Operational floor:** NATS must run with persistence and replication before the bus is treated as durable in production; the current single-replica deployment ([deployments/kubernetes/base/nats-deployment.yaml:15](../../../deployments/kubernetes/base/nats-deployment.yaml)) is a gap to close, not a design.

## Alternatives considered

1. **Full CloudEvents migration (replace the envelope).** Breaks every existing consumer and the Postgres schema; no benefit that the additive extension does not give. Rejected.
2. **Kafka.** Heavier operations burden (ZooKeeper/KRaft, topic management) for a workload JetStream already serves durably. Rejected.
3. **Postgres-only event store (no broker).** Loses push delivery, backpressure, and consumer groups; makes the event API a database client. Rejected.
4. **Keep the in-process DLQ.** Data loss on restart of any API process is unacceptable for an "event fabric." Rejected.

## Consequences

- `EventEnvelope` gains optional fields; old consumers ignore them, new consumers require them — a rolling compatibility window is needed.
- Object storage becomes a hard dependency for sensitive/large events; key management lives outside the event system (no vault exists today — grep for "vault" over `*.py *.md *.yaml` returns nothing, checked 2026-10-10).
- DLQ becomes observable infrastructure: it needs its own stream retention policy, alerts, and a replay runbook.
- Single-replica NATS must move to a replicated configuration before durability claims are valid.

## References

- [backend/events/publisher.py:126](../../../backend/events/publisher.py)
- [backend/events/models.py:7-11](../../../backend/events/models.py), [backend/events/models.py:10-11](../../../backend/events/models.py)
- [backend/events/nats_client.py:304](../../../backend/events/nats_client.py)
- [backend/events/subscriber.py:125](../../../backend/events/subscriber.py)
- [backend/persistence/alembic/versions/001_initial.py:73](../../../backend/persistence/alembic/versions/001_initial.py)
- [backend/storage/s3.py:1](../../../backend/storage/s3.py), [backend/storage/memory.py](../../../backend/storage/memory.py)
- [backend/api/wiring.py:29-36](../../../backend/api/wiring.py)
- [deployments/kubernetes/base/nats-deployment.yaml:15,26](../../../deployments/kubernetes/base/nats-deployment.yaml)
