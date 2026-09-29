import XCTest
@testable import NerveAPI
@testable import NerveModels

final class MockTransportTests: XCTestCase {
    func testMockTransportRecordsCalls() async throws {
        let transport = MockTransport()
        let client = APIClient(
            baseURL: URL(string: "https://nerv.bot/api")!,
            transport: transport
        )

        // MockTransport returns an empty body for unmatched requests; decoding
        // an `[Event]` from it fails, which is still a completed round trip.
        let result: Result<[Event], Error> = await Result {
            try await client.send(path: "/events")
        }

        if case .failure(let error) = result {
            XCTAssertTrue(error is NerveAPIError, "expected a NerveAPIError decode failure, got \(error)")
        }

        XCTAssertEqual(transport.callCount, 1)
        XCTAssertEqual(transport.lastCall?.request.url?.path, "/api/events")
        XCTAssertEqual(transport.lastCall?.request.httpMethod, "GET")
        XCTAssertEqual(
            transport.lastCall?.request.value(forHTTPHeaderField: "Content-Type"),
            "application/json"
        )
    }

    func testMockTransportFixedResponse() async throws {
        let transport = MockTransport()
        transport.fixedResponse = .success("""
            [{
                "event_type": "entity.created",
                "category": "knowledge",
                "occurred_at": "2026-01-31T12:00:00Z",
                "source": "agent-001",
                "payload": {
                    "entity_id": "ent-001"
                },
                "severity": "info",
                "id": "evt-001",
                "created_at": "2026-01-31T12:00:00Z",
                "schema_version": "v0"
            }]
            """.data(using: .utf8)!)

        let client = APIClient(
            baseURL: URL(string: "https://nerv.bot/api")!,
            transport: transport
        )

        let events: [Event] = try await client.send(path: "/events")

        XCTAssertEqual(events.count, 1)
        XCTAssertEqual(events[0].eventType, "entity.created")
        XCTAssertEqual(events[0].source, "agent-001")
        XCTAssertEqual(transport.callCount, 1)
        XCTAssertEqual(transport.lastCall?.request.url?.path, "/api/events")
    }

    func testMockTransportCorrelationHeaders() async throws {
        let transport = MockTransport()
        let client = APIClient(
            baseURL: URL(string: "https://nerv.bot/api")!,
            transport: transport,
            correlation: CorrelationMetadata(
                traceId: "trace-1",
                goalId: "goal-1",
                verificationPolicy: "tool-based"
            )
        )

        _ = await Result<[Event], Error> {
            try await client.send(path: "/events")
        }

        let request = transport.lastCall?.request
        XCTAssertEqual(request?.value(forHTTPHeaderField: "nerve_trace_id"), "trace-1")
        XCTAssertEqual(request?.value(forHTTPHeaderField: "nerve_goal_id"), "goal-1")
        XCTAssertEqual(request?.value(forHTTPHeaderField: "verification_policy"), "tool-based")
        XCTAssertNil(request?.value(forHTTPHeaderField: "nerve_task_id"))
    }
}
