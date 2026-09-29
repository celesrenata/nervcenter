import XCTest
@testable import NerveModels

final class SynchronizedStateTests: XCTestCase {
    func testSynchronizedStatePayload() {
        let state = SynchronizedState(
            systemHealth: "healthy",
            activeIncidents: 1,
            runningAgents: 7,
            pendingApprovals: 2,
            primaryGoalProgress: 0.76
        )

        XCTAssertEqual(state.systemHealth, "healthy")
        XCTAssertEqual(state.activeIncidents, 1)
        XCTAssertEqual(state.runningAgents, 7)
        XCTAssertEqual(state.pendingApprovals, 2)
        XCTAssertEqual(state.primaryGoalProgress, 0.76)
    }

    func testSynchronizedStateRoundtrip() throws {
        let state = SynchronizedState(
            systemHealth: "degraded",
            activeIncidents: 3,
            runningAgents: 5,
            pendingApprovals: 0,
            primaryGoalProgress: 0.42
        )

        let encoded = try NerveJSON.encode(state)
        let decoded = try NerveJSON.decode(SynchronizedState.self, from: encoded!)

        XCTAssertEqual(state, decoded)
    }
}
