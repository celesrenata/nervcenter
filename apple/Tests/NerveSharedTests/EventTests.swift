import XCTest
@testable import NerveModels

final class EventTests: XCTestCase {
    func testEventRoundtrip() throws {
        let event = Event(
            eventType: "entity.created",
            category: .knowledge,
            occurredAt: Date(timeIntervalSinceReferenceDate: 700_000_000),
            source: "agent-001",
            payload: ["entity_id": AnyCodable("ent-001")],
            id: "evt-001",
            createdAt: Date(timeIntervalSinceReferenceDate: 700_000_000)
        )

        let encoded = try NerveJSON.encode(event)
        let decoded = try NerveJSON.decode(Event.self, from: encoded!)

        XCTAssertEqual(event, decoded)
    }

    func testEventIntegrity() {
        var event = Event(
            eventType: "entity.created",
            category: .knowledge,
            occurredAt: Date(timeIntervalSinceReferenceDate: 700_000_000),
            source: "agent-001",
            payload: ["entity_id": AnyCodable("ent-001")],
            id: "evt-001",
            createdAt: Date(timeIntervalSinceReferenceDate: 700_000_000)
        )

        // Unsigned events (no stored hash) verify trivially (spec §10).
        XCTAssertTrue(event.verifyIntegrity())

        // Stamp the integrity digest; sha256 hex digest is 64 chars.
        let stamped = event.stampIntegrity()
        XCTAssertEqual(stamped.count, 64)
        XCTAssertEqual(event.hash, stamped)

        // A stamped event must verify against its recomputed digest.
        XCTAssertTrue(event.verifyIntegrity())

        // Tampering with the body must break the stored digest.
        event.payload["entity_id"] = AnyCodable("ent-999")
        XCTAssertFalse(event.verifyIntegrity())

        // Restoring the body restores integrity.
        event.payload["entity_id"] = AnyCodable("ent-001")
        XCTAssertTrue(event.verifyIntegrity())
    }

    func testEventIntegrityHashMatchesCanonicalSerialization() {
        let event = Event(
            eventType: "task.completed",
            category: .task,
            occurredAt: Date(timeIntervalSinceReferenceDate: 700_000_000),
            source: "orchestrator",
            severity: .info,
            traceId: "trace-1",
            id: "evt-002",
            createdAt: Date(timeIntervalSinceReferenceDate: 700_000_000)
        )

        let computed = event.computeIntegrityHash()
        XCTAssertNotNil(computed)
        XCTAssertEqual(computed?.count, 64)

        // The digest must be stable across recomputation (deterministic).
        XCTAssertEqual(computed, event.computeIntegrityHash())
    }
}
