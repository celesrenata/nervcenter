import SwiftUI

import NerveDesign
import NerveApps

// NervePhone design layer. Maps NerveDesign's platform-free tokens to SwiftUI,
// per NerveDesign's own contract (the shared SDK is SwiftUI-free on purpose).

public extension Color {
    /// Build a SwiftUI ``Color`` from a platform-free ``NerveColor`` token.
    static func nerve(_ token: NerveColor) -> Color {
        Color(red: token.red, green: token.green, blue: token.blue, opacity: token.opacity)
    }

    /// System-health colour for a health string (spec §57/§64).
    static func nerveHealth(_ health: String) -> Color {
        let h = health.lowercased()
        if h == "healthy" || h == "ok" || h == "online" {
            return .nerve(HealthColor.healthy.color)
        }
        if h == "degraded" || h == "warning" || h == "draining" {
            return .nerve(HealthColor.degraded.color)
        }
        return .nerve(HealthColor.critical.color)
    }

    /// App canvas background — the "recessed" surface behind a screen. Mapped
    /// per platform so the same view builds for the macOS host (used by
    /// `swift test`) and for the real iOS / watchOS targets alike.
    static var phoneCanvas: Color {
        #if os(macOS)
        Color(nsColor: .windowBackgroundColor)
        #elseif os(watchOS)
        // watchOS's UIColor exposes no grouped/surface background token
        // (only label, separator and link). Fall back to a fixed light
        // neutral; the Watch app's own surfaces live in the NerveWatch
        // target (T312) and will own their canvas there.
        Color(.sRGB, red: 0.953, green: 0.953, blue: 0.965, opacity: 1)
        #else
        Color(uiColor: .systemGroupedBackground)
        #endif
    }
}

/// A coarse health state used by the overview and settings headers.
public enum PhoneHealthBadge: String, CaseIterable, Identifiable {
    case healthy, degraded, critical
    public var id: String { rawValue }

    public var label: String { rawValue.capitalized }

    public var color: Color {
        switch self {
        case .healthy: return Color.nerve(HealthColor.healthy.color)
        case .degraded: return Color.nerve(HealthColor.degraded.color)
        case .critical: return Color.nerve(HealthColor.critical.color)
        }
    }

    public static func from(_ health: String) -> PhoneHealthBadge {
        let h = health.lowercased()
        if h == "healthy" || h == "ok" || h == "online" || h == "unknown" { return .healthy }
        if h == "degraded" || h == "warning" || h == "draining" { return .degraded }
        return .critical
    }
}

/// A stale-marker overlay: spec §73, §69, §74 require cached data to be
/// clearly marked as possibly stale. Reused by every phone screen.
public struct StaleBadge: View {
    public let isStale: Bool
    public let ageLabel: String?

    public init(isStale: Bool, ageLabel: String? = nil) {
        self.isStale = isStale
        self.ageLabel = ageLabel
    }

    public var body: some View {
        if isStale {
            Label(
                ageLabel ?? "Cached",
                systemImage: "clock.badge"
            )
            .font(.caption2)
            .foregroundStyle(.secondary)
            .accessibilityLabel("Cached data")
            .accessibilityValue(ageLabel ?? "")
        }
    }
}

/// One labelled row (value + optional trailing).
public struct Row: View {
    public let label: String
    public let value: String
    public var tint: Color? = nil

    public init(_ label: String, _ value: String, tint: Color? = nil) {
        self.label = label
        self.value = value
        self.tint = tint
    }

    public var body: some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer(minLength: Spacing.md)
            Text(value)
                .font(.body.monospacedDigit())
                .foregroundStyle(tint ?? .primary)
        }
        .padding(.vertical, Spacing.xxs)
    }
}

/// A titled section used across the six tabs to keep spacing consistent.
public struct PhoneSection<Content: View>: View {
    public let title: String
    public let content: Content

    public init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text(title)
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            content
        }
        .padding(.horizontal, Spacing.md)
    }
}
