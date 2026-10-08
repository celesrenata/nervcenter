import Foundation

import NerveModels

// MARK: - §61 Live Activities

/// §61 Live Activities: operations suitable for a Live Activity. Each carries
/// a progress value and a set of sub-steps with completion state so the
/// Dynamic Island / lock-screen UI can render the `4/6` progress example.
public enum LiveOperationKind: String, CaseIterable, Codable, Sendable, Identifiable {
    case investigation
    case deployment
    case benchmarkCampaign
    case migration
    case largeGoalOperation

    public var id: String { rawValue }

    public static var canonicalKinds: [LiveOperationKind] {
        [.investigation, .deployment, .benchmarkCampaign, .migration, .largeGoalOperation]
    }

    public static var conformsToSection61: Bool { allCases == canonicalKinds }

    public var displayTitle: String {
        switch self {
        case .investigation: return "Incident investigation"
        case .deployment: return "Deployment"
        case .benchmarkCampaign: return "Benchmark campaign"
        case .migration: return "Migration"
        case .largeGoalOperation: return "Large goal operation"
        }
    }
}

/// One sub-step in a Live Activity (e.g. `Git ✓`, `Logs ✓`, `Network …`).
public struct LiveActivityStep: Codable, Hashable, Sendable, Identifiable {
    public var id: String { name }

    /// Sub-step name (e.g. "Git", "Logs", "Verify").
    public var name: String
    /// True when the sub-step has completed.
    public var isDone: Bool

    public init(name: String, isDone: Bool) {
        self.name = name
        self.isDone = isDone
    }
}

/// Live Activity state — a pure, platform-free snapshot the platform layer
/// renders via `ActivityKit`. Keeps the domain testable without a simulator.
public struct LiveActivityState: Codable, Hashable, Sendable {
    public var kind: LiveOperationKind
    /// The subject label, e.g. "HELLODJ INCIDENT".
    public var title: String
    public var steps: [LiveActivityStep]
    /// Overall progress 0…1.
    public var progress: Double

    public init(
        kind: LiveOperationKind,
        title: String,
        steps: [LiveActivityStep],
        progress: Double? = nil
    ) {
        self.kind = kind
        self.title = title
        self.steps = steps
        // When not given, progress is the fraction of completed steps.
        self.progress = progress ?? (steps.isEmpty ? 0 : Double(steps.filter(\.isDone).count) / Double(steps.count))
    }

    /// §61 progress line, e.g. `4/6 investigations complete`.
    public var progressLine: String {
        let done = steps.filter(\.isDone).count
        let total = steps.count
        return "\(done)/\(total) complete"
    }
}
