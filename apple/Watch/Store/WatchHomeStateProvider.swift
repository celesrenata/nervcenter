import Foundation

import NerveApps
import NervePersistence

// MARK: - §64 home-state derivation from a §73 snapshot

/// Derives the §64 ``WatchHomeState`` from a §73 ``CachedState`` snapshot.
///
/// The mapping is deliberately conservative so the Watch never presents
/// something it cannot hold from the cache:
///
/// - `systemHealth == "healthy"` (or `ok`/`online`) with no active
///   incidents and no pending approvals → `.healthy`.
/// - Anything else with `activeIncidents > 0` → `.problem`.
/// - Anything else (unknown health, degraded, …) → `.healthy` with the
///   counts still visible — the counts are the source of truth, and the
///   "Healthy" word is the calm default when there is no incident to name.
public enum WatchHomeStateBuilder {
    public static let calmHealth = Set(["healthy", "ok", "online"])

    public static func homeState(from cached: CachedState) -> WatchHomeState {
        if cached.activeIncidents > 0 {
            return .problem(problem(from: cached))
        }
        return .healthy(healthy(from: cached))
    }

    private static func healthy(from cached: CachedState) -> WatchHomeState.HealthySummary {
        WatchHomeState.HealthySummary(
            agents: cached.runningAgents,
            incidents: cached.activeIncidents,
            approvals: cached.pendingApprovals,
            leadingComputeNode: "—",
            leadingComputePercent: 0
        )
    }

    private static func problem(from cached: CachedState) -> WatchHomeState.ProblemSummary {
        WatchHomeState.ProblemSummary(
            incidentCount: cached.activeIncidents,
            goalLabel: "System",
            topEntityLabel: topEntityLabel(from: cached),
            ageLabel: ageLabel(from: cached)
        )
    }

    /// The §73 cache has no per-entity incident detail; the most honest
    /// compact label is the recent incident count, or the snapshot's own
    /// `unknown` marker when none is recorded.
    private static func topEntityLabel(from cached: CachedState) -> String {
        if cached.recentIncidentIDs.isEmpty { return "Unknown" }
        return "\(cached.recentIncidentIDs.count) recent"
    }

    private static func ageLabel(from cached: CachedState) -> String {
        StaleState.asOfLabel(StaleState.evaluate(updatedAt: cached.updatedAt))
    }
}
