import SwiftUI

import NerveDesign

// NerveWidgets design layer. Maps NerveDesign's platform-free tokens to
// SwiftUI, following the same `#if os(macOS)` / `#else` pattern as
// `apple/iOS/App/Support/PhoneDesign.swift` so the target builds on the
// macOS host (`swift build` / `swift test`) and on real iOS alike.

public extension Color {
    /// Build a SwiftUI ``Color`` from a platform-free ``NerveColor`` token.
    static func nerve(_ token: NerveColor) -> Color {
        Color(red: token.red, green: token.green, blue: token.blue, opacity: token.opacity)
    }

    /// System-health colour for a health string (spec §57/§64/§62).
    ///
    /// Same mapping the phone uses (`Color.nerveHealth` in PhoneDesign):
    /// "healthy"/"ok"/"online" → green, "degraded"/"warning"/"draining" →
    /// amber, anything else (including unknown) → red so an unrecognized
    /// state reads as a problem, not a success.
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

    /// Widget canvas: transparent so the widget family's default tint
    /// (iOS) shows through; the macOS host renders on the window background
    /// so previews remain legible.
    static var nerveWidgetCanvas: Color {
        #if os(macOS)
        Color(nsColor: .windowBackgroundColor)
        #else
        Color.clear
        #endif
    }

    /// Muted secondary text (labels, stale captions).
    static var nerveWidgetSecondary: Color {
        #if os(macOS)
        Color(nsColor: .secondaryLabelColor)
        #else
        Color.secondary
        #endif
    }

    /// Primary text.
    static var nerveWidgetPrimary: Color {
        #if os(macOS)
        Color(nsColor: .labelColor)
        #else
        Color.primary
        #endif
    }
}

/// Health string → coarse health state, used for the tile's dot.
///
/// The dot colour is the token's own `NerveColor` (via
/// ``Color/nerve(_:)-8p12c``); the `Color.nerveHealth(_:)` mapping is
/// retained as the single source of truth for unknown-string handling.
public enum WidgetHealthState {
    case healthy
    case degraded
    case critical

    public init(_ health: String) {
        let h = health.lowercased()
        if h == "healthy" || h == "ok" || h == "online" {
            self = .healthy
        } else if h == "degraded" || h == "warning" || h == "draining" {
            self = .degraded
        } else {
            self = .critical
        }
    }

    /// The underlying `HealthColor` token for this state.
    public var healthColor: HealthColor {
        switch self {
        case .healthy: return .healthy
        case .degraded: return .degraded
        case .critical: return .critical
        }
    }
}

/// Small, consistent spacing/radius for the tiles (derived from NerveDesign
/// `Spacing` so the widget matches the phone's rhythm).
public enum WidgetMetrics {
    public static let cornerRadius: CGFloat = 12
    public static let rowPadding: CGFloat = Spacing.xs
    public static let sectionGap: CGFloat = Spacing.sm
}
