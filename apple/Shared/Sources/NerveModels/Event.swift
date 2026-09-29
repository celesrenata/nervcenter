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

    // MARK: - Integrity (spec §10 `hash` field)

    /// Recompute the SHA-256 integrity digest over the canonical serialization
    /// of this event's body, excluding the `hash` field itself (spec §10:
    /// `"hash": "sha256"`; see also ``RecordBase/hash``).
    ///
    /// The digest covers every wire field of the event — identity, provenance,
    /// classification, payload, and correlation — serialized through the shared
    /// ``NerveJSON`` contract (snake_case keys, ISO-8601 dates, sorted keys)
    /// so it matches the backend's `Record.fingerprint()` behavior.
    ///
    /// - Returns: The lowercase hex SHA-256 digest, or `nil` when the event
    ///   cannot be canonically encoded (never happens for a valid `Event`).
    public func computeIntegrityHash() -> String? {
        var encoder = NerveJSON.encoder
        encoder.outputFormatting = [.sortedKeys]

        guard let baseData = try? encoder.encode(self),
              let json = try? JSONSerialization.jsonObject(with: baseData) as? [String: Any],
              var cleaned = json as [String: Any]? else { return nil }

        cleaned.removeValue(forKey: "hash")
        guard let canonical = try? JSONSerialization.data(
            withJSONObject: cleaned,
            options: [.sortedKeys]
        ) else { return nil }

        return SHA256Helper.contentHash(canonical)
    }

    /// Verify the stored ``hash`` field against a freshly recomputed digest of
    /// the event body (spec §10: events are immutable and integrity-checked).
    ///
    /// - Returns: `true` when the stored digest is `nil` (unsigned event) or
    ///   matches the recomputed canonical digest; `false` on mismatch or when
    ///   the canonical digest could not be recomputed.
    public func verifyIntegrity() -> Bool {
        guard let storedHash = hash else { return true }
        guard let computed = computeIntegrityHash() else { return false }
        return storedHash == computed
    }

    /// Convenience factory: stamp `hash` with the freshly computed integrity
    /// digest (producer/test use per spec §10).
    @discardableResult
    public mutating func stampIntegrity() -> String {
        let computed = computeIntegrityHash()
        hash = computed
        return computed ?? ""
    }
}
