import SwiftUI

import NerveApps
import NerveDesign

// MARK: - Incidents tab

/// Incidents tab — §65 "Incidents with detail".
public struct IncidentsView: View {
    @ObservedObject public var store: PhoneDataStore

    public init(store: PhoneDataStore) {
        self.store = store
    }

    public var body: some View {
        ScrollView {
            LazyVStack(spacing: Spacing.sm) {
                if store.incidents.isEmpty {
                    EmptyState(title: "No incidents", actionLabel: "Refresh", onAction: {})
                } else {
                    ForEach(store.incidents) { incident in
                        IncidentRow(incident: incident)
                    }
                }
            }
            .padding(.horizontal, Spacing.md)
            .padding(.top, Spacing.sm)
        }
        .background(Color.phoneCanvas.ignoresSafeArea())
    }

    // MARK: - Incident row

    struct IncidentRow: View {
        let incident: IncidentDetail

        var body: some View {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(incident.summary)
                    .font(.headline)
                    .foregroundStyle(.primary)
                if !incident.facts.isEmpty {
                    Text("\(incident.facts.count) fact\(incident.facts.count == 1 ? "" : "s")")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                if !incident.hypotheses.isEmpty {
                    Text("\(incident.hypotheses.count) hypothesis\(incident.hypotheses.count == 1 ? "" : "es")")
                        .font(.caption2)
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
