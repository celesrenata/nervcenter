import Foundation
import Combine

import NerveApps
import NerveAuth
import NervePersistence

// MARK: - §67 emergency stop action

/// A small, stateless action the Watch's emergency STOP control invokes
/// (spec §67). The production default posts a `stop-agents.json` marker
/// into the App Group container; tests inject a spy.
public protocol WatchStopAction: Sendable {
    /// Request the emergency stop. Throws on I/O failure so the UI can
    /// render an honest error rather than silently pretend it worked.
    func stop(at date: Date) throws
}

/// Default production action: write the §67 marker file through the same
/// source that owns the App Group container.
public struct MarkerFileStopAction: WatchStopAction {
    public let source: WatchSnapshotSource

    public init(source: WatchSnapshotSource) {
        self.source = source
    }

    public func stop(at date: Date) throws {
        try source.writeStopMarker(at: date)
    }
}

// MARK: - Navigation destinations

/// The non-home screens reachable from the §63 goal navigation. Glance
/// (the home screen) and the emergency STOP are anchored on the home
/// screen; the rest are push destinations inside the single NavigationStack.
public enum WatchDestination: Hashable, Identifiable {
    /// §63 `alert` — the incident list from the snapshot.
    case alert
    /// §63 `query` — short question (honest offline note; no watch-side
    /// Ask service exists).
    case query
    /// §63 `acknowledge` — mark an incident acknowledged locally.
    case acknowledge
    /// §63 `approve` / `reject` — the shared approvals inbox. One screen
    /// serves both goals (spec §63 groups them): each watch-eligible row
    /// offers both an Approve and a Reject action.
    case approvals
    /// §67 — the emergency STOP confirmation surface.
    case stop

    public var id: String {
        switch self {
        case .alert: return "alert"
        case .query: return "query"
        case .acknowledge: return "acknowledge"
        case .approvals: return "approvals"
        case .stop: return "stop"
        }
    }
}

// MARK: - §63/§64/§66/§68/§69/§73 Watch data store

/// The Watch's single source of truth.
///
/// - Loads the §73 ``CachedState`` snapshot and the pending approvals from
///   the ``WatchSnapshotSource`` (App Group container in production).
/// - When no snapshot exists or it does not decode, every derived value is
///   `nil`/empty — the UI renders an honest "Not connected" state, never
///   fabricated counts, names, or progress.
/// - Exposes the §64 ``WatchHomeState``, the §73 staleness report
///   (``StaleState.evaluate`` against ``StalenessPolicy/default`` = 90s),
///   the §66 approvals with each row's ``WatchApprovalDecision``, and the
///   §68 ``ComplicationInputs`` derived from the same snapshot.
/// A plain (non-isolated) observable store mirroring the phone target's
/// `PhoneDataStore`; it is only ever touched from the main actor by the
/// SwiftUI layer, so it needs no actor isolation of its own.
public final class WatchDataStore: ObservableObject {
    // MARK: Published state

    /// The last successfully decoded §73 snapshot. `nil` = nothing to show.
    @Published public private(set) var snapshot: CachedState?
    /// Freshness of the snapshot (``StaleState.evaluate``), or `nil` when
    /// there is no snapshot to measure.
    @Published public private(set) var staleness: StalenessReport?
    /// Pending approvals read from `approvals.json` (`[]` when absent).
    @Published public private(set) var approvals: [WatchApprovalRow] = []
    /// Incident ids the wearer marked acknowledged locally (§63 acknowledge).
    @Published public var acknowledgedIncidentIDs: Set<String> = []
    /// Approvals the wearer decided locally: `id` → `true` (approved) /
    /// `false` (rejected). The phone owns the canonical decision; this only
    /// reflects the watch's local action so the screen can confirm honestly.
    @Published public var decidedApprovals: [String: Bool] = [:]
    /// True once the §67 STOP marker has been posted this session.
    @Published public private(set) var stopRequested = false
    /// Honest result of the last STOP request (nil = none yet / success).
    @Published public private(set) var stopError: String?

    // MARK: Dependencies

    public let source: WatchSnapshotSource
    public let stopAction: WatchStopAction
    let stalenessPolicy: StalenessPolicy
    let nowProvider: () -> Date

    // MARK: Init

    public init(
        source: WatchSnapshotSource,
        stopAction: WatchStopAction? = nil,
        stalenessPolicy: StalenessPolicy = .default,
        nowProvider: @escaping () -> Date = { Date() }
    ) {
        self.source = source
        self.stopAction = stopAction ?? MarkerFileStopAction(source: source)
        self.stalenessPolicy = stalenessPolicy
        self.nowProvider = nowProvider
        refresh()
    }

    /// Production wiring: App Group container, App Group stop marker.
    public convenience init() {
        self.init(source: AppGroupSnapshotSource())
    }

    /// Read the latest snapshot and approvals from the source and re-derive
    /// every derived value. Called at init, on the refresh control, and when
    /// the app becomes active (the phone writes while the Watch is awake).
    public func refresh() {
        let cache = source.readSnapshot()
        snapshot = cache
        staleness = cache.map {
            StaleState.evaluate(updatedAt: $0.updatedAt, now: nowProvider(), policy: stalenessPolicy)
        }
        if cache != nil {
            approvals = source.readApprovals()
        } else {
            // No trustworthy cache → no approvals either (honest).
            approvals = []
        }
    }

    // MARK: Derived state

    /// §64 home state. `nil` when no snapshot exists — the home screen then
    /// renders the "Not connected" state, not a zero-filled dashboard.
    public var homeState: WatchHomeState? {
        snapshot.map { WatchHomeStateBuilder.homeState(from: $0) }
    }

    /// §68 complication inputs, derived from the same §73 snapshot the home
    /// screen renders — so the complication and the glance never disagree.
    ///
    /// `nil` when offline (no snapshot to derive from).
    ///
    /// *Honest derivation notes:* the §73 cache carries no per-incident
    /// severity, so "urgent incident" is derived as "incidents present
    /// while system health is not calm". The cache also carries no
    /// investigation count, so `activeInvestigations` is always `0`.
    public var complicationInputs: ComplicationInputs? {
        guard let cached = snapshot else { return nil }
        let calm = WatchHomeStateBuilder.calmHealth.contains(cached.systemHealth.lowercased())
        return ComplicationInputs(
            hasUrgentIncident: cached.activeIncidents > 0 && !calm,
            pendingApprovals: cached.pendingApprovals,
            activeIncidents: cached.activeIncidents,
            activeInvestigations: 0,
            primaryGoalProgress: cached.primaryGoalProgress > 0 ? cached.primaryGoalProgress : nil,
            systemHealth: cached.systemHealth
        )
    }

    /// §66 decision for a single approval row. When the row cannot be lifted
    /// to a `PlannedChange` (unknown change-type literal, …) the answer is
    /// *always* a deep link — never an approval the policy cannot see.
    public func decision(for row: WatchApprovalRow) -> WatchApprovalDecision {
        guard let change = row.makePlannedChange() else {
            return .deepLink(link: "\(WatchApprovalPolicy.deepLinkPrefix)/\(row.id)")
        }
        return WatchApprovalPolicy.evaluate(
            change: change,
            maxRisk: WatchApprovalPolicy.maxWatchRiskLevel
        )
    }

    // MARK: The seven §63 goal flows

    /// §63 `acknowledge` — mark an incident acknowledged in the *local*
    /// store only. The phone owns the canonical acknowledgement; the Watch
    /// does not pretend to have written to the server.
    public func acknowledge(incidentID: String) {
        acknowledgedIncidentIDs.insert(incidentID)
    }

    public func isAcknowledged(_ incidentID: String) -> Bool {
        acknowledgedIncidentIDs.contains(incidentID)
    }

    /// Record a local approve/reject decision for an approval row. The
    /// caller is responsible for only calling this on rows whose §66
    /// decision is `.approve`; the approvals screen enforces that.
    public func recordDecision(for rowID: String, approved: Bool) {
        decidedApprovals[rowID] = approved
    }

    /// §67 emergency stop. Posts the marker file through the injectable
    /// ``WatchStopAction``; on success sets ``stopRequested``.
    public func requestStop() {
        do {
            try stopAction.stop(at: nowProvider())
            stopRequested = true
            stopError = nil
        } catch {
            stopError = error.localizedDescription
        }
    }
}
