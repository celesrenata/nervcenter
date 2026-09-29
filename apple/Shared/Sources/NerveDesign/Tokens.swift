import Foundation

/// Platform-agnostic RGBA color token (SwiftUI-free: the app targets map
/// these to `Color`/`UIColor` at their own layer, keeping the shared SDK
/// portable across iOS / watchOS / macOS / Mac Catalyst).
public struct NerveColor: Codable, Hashable, Sendable {
    /// Red channel (0…1).
    public var red: Double
    /// Green channel (0…1).
    public var green: Double
    /// Blue channel (0…1).
    public var blue: Double
    /// Opacity (0…1).
    public var opacity: Double

    public init(red: Double, green: Double, blue: Double, opacity: Double = 1.0) {
        self.red = red
        self.green = green
        self.blue = blue
        self.opacity = opacity
    }
}

/// A typography token (SwiftUI-free size + weight).
public struct NerveTextStyle: Codable, Hashable, Sendable {
    /// Point size.
    public var size: Double
    /// Weight (0…1, where 0.5 is regular and 1.0 is heavy).
    public var weight: Double

    public init(size: Double, weight: Double = 0.5) {
        self.size = size
        self.weight = weight
    }
}

/// System-health color tokens (spec §57/§64: the glance UI keys off a coarse
/// health state first).
public enum HealthColor: CaseIterable, Sendable {
    case healthy
    case degraded
    case critical

    /// The backing color for this health state.
    public var color: NerveColor {
        switch self {
        case .healthy: return NerveColor(red: 0.20, green: 0.78, blue: 0.35)
        case .degraded: return NerveColor(red: 0.95, green: 0.77, blue: 0.06)
        case .critical: return NerveColor(red: 0.90, green: 0.22, blue: 0.21)
        }
    }
}

/// One color per task DAG visual state (spec §22/§50: 8 states including
/// `cancelled`, added per §22).
public enum TaskStateColor: CaseIterable, Sendable {
    case pending
    case ready
    case running
    case blocked
    case verifying
    case succeeded
    case failed
    case cancelled

    /// The backing color for this task state.
    public var color: NerveColor {
        switch self {
        case .pending: return NerveColor(red: 0.56, green: 0.56, blue: 0.58)
        case .ready: return NerveColor(red: 0.04, green: 0.52, blue: 1.00)
        case .running: return NerveColor(red: 1.00, green: 0.58, blue: 0.00)
        case .blocked: return NerveColor(red: 0.69, green: 0.32, blue: 0.87)
        case .verifying: return NerveColor(red: 0.13, green: 0.74, blue: 0.68)
        case .succeeded: return NerveColor(red: 0.20, green: 0.78, blue: 0.35)
        case .failed: return NerveColor(red: 0.90, green: 0.22, blue: 0.21)
        case .cancelled: return NerveColor(red: 0.56, green: 0.56, blue: 0.58, opacity: 0.55)
        }
    }
}

/// Spacing tokens.
public enum Spacing {
    public static let xxs: CGFloat = 2
    public static let xs: CGFloat = 4
    public static let sm: CGFloat = 8
    public static let md: CGFloat = 16
    public static let lg: CGFloat = 24
    public static let xl: CGFloat = 32
    public static let xxl: CGFloat = 48

    /// All spacing values in ascending order.
    public static var allValues: [CGFloat] { [xxs, xs, sm, md, lg, xl, xxl] }
}

/// Typography tokens.
public enum Typography {
    public static let title1 = NerveTextStyle(size: 34, weight: 0.8)
    public static let title2 = NerveTextStyle(size: 22, weight: 0.7)
    public static let title3 = NerveTextStyle(size: 20, weight: 0.6)
    public static let headline = NerveTextStyle(size: 17, weight: 0.7)
    public static let body = NerveTextStyle(size: 17, weight: 0.5)
    public static let body2 = NerveTextStyle(size: 15, weight: 0.5)
    public static let caption = NerveTextStyle(size: 12, weight: 0.5)
}
