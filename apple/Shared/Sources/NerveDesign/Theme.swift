import Foundation

#if canImport(SwiftUI)
import SwiftUI
#endif

// MARK: - Theme

/// A resolved, platform-agnostic set of named UI tokens.
///
/// Built on ``NerveColor`` (the shared platform-free RGBA token) so it stays
/// SwiftUI-free at the type level — app targets map tokens to `Color`/`UIColor`
/// at their own layer, exactly as they do for the existing design tokens.
///
/// `Theme` is intentionally the *resolved* value (dark or light). The user's
/// preference is separate (``ThemePreference``) and is resolved by
/// ``ThemeStore``.
public struct Theme: Equatable {
    /// Page / window background.
    public var background: NerveColor
    /// Elevated surfaces — cards, sidebar, panels.
    public var surface: NerveColor
    /// Primary (headings / emphasis) text.
    public var textPrimary: NerveColor
    /// Secondary (body) text.
    public var textSecondary: NerveColor
    /// Interactive accent.
    public var accent: NerveColor
    /// Positive / success state.
    public var success: NerveColor
    /// Warning state.
    public var warning: NerveColor
    /// Negative / danger state.
    public var danger: NerveColor

    public init(
        background: NerveColor,
        surface: NerveColor,
        textPrimary: NerveColor,
        textSecondary: NerveColor,
        accent: NerveColor,
        success: NerveColor,
        warning: NerveColor,
        danger: NerveColor
    ) {
        self.background = background
        self.surface = surface
        self.textPrimary = textPrimary
        self.textSecondary = textSecondary
        self.accent = accent
        self.success = success
        self.warning = warning
        self.danger = danger
    }

    /// The app's current look (dark, matching the shipped UI).
    public static let dark = Theme(
        background: NerveColor(red: 0x11 / 255, green: 0x18 / 255, blue: 0x27 / 255), // #111827
        surface: NerveColor(red: 0x1f / 255, green: 0x29 / 255, blue: 0x37 / 255), // #1f2937
        textPrimary: NerveColor(red: 1.0, green: 1.0, blue: 1.0), // #ffffff
        textSecondary: NerveColor(red: 0xb4 / 255, green: 0xbb / 255, blue: 0xc6 / 255), // #b4bbc6
        accent: NerveColor(red: 0x3b / 255, green: 0x82 / 255, blue: 0xf6 / 255), // #3b82f6
        success: NerveColor(red: 0x34 / 255, green: 0xd3 / 255, blue: 0x99 / 255), // #34d399
        warning: NerveColor(red: 0xfb / 255, green: 0xbf / 255, blue: 0x24 / 255), // #fbbf24
        danger: NerveColor(red: 0xf8 / 255, green: 0x71 / 255, blue: 0x71 / 255) // #f87171
    )

    /// The light variant.
    public static let light = Theme(
        background: NerveColor(red: 0xf3 / 255, green: 0xf4 / 255, blue: 0xf6 / 255), // #f3f4f6
        surface: NerveColor(red: 1.0, green: 1.0, blue: 1.0), // #ffffff
        textPrimary: NerveColor(red: 0x26 / 255, green: 0x2b / 255, blue: 0x33 / 255), // #262b33
        textSecondary: NerveColor(red: 0x5c / 255, green: 0x64 / 255, blue: 0x71 / 255), // #5c6471
        accent: NerveColor(red: 0x25 / 255, green: 0x63 / 255, blue: 0xeb / 255), // #2563eb
        success: NerveColor(red: 0x10 / 255, green: 0xb9 / 255, blue: 0x81 / 255), // #10b981
        warning: NerveColor(red: 0xf5 / 255, green: 0x9e / 255, blue: 0x0b / 255), // #f59e0b
        danger: NerveColor(red: 0xb9 / 255, green: 0x1c / 255, blue: 0x1c / 255) // #b91c1c
    )

    /// The theme used when no explicit dark/light choice applies (default dark).
    public static let fallback = Theme.dark
}

// MARK: - ThemePreference

/// The user's theme choice. `.system` defers to the OS appearance.
public enum ThemePreference: String, CaseIterable, Codable, Sendable {
    case system
    case light
    case dark
}

// MARK: - ThemeStore

/// Holds the user's theme preference and resolves it to a concrete ``Theme``.
///
/// Persistence is a plain `@AppStorage` string (no keychain) under the
/// `nerveTheme` key. Resolution of `.system` defers to the *effective*
/// appearance of the running view, so app roots pass the SwiftUI
/// `colorScheme` into ``resolvedTheme(for:)`` — that keeps the store
/// platform-agnostic (no UIApplication / NSAppearance reads in the shared
/// module) and re-resolves live as the OS appearance changes.
public final class ThemeStore: ObservableObject {
    /// The persisted user preference (raw ``ThemePreference`` value).
    @AppStorage("nerveTheme") public var preference: String = ThemePreference.system.rawValue

    public init(preference: String = ThemePreference.system.rawValue) {
        self.preference = preference
    }

    /// The current ``ThemePreference`` (falls back to `.system`).
    public var themePreference: ThemePreference {
        ThemePreference(rawValue: preference) ?? .system
    }

    /// Resolve the current preference against the running view's scheme.
    ///
    /// - Parameter colorScheme: the `ColorScheme` SwiftUI reports for the
    ///   enclosing view (`.light` / `.dark`). When the preference is
    ///   `.system` this is what the theme follows; for explicit
    ///   `.light` / `.dark` the preference wins.
    public func resolvedTheme(for colorScheme: ColorScheme) -> Theme {
        switch themePreference {
        case .dark:  return .dark
        case .light: return .light
        case .system: return colorScheme == .light ? .light : .dark
        }
    }
}

// MARK: - SwiftUI environment injection (SwiftUI-optional)

#if canImport(SwiftUI)

/// Environment key that carries the resolved ``Theme`` down the view tree.
private struct NerveThemeKey: EnvironmentKey {
    static let defaultValue: Theme = .dark
}

public extension EnvironmentValues {
    /// The resolved theme, injected by `View.theme(_:)` / `ThemeModifier`.
    var nerveTheme: Theme {
        get { self[NerveThemeKey.self] }
        set { self[NerveThemeKey.self] = newValue }
    }
}

/// A `ViewModifier` that injects a resolved ``Theme`` through the
/// `Environment`. App roots apply this once so descendant views can read
/// `@Environment(\.nerveTheme)` and adopt tokens.
public struct ThemeModifier: ViewModifier {
    private let theme: Theme

    public init(_ theme: Theme) {
        self.theme = theme
    }

    public func body(content: Content) -> some View {
        content.environment(\.nerveTheme, theme)
    }
}

public extension View {
    /// Inject `theme` into the environment for this view and its descendants.
    func theme(_ theme: Theme) -> some View {
        modifier(ThemeModifier(theme))
    }
}
#endif
