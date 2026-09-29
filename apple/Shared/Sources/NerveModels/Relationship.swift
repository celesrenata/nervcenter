import Foundation

/// Classification of a directed knowledge-graph edge.
public enum RelationType: String, Codable, CaseIterable, Sendable {
    case memberOf = "member_of"
    case parentOf = "parent_of"
    case childOf = "child_of"
    case owns
    case ownedBy = "owned_by"
    case locatedIn = "located_in"
    case partOf = "part_of"
    case dependsOn = "depends_on"
    case createdBy = "created_by"
    case created
    case supports
    case contradicts
    case relatedTo = "related_to"
    case other
}

/// A directed, time-scoped edge between two entities.
///
/// Mirrors `schemas.relationships.Relationship`. Relationships are evidence-backed
/// and carry a ``confidence``.
public struct Relationship: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Id of the source entity of this relationship.
    public var sourceEntityId: String

    /// Id of the target entity of this relationship.
    public var targetEntityId: String

    /// Classification of the relationship.
    public var relationType: RelationType

    /// Typed, relation-specific properties.
    public var properties: [String: AnyCodable]

    /// Temporal validity window: when this relationship is / was true.
    public var valid: TemporalWindow

    /// When the core first asserted this relationship (UTC).
    public var assertedAt: Date

    /// Confidence (0..1) in the truth of this relationship.
    public var confidence: Double

    /// Ids of ``Evidence`` records supporting this relationship.
    public var evidence: [String]

    public init(
        id: String,
        sourceEntityId: String,
        targetEntityId: String,
        relationType: RelationType,
        properties: [String: AnyCodable] = [:],
        valid: TemporalWindow = TemporalWindow(),
        assertedAt: Date = Date(),
        confidence: Double = 1.0,
        evidence: [String] = [],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.sourceEntityId = sourceEntityId
        self.targetEntityId = targetEntityId
        self.relationType = relationType
        self.properties = properties
        self.valid = valid
        self.assertedAt = assertedAt
        self.confidence = confidence
        self.evidence = evidence
    }
}
