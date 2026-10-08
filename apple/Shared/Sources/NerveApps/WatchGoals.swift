import Foundation

// MARK: - §63 Apple Watch

/// The seven primary goals of the Watch application (spec §63).
///
/// The Watch is *not* a miniature dashboard (spec §63). It is a focused
/// interaction surface whose jobs are exactly these seven:
///
/// ```text
/// glance
/// alert
/// query
/// acknowledge
/// approve
/// reject
/// stop
/// ```
public enum WatchGoal: String, CaseIterable, Codable, Sendable, Identifiable {
    case glance
    case alert
    case query
    case acknowledge
    case approve
    case reject
    case stop

    public var id: String { rawValue }

    /// The exact seven goals, in §63 order.
    public static var canonicalOrder: [WatchGoal] {
        [.glance, .alert, .query, .acknowledge, .approve, .reject, .stop]
    }

    public static var conformsToSection63: Bool { allCases == canonicalOrder }

    /// The primary Watch question (spec §63).
    public static let primaryQuestion = "Does something need me?"

    public var description: String {
        switch self {
        case .glance: return
            "Glance the current situation at a glance"
        case .alert: return
            "Alert on things that require the wearer"
        case .query: return
            "Ask a short question and get a short answer"
        case .acknowledge: return
            "Acknowledge a notification or alert"
        case .approve: return
            "Approve a low-risk, reversible change"
        case .reject: return
            "Reject a low-risk, reversible change"
        case .stop: return
            "Stop agents or mutations as an emergency control"
        }
    }
}

/// §64 Watch home state: healthy (calm) or problem (action).
///
/// Spec §64 renders two home states only:
///
/// Healthy:
/// ```text
/// NERVE
/// ● Healthy
/// Agents      7
/// Incidents   0
/// Approvals   0
/// 5090       72%
/// ```
///
/// Problem state:
/// ```text
/// NERVE
/// 🔴 1 INCIDENT
/// HelloDJ
/// Video Worker
/// 8m
/// [Details]
/// ```
public enum WatchHomeState: Codable, Hashable, Sendable {
    /// A healthy overview with the count line and one compute row.
    indirect case healthy(HealthySummary)
    /// A problem state naming the incident and its primary affected entity.
    indirect case problem(ProblemSummary)

    public init(healthy: HealthySummary) { self = .healthy(healthy) }
    public init(problem: ProblemSummary) { self = .problem(problem) }

    public struct HealthySummary: Codable, Hashable, Sendable {
        public var agents: Int
        public var incidents: Int
        public var approvals: Int
        public var leadingComputeNode: String
        public var leadingComputePercent: Int

        public init(agents: Int, incidents: Int, approvals: Int,
                   leadingComputeNode: String, leadingComputePercent: Int) {
            self.agents = agents
            self.incidents = incidents
            self.approvals = approvals
            self.leadingComputeNode = leadingComputeNode
            self.leadingComputePercent = leadingComputePercent
        }
    }

    public struct ProblemSummary: Codable, Hashable, Sendable {
        public var incidentCount: Int
        /// The primary goal / system the incident belongs to (e.g. "HelloDJ").
        public var goalLabel: String
        /// The most-affected entity within that goal (e.g. "Video Worker").
        public var topEntityLabel: String
        /// Human duration (e.g. "8m").
        public var ageLabel: String

        public init(incidentCount: Int, goalLabel: String, topEntityLabel: String,
                   ageLabel: String) {
            self.incidentCount = incidentCount
            self.goalLabel = goalLabel
            self.topEntityLabel = topEntityLabel
            self.ageLabel = ageLabel
        }
    }

    /// Whether the state is a "problem" state (a problem renders the alert
    /// variant even for a healthy home).
    public var isProblem: Bool {
        if case .problem = self { return true }
        return false
    }
}

// MARK: - §67 Emergency controls

/// §67 emergency stop controls: "STOP AGENTS" and "STOP MUTATIONS".
///
/// Both are destructive, high-consequence controls. They must not be
/// presented as ordinary row actions; they need an explicit confirmation
/// surface. The platform layer owns the confirmation interaction; this enum
/// captures the two §67 controls and the distinction that each is *emergency
/// only*.
public enum EmergencyControl: String, CaseIterable, Codable, Sendable, Identifiable {
    case stopAgents = "STOP AGENTS"
    case stopMutations = "STOP MUTATIONS"

    public var id: String { rawValue }

    public var confirmationCopy: String {
        switch self {
        case .stopAgents: return
            "This halts every running agent immediately. Continue?"
        case .stopMutations: return
            "This queues a STOP for every pending mutation. This cannot be undone. Continue?"
        }
    }

    /// Deep link the platform layer posts when the control is confirmed.
    public var deepLink: String {
        switch self {
        case .stopAgents: return "nerv://emergency/stop-agents"
        case .stopMutations: return "nerv://emergency/stop-mutations"
        }
    }
}
