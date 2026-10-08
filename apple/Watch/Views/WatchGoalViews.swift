import SwiftUI

import NerveApps
import NerveDesign

// MARK: - §63 `alert` — the incident list from the snapshot

/// The §63 `alert` goal: shows what the wearer needs to know from the §73
/// snapshot — the recent incident ids. Only real snapshot data is shown;
/// with an empty snapshot this screen is honestly empty.
public struct WatchAlertView: View {
    @ObservedObject var store: WatchDataStore

    public init(store: WatchDataStore) {
        self.store = store
    }

    public var body: some View {
        Group {
            if let cached = store.snapshot {
                let incidentIDs = cached.recentIncidentIDs
                if incidentIDs.isEmpty {
                    VStack(spacing: 4) {
                        Text("\(cached.activeIncidents) active")
                            .font(.headline)
                        Text("Incident details are not in the compact snapshot — open the iPhone app for the full list.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 12)
                } else {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(incidentIDs, id: \.self) { incidentID in
                            incidentRow(incidentID)
                        }
                    }
                }
            } else {
                emptyHint("No incident data from the last sync.")
            }
        }
        .padding(6)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.watchCanvas.ignoresSafeArea())
        .navigationTitle("Incidents")
    }

    private func incidentRow(_ incidentID: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: "exclamationmark.triangle")
                .font(.caption)
                .foregroundStyle(Color.nerve(HealthColor.critical.color))
            Text(incidentID)
                .font(.caption)
                .lineLimit(2)
            Spacer(minLength: 0)
            if store.isAcknowledged(incidentID) {
                Image(systemName: "checkmark.seal.fill")
                    .font(.caption)
                    .foregroundStyle(Color.nerve(HealthColor.healthy.color))
                    .accessibilityLabel("Acknowledged")
            }
        }
    }

    private func emptyHint(_ text: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: "checkmark.shield")
                .font(.title3)
                .foregroundStyle(.secondary)
            Text(text)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 12)
    }
}

// MARK: - §63 `query` — short question, honest offline note

/// The §63 `query` goal: "Ask a short question and get a short answer".
///
/// The Watch has no Ask service of its own (spec §58 Ask runs on the
/// iPhone/backend). Rather than fabricate answers, this screen collects the
/// question and states honestly that it cannot be answered offline.
public struct WatchQueryView: View {
    @ObservedObject var store: WatchDataStore

    @State private var question = ""

    public init(store: WatchDataStore) {
        self.store = store
    }

    public var body: some View {
        VStack(spacing: 6) {
            TextField("Ask…", text: $question)
                .font(.caption)

            Button("Ask") {}
                .buttonStyle(.borderedProminent)
                .font(.caption)
                .disabled(question.trimmingCharacters(in: .whitespaces).isEmpty)

            if !question.isEmpty {
                Text("Query unavailable offline — the Watch has no Ask service. Ask from the iPhone app instead.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            if let report = store.staleness, report.isStale {
                WatchStaleBadge(report: report)
            }
        }
        .padding(6)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.watchCanvas.ignoresSafeArea())
        .navigationTitle("Query")
    }
}

// MARK: - §63 `acknowledge` — mark acknowledged locally

/// The §63 `acknowledge` goal: mark a notification/alert acknowledged.
///
/// Honest scope: acknowledgement is recorded in the Watch's *local* store.
/// The canonical acknowledgement lives on the iPhone; this screen says so
/// instead of pretending the Watch wrote to the server.
public struct WatchAcknowledgeView: View {
    @ObservedObject var store: WatchDataStore

    public init(store: WatchDataStore) {
        self.store = store
    }

    public var body: some View {
        Group {
            if let cached = store.snapshot, !cached.recentIncidentIDs.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(cached.recentIncidentIDs, id: \.self) { incidentID in
                        Button {
                            store.acknowledge(incidentID: incidentID)
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: store.isAcknowledged(incidentID)
                                    ? "checkmark.circle.fill" : "circle")
                                    .font(.caption)
                                Text(incidentID)
                                    .font(.caption)
                                    .lineLimit(2)
                                Spacer(minLength: 0)
                                Text(store.isAcknowledged(incidentID) ? "Acked" : "Ack")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            } else {
                VStack(spacing: 4) {
                    Image(systemName: "checkmark.seal")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                    Text("Nothing to acknowledge right now.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 12)
            }
        }
        .padding(6)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.watchCanvas.ignoresSafeArea())
        .navigationTitle("Acknowledge")
    }
}
