import XCTest
@testable import NerveModels
@testable import NervePersistence

final class CacheTests: XCTestCase {
    func testCacheRoundtrip() async throws {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("nerve-test-\(UUID().uuidString)")

        defer { try? FileManager.default.removeItem(at: tempDir) }

        let cache = LocalCache(directory: tempDir)
        let initialState = await cache.snapshot
        XCTAssertEqual(initialState.systemHealth, "unknown")

        let updatedState = CachedState(
            systemHealth: "healthy",
            activeIncidents: 0,
            runningAgents: 7,
            pendingApprovals: 1,
            primaryGoalProgress: 0.76
        )
        await cache.replace(with: updatedState)

        // Re-instantiate from the same directory: the atomic snapshot must
        // reload intact from disk (actor init re-reads the state file).
        let reloaded = LocalCache(directory: tempDir)
        let loaded = await reloaded.snapshot
        XCTAssertEqual(loaded.systemHealth, "healthy")
        XCTAssertEqual(loaded.runningAgents, 7)
        XCTAssertEqual(loaded.pendingApprovals, 1)
        XCTAssertEqual(loaded.primaryGoalProgress, 0.76)
    }

    func testCacheUpdateMutation() async throws {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("nerve-test-\(UUID().uuidString)")

        defer { try? FileManager.default.removeItem(at: tempDir) }

        let cache = LocalCache(directory: tempDir)

        await cache.update { state in
            state.systemHealth = "degraded"
            state.pendingApprovals += 1
        }

        let reloaded = LocalCache(directory: tempDir)
        let loaded = await reloaded.snapshot
        XCTAssertEqual(loaded.systemHealth, "degraded")
        XCTAssertEqual(loaded.pendingApprovals, 1)
    }

    func testCacheAtomicWriteDoesNotCorruptJSON() async throws {
        let tempDir = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("nerve-test-\(UUID().uuidString)")

        defer { try? FileManager.default.removeItem(at: tempDir) }

        let cache = LocalCache(directory: tempDir)
        await cache.replace(with: CachedState(
            systemHealth: "healthy",
            runningAgents: 3
        ))

        // The on-disk snapshot must be valid JSON decodable by the wire
        // decoder (atomic `.atomic` replace guarantees no mid-write torn file).
        let fileURL = await cache.fileURL
        let data = try Data(contentsOf: fileURL)
        let decoded = LocalCache.decode(data)
        XCTAssertNotNil(decoded)
        XCTAssertEqual(decoded?.systemHealth, "healthy")
        XCTAssertEqual(decoded?.runningAgents, 3)
    }
}
