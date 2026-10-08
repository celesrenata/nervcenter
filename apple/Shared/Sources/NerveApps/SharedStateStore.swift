import Foundation

import NerveModels
import NervePersistence

// MARK: - Cross-target shared state (App Group container)

/// The payload the iPhone publishes to the App Group container so the Watch
/// app (§69) and the WidgetKit extension (§62) can render from cached state
/// without a live connection. Written by ``NervePhone``, read by
/// ``NerveWatch`` / ``NerveWidgets``.
public struct PublishedNerveState: Codable, Hashable, Sendable {
    /// §69 compact phone↔Watch contract (consumed by the Watch app).
    public var sync: SynchronizedState
    /// §62 widget render contract (consumed by the Widget extension).
    public var tile: WidgetTile
    /// When the phone last wrote this state (drives stale marking).
    public var updatedAt: Date

    public init(sync: SynchronizedState, tile: WidgetTile, updatedAt: Date = Date()) {
        self.sync = sync
        self.tile = tile
        self.updatedAt = updatedAt
    }

    /// Build a publishable snapshot from a §73 cache plus the leading compute
    /// rows, primary goal, and summaries.
    public static func make(
        from cache: CachedState,
        primaryGoalLabel: String?,
        incidentsSummary: String?,
        agentActivitySummary: String?,
        computeRows: [ComputeWidgetRow]
    ) -> PublishedNerveState {
        let sync = StaleState.compact(from: cache)
        let tile = WidgetTile(
            systemHealth: cache.systemHealth,
            agents: cache.runningAgents,
            incidents: cache.activeIncidents,
            pendingApprovals: cache.pendingApprovals,
            primaryGoalLabel: primaryGoalLabel,
            primaryGoalProgress: cache.primaryGoalProgress,
            computeRows: computeRows,
            incidentsSummary: incidentsSummary,
            agentActivitySummary: agentActivitySummary,
            updatedAt: cache.updatedAt
        )
        return PublishedNerveState(sync: sync, tile: tile, updatedAt: cache.updatedAt)
    }
}

/// Error surfaced when the shared-state payload cannot be read.
public enum SharedStoreError: Error {
    case missing
    case unreadable(String)
}

/// Reads and writes the publishable Nerve state inside an App Group container
/// directory. Platform-free (file I/O only) so the phone/Watch/Widget targets
/// and tests all share one implementation.
public struct SharedStateStore: Sendable {
    public let directory: URL
    private let filename = "nerve-published-state.json"

    public init(directory: URL) {
        self.directory = directory
    }

    public var fileURL: URL { directory.appendingPathComponent(filename) }

    /// Atomically write the published state into the container.
    public func write(_ state: PublishedNerveState) throws {
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        guard let data = NerveJSON.encode(state) else {
            throw SharedStoreError.unreadable("could not encode published state")
        }
        try data.write(to: fileURL, options: .atomic)
    }

    /// Read the published state, returning `nil` when nothing has been written.
    public func read() -> PublishedNerveState? {
        guard let data = try? Data(contentsOf: fileURL) else { return nil }
        return NerveJSON.decode(PublishedNerveState.self, from: data)
    }

    /// Delete the shared state (used by "unpair" / reset).
    public func clear() {
        try? FileManager.default.removeItem(at: fileURL)
    }
}
