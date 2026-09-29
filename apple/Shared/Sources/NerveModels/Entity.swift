import Foundation

/// Classification of a knowledge-graph node.
public enum EntityType: String, Codable, CaseIterable, Sendable {
    case person
    case organization
    case place
    case document
    case artifact
    case concept
    case device
    case agent
    case credential
    case resource
    case other
}

/// A node in the NerveCenter knowledge graph.
///
/// Mirrors `schemas.entities.Entity`. Every entity is evidence-backed: it records
/// *where* its facts came from via ``sourceEvidence`` and carries a temporal
/// validity window expressing *when* the entity's facts hold.
public struct Entity: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Classification of the entity.
    public var entityType: EntityType

    /// Primary human-readable name of the entity.
    public var name: String

    /// Free-form summary of the entity.
    public var description: String?

    /// Structured, type-specific key/value attributes.
    public var attributes: [String: AnyCodable]

    /// Alternative names and identifiers the entity is known by.
    public var aliases: [String]

    /// Confidence (0..1) that this entity and its attributes are correct.
    public var confidence: Double

    /// Time interval during which the entity's facts hold.
    public var valid: TemporalWindow

    /// Ids of ``Evidence`` records backing this entity.
    public var sourceEvidence: [String]

    public init(
        id: String,
        entityType: EntityType,
        name: String,
        description: String? = nil,
        attributes: [String: AnyCodable] = [:],
        aliases: [String] = [],
        confidence: Double = 1.0,
        valid: TemporalWindow = TemporalWindow(),
        sourceEvidence: [String] = [],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.entityType = entityType
        self.name = name
        self.description = description
        self.attributes = attributes
        self.aliases = aliases
        self.confidence = confidence
        self.valid = valid
        self.sourceEvidence = sourceEvidence
    }
}
