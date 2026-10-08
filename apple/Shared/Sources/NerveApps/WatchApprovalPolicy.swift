import Foundation

import NerveAuth
import NerveModels

// MARK: - §66 Watch Approvals

/// Watch approval decision.
public enum WatchApprovalDecision: Codable, Sendable {
    /// Watch MAY approve this change.
    case approve
    /// Watch must deep-link to the iPhone for this change.
    case deepLink(link: String)
}

/// §66: which `ChangeType`s the Watch may approve directly. All others must
/// deep-link to the iPhone. The list of *forbidden* change types is explicit so
/// a future change that adds a destructive `ChangeType` does not silently
/// extend the Watch surface.
public enum WatchApprovalPolicy {
    /// Maximum risk level (on the `PlannedChange.riskLevel` 0–4 scale) the
    /// Watch may approve. §66: "LOW-RISK REVERSIBLE".
    public static let maxWatchRiskLevel = 1

    /// Deep link prefix the platform layer uses to open the iPhone approvals
    /// inbox for a specific change.
    public static let deepLinkPrefix = "nerv://phone/approval"

    private static func deepLink(for change: PlannedChange) -> WatchApprovalDecision {
        .deepLink(link: "\(deepLinkPrefix)/\(change.id)")
    }

    /// Decide whether the Watch may approve this planned change.
    ///
    /// A planned change is *eligible* when **all** hold:
    ///
    /// 1. Its `status` is still `.pendingApproval` (not yet applied/expired).
    /// 2. It has a non-empty `rollback` representation (reversible).
    /// 3. Its `riskLevel` is at or below ``maxWatchRiskLevel`` (≤ 1).
    /// 4. Its `changeType` is not in the §66 "deep-link required" set:
    ///    `dataDeletion`, `configUpdate`, `policyUpdate`, `taskCreate`,
    ///    `taskCancel`, `other`.
    ///
    /// Every other combination deep-links to the iPhone.
    public static func evaluate(
        change: PlannedChange,
        maxRisk: Int = maxWatchRiskLevel
    ) -> WatchApprovalDecision {
        // Not reversible → deep-link.
        guard !change.rollback.isEmpty else { return deepLink(for: change) }

        // Out of the Watch's risk band → deep-link.
        guard change.riskLevel <= maxRisk else { return deepLink(for: change) }

        // Must still be awaiting approval.
        guard change.status == .pendingApproval else { return deepLink(for: change) }

        // Disallowed change type → deep-link.
        if !isWatchApprovable(changeType: change.changeType) {
            return deepLink(for: change)
        }

        return .approve
    }

    /// The explicit §66 "deep-link required" change types. These are destructive
    /// or security-relevant and must always go to the iPhone.
    static func isWatchApprovable(changeType: ChangeType) -> Bool {
        // Everything not on the deny-list is approvable (subject to the other
        // gates). Keeping the allow-set is safer than a deny-set for new kinds.
        switch changeType {
        case .dataDeletion, .configUpdate, .policyUpdate, .taskCreate, .taskCancel, .other:
            return false
        case .entityUpsert, .relationshipUpsert, .claimTransition, .goalChange:
            return true
        }
    }

    /// Human-readable reason the Watch may (or may not) approve.
    public static func explain(_ change: PlannedChange) -> String {
        switch evaluate(change: change) {
        case .approve:
            return "Low-risk reversible change within Watch limits (risk ≤ \(maxWatchRiskLevel))."
        case .deepLink:
            return "This change requires iPhone approval; opening the approvals inbox."
        }
    }
}
