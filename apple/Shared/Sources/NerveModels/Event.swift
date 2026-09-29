import Foundation

/// Classification of a subsystem the event belongs to.
public enum EventCategory: String, Codable, CaseIterable, Sendable {
    case system
    case knowledge
    case evidence
    case goal
    case task
    case inference
    case policy
    case orchestration
    case connector
}

/// Severity levels for operational/signal events.
public enum EventSeverity: String, Codable, CaseIterable, Sendable {
    case debug
    case info
    case warning
    case error
    case critical
}

/// A single immutable event on the NerveCenter event bus.
///
/// Mirrors `schemas.events.Event`. Events are append-only; corrections are emitted
/// as new events referencing the original via ``parentEventId``. The ``payload`` is
/// an opaque, type-specific document whose shape is described by the matching
/// ``eventType`` contract.
public struct Event: Codable, Hashable, Sendable {
    /// Machine-readable event type, e.g. 'entity.created' or 'task.completed'.
    public var eventType: String

    /// Coarse subsystem the event belongs to.
    public var category: EventCategory

    /// When the underlying phenomenon occurred (UTC), as opposed to creation time.
    public var occurredAt: Date

    /// Origin of the event, e.g. a connector id, agent id, or 'internal'.
    public var source: String

    /// Optional primary subject id (entity, task, goal, ...) the event is about.
    public var subject: String?

    /// Type-specific event body; validated by the matching eventType contract.
    public var payload: [String: AnyCodable]

    /// Operational severity of the event.
    public var severity: EventSeverity

    /// Distributed trace id linking related events across subsystems.
    public var traceId: String?

    /// Correlation id grouping a logical unit of work.
    public var correlationId: String?

    /// Id of the event that caused or is corrected by this event.
    public var parentEventId: String?

    /// Logical stream name this event belongs to.
    public var stream: String?

    /// Monotonic offset of this event within its stream (WAL position).
    public var sequence: Int?

    /// Key used to deduplicate retried or replayed events.
    public var idempotencyKey: String?

    /// Base record fields.
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    public init(
        eventType: String,
        category: EventCategory,
        occurredAt: Date = Date(),
        source: String,
        subject: String? = nil,
        payload: [String: AnyCodable] = [:],
        severity: EventSeverity = .info,
        traceId: String? = nil,
        correlationId: String? = nil,
        parentEventId: String? = nil,
        stream: String? = nil,
        sequence: Int? = nil,
        idempotencyKey: String? = nil,
        id: String,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.eventType = eventType
        self.category = category
        self.occurredAt = occurredAt
        self.source = source
        self.subject = subject
        self.payload = payload
        self.severity = severity
        self.traceId = traceId
        self.correlationId = correlationId
        self.parentEventId = parentEventId
        self.stream = stream
        self.sequence = sequence
        self.idempotencyKey = idempotencyKey
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
    }
}
