import SwiftUI

import NerveApps
import NerveDesign
import NerveModels

// MARK: - Goals tab

/// Goals tab — §65 "Goals with progress".
public struct GoalsView: View {
    @ObservedObject public var store: PhoneDataStore

    public init(store: PhoneDataStore) {
        self.store = store
    }

    public var body: some View {
        ScrollView {
            LazyVStack(spacing: Spacing.sm) {
                if store.goals.isEmpty {
                    EmptyState(title: "No goals", actionLabel: "Load", onAction: {})
                } else {
                    ForEach(store.goals) { goal in
                        GoalRow(goal: goal)
                    }
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.top, Spacing.sm)
        }
        .background(Color.phoneCanvas.ignoresSafeArea())
    }

    // MARK: - Goal row

    struct GoalRow: View {
        let goal: Goal

        var body: some View {
            HStack {
                Text(goal.title)
                    .font(.body)
                    .foregroundStyle(.primary)
                Spacer()
                if goal.progress > 0 {
                    Text("\(Int(goal.progress * 100))%")
                        .font(.body.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, Spacing.xs)
        }
    }

    // MARK: - Empty state

    struct EmptyState: View {
        let title: String
        let actionLabel: String?
        let onAction: () -> Void

        var body: some View {
            VStack(spacing: Spacing.sm) {
                Text(title)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if let actionLabel {
                    Button(actionLabel, action: onAction)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.xs)
                        .background(Color.secondary.opacity(0.15))
                        .clipShape(Capsule())
                }
            }
            .padding(.top, Spacing.lg)
        }
    }
}
