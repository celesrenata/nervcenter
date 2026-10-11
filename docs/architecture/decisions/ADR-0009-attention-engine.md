# ADR-0009: Attention engine

- **Number:** ADR-0009
- **Title:** Attention engine — durable, LLM-independent core; calm queue; non-binding health hints
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

The product's attention/communication-style entities are specified but not yet implemented: the spec-2 addendum's "New Core Entities" section (beginning [prompt2.md:195](../../../prompt2.md)) includes `AttentionItem`/`Communication`-style records, and the uplift tracker records them as absent from `backend/persistence/models/` — [specs/nervcenter-uplift/tasks.md:45](../../../specs/nervcenter-uplift/tasks.md) ("Prompt2 addendum entities unimplemented … `AttentionItem`, `Communication`, etc. absent"). There is no attention engine in the codebase today (grep for "attention" over `backend/` finds no module, checked 2026-10-10).

Supporting context: durable execution is being adopted (ADR-0004), LLM routing exists but is unwired from the API ([backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py), [backend/inference/policy.py:95](../../../backend/inference/policy.py); no `backend/api/` call sites, grep checked 2026-10-10), and the spec-2 addendum's wake-up-clock concept implies a periodic trigger. iOS surface (widgets — [apple/Widgets/NerveCenterWidgetBundle.swift](../../../apple/Widgets/NerveCenterWidgetBundle.swift)) is where a ranked queue would be rendered.

## Decision

1. **Durable core.** The attention engine runs on the durable workflow runtime (ADR-0004): observation → triage → ranking → surfacing is a durable pipeline, not an in-process loop. Queue state is queryable from Postgres and survives restarts.
2. **LLM-independent core.** Ranking, prioritization, and surfacing logic must work with *no* model available. LLM calls (via the ADR-0003-gated inference path) are optional enrichment (summarization, phrasing) layered on top, never a dependency of the core ranking. If inference is down or denied, the queue still ranks and surfaces.
3. **Calm ranked queue.** The user-facing artifact is a single ranked queue with a small stable top-N. Ranking signals are explicit and inspectable (age, consequence, dependencies, user-stated priority, repeat-occurrence). Anti-patterns are prohibited by policy:
   - **no guilt mechanics** (no "you've been ignoring this" framing, no shame-based copy or styling);
   - **no streak mechanics** (no streaks, no loss-of-progress pressure, no artificial escalation cadence);
   - quietness is a feature: items may legitimately stay un-notified.
4. **Wake-up clock trigger.** A durable periodic trigger (wake-up clock) drives re-evaluation of the queue at a user-configurable cadence. It decides *when the system looks*, never that the user must act.
5. **Non-binding HealthKit hints.** Where HealthKit observer data is available (local-first, user-granted, per ADR-0008 decision 6; observer model: https://developer.apple.com/documentation/healthkit/executing-observer-queries , checked 2026-10-10), it may adjust *timing hints* (e.g., prefer surfacing at a time consistent with the user's observed wake pattern). Hints are: non-binding (the clock cadence still governs), user-visible, user-disablable, and raw health data never leaves the device (ADR-0008).
6. **External notification via standard channels only.** Outbound notifications use standard, user-managed channels (e.g., a webhook contact point in the style of Grafana's webhook notifier — https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/ , checked 2026-10-10; Home Assistant automations via its WebSocket API — https://developers.home-assistant.io/docs/api/websocket/ , checked 2026-10-10). Every external message is PDP-checked (ADR-0003) and recorded as an event (ADR-0002).

## Alternatives considered

1. **LLM-ranked queue (model is the ranker).** Makes the product's core UX depend on model availability/latency/cost and on policy approval for each ranking pass; violates decision 2. Rejected.
2. **Streaks/gamification for engagement.** Directly conflicts with the calm design intent and with decision 3; engagement pressure on a personal-operations product is a design defect, not a feature. Rejected categorically.
3. **In-process scheduler for wake-up (reuse [backend/scheduler/scheduler.py:102](../../../backend/scheduler/scheduler.py)).** Scheduler placement is not durable execution; a missed wake-up should be recoverable, which requires the durable runtime. Rejected.
4. **Raw HealthKit data as a ranking feature on the backend.** Violates the local-first constraint (ADR-0008); only non-binding derived hints cross the boundary. Rejected.

## Consequences

- New durable pipeline + Postgres queue tables; the spec-2 addendum entities ([specs/nervcenter-uplift/tasks.md:45](../../../specs/nervcenter-uplift/tasks.md)) get implemented against this design, not as ad-hoc models.
- Ranking is auditable: every rank decision stores its signal breakdown; users can see *why* an item moved.
- The anti-patterns (guilt/streak) are policy-testable: CI should assert no streak/guilt constructs in queue schema or copy.
- HealthKit integration stays minimal (observer queries, timing hints only), keeping the privacy surface at the ADR-0008 floor.
- Webhook/WebSocket integrations inherit standard contact-point configuration (secret management, delivery receipts); no custom push infrastructure is invented.

## References

- [prompt2.md:195](../../../prompt2.md) ("# 5. New Core Entities")
- [specs/nervcenter-uplift/tasks.md:45](../../../specs/nervcenter-uplift/tasks.md)
- [apple/Widgets/NerveCenterWidgetBundle.swift](../../../apple/Widgets/NerveCenterWidgetBundle.swift)
- [backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py), [backend/inference/policy.py:95](../../../backend/inference/policy.py)
- [backend/scheduler/scheduler.py:102](../../../backend/scheduler/scheduler.py)
- HealthKit observer queries: https://developer.apple.com/documentation/healthkit/executing-observer-queries (checked 2026-10-10)
- Grafana webhook notifier: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/ (checked 2026-10-10)
- Home Assistant WebSocket API: https://developers.home-assistant.io/docs/api/websocket/ (checked 2026-10-10)
- Absence of an attention module in `backend/`: grep, checked 2026-10-10.
