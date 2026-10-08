import SwiftUI

import NerveApps
import NerveDesign

// MARK: - Systems tab

/// Systems tab — §65 "System health overview".
public struct SystemsView: View {
    @ObservedObject public var store: PhoneDataStore

    public init(store: PhoneDataStore) {
        self.store = store
    }

    public var body: some View {
        ScrollView {
            LazyVStack(spacing: Spacing.sm) {
                if store.systems.isEmpty {
                    VStack(spacing: Spacing.sm) {
                        Text("No systems recorded")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.top, Spacing.lg)
                } else {
                    ForEach(store.systems) { system in
                        SystemRowView(system: system)
                    }
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.top, Spacing.sm)
        }
        .background(Color.phoneCanvas.ignoresSafeArea())
    }

    // MARK: - Row

    struct SystemRowView: View {
        let system: SystemRow

        var body: some View {
            HStack {
                Text(system.name)
                    .font(.body)
                    .foregroundStyle(.primary)
                Spacer()
                Text(system.health)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.vertical, Spacing.xs)
        }
    }
}
