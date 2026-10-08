import SwiftUI

import NerveDesign
import NerveApps

// NerveWatch design layer. Maps NerveDesign's platform-free tokens to
// SwiftUI, following the same convention as the phone target's
// `PhoneDesign.swift`: the shared SDK stays SwiftUI-free, and each app
// target owns its own canvas/surface mapping with per-platform branches so
// the code compiles on the macOS host, iOS and watchOS alike.

public extension Color {
    /// Build a SwiftUI ``Color`` from a platform-free ``NerveColor`` token.
    static func nerve(_ token: NerveColor) -> Color {
        Color(red: token.red, green: token.green, blue: token.blue, opacity: token.opacity)
    }

    /// App canvas background for the Watch app. watchOS's `UIColor` exposes
    /// no grouped/surface background token, so every platform uses a fixed
    /// neutral canvas here (matching the phone target's watchOS fallback).
    static var watchCanvas: Color {
        Color(.sRGB, red: 0.953, green: 0.953, blue: 0.965, opacity: 1)
    }
}

// MARK: - Reusable watch components

/// Compact small-caps wordmark used at the top of the home screen
/// (spec §64: `NERVE` header).
public struct WatchWordmark: View {
    public init() {}

    public var body: some View {
        Text("NERVE")
            .font(.caption)
            .fontWeight(.bold)
            .kerning(2)
            .foregroundStyle(.secondary)
    }
}

/// §73/§69 stale marker: rendered whenever the snapshot's age exceeds the
/// freshness policy (``StalenessPolicy.default`` = 90s). The label is
/// produced by ``StaleState.asOfLabel(_:)``.
public struct WatchStaleBadge: View {
    public let report: StalenessReport

    public init(report: StalenessReport) {
        self.report = report
    }

    public var body: some View {
        if report.isStale {
            Label("stale · " + StaleState.asOfLabel(report), systemImage: "clock")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Stale cached data")
                .accessibilityValue(StaleState.asOfLabel(report))
        }
    }
}

/// One label/value row for the healthy summary (spec §64 count line).
public struct WatchStatRow: View {
    public let label: String
    public let value: String

    public init(label: String, value: String) {
        self.label = label
        self.value = value
    }

    public var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer(minLength: 12)
            Text(value)
                .font(.caption)
                .fontWeight(.semibold)
        }
        .accessibilityElement(children: .combine)
    }
}

/// The §63 goal that a given navigation destination serves.
public extension WatchDestination {
    var goal: WatchGoal {
        switch self {
        case .alert: return .alert
        case .query: return .query
        case .acknowledge: return .acknowledge
        case .approvals: return .approve
        case .stop: return .stop
        }
    }
}
