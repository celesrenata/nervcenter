import Foundation

import NerveModels

/// Who is authorizing the change (wire contract, `schemas/approvals.py`).
public enum ApproverType: String, Codable, CaseIterable, Sendable {
    case human
    case policy
    case orchestrator
    case agent
}

/// Terminal verdict of an approval (wire contract, `schemas/approvals.py`).
public enum ApprovalDecision: String, Codable, CaseIterable, Sendable {
    case approved
    case denied
    case noResponse = "no_response"
}

/// A sign-off (or refusal) on a ``PlannedChange``.
///
/// Mirrors `schemas/approvals.py` `Approval`.
public struct Approval: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Id of the ``PlannedChange`` this approval applies to.
    public var plannedChangeId: String

    /// Kind of approver (human, policy, orchestrator, agent).
    public var approverType: ApproverType

    /// Identifier of the approver (user id, policy rule id, agent id, ...).
    public var approverId: String

    /// Terminal verdict.
    public var decision: ApprovalDecision

    /// Explanation of the verdict, if any.
    public var rationale: String?

    /// When the verdict was issued (UTC).
    public var decidedAt: Date?

    /// When the approval was first requested (UTC).
    public var requestedAt: Date?

    /// End of the approval validity window (UTC).
    public var expiresAt: Date?

    /// Optional scope constraint.
    public var scope: String?

    public init(
        id: String,
        plannedChangeId: String,
        approverType: ApproverType,
        approverId: String,
        decision: ApprovalDecision,
        rationale: String? = nil,
        decidedAt: Date? = nil,
        requestedAt: Date? = nil,
        expiresAt: Date? = nil,
        scope: String? = nil,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.plannedChangeId = plannedChangeId
        self.approverType = approverType
        self.approverId = approverId
        self.decision = decision
        self.rationale = rationale
        self.decidedAt = decidedAt
        self.requestedAt = requestedAt
        self.expiresAt = expiresAt
        self.scope = scope
    }

    /// Whether this approval is currently valid (approved and unexpired).
    public var isCurrentlyValid: Bool {
        guard decision == .approved else { return false }
        if let expiresAt { return expiresAt > Date() }
        return true
    }
}

/// Sensitive mobile approval record (spec §72):
///
/// ```json
/// {
///   "approval_id": "...",
///   "change_id": "...",
///   "device_id": "...",
///   "expires_at": "...",
///   "nonce": "..."
/// }
/// ```
///
/// Authorization applies to an *exact* ``PlannedChange``; any modification of
/// the planned change invalidates the approval (the backend re-checks the
/// change fingerprint server-side).
public struct SensitiveApproval: Codable, Hashable, Sendable {
    /// Server-side approval identifier.
    public var approvalId: String

    /// Id of the exact ``PlannedChange`` this authorizes.
    public var changeId: String

    /// Id of the device that issued the approval.
    public var deviceId: String

    /// When this approval expires (UTC).
    public var expiresAt: Date

    /// Replay-prevention nonce.
    public var nonce: String

    public init(
        approvalId: String,
        changeId: String,
        deviceId: String,
        expiresAt: Date,
        nonce: String
    ) {
        self.approvalId = approvalId
        self.changeId = changeId
        self.deviceId = deviceId
        self.expiresAt = expiresAt
        self.nonce = nonce
    }

    /// Whether this approval is still inside its validity window.
    public var isCurrentlyValid: Bool { expiresAt > Date() }
}
