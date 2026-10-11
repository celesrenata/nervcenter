# ADR-0008: Photo/health local-first

- **Number:** ADR-0008
- **Title:** Photo/health local-first — Immich subsystem, PhotoKit-permitted ingest, face data never leaves
- **Status:** Proposed
- **Date:** 2026-10-10
- **Spec:** NC-SPEC-2026-010 (C0)

## Context

NerveCenter's spec (3,566 lines — `wc -l docs/nervcenter-spec.md`, checked 2026-10-10; header "NerveCenter — Version 0.2 Initial Build Specification" at [docs/nervcenter-spec.md:1-3](../../../docs/nervcenter-spec.md)) and the spec-2 addendum introduce person-centric entities (the "New Core Entities" section begins at [prompt2.md:195](../../../prompt2.md), tracking note: [specs/nervcenter-uplift/tasks.md:45](../../../specs/nervcenter-uplift/tasks.md)) — including attention/communication-style records. The iOS surface exists (widget bundle, app skeleton — [apple/Widgets/NerveCenterWidgetBundle.swift](../../../apple/Widgets/NerveCenterWidgetBundle.swift), [apple/iOS/App](../../../apple/iOS/App)) but a search for `PhotoKit`/`HealthKit` across `apple/` finds no integrations yet (grep, checked 2026-10-10). No photo/ML subsystem is deployed in the repository (no Immich references anywhere, grep checked 2026-10-10).

Relevant external capabilities (all URLs checked 2026-10-10):
- Immich facial recognition (on-device/server-side face embeddings and clustering): https://docs.immich.app/features/facial-recognition/
- Immich external libraries (shared/remote library mounting): https://docs.immich.app/features/libraries/

The privacy bar is explicit in this product's domain: face embeddings and health data are special-category data. The decisions below are privacy constraints, not features.

## Decision

1. **Immich as the photo library / ML subsystem.** Immich is adopted as the photo-library backend (ingest, storage, face recognition, clustering). NerveCenter is a *consumer* of Immich (library + ML results), never a fork of it (adapter rule, ADR-0007). Multi-person access to shared collections uses Immich's library model (https://docs.immich.app/features/libraries/ , checked 2026-10-10) rather than a bespoke share system.
2. **PhotoKit, user-permitted ingest only.** The iOS app requests Photos library access via PhotoKit with explicit user permission per the platform's enhanced-privacy guidance (https://developer.apple.com/documentation/photokit/delivering-an-enhanced-privacy-experience-in-your-photos-app , checked 2026-10-10). Ingest is always user-initiated and user-scoped; no silent background scanning of the photo library.
3. **Local embeddings / face clustering.** Face embeddings and clusters are computed in the local/Immich subsystem (server-local by deployment, user-owned). Results are referenced by ID from NerveCenter's entity model (person entities per ADR-0001) — the *embedding bytes* are not copied into the NerveCenter knowledge graph.
4. **Explicit user labels.** Any face→person assignment is an explicit user label; the system may *suggest* clusters but never auto-assigns identities. Suggestion data is visible, correctable, and deletable by the user.
5. **Never publish face embeddings to remote providers.** Hard invariant: face embeddings (and the derived face-cluster data) are never sent to any remote inference provider, model API, or third-party service — including the inference routing path of [backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py). Enforced at the policy layer (ADR-0003 PDP rule: face-embedding resources have no remote-egress permit) and at the adapter boundary (ADR-0007 untrusted-content/egress rules). This is the single most important constraint in this ADR and supersedes any future routing convenience.
6. **Health data: local-first observer pattern.** Health inputs (where present) follow the HealthKit observer-query model (https://developer.apple.com/documentation/healthkit/executing-observer-queries , checked 2026-10-10): user-granted, on-device, query-scoped. Raw health records are not ingested into the backend; only user-approved, minimal derived signals are (e.g., "saw a wake-up pattern") and are treated under ADR-0009 as non-binding hints.

## Alternatives considered

1. **Roll our own photo ML (detection + embeddings) in-repo.** Duplicates a mature subsystem; slower to trustworthy quality; same privacy surface with less review history. Rejected.
2. **Remote face recognition via cloud model APIs.** Violates decision 5; unacceptable for special-category biometric data in this product. Rejected categorically.
3. **Store face embeddings in the NerveCenter Postgres knowledge graph.** Couples biometric data to the general-purpose DB, expands its breach blast radius, and breaks the local-first boundary. Rejected.
4. **Auto-assign person identities from clustering accuracy.** Accuracy claims are not consent; wrong assignments on biometric data are worse than no assignment. Rejected.

## Consequences

- Immich becomes a required component of the personal-deployment topology (its own service, storage, and backup lane); NerveCenter deploys against it via the connector/adapter pattern.
- iOS app gains a Photos permission flow with granular, revocable scope; the widget/app code (e.g. [apple/Widgets/NerveCenterWidgetBundle.swift](../../../apple/Widgets/NerveCenterWidgetBundle.swift)) reads only NerveCenter-side data, never raw photos.
- The PDP gains an explicit face-data egress rule; CI should include a policy test asserting no remote-egress permit exists for face-embedding resources.
- "Suggest, don't assign" changes UX: person identification is a user loop, not a system claim — slower, and intentionally so.
- Backup policy: face data is backed up only in the Immich subsystem's lane, encrypted, and subject to the same no-remote-publication rule; NerveCenter backups contain IDs/labels, not embedding bytes.

## References

- [docs/nervcenter-spec.md:1-3](../../../docs/nervcenter-spec.md) (3,566 lines, `wc -l`, checked 2026-10-10)
- [prompt2.md:195](../../../prompt2.md) ("# 5. New Core Entities")
- [specs/nervcenter-uplift/tasks.md:45](../../../specs/nervcenter-uplift/tasks.md)
- [apple/Widgets/NerveCenterWidgetBundle.swift](../../../apple/Widgets/NerveCenterWidgetBundle.swift)
- [backend/inference/omniroute.py:60](../../../backend/inference/omniroute.py)
- Immich facial recognition: https://docs.immich.app/features/facial-recognition/ (checked 2026-10-10)
- Immich external libraries: https://docs.immich.app/features/libraries/ (checked 2026-10-10)
- PhotoKit enhanced-privacy guidance: https://developer.apple.com/documentation/photokit/delivering-an-enhanced-privacy-experience-in-your-photos-app (checked 2026-10-10)
- HealthKit observer queries: https://developer.apple.com/documentation/healthkit/executing-observer-queries (checked 2026-10-10)
- Absence of PhotoKit/HealthKit/Immich code in the repository: grep over `apple/`, code, and manifests, checked 2026-10-10.
