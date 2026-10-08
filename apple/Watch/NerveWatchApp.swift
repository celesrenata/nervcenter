import SwiftUI

import NerveApps
import NerveDesign

// MARK: - Watch app entry point (spec §63–§68)

/// The `@main` app for the `NerveWatch` target.
///
/// Watch apps use a single NavigationStack (no TabView) — the §63 goal
/// flows are reached from the home screen's goal navigation:
///
/// ```text
/// glance          → WatchHomeView (root)
/// alert           → WatchAlertView
/// query           → WatchQueryView
/// acknowledge     → WatchAcknowledgeView
/// approve/reject  → WatchApprovalsView (one inbox for both goals)
/// stop            → WatchStopView (explicit §67 confirmation surface)
/// ```
///
/// Data flows from the App Group container (`WatchAppGroup.identifier`,
/// files `cached-state.json` + `approvals.json`) through
/// ``WatchDataStore``. With no snapshot the app renders an honest
/// "Not connected" state — it never fabricates counts.
@main
struct NerveWatchApp: App {
    @StateObject private var store = WatchDataStore()

    var body: some Scene {
        WindowGroup {
            NavigationStack {
                WatchHomeView(store: store)
                    .navigationDestination(for: WatchDestination.self) { destination in
                        destinationView(destination)
                    }
            }
            .environmentObject(store)
        }
    }

    private func destinationView(_ destination: WatchDestination) -> AnyView {
        switch destination {
        case .alert:
            return AnyView(WatchAlertView(store: store))
        case .query:
            return AnyView(WatchQueryView(store: store))
        case .acknowledge:
            return AnyView(WatchAcknowledgeView(store: store))
        case .approvals:
            return AnyView(WatchApprovalsView(store: store))
        case .stop:
            return AnyView(WatchStopView(store: store))
        }
    }
}

// MARK: - §68 Complication support

/// Entry point for feeding the Watch complications (spec §68).
///
/// The §68 ladder decision is computed *outside* SwiftUI so it is testable
/// and reusable:
///
/// ```swift
/// let inputs = store.complicationInputs   // nil when offline
/// let item = inputs.map { ComplicationLadder.render(for: $0) }
/// ```
///
/// No live-complication entry point is implemented in this target:
/// `AccessoryWidgetBundle` / `LiveComplicationController` require the
/// watchOS SDK and a separate widget-extension target. Per the task
/// contract a live entry is not required when the API is unavailable; the
/// §68 decision logic is fully available above for the extension target to
/// consume. (Keeping `WidgetKit`/`SwiftUI` accessory APIs out of this file
/// also keeps the target building on the macOS host.)
public enum NerveWatchComplication {
    /// Render the single §68 rung the current snapshot supports, or `nil`
    /// when no snapshot exists (the complication then shows its
    /// unavailable configuration — an honest "no data", not a fake 0).
    public static func render(from store: WatchDataStore) -> ComplicationItem? {
        store.complicationInputs.map { ComplicationLadder.render(for: $0) }
    }
}
