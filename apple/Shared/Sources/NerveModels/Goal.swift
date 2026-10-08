import Foundation

/// Lifecycle state of a goal (wire contract, `schemas/goals.py` `GoalStatus`).
public enum GoalStatus: String, Codable, CaseIterable, Sendable {
    case active
    case paused
    case achieved
    case abandoned
}

/// Presentation state of a goal per spec §20 (uppercase wire values):
/// `DRAFT / ACTIVE / BLOCKED / COMPLETE / ABANDONED`.
public enum GoalState: String, Codable, CaseIterable, Sendable {
    case draft = "DRAFT"
    case active = "ACTIVE"
    case blocked = "BLOCKED"
    case complete = "COMPLETE"
    case abandoned = "ABANDONED"
}

/// Outcome status of an agent execution.
public enum AgentResultStatus: String, Codable, CaseIterable, Sendable {
    case succeeded
    case failed
    case partial
    case needsApproval = "needs_approval"
}

/// A desired state the core works toward, with measurable criteria.
///
/// Mirrors `schemas/goals.py` `Goal`.
public struct Goal: Codable, Hashable, Sendable, Identifiable {
    public let id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Short statement of the goal.
    public var title: String

    /// Full description of the goal and its intent.
    public var description: String?

    /// Lifecycle state of the goal.
    public var status: GoalStatus

    /// Overall progress toward completion (0..1).
    public var progress: Double

    /// Measurable criteria that define completion.
    public var criteria: [String]

    /// Ids of child ``Goal`` records this goal decomposes into.
    public var subgoalIds: [String]

    /// Goal priority; 0 (lowest) to 10 (highest).
    public var priority: Int

    /// Optional deadline for the goal (UTC).
    public var deadline: Date?

    /// Ids of ``Entity`` records the goal concerns.
    public var relatedEntityIds: [String]

    public init(
        id: String,
        title: String,
        description: String? = nil,
        status: GoalStatus = .active,
        progress: Double = 0.0,
        criteria: [String] = [],
        subgoalIds: [String] = [],
        priority: Int = 0,
        deadline: Date? = nil,
        relatedEntityIds: [String] = [],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.title = title
        self.description = description
        self.status = status
        self.progress = progress
        self.criteria = criteria
        self.subgoalIds = subgoalIds
        self.priority = priority
        self.deadline = deadline
        self.relatedEntityIds = relatedEntityIds
    }
}

/// Structured output produced by an agent/task execution.
///
/// Mirrors `schemas/goals.py` `AgentResult`.
public struct AgentResult: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Id of the ``TaskRun`` that produced this result.
    public var taskRunId: String

    /// Id of the agent that produced the result.
    public var agentId: String?

    /// Outcome status of the execution.
    public var status: AgentResultStatus

    /// Human-readable summary of what was accomplished.
    public var summary: String?

    /// Typed, machine-readable output produced by the agent.
    public var structuredOutput: [String: NerveJSONValue]

    /// Ids of ``Entity`` records created or updated.
    public var producedEntityIds: [String]

    /// Ids of ``Evidence`` records created by the run.
    public var producedEvidenceIds: [String]

    /// Ids of ``Claim`` records produced by the run.
    public var producedClaimIds: [String]

    /// Optional cost (in USD) of the execution, if tracked.
    public var cost: Double?

    /// Total tokens consumed, if tracked.
    public var tokensUsed: Int?

    public init(
        id: String,
        taskRunId: String,
        agentId: String? = nil,
        status: AgentResultStatus = .succeeded,
        summary: String? = nil,
        structuredOutput: [String: NerveJSONValue] = [:],
        producedEntityIds: [String] = [],
        producedEvidenceIds: [String] = [],
        producedClaimIds: [String] = [],
        cost: Double? = nil,
        tokensUsed: Int? = nil,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.taskRunId = taskRunId
        self.agentId = agentId
        self.status = status
        self.summary = summary
        self.structuredOutput = structuredOutput
        self.producedEntityIds = producedEntityIds
        self.producedEvidenceIds = producedEvidenceIds
        self.producedClaimIds = producedClaimIds
        self.cost = cost
        self.tokensUsed = tokensUsed
    }
}
