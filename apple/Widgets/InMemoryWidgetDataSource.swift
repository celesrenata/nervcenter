import Foundation

import NerveApps

// MARK: - In-memory widget data source (tests / previews)

/// A simple in-memory ``WidgetDataSource`` for tests and previews.
///
/// Deterministic: no file I/O, no network. Seed `state` directly to exercise
/// the connected / not-connected / no-data paths.
public final class InMemoryWidgetDataSource: WidgetDataSource, @unchecked Sendable {
    public var state: WidgetDataState

    public init(state: WidgetDataState = .notConnected) {
        self.state = state
    }

    /// Convenience: seed a connected snapshot from a tile.
    public init(tile: NerveApps.WidgetTile, updatedAt: Date? = nil) {
        self.state = .connected(
            snapshot: WidgetSnapshot(tile: tile, updatedAt: updatedAt ?? tile.updatedAt)
        )
    }

    public func makeTile() async throws -> WidgetSnapshot {
        switch state {
        case .connected(let snapshot):
            return snapshot
        case .notConnected, .noData:
            return WidgetSnapshot(tile: nil, updatedAt: nil)
        }
    }

    public func hasStateFile() async -> Bool {
        switch state {
        case .connected, .noData:
            return true
        case .notConnected:
            return false
        }
    }
}
