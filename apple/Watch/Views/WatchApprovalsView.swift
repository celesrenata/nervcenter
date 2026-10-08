import SwiftUI

import NerveApps
import NerveDesign

// MARK: - §63 `approve` / `reject` — the approvals inbox

/// The §66 approvals screen, shared by the `approve` and `reject` goals.
///
/// Policy gate (spec §66): a row may only be decided on the Watch when
/// ``WatchApprovalPolicy.evaluate(change:maxRisk:)`` returns
/// ``WatchApprovalDecision/approve``. Every other row — including rows the
/// Watch cannot even lift into a `PlannedChange` — is a *deep link* to the
/// iPhone. The Watch NEVER approves what the policy says to deep-link.
public struct WatchApprovalsView: View {
    @ObservedObject var store: WatchDataStore

    public init(store: WatchDataStore) {
        self.store = store
    }

    public var body: some View {
        Group {
            if store.approvals.isEmpty {
                VStack(spacing: 4) {
                    Image(systemName: "checkmark.shield")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                    Text("No pending approvals.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 12)
            } else {
                ScrollView {
                    VStack(spacing: 6) {
                        ForEach(store.approvals) { row in
                            approvalCard(row)
                        }
                    }
                    .padding(6)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.watchCanvas.ignoresSafeArea())
        .navigationTitle("Approvals")
    }

    private func approvalCard(_ row: WatchApprovalRow) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(row.title)
                .font(.caption.weight(.semibold))
                .lineLimit(2)
            if !row.summary.isEmpty {
                Text(row.summary)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            switch store.decision(for: row) {
            case .approve:
                decisionButtons(row)
            case .deepLink:
                deepLinkRow(row)
            }
        }
        .padding(6)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(.background)
        )
        .accessibilityElement(children: .combine)
    }

    /// §66-eligible row: the Watch may act. Approve and Reject are both
    /// offered (spec §63: both goals exist on the Watch). The decision is
    /// recorded *locally* — the canonical decision is written by the
    /// iPhone/phone app, so the screen says so.
    private func decisionButtons(_ row: WatchApprovalRow) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 6) {
                Button {
                    store.recordDecision(for: row.id, approved: true)
                } label: {
                    Label("Approve", systemImage: "checkmark.circle")
                        .font(.caption2.weight(.semibold))
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.nerve(HealthColor.healthy.color))

                Button {
                    store.recordDecision(for: row.id, approved: false)
                } label: {
                    Label("Reject", systemImage: "xmark.circle")
                        .font(.caption2.weight(.semibold))
                }
                .buttonStyle(.bordered)
                .tint(Color.nerve(HealthColor.critical.color))
            }

            if let decided = store.decidedApprovals[row.id] {
                Text(decided
                    ? "Approved on Watch (sent to iPhone for the canonical decision)."
                    : "Rejected on Watch (sent to iPhone for the canonical decision).")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }

    /// §66 deep-link row: the Watch must not act on it. Show the reason the
    /// policy excluded it and point at the iPhone — never a hidden approve.
    private func deepLinkRow(_ row: WatchApprovalRow) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Label(deepLinkReason(row), systemImage: "link")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(2)
            Text("Open on iPhone")
                .font(.caption2.weight(.semibold))
                .foregroundStyle(Color.nerve(HealthColor.degraded.color))
        }
        .accessibilityLabel("Deep link required. Reason: \(deepLinkReason(row))")
    }

    /// A short, honest reason string for why the policy deep-linked this
    /// row. Computed from the row's own fields — no fabricated detail.
    private func deepLinkReason(_ row: WatchApprovalRow) -> String {
        guard let change = row.makePlannedChange() else {
            return "Unknown change type — iPhone required"
        }
        if change.status != .pendingApproval {
            return "Not pending approval — iPhone required"
        }
        if change.rollback.isEmpty {
            return "Not reversible — iPhone required"
        }
        if change.riskLevel > WatchApprovalPolicy.maxWatchRiskLevel {
            return "Risk \(change.riskLevel) exceeds Watch limit — iPhone required"
        }
        return "Change type requires iPhone"
    }
}
