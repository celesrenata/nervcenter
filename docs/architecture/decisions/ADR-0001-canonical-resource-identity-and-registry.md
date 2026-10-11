# ADR-0001: Canonical resource identity & registry

- **Number:** ADR-0001
- **Title:** Canonical resource identity & registry
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

NerveCenter today has no URI-based resource identity. A repository-wide search for `nc://` finds no code, schema, or deployment artifact (grep, checked 2026-10-10). The knowledge graph already exists and is the natural home for identity:

- `Entity` is "a node in the NerveCenter knowledge graph" with an `aliases: list[str]` field ([schemas/entities.py:37](../../../schemas/entities.py), [:56](../../../schemas/entities.py)).
- `EntityService` provides CRUD plus alias lookup and management: `find_by_alias` ([backend/knowledge/entity.py:292](../../../backend/knowledge/entity.py)), `add_alias` ([backend/knowledge/entity.py:353](../../../backend/knowledge/entity.py)); the service class is at [backend/knowledge/entity.py:139](../../../backend/knowledge/entity.py).
- `RelationshipService` manages edges between entities ([backend/knowledge/relationship.py:142](../../../backend/knowledge/relationship.py)); `entities`/`relationships` are created in the initial schema migration ([backend/persistence/alembic/versions/001_initial.py:13-14](../../../backend/persistence/alembic/versions/001_initial.py)).
- Four concrete connectors (`GitConnector` [backend/connectors/git.py:152](../../../backend/connectors/git.py), `GPUConnector` [backend/connectors/gpu.py:52](../../../backend/connectors/gpu.py), `HostConnector` [backend/connectors/host.py:64](../../../backend/connectors/host.py), `KubernetesConnector` [backend/connectors/kubernetes.py:25](../../../backend/connectors/kubernetes.py)) each expose their own provider-native ID spaces through the `Connector` ABC ([backend/connectors/base.py:524](../../../backend/connectors/base.py)) and `snapshot()` ([backend/connectors/base.py:697](../../../backend/connectors/base.py)). Nothing today maps those IDs to one another.

Consequences of the status quo: the same real-world resource (a repo, a pod, a photo, a person) appears under different opaque IDs per source, deduplication is manual, and cross-source queries have no stable join key.

## Decision

Adopt a canonical URI scheme `nc://` as the unique identity for every NerveCenter resource, backed by a PostgreSQL identity registry, with connector reconciliation as the population mechanism:

1. **URI grammar (proposed shape, to be ratified in C1):** `nc://<resource-type>/<stable-id>` — e.g. `nc://entity/0193...`, `nc://task/...`, `nc://incident/...`, `nc://media/...`. The exact path grammar is deliberately not frozen here; no existing API uses it, so nothing invented is claimed as current behavior.
2. **Registry:** a new PostgreSQL table (new Alembic revision on top of [backend/persistence/alembic/versions/001_initial.py](../../../backend/persistence/alembic/versions/001_initial.py)) mapping each `nc://` URI to its provider-native IDs (per connector/source), creation provenance, and lifecycle state.
3. **Extend, don't fork:** the registry reuses the existing entity/relationship model. The entity's canonical `nc://` URI becomes its identity; provider-native IDs are stored in the existing `aliases` field ([schemas/entities.py:56](../../../schemas/entities.py)) with source attribution, so `EntityService.find_by_alias` ([backend/knowledge/entity.py:292](../../../backend/knowledge/entity.py)) already resolves provider IDs to entities without a parallel lookup service.
4. **Connector reconciliation:** a periodic durable job consumes `Connector.snapshot()` ([backend/connectors/base.py:697](../../../backend/connectors/base.py)) for every registered connector, proposes identity merges (same provider ID, or alias collision), and writes registry rows only with a human-visible decision record for ambiguous merges.

## Alternatives considered

1. **UUID-only identity, no URIs.** Cheaper, but loses human-addressable resources, cross-source readability, and future URL-based routing (web/CLI/MCP). Rejected.
2. **Separate identity microservice.** An extra network hop and a second system of record before the core product exists. Rejected; a table in the existing Postgres is sufficient.
3. **Fork the knowledge graph into a dedicated identity model.** Would duplicate `EntityService`/`RelationshipService` behavior and create two graph stores to reconcile. Rejected per the extend-don't-fork principle.

## Consequences

- New migration (registry table) and one new durable reconciliation job; no changes to existing entity endpoints.
- Every new source that appears must register into the registry; provider-native IDs are never mutated at the source, only mapped.
- Ambiguous merges require a decision record; identity merges are irreversible once published URIs are referenced, so reconciliation must be conservative (alias-level until confirmed).
- `nc://` URIs are stable forever; renaming is handled by aliases, not by reissuing URIs.

## References

- [schemas/entities.py:37](../../../schemas/entities.py), [schemas/entities.py:56](../../../schemas/entities.py)
- [backend/knowledge/entity.py:139](../../../backend/knowledge/entity.py), [backend/knowledge/entity.py:292](../../../backend/knowledge/entity.py), [backend/knowledge/entity.py:353](../../../backend/knowledge/entity.py)
- [backend/knowledge/relationship.py:142](../../../backend/knowledge/relationship.py)
- [backend/connectors/base.py:524](../../../backend/connectors/base.py), [backend/connectors/base.py:697](../../../backend/connectors/base.py)
- [backend/persistence/alembic/versions/001_initial.py:13-14](../../../backend/persistence/alembic/versions/001_initial.py)
- Absence of `nc://` in the repository: grep over `*.py *.md *.yaml *.toml *.json *.ts *.tsx`, checked 2026-10-10.
