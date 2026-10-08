import Foundation

// MARK: - §68 Watch Complications

/// The §68 complication display priority ladder, highest precedence first:
///
/// ```text
/// 1. urgent incident
/// 2. approval required
/// 3. active incident
/// 4. active investigation
/// 5. goal progress
/// 6. general status
/// ```
///
/// The complication renders exactly *one* of these, selected by
/// ``ComplicationLadder.select(for:)''. Lower rawValue == higher precedence.
public enum ComplicationPriority: Int, CaseIterable, Codable, Sendable, Comparable, Identifiable {
    case urgentIncident = 0
    case approvalRequired = 1
    case activeIncident = 2
    case activeInvestigation = 3
    case goalProgress = 4
    case generalStatus = 5

    public var id: Int { rawValue }

    /// The exact six ladder rungs, in §68 precedence order.
    public static var canonicalOrder: [ComplicationPriority] {
        [.urgentIncident, .approvalRequired, .activeIncident,
         .activeInvestigation, .goalProgress, .generalStatus]
    }

    public static var conformsToSection68: Bool { allCases == canonicalOrder }

    public static func < (lhs: ComplicationPriority, rhs: ComplicationPriority) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    public var label: String {
        switch self {
        case .urgentIncident: return "Urgent incident"
        case .approvalRequired: return "Approval required"
        case .activeIncident: return "Active incident"
        case .activeInvestigation: return "Active investigation"
        case .goalProgress: return "Goal progress"
        case .generalStatus: return "General status"
        }
    }
}

/// The six complication data providers the Watch exposes (spec §68): system
/// health, incident count, agent count, GPU state, goal progress, approval
/// count. Each is a *view* over shared state; ``ComplicationPriority`` decides
/// *which* view renders in the current moment.
public enum ComplicationType: String, CaseIterable, Codable, Sendable, Identifiable {
    case systemHealth
    case incidentCount
    case agentCount
    case gpuState
    case goalProgress
    case approvalCount

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .systemHealth: return "System health"
        case .incidentCount: return "Incident count"
        case .agentCount: return "Agent count"
        case .gpuState: return "GPU state"
        case .goalProgress: return "Goal progress"
        case .approvalCount: return "Approval count"
        }
    }
}

/// The inputs the §68 ladder decides on. Every field is a coarse snapshot the
/// Watch can hold from cached §69 state, so the ladder works offline.
public struct ComplicationInputs: Codable, Hashable, Sendable {
    public var hasUrgentIncident: Bool
    public var pendingApprovals: Int
    public var activeIncidents: Int
    public var activeInvestigations: Int
    public var primaryGoalProgress: Double?
    public var systemHealth: String

    public init(
        hasUrgentIncident: Bool,
        pendingApprovals: Int,
        activeIncidents: Int,
        activeInvestigations: Int,
        primaryGoalProgress: Double?,
        systemHealth: String
    ) {
        self.hasUrgentIncident = hasUrgentIncident
        self.pendingApprovals = pendingApprovals
        self.activeIncidents = activeIncidents
        self.activeInvestigations = activeInvestigations
        self.primaryGoalProgress = primaryGoalProgress
        self.systemHealth = systemHealth
    }
}

/// A rendered complication cell: the selected rung plus a short value string.
public struct ComplicationItem: Codable, Hashable, Sendable {
    public var priority: ComplicationPriority
    public var value: String
    public var detail: String

    public init(priority: ComplicationPriority, value: String, detail: String) {
        self.priority = priority
        self.value = value
        self.detail = detail
    }
}

public enum ComplicationLadder {
    /// Select the single §68 rung with the highest precedence for these
    /// inputs. Ruggedness: a rung is only selectable when its signal is
    /// actually present.
    public static func select(for inputs: ComplicationInputs) -> ComplicationPriority {
        if inputs.hasUrgentIncident { return .urgentIncident }
        if inputs.pendingApprovals > 0 { return .approvalRequired }
        if inputs.activeIncidents > 0 { return .activeIncident }
        if inputs.activeInvestigations > 0 { return .activeInvestigation }
        if inputs.primaryGoalProgress != nil { return .goalProgress }
        return .generalStatus
    }

    /// Render the selected rung into a compact value pair for the complication.
    public static func render(for inputs: ComplicationInputs) -> ComplicationItem {
        switch select(for: inputs) {
        case .urgentIncident:
            return ComplicationItem(
                priority: .urgentIncident,
                value: "‼",
                detail: "Urgent"
            )
        case .approvalRequired where inputs.pendingApprovals > 0:
            return ComplicationItem(
                priority: .approvalRequired,
                value: "\(inputs.pendingApprovals)",
                detail: "approval\(inputs.pendingApprovals == 1 ? "" : "s")"
            )
        case .activeIncident where inputs.activeIncidents > 0:
            return ComplicationItem(
                priority: .activeIncident,
                value: "\(inputs.activeIncidents)",
                detail: "incident\(inputs.activeIncidents == 1 ? "" : "s")"
            )
        case .activeInvestigation where inputs.activeInvestigations > 0:
            return ComplicationItem(
                priority: .activeInvestigation,
                value: "\(inputs.activeInvestigations)",
                detail: "investigating"
            )
        case .goalProgress where inputs.primaryGoalProgress != nil:
            let pct = Int((inputs.primaryGoalProgress ?? 0) * 100)
            return ComplicationItem(
                priority: .goalProgress,
                value: "\(pct)%",
                detail: "goal"
            )
        default:
            return ComplicationItem(
                priority: .generalStatus,
                value: "●",
                detail: inputs.systemHealth
            )
        }
    }
}
