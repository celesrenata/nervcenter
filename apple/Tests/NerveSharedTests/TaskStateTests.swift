import XCTest
@testable import NerveModels

final class TaskStateTests: XCTestCase {
    func testTaskStateCases() {
        let allCases: [TaskState] = [
            .pending,
            .ready,
            .running,
            .blocked,
            .verifying,
            .succeeded,
            .failed,
            .cancelled
        ]
        XCTAssertEqual(TaskState.allCases, allCases)
    }

    func testTaskStateWireValues() {
        XCTAssertEqual(TaskState.pending.rawValue, "PENDING")
        XCTAssertEqual(TaskState.ready.rawValue, "READY")
        XCTAssertEqual(TaskState.running.rawValue, "RUNNING")
        XCTAssertEqual(TaskState.blocked.rawValue, "BLOCKED")
        XCTAssertEqual(TaskState.verifying.rawValue, "VERIFYING")
        XCTAssertEqual(TaskState.succeeded.rawValue, "SUCCEEDED")
        XCTAssertEqual(TaskState.failed.rawValue, "FAILED")
        XCTAssertEqual(TaskState.cancelled.rawValue, "CANCELLED")
    }
}
