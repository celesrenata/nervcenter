import Foundation

/// Snapshot of the local cache state (per spec §73):
/// systems, incidents, goals, agent activity, compute, approvals,
/// recent responses.
///
/// Wire fields are snake_case to match §69 compact state naming.
public struct CachedState: Codable, Hashable, Sendable {
    /// System health (e.g. "healthy").
    public var systemHealth: String

    /// Number of active incidents.
    public var activeIncidents: Int

    /// Number of running agents.
    public var runningAgents: Int

    /// Number of pending approvals.
    public var pendingApprovals: Int

    /// Primary goal progress (0..1).
    public var primaryGoalProgress: Double

    /// When this snapshot was last updated (UTC).
    public var updatedAt: Date

    /// Optional list of incident ids (compact).
    public var recentIncidentIDs: [String]

    /// Optional list of goal ids (compact).
    public var recentGoalIDs: [String]

    public init(
        systemHealth: String = "unknown",
        activeIncidents: Int = 0,
        runningAgents: Int = 0,
        pendingApprovals: Int = 0,
        primaryGoalProgress: Double = 0.0,
        updatedAt: Date = Date(),
        recentIncidentIDs: [String] = [],
        recentGoalIDs: [String] = []
    ) {
        self.systemHealth = systemHealth
        self.activeIncidents = activeIncidents
        self.runningAgents = runningAgents
        self.pendingApprovals = pendingApprovals
        self.primaryGoalProgress = primaryGoalProgress
        self.updatedAt = updatedAt
        self.recentIncidentIDs = recentIncidentIDs
        self.recentGoalIDs = recentGoalIDs
    }
}
