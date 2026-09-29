import Foundation

import NerveModels

/// Kind of change being proposed (wire contract, `schemas/planned_changes.py`).
public enum ChangeType: String, Codable, CaseIterable, Sendable {
    case entityUpsert = "entity_upsert"
    case relationshipUpsert = "relationship_upsert"
    case claimTransition = "claim_transition"
    case goalChange = "goal_change"
    case taskCreate = "task_create"
    case taskCancel = "task_cancel"
    case configUpdate = "config_update"
    case policyUpdate = "policy_update"
    case dataDeletion = "data_deletion"
    case other
}

/// Lifecycle state of a planned change (wire contract, `schemas/planned_changes.py`).
public enum PlannedChangeStatus: String, Codable, CaseIterable, Sendable {
    case draft
    case pendingApproval = "pending_approval"
    case approved
    case rejected
    case applied
    case rolledBack = "rolled_back"
    case expired
}

/// A proposed, reviewable modification to NerveCenter state.
///
/// Mirrors `schemas/planned_changes.py` `PlannedChange`.
public struct PlannedChange: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Kind of change being proposed.
    public var changeType: ChangeType

    /// Short human-readable summary of the change.
    public var title: String

    /// Full description of what will change and why.
    public var description: String?

    /// Lifecycle state of this planned change.
    public var status: PlannedChangeStatus

    /// Risk severity; 0 (trivial) to 4 (critical).
    public var riskLevel: Int

    /// Ids of records this change targets (entities, goals, tasks, ...).
    public var subjectIds: [String]

    /// Id of the ``Decision`` that produced this change.
    public var sourceDecisionId: String?

    /// Before/after diff representation of the change.
    public var diff: [String: NerveJSONValue]

    /// Instructions/payload for reverting this change if applied.
    public var rollback: [String: NerveJSONValue]

    /// When the change was first proposed (UTC).
    public var proposedAt: Date

    /// If set, the change is auto-expired (not applied) after this moment.
    public var expiresAt: Date?

    /// Id of the ``Approval`` governing this change, if any.
    public var approvalId: String?

    public init(
        id: String,
        changeType: ChangeType,
        title: String,
        description: String? = nil,
        status: PlannedChangeStatus = .draft,
        riskLevel: Int = 1,
        subjectIds: [String] = [],
        sourceDecisionId: String? = nil,
        diff: [String: NerveJSONValue] = [:],
        rollback: [String: NerveJSONValue] = [:],
        proposedAt: Date = Date(),
        expiresAt: Date? = nil,
        approvalId: String? = nil,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.changeType = changeType
        self.title = title
        self.description = description
        self.status = status
        self.riskLevel = riskLevel
        self.subjectIds = subjectIds
        self.sourceDecisionId = sourceDecisionId
        self.diff = diff
        self.rollback = rollback
        self.proposedAt = proposedAt
        self.expiresAt = expiresAt
        self.approvalId = approvalId
    }
}
