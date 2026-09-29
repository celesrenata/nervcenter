import XCTest
@testable import NerveModels

final class EventTests: XCTestCase {
    func testEventRoundtrip() throws {
        let event = Event(
            eventType: "entity.created",
            category: .knowledge,
            source: "agent-001",
            payload: ["entity_id": AnyCodable("ent-001")],
            id: "evt-001"
        )

        let encoded = try NerveJSON.encode(event)
        let decoded = try NerveJSON.decode(Event.self, from: encoded!)

        XCTAssertEqual(event, decoded)
    }

    func testEventHashing() {
        let event = Event(
            eventType: "entity.created",
            category: .knowledge,
            source: "agent-001",
            payload: ["entity_id": AnyCodable("ent-001")],
            id: "evt-001"
        )

        XCTAssertTrue(event.verifyIntegrity())
    }
}
