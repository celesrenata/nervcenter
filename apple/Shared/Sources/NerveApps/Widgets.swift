import Foundation

import NerveModels

// MARK: - §62 iPhone Widgets

/// A single compute node row rendered in the medium/large widget.
public struct ComputeWidgetRow: Codable, Hashable, Sendable, Identifiable {
    public var id: String { nodeID.isEmpty ? "unknown" : nodeID }
    public var nodeID: String
    public var hardware: String
    public var utilizationPercent: Int

    public init(nodeID: String, hardware: String, utilizationPercent: Int) {
        self.nodeID = nodeID
        self.hardware = hardware
        self.utilizationPercent = min(100, max(0, utilizationPercent))
    }
}

/// §62 widget contract: three sizes with fixed content.
///
/// ```text
/// Small:
/// ● HEALTHY
/// 7 agents
/// 0 incidents
///
/// Medium:
/// 5090      72%
/// 4070      14%
/// M5        58%
/// Agents   7
/// Incidents 0
///
/// Large:
/// goal progress
/// compute state
/// incidents
/// agent activity
/// ```
public enum WidgetSize: String, CaseIterable, Codable, Sendable {
    case small = "systemSmall"
    case medium = "systemMedium"
    case large = "systemLarge"

    public var id: String { rawValue }
}

/// Snapshot of everything a widget tile can render. Derived from cached
/// §73 state, so widgets work offline.
public struct WidgetTile: Codable, Hashable, Sendable {
    public var systemHealth: String
    public var agents: Int
    public var incidents: Int
    public var pendingApprovals: Int
    public var primaryGoalLabel: String?
    public var primaryGoalProgress: Double?
    public var computeRows: [ComputeWidgetRow]
    public var incidentsSummary: String?
    public var agentActivitySummary: String?
    /// When the backing cache was last updated (drives stale marking).
    public var updatedAt: Date

    public init(
        systemHealth: String,
        agents: Int,
        incidents: Int,
        pendingApprovals: Int,
        primaryGoalLabel: String?,
        primaryGoalProgress: Double?,
        computeRows: [ComputeWidgetRow],
        incidentsSummary: String?,
        agentActivitySummary: String?,
        updatedAt: Date
    ) {
        self.systemHealth = systemHealth
        self.agents = agents
        self.incidents = incidents
        self.pendingApprovals = pendingApprovals
        self.primaryGoalLabel = primaryGoalLabel
        self.primaryGoalProgress = primaryGoalProgress
        self.computeRows = computeRows
        self.incidentsSummary = incidentsSummary
        self.agentActivitySummary = agentActivitySummary
        self.updatedAt = updatedAt
    }

    // MARK: Small

    /// `● HEALTHY` / `7 agents` / `0 incidents`.
    public struct SmallContent: Codable, Hashable, Sendable {
        public var healthLabel: String
        public var agentCount: Int
        public var incidentCount: Int
        public var healthy: Bool

        public init(tile: WidgetTile) {
            self.healthy = tile.systemHealth.lowercased() == "healthy"
            self.healthLabel = tile.systemHealth.uppercased()
            self.agentCount = tile.agents
            self.incidentCount = tile.incidents
        }
    }

    // MARK: Medium

    /// Compute rows plus agent/incident counts.
    public struct MediumContent: Codable, Hashable, Sendable {
        public var computeRows: [ComputeWidgetRow]
        public var agentCount: Int
        public var incidentCount: Int

        public init(tile: WidgetTile) {
            self.computeRows = tile.computeRows
            self.agentCount = tile.agents
            self.incidentCount = tile.incidents
        }
    }

    // MARK: Large

    /// Goal progress, compute state, incidents, agent activity.
    public struct LargeContent: Codable, Hashable, Sendable {
        public var goalLabel: String?
        public var goalProgress: Double?
        public var computeRows: [ComputeWidgetRow]
        public var incidentsSummary: String?
        public var agentActivitySummary: String?
        /// Approvals require attention — §62 large widget surfaces the count
        /// in the incidents block header when non-zero.
        public var pendingApprovals: Int

        public init(tile: WidgetTile) {
            self.goalLabel = tile.primaryGoalLabel
            self.goalProgress = tile.primaryGoalProgress
            self.computeRows = tile.computeRows
            self.incidentsSummary = tile.incidentsSummary
            self.agentActivitySummary = tile.agentActivitySummary
            self.pendingApprovals = tile.pendingApprovals
        }
    }

    public var small: SmallContent { SmallContent(tile: self) }
    public var medium: MediumContent { MediumContent(tile: self) }
    public var large: LargeContent { LargeContent(tile: self) }
}
