import Foundation

import NerveModels
import NervePersistence

// MARK: - §69 / §73 Stale state

/// How fresh a snapshot is, used to mark state as stale (spec §69/§73).
///
/// The Watch must remain useful from *cached* state, but stale data must be
/// clearly marked rather than presented as live.
public struct StalenessReport: Sendable, Hashable {
    public let elapsed: TimeInterval
    public let isStale: Bool

    public init(elapsed: TimeInterval, isStale: Bool) {
        self.elapsed = elapsed
        self.isStale = isStale
    }
}

public struct StalenessPolicy: Sendable, Hashable {
    /// After this many seconds, a snapshot reads as stale.
    public var staleAfter: TimeInterval

    public init(staleAfter: TimeInterval = 90) {
        self.staleAfter = staleAfter
    }

    public static let `default` = StalenessPolicy(staleAfter: 90)
}

public enum StaleState {
    /// Classify a snapshot age against a freshness policy.
    public static func evaluate(
        updatedAt: Date,
        now: Date = Date(),
        policy: StalenessPolicy = .default
    ) -> StalenessReport {
        let elapsed = max(0, now.timeIntervalSince(updatedAt))
        return StalenessReport(elapsed: elapsed, isStale: elapsed > policy.staleAfter)
    }

    /// Derive a §69 ``SynchronizedState`` (compact phone↔Watch contract) from a
    /// §73 ``CachedState`` (the phone's local cache).
    public static func compact(from cached: CachedState) -> SynchronizedState {
        SynchronizedState(
            systemHealth: cached.systemHealth,
            activeIncidents: cached.activeIncidents,
            runningAgents: cached.runningAgents,
            pendingApprovals: cached.pendingApprovals,
            primaryGoalProgress: cached.primaryGoalProgress,
            updatedAt: cached.updatedAt
        )
    }

    /// Render a compact "as of" label for stale-marking in the UI, e.g.
    /// `as of 3:12 PM` or `3m ago`.
    public static func asOfLabel(_ report: StalenessReport) -> String {
        let minutes = Int((report.elapsed / 60).rounded())
        if minutes < 1 { return "just now" }
        if minutes < 60 { return "\(minutes)m ago" }
        return "\(minutes / 60)h \(minutes % 60)m ago"
    }
}
