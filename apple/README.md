# NerveCenter Apple Shared SDK

## Overview

This package contains the shared Swift modules for NerveCenter's Apple platforms:

- **NerveModels**: Core data types (events, entities, evidence, claims, tasks, goals)
- **NerveAPI**: HTTP client and mock transport
- **NerveAuth**: Authentication and approval system
- **NervePersistence**: Local cache and synchronization
- **NerveRealtime**: WebSocket/SSE client
- **NerveDesign**: Design tokens and styling

## Usage

```swift
import NerveShared

let event = Event(
    eventType: "entity.created",
    category: .knowledge,
    source: "agent-001",
    payload: ["entity_id": AnyCodable("ent-001")],
    id: "evt-001"
)
```

## Contracts

All modules mirror the v0 Python schemas in `schemas/`:

- `schemas.base.py` → `NerveModels/Record.swift`
- `schemas.events.py` → `NerveModels/Event.swift`
- ...

## Platforms

- iOS 17+
- watchOS 10+
- macOS 14+
- macCatalyst 17+

## Dependencies

None (zero external dependencies per spec §54).
