import Foundation

import NerveModels

// MARK: - §58 Mobile Ask Interface

/// A provenance-preserving answer returned by the Ask surface (spec §58).
///
/// "Answers retain provenance. Evidence is inspectable." — every answer is
/// paired with the `Evidence` records that back it, so the UI can render
/// inspectable citations rather than a bare string.
public struct AskAnswer: Codable, Hashable, Sendable {
    public let answer: String
    public let evidence: [Evidence]
    public let traceID: String?
    public let receivedAt: Date

    public init(
        answer: String,
        evidence: [Evidence],
        traceID: String? = nil,
        receivedAt: Date = Date()
    ) {
        self.answer = answer
        self.evidence = evidence
        self.traceID = traceID
        self.receivedAt = receivedAt
    }

    /// One-line provenance summary, e.g. `3 evidence records · trace 0af…`.
    public var provenanceSummary: String {
        var parts: [String] = [("\(evidence.count) evidence record\(evidence.count == 1 ? "" : "s")")]
        if let traceID { parts.append("trace \(traceID.prefix(8))…") }
        return parts.joined(separator: " · ")
    }

    /// Whether the answer is backed by at least one inspectable evidence record.
    public var hasInspectableEvidence: Bool { !evidence.isEmpty }
}

/// A provenance citation rendered in the Ask detail view.
public struct EvidenceCitation: Identifiable, Sendable, Hashable {
    public let id: String
    public let sourceType: EvidenceSourceType
    public let sourceRef: String
    public let content: String?
    public let trust: Double
    public let capturedAt: Date

    public init(evidence: Evidence) {
        self.id = evidence.id
        self.sourceType = evidence.sourceType
        self.sourceRef = evidence.sourceRef
        self.content = evidence.content
        self.trust = evidence.trust
        self.capturedAt = evidence.capturedAt
    }

    /// Human-readable source type, e.g. "Tool result".
    public var sourceLabel: String {
        switch sourceType {
        case .webPage: return "Web page"
        case .document: return "Document"
        case .transcript: return "Transcript"
        case .message: return "Message"
        case .toolResult: return "Tool result"
        case .screenshot: return "Screenshot"
        case .databaseRow: return "Database row"
        case .file: return "File"
        case .manualNote: return "Manual note"
        case .modelOutput: return "Model output"
        case .other: return "Other"
        }
    }
}

extension AskAnswer {
    /// Inspectable citations for every backing evidence record.
    public var citations: [EvidenceCitation] { evidence.map { EvidenceCitation(evidence: $0) } }
}
