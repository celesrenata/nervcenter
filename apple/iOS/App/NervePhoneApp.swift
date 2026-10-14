import SwiftUI

import NerveApps
import NerveDesign

// MARK: - iPhone app entry point

/// The `@main` app for the `NervePhone` target.
///
/// Wires:
/// - `PhoneEnvironment` (service container: cache, credentials, shared state,
///   biometric gate)
/// - `PhoneDataStore` (per-tab data; hydrated from cache at bootstrap)
/// - The six §56 tabs (Overview, Goals, Incidents, Agents, Systems, Ask)
@main
struct NervePhoneApp: App {
    @StateObject private var environment = PhoneEnvironment(
        server: ServerConfig(host: "nerv.celestium.life")
    )
    @StateObject private var store = PhoneDataStore()
    @StateObject private var themeStore = ThemeStore()
    @Environment(\.colorScheme) private var colorScheme

    var body: some Scene {
        WindowGroup {
            AppShell()
                .environmentObject(environment)
                .environmentObject(themeStore)
                .theme(themeStore.resolvedTheme(for: colorScheme))
                .task {
                    await bootstrap()
                }
        }
    }

    /// Load persisted credentials and hydrate the cache snapshot.
    @MainActor
    private func bootstrap() async {
        await environment.bootstrap()
        store.apply(environment.cacheState)
    }
}

// MARK: - App shell with six tabs

/// The app shell hosts the tab view that renders the six §56 tabs.
struct AppShell: View {
    @EnvironmentObject private var environment: PhoneEnvironment
    @StateObject private var store = PhoneDataStore()

    var body: some View {
        TabView {
            OverviewView(store: store)
                .tabItem {
                    Label("Overview", systemImage: PhoneTab.overview.symbolName)
                }

            GoalsView(store: store)
                .tabItem {
                    Label("Goals", systemImage: PhoneTab.goals.symbolName)
                }

            IncidentsView(store: store)
                .tabItem {
                    Label("Incidents", systemImage: PhoneTab.incidents.symbolName)
                }

            AgentsView(store: store)
                .tabItem {
                    Label("Agents", systemImage: PhoneTab.agents.symbolName)
                }

            SystemsView(store: store)
                .tabItem {
                    Label("Systems", systemImage: PhoneTab.systems.symbolName)
                }

            AskView(store: store)
                .tabItem {
                    Label("Ask", systemImage: PhoneTab.ask.symbolName)
                }
        }
        .tint(.blue)
    }
}
