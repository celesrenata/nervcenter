import Foundation

/// A compact Phone ↔ Watch synchronized state snapshot (spec §69).
///
/// The phone ↔ watch contract is intentionally tiny so the Watch stays
/// useful from cached state:
///
/// ```json
/// {
///   "system_health": "healthy",
///   "active_incidents": 0,
///   "running_agents": 7,
///   "pending_approvals": 1,
///   "primary_goal_progress": 0.76,
///   "updated_at": "2026-01-31T12:00:00Z"
/// }
/// ```
public struct SynchronizedState: Codable, Hashable, Sendable {
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

    public init(
        systemHealth: String = "unknown",
        activeIncidents: Int = 0,
        runningAgents: Int = 0,
        pendingApprovals: Int = 0,
        primaryGoalProgress: Double = 0.0,
        updatedAt: Date = Date()
    ) {
        self.systemHealth = systemHealth
        self.activeIncidents = activeIncidents
        self.runningAgents = runningAgents
        self.pendingApprovals = pendingApprovals
        self.primaryGoalProgress = primaryGoalProgress
        self.updatedAt = updatedAt
    }
}
