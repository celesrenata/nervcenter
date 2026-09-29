import XCTest
@testable import NerveModels
@testable import NervePersistence

final class CacheTests: XCTestCase {
    func testCacheRoundtrip() throws {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("nerve-test-\(UUID().uuidString)")

        defer { try? FileManager.default.removeItem(at: tempDir) }

        let cache = LocalCache(directory: tempDir)
        let initialState = cache.snapshot

        let updatedState = CachedState(
            systemHealth: "healthy",
            activeIncidents: 0,
            runningAgents: 7,
            pendingApprovals: 1,
            primaryGoalProgress: 0.76
        )
        cache.replace(with: updatedState)

        let loaded = cache.loadFromDisk()
        XCTAssertEqual(loaded.systemHealth, "healthy")
        XCTAssertEqual(loaded.runningAgents, 7)
    }

    func testCacheUpdateMutation() {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("nerve-test-\(UUID().uuidString)")

        defer { try? FileManager.default.removeItem(at: tempDir) }

        let cache = LocalCache(directory: tempDir)

        cache.update { state in
            state.systemHealth = "degraded"
            state.pendingApprovals += 1
        }

        let loaded = cache.loadFromDisk()
        XCTAssertEqual(loaded.systemHealth, "degraded")
    }
}
