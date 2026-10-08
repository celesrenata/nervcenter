import Foundation
import WidgetKit

import NerveApps

// MARK: - §62 Timeline provider

/// One point in the widget timeline.
///
/// The entry carries the resolved ``WidgetDataState`` so views can render the
/// honest placeholder states directly (no per-render I/O on the widget
/// process).
public struct NerveCenterWidgetEntry: TimelineEntry {
    public let date: Date
    public let state: WidgetDataState

    public init(date: Date, state: WidgetDataState) {
        self.date = date
        self.state = state
    }

    /// Staleness of this entry's tile (``StaleState/StalenessPolicy/default``:
    /// 90 s). `false` when there is no tile.
    public var isStale: Bool {
        guard case .connected(let snapshot) = state,
              let updatedAt = snapshot.effectiveUpdatedAt else {
            return false
        }
        return StaleState.evaluate(updatedAt: updatedAt).isStale
    }
}

/// Builds widget timelines for all three §62 sizes from a
/// ``WidgetDataSource``.
///
/// Uses the classic completion-based ``TimelineProvider`` (NOT
/// `AsyncTimelineProvider`, which does not exist on the macOS host — the
/// repo requires every target to build on macOS for `swift build` /
/// `swift test`). The async data source is bridged with `Task`.
///
/// Refresh cadence (spec §62: widgets render from cached App Group state):
/// - Connected + fresh: 15 min (the phone re-publishes as it syncs).
/// - Connected but stale: 5 min, so a "stale" caption is replaced by a fresh
///   tile as soon as the phone writes again.
/// - No data at all: 30 min, so "Not connected" / "No data yet" keeps
///   checking for the phone to show up without hammering the system.
public struct NerveCenterWidgetProvider: TimelineProvider {
    /// The data source. Injectable so tests/previews can use
    /// ``InMemoryWidgetDataSource``.
    public let dataSource: any WidgetDataSource

    public init() {
        self.dataSource = AppGroupWidgetDataSource()
    }

    public init(dataSource: any WidgetDataSource) {
        self.dataSource = dataSource
    }

    public func placeholder(in context: Context) -> NerveCenterWidgetEntry {
        // Honest: the placeholder is the "Not connected" state, never fake
        // data. It is what the system shows while the first timeline loads.
        NerveCenterWidgetEntry(date: Date(), state: .notConnected)
    }

    public func getSnapshot(in context: Context, completion: @escaping (NerveCenterWidgetEntry) -> Void) {
        Task {
            completion(await makeEntry())
        }
    }

    public func getTimeline(in context: Context, completion: @escaping (Timeline<NerveCenterWidgetEntry>) -> Void) {
        Task {
            let entry = await makeEntry()
            let entries = makeEntries(after: entry)
            completion(Timeline(entries: entries, policy: .never))
        }
    }

    // MARK: - Timeline construction

    /// Read the source once and resolve the display state.
    private func makeEntry(date: Date = Date()) async -> NerveCenterWidgetEntry {
        do {
            let snapshot = try await dataSource.makeTile()
            let hasFile = await dataSource.hasStateFile()
            return NerveCenterWidgetEntry(date: date, state: dataSource.state(snapshot: snapshot, hasFile: hasFile))
        } catch {
            // A source failure is treated as honest absence, not fabricated
            // data.
            let hasFile = await dataSource.hasStateFile()
            return NerveCenterWidgetEntry(date: date, state: hasFile ? .noData : .notConnected)
        }
    }

    /// Follow-up entries at the cadence implied by the current state, ending
    /// with the standard 15-minute horizon.
    private func makeEntries(after first: NerveCenterWidgetEntry) -> [NerveCenterWidgetEntry] {
        let cadence: TimeInterval
        if first.state.needsAttention {
            cadence = 30 * 60
        } else if first.isStale {
            cadence = 5 * 60
        } else {
            cadence = 15 * 60
        }
        let end = Date().addingTimeInterval(15 * 60)
        var entries = [first]
        var next = first.date
        while true {
            next = next.addingTimeInterval(cadence)
            guard next < end else { break }
            entries.append(NerveCenterWidgetEntry(date: next, state: first.state))
        }
        return entries
    }
}
