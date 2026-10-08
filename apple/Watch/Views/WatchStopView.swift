import SwiftUI

import NerveApps
import NerveDesign

// MARK: - §63 `stop` / §67 emergency stop

/// The §67 emergency STOP surface.
///
/// Deliberately a standalone push destination (not a row action): spec §67
/// demands an explicit confirmation surface for destructive, high-
/// consequence controls. The big red button invokes the injectable
/// ``WatchStopAction`` (production: writes `stop-agents.json` into the App
/// Group container) and confirms via a state flag.
public struct WatchStopView: View {
    @ObservedObject var store: WatchDataStore

    @State private var confirming = false

    public init(store: WatchDataStore) {
        self.store = store
    }

    public var body: some View {
        VStack(spacing: 8) {
            if store.stopRequested {
                confirmationBlock
            } else {
                confirmBlock
            }

            if let error = store.stopError {
                Label(error, systemImage: "exclamationmark.triangle")
                    .font(.caption2)
                    .foregroundStyle(Color.nerve(HealthColor.critical.color))
                    .multilineTextAlignment(.center)
            }
        }
        .padding(6)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.watchCanvas.ignoresSafeArea())
        .navigationTitle("Emergency")
    }

    private var confirmBlock: some View {
        VStack(spacing: 6) {
            Image(systemName: "stop.circle")
                .font(.largeTitle)
                .foregroundStyle(Color.nerve(HealthColor.critical.color))

            Text("STOP AGENTS")
                .font(.headline.weight(.bold))

            Text(EmergencyControl.stopAgents.confirmationCopy)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            if confirming {
                Button {
                    store.requestStop()
                    confirming = false
                } label: {
                    Label("Confirm STOP", systemImage: "stop.circle.fill")
                        .font(.callout.weight(.bold))
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.nerve(HealthColor.critical.color))
                .accessibilityLabel("Confirm stop all agents")
            } else {
                Button("I understand — continue") {
                    confirming = true
                }
                .buttonStyle(.bordered)
                .font(.caption)
            }
        }
    }

    private var confirmationBlock: some View {
        VStack(spacing: 6) {
            Image(systemName: "checkmark.circle.fill")
                .font(.largeTitle)
                .foregroundStyle(Color.nerve(HealthColor.healthy.color))

            Text("Stop requested")
                .font(.headline)

            Text("The stop marker was written to the shared container. The iPhone app picks it up and halts the agents.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .accessibilityElement(children: .combine)
    }
}
