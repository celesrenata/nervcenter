import Foundation

/// Lifecycle of a scheduled task (wire contract, `schemas.tasks.TaskStatus`).
public enum TaskStatus: String, Codable, CaseIterable, Sendable {
    case pending
    case scheduled
    case inProgress = "in_progress"
    case completed
    case failed
    case cancelled
}

/// Outcome of a single task execution attempt.
public enum TaskRunStatus: String, Codable, CaseIterable, Sendable {
    case running
    case succeeded
    case failed
    case timedOut = "timed_out"
    case cancelled
}

/// Visual task DAG state per spec §22 / §50 — the 8 presentation states,
/// including `CANCELLED` added by §22 (wire values are uppercase `PENDING`,
/// `READY`, … `CANCELLED`).
public enum TaskState: String, Codable, CaseIterable, Sendable {
    case pending = "PENDING"
    case ready = "READY"
    case running = "RUNNING"
    case blocked = "BLOCKED"
    case verifying = "VERIFYING"
    case succeeded = "SUCCEEDED"
    case failed = "FAILED"
    case cancelled = "CANCELLED"
}

/// A unit of work scheduled by the core.
///
/// Mirrors `schemas.tasks.Task`.
public struct Task: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Short human-readable task title.
    public var title: String

    /// Full description of the work to be performed.
    public var description: String?

    /// Lifecycle state of the task.
    public var status: TaskStatus

    /// Scheduling priority; 0 (lowest) to 10 (highest).
    public var priority: Int

    /// Id of the ``Goal`` this task contributes to, if any.
    public var goalId: String?

    /// Id of the ``Decision`` that triggered this task, if any.
    public var decisionId: String?

    /// Id of the agent/runtime that should execute this task.
    public var assigneeAgentId: String?

    /// Optional deadline for the task (UTC).
    public var dueAt: Date?

    /// When the task was placed on the queue (UTC).
    public var scheduledAt: Date?

    /// Structured inputs the executor will consume.
    public var inputs: [String: AnyCodable]

    /// Id of the parent task for hierarchical decomposition.
    public var parentTaskId: String?

    /// Ids of tasks that must finish before this task may start (DAG edges).
    public var dependencies: [String]

    public init(
        id: String,
        title: String,
        description: String? = nil,
        status: TaskStatus = .pending,
        priority: Int = 0,
        goalId: String? = nil,
        decisionId: String? = nil,
        assigneeAgentId: String? = nil,
        dueAt: Date? = nil,
        scheduledAt: Date? = nil,
        inputs: [String: AnyCodable] = [:],
        parentTaskId: String? = nil,
        dependencies: [String] = [],
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
        self.priority = priority
        self.goalId = goalId
        self.decisionId = decisionId
        self.assigneeAgentId = assigneeAgentId
        self.dueAt = dueAt
        self.scheduledAt = scheduledAt
        self.inputs = inputs
        self.parentTaskId = parentTaskId
        self.dependencies = dependencies
    }
}

/// A single execution attempt of a ``Task``.
///
/// Mirrors `schemas.tasks.TaskRun`.
public struct TaskRun: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Id of the task this run executes.
    public var taskId: String

    /// Outcome of this execution attempt.
    public var status: TaskRunStatus

    /// 1-based attempt number for this task.
    public var attempt: Int

    /// When execution began (UTC).
    public var startedAt: Date?

    /// When execution ended (UTC).
    public var finishedAt: Date?

    /// Id of the agent/runtime that performed the run.
    public var agentId: String?

    /// Id of the model used, when a model was involved.
    public var modelId: String?

    /// Id of the produced ``AgentResult``, if any.
    public var resultRef: String?

    /// Error message, when the attempt failed or timed out.
    public var error: String?

    /// Reference to captured logs for this run.
    public var logsRef: String?

    public init(
        id: String,
        taskId: String,
        status: TaskRunStatus = .running,
        attempt: Int = 1,
        startedAt: Date? = nil,
        finishedAt: Date? = nil,
        agentId: String? = nil,
        modelId: String? = nil,
        resultRef: String? = nil,
        error: String? = nil,
        logsRef: String? = nil,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.taskId = taskId
        self.status = status
        self.attempt = attempt
        self.startedAt = startedAt
        self.finishedAt = finishedAt
        self.agentId = agentId
        self.modelId = modelId
        self.resultRef = resultRef
        self.error = error
        self.logsRef = logsRef
    }
}
