import Foundation

/// Classification of the consumer a context package is assembled for.
public enum ContextPurpose: String, Codable, CaseIterable, Sendable {
    case planning
    case taskExecution = "task_execution"
    case inference
    case review
    case decision
    case summarization
    case other
}

/// Which knowledge records a context section references.
public enum ContextSectionKind: String, Codable, CaseIterable, Sendable {
    case entities
    case relationships
    case evidence
    case claims
    case decisions
    case tasks
    case goals
    case agentResults = "agent_results"
    case notes
}

/// One section of a ``ContextPackage``: a curated, ordered view.
///
/// Mirrors `schemas.context.ContextSection`.
public struct ContextSection: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Which record kind this section references.
    public var kind: ContextSectionKind

    /// Human-readable label for this section.
    public var title: String?

    /// Ids of the stored records, in presentation order.
    public var recordIds: [String]

    /// Section ordering within the package.
    public var order: Int

    /// Token budget allocated to this section, if any.
    public var budgetTokens: Int?

    /// Section assembly metadata (retrieval query, score, ...).
    public var metadata: [String: AnyCodable]

    public init(
        id: String,
        kind: ContextSectionKind,
        title: String? = nil,
        recordIds: [String] = [],
        order: Int = 1,
        budgetTokens: Int? = nil,
        metadata: [String: AnyCodable] = [:],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.kind = kind
        self.title = title
        self.recordIds = recordIds
        self.order = order
        self.budgetTokens = budgetTokens
        self.metadata = metadata
    }
}

/// An assembled, token-budgeted bundle of records for a single use.
///
/// Mirrors `schemas.context.ContextPackage`.
public struct ContextPackage: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// What the assembled context is being consumed by.
    public var purpose: ContextPurpose

    /// Id of the ``Goal`` driving this assembly, if any.
    public var goalId: String?

    /// Id of the ``Task`` this context is attached to, if any.
    public var taskId: String?

    /// Total token budget allocated for the assembled context.
    public var tokenBudget: Int

    /// Estimated tokens actually used by the assembled sections.
    public var tokensUsed: Int

    /// Ordered sections composing the package.
    public var sections: [ContextSection]

    /// Whether policy redaction was applied before assembly.
    public var redacted: Bool

    /// Digest of the assembled content for reproducibility.
    public var contextHash: String?

    public init(
        id: String,
        purpose: ContextPurpose,
        goalId: String? = nil,
        taskId: String? = nil,
        tokenBudget: Int,
        tokensUsed: Int = 0,
        sections: [ContextSection] = [],
        redacted: Bool = false,
        contextHash: String? = nil,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.purpose = purpose
        self.goalId = goalId
        self.taskId = taskId
        self.tokenBudget = tokenBudget
        self.tokensUsed = tokensUsed
        self.sections = sections
        self.redacted = redacted
        self.contextHash = contextHash
    }
}
