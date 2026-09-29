import XCTest
@testable import NerveAPI

final class MockTransportTests: XCTestCase {
    func testMockTransportRecordsCalls() {
        let transport = MockTransport()
        let client = APIClient(
            baseURL: URL(string: "https://nerv.bot/api")!,
            transport: transport
        )

        let expectation = expectation(description: "Request completes")
        client.send(path: "/events") { (result: Result<[Event], Error>) in
            expectation.fulfill()
        }
        wait(for: [expectation], timeout: 1)

        XCTAssertEqual(transport.callCount, 1)
        XCTAssertEqual(transport.lastCall?.request.url?.path, "/api/events")
    }

    func testMockTransportFixedResponse() {
        let transport = MockTransport()
        transport.fixedResponse = .success("""
            {
                "event_type": "entity.created",
                "category": "knowledge",
                "source": "agent-001",
                "payload": {
                    "entity_id": "ent-001"
                }
            }
            """.data(using: .utf8)!)

        let client = APIClient(
            baseURL: URL(string: "https://nerv.bot/api")!,
            transport: transport
        )

        let expectation = expectation(description: "Request completes")
        client.send(path: "/events") { (result: Result<[Event], Error>) in
            switch result {
            case .success(let events):
                XCTAssertEqual(events.count, 1)
                XCTAssertEqual(events[0].eventType, "entity.created")
            case .failure:
                XCTFail("Request should succeed")
            }
            expectation.fulfill()
        }
        wait(for: [expectation], timeout: 1)
    }
}
