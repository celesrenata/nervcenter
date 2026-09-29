import Foundation

/// Classification of the source an evidence record was captured from.
public enum EvidenceSourceType: String, Codable, CaseIterable, Sendable {
    case webPage = "web_page"
    case document
    case transcript
    case message
    case toolResult = "tool_result"
    case screenshot
    case databaseRow = "database_row"
    case file
    case manualNote = "manual_note"
    case modelOutput = "model_output"
    case other
}

/// An immutable, citable provenance record.
///
/// Mirrors `schemas.evidence.Evidence`. Evidence is the provenance primitive of
/// NerveCenter: every inference, decision, entity, and relationship must cite
/// captured evidence.
public struct Evidence: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Kind of source this evidence was captured from.
    public var sourceType: EvidenceSourceType

    /// Locating reference for the source (URL, path, URI, or id).
    public var sourceRef: String

    /// Captured text/content excerpt; may be redacted per policy.
    public var content: String?

    /// SHA-256 digest of the captured content for verifiability.
    public var contentHash: String?

    /// When the content was captured (UTC).
    public var capturedAt: Date

    /// Trusted-source score (0..1) assigned at capture time.
    public var trust: Double

    /// Capture-time metadata (http status, offsets, tool name, ...).
    public var metadata: [String: AnyCodable]

    /// Whether the content was redacted by policy before storage.
    public var redacted: Bool

    public init(
        id: String,
        sourceType: EvidenceSourceType,
        sourceRef: String,
        content: String? = nil,
        contentHash: String? = nil,
        capturedAt: Date = Date(),
        trust: Double = 0.5,
        metadata: [String: AnyCodable] = [:],
        redacted: Bool = false,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.sourceType = sourceType
        self.sourceRef = sourceRef
        self.content = content
        self.contentHash = contentHash
        self.capturedAt = capturedAt
        self.trust = trust
        self.metadata = metadata
        self.redacted = redacted
    }
}
