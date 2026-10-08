import Foundation

import NerveModels

// MARK: - §59 iPhone Incidents

/// A single fact or hypothesis line within an incident.
public struct IncidentStatement: Codable, Hashable, Sendable, Identifiable {
    public let id: String
    public let text: String
    /// Optional confidence (0…1) when the statement is a hypothesis.
    public let confidence: Double?
    /// Evidence ids backing this statement (inspectable provenance).
    public let evidenceIDs: [String]

    public init(id: String, text: String, confidence: Double? = nil, evidenceIDs: [String] = []) {
        self.id = id
        self.text = text
        self.confidence = confidence
        self.evidenceIDs = evidenceIDs
    }
}

/// A timeline entry in the §59 incident view.
public struct IncidentTimelineEntry: Codable, Hashable, Sendable, Identifiable {
    public let id: String
    public let at: Date
    public let text: String
    public let severity: EventSeverity

    public init(id: String, at: Date, text: String, severity: EventSeverity) {
        self.id = id
        self.at = at
        self.text = text
        self.severity = severity
    }
}

/// The §59 incident render contract.
///
/// Spec §59 fixes *what the incident view contains*:
///
/// ```text
/// summary
/// timeline
/// affected entities
/// facts
/// hypotheses
/// confidence
/// supporting evidence
/// agents investigating
/// recommended actions
/// planned changes
/// verification
/// ```
///
/// Facts and hypotheses remain separate (spec: evidence-backed reasoning).
/// `sectionOrder` lists the sections exactly as §59 enumerates them; the
/// SwiftUI `IncidentDetailScreen` renders in that order, so a regression that
/// reorders or drops a section is caught by the unit test, not visually.
public struct IncidentDetail: Codable, Hashable, Sendable, Identifiable {
    public typealias Section = String

    /// Section keys in the exact §59 presentation order.
    public static let sectionOrder: [Section] = [
        "summary",
        "timeline",
        "affectedEntities",
        "facts",
        "hypotheses",
        "confidence",
        "supportingEvidence",
        "agentsInvestigating",
        "recommendedActions",
        "plannedChanges",
        "verification",
    ]

    // One required section key per §59 line.

    public let id: String
    public let summary: String
    public let affectedEntityIDs: [String]
    public let facts: [IncidentStatement]
    public let hypotheses: [IncidentStatement]
    public let confidence: Double?
    public let supportingEvidenceIDs: [String]
    public let investigatingAgentIDs: [String]
    public let recommendedActions: [String]
    public let plannedChangeIDs: [String]
    public let verification: String?
    public let timeline: [IncidentTimelineEntry]

    public init(
        id: String,
        summary: String,
        timeline: [IncidentTimelineEntry] = [],
        affectedEntityIDs: [String] = [],
        facts: [IncidentStatement] = [],
        hypotheses: [IncidentStatement] = [],
        confidence: Double? = nil,
        supportingEvidenceIDs: [String] = [],
        investigatingAgentIDs: [String] = [],
        recommendedActions: [String] = [],
        plannedChangeIDs: [String] = [],
        verification: String? = nil
    ) {
        self.id = id
        self.summary = summary
        self.timeline = timeline
        self.affectedEntityIDs = affectedEntityIDs
        self.facts = facts
        self.hypotheses = hypotheses
        self.confidence = confidence
        self.supportingEvidenceIDs = supportingEvidenceIDs
        self.investigatingAgentIDs = investigatingAgentIDs
        self.recommendedActions = recommendedActions
        self.plannedChangeIDs = plannedChangeIDs
        self.verification = verification
    }

    /// Human-readable label for a §59 section key.
    public static func label(for section: Section) -> String {
        switch section {
        case "summary": return "Summary"
        case "timeline": return "Timeline"
        case "affectedEntities": return "Affected entities"
        case "facts": return "Facts"
        case "hypotheses": return "Hypotheses"
        case "confidence": return "Confidence"
        case "supportingEvidence": return "Supporting evidence"
        case "agentsInvestigating": return "Agents investigating"
        case "recommendedActions": return "Recommended actions"
        case "plannedChanges": return "Planned changes"
        case "verification": return "Verification"
        default: return section
        }
    }

    /// Whether a section is genuinely empty (renders "Not recorded").
    public func isEmpty(section: Section) -> Bool {
        switch section {
        case "summary": return summary.isEmpty
        case "timeline": return timeline.isEmpty
        case "affectedEntities": return affectedEntityIDs.isEmpty
        case "facts": return facts.isEmpty
        case "hypotheses": return hypotheses.isEmpty
        case "confidence": return confidence == nil
        case "supportingEvidence": return supportingEvidenceIDs.isEmpty
        case "agentsInvestigating": return investigatingAgentIDs.isEmpty
        case "recommendedActions": return recommendedActions.isEmpty
        case "plannedChanges": return plannedChangeIDs.isEmpty
        case "verification": return verification == nil
        default: return true
        }
    }
}
