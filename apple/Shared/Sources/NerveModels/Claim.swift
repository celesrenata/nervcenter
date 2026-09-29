import Foundation

/// Lifecycle state of a claim (wire contract, `schemas/claims.py`).
public enum ClaimStatus: String, Codable, CaseIterable, Sendable {
    case open
    case supported
    case contradicted
    case superseded
    case rejected
}

/// Classification of how a claim was formed per spec §16
/// (`FACT|DERIVED_FACT|HYPOTHESIS|RECOMMENDATION`).
public enum ClaimClassification: String, Codable, CaseIterable, Sendable {
    case fact = "FACT"
    case derivedFact = "DERIVED_FACT"
    case hypothesis = "HYPOTHESIS"
    case recommendation = "RECOMMENDATION"
}

/// Verification posture of a claim or inference per spec §16 / §37
/// (`unverified|verified|rejected|conflicted`).
public enum VerificationState: String, Codable, CaseIterable, Sendable {
    case unverified
    case verified
    case rejected
    case conflicted
}

/// A proposition formed from evidence, with a lifecycle and confidence.
///
/// Mirrors `schemas/claims.py` `Claim`.
public struct Claim: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// The claim, stated as a single sentence.
    public var statement: String

    /// Primary entity the claim is about, if any.
    public var subjectEntityId: String?

    /// Lifecycle state of the claim.
    public var status: ClaimStatus

    /// Classification of how the claim was formed (spec §16).
    public var classification: ClaimClassification

    /// Confidence (0..1) that the claim is true.
    public var confidence: Double

    /// Ids of ``Evidence`` records supporting the claim.
    public var supportingEvidence: [String]

    /// Ids of ``Evidence`` records contradicting the claim.
    public var contradictingEvidence: [String]

    /// Ids of other claims this claim was inferred from.
    public var derivedFromClaims: [String]

    /// Id of the earlier claim this one replaces, when superseded.
    public var supersedesClaimId: String?

    /// Structured, claim-specific data (values, ranges, tags, ...).
    public var attributes: [String: NerveJSONValue]

    /// Verification posture of this claim's content (spec §37).
    public var verification: VerificationState

    public init(
        id: String,
        statement: String,
        subjectEntityId: String? = nil,
        status: ClaimStatus = .open,
        classification: ClaimClassification = .hypothesis,
        confidence: Double = 0.5,
        supportingEvidence: [String] = [],
        contradictingEvidence: [String] = [],
        derivedFromClaims: [String] = [],
        supersedesClaimId: String? = nil,
        attributes: [String: NerveJSONValue] = [:],
        verification: VerificationState = .unverified,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.statement = statement
        self.subjectEntityId = subjectEntityId
        self.status = status
        self.classification = classification
        self.confidence = confidence
        self.supportingEvidence = supportingEvidence
        self.contradictingEvidence = contradictingEvidence
        self.derivedFromClaims = derivedFromClaims
        self.supersedesClaimId = supersedesClaimId
        self.attributes = attributes
        self.verification = verification
    }
}

/// How a decision was reached.
///
/// `schemas/claims.py` `DecisionMechanism`: heuristic, model_inference,
/// human, policy, orchestrator.
public enum DecisionMechanism: String, Codable, CaseIterable, Sendable {
    case heuristic
    case modelInference = "model_inference"
    case human
    case policy
    case orchestrator
}

/// A claim the system acted on, with rationale and execution links.
///
/// Mirrors `schemas/claims.py` `Decision`.
public struct Decision: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Id of the ``Claim`` this decision was made on.
    public var claimId: String

    /// Restatement of the decision taken.
    public var statement: String

    /// How the decision was reached.
    public var mechanism: DecisionMechanism

    /// Explainable rationale for the decision.
    public var rationale: String?

    /// Machine-readable action identifier chosen (e.g. 'task.schedule').
    public var action: String

    /// Ids of ``Evidence`` records justifying the decision.
    public var supportingEvidence: [String]

    /// Id of the resulting ``PlannedChange``, if one was emitted.
    public var plannedChangeId: String?

    /// Id of the resulting ``Task``, if one was scheduled.
    public var taskId: String?

    /// When the decision was made (UTC).
    public var decidedAt: Date

    public init(
        id: String,
        claimId: String,
        statement: String,
        mechanism: DecisionMechanism,
        rationale: String? = nil,
        action: String = "no_action",
        supportingEvidence: [String] = [],
        plannedChangeId: String? = nil,
        taskId: String? = nil,
        decidedAt: Date = Date(),
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.claimId = claimId
        self.statement = statement
        self.mechanism = mechanism
        self.rationale = rationale
        self.action = action
        self.supportingEvidence = supportingEvidence
        self.plannedChangeId = plannedChangeId
        self.taskId = taskId
        self.decidedAt = decidedAt
    }
}
