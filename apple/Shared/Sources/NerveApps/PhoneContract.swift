import Foundation

// MARK: - §56 iPhone Application

/// The fixed primary navigation contract for the iPhone application (spec §56).
///
/// ```text
/// Overview
/// Goals
/// Incidents
/// Agents
/// Systems
/// Ask
/// ```
///
/// The order, the count (exactly six), and the exact titles are part of the
/// product contract; the SwiftUI `TabView` renders this enumeration directly so
/// the app can never drift from §56.
public enum PhoneTab: String, CaseIterable, Codable, Sendable, Identifiable {
    case overview = "Overview"
    case goals = "Goals"
    case incidents = "Incidents"
    case agents = "Agents"
    case systems = "Systems"
    case ask = "Ask"

    public var id: String { rawValue }

    /// The exact six tabs, in §56 order.
    public static var canonicalOrder: [PhoneTab] {
        [.overview, .goals, .incidents, .agents, .systems, .ask]
    }

    /// True when `allCases` still matches §56 exactly.
    public static var conformsToSection56: Bool { allCases == canonicalOrder }

    /// SF Symbol used by the tab bar (professional, not emoji).
    public var symbolName: String {
        switch self {
        case .overview: return "gauge.with.dots.needle.50percent"
        case .goals: return "target"
        case .incidents: return "exclamationmark.triangle"
        case .agents: return "person.2"
        case .systems: return "server.rack"
        case .ask: return "questionmark.bubble"
        }
    }

    /// Accessible label for the tab.
    public var accessibilityLabel: String { rawValue }
}
