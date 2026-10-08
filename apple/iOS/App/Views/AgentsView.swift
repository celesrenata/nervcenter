import SwiftUI

import NerveApps
import NerveDesign

// MARK: - Agents tab

/// Agents tab — §65 "Agent activity".
public struct AgentsView: View {
    @ObservedObject public var store: PhoneDataStore

    public init(store: PhoneDataStore) {
        self.store = store
    }

    public var body: some View {
        ScrollView {
            LazyVStack(spacing: Spacing.sm) {
                if store.agents.isEmpty {
                    VStack(spacing: Spacing.sm) {
                        Text("No agents running")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.top, Spacing.lg)
                } else {
                    ForEach(store.agents) { agent in
                        AgentActivityRow(agent: agent)
                    }
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.top, Spacing.sm)
        }
        .background(Color.phoneCanvas.ignoresSafeArea())
    }

    // MARK: - Row

    struct AgentActivityRow: View {
        let agent: AgentRow

        var body: some View {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(agent.name)
                        .font(.body)
                        .foregroundStyle(.primary)
                    if let task = agent.currentTask {
                        Text(task)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }
                Spacer()
                Text(agent.status)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.vertical, Spacing.xs)
        }
    }
}
