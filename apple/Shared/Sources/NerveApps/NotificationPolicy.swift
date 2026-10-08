import Foundation

import NerveModels

// MARK: - §60 Notifications

/// Notification classes (spec §60):
///
/// ```text
/// INFORMATIONAL
/// ACTION_REQUIRED
/// URGENT
/// ```
public enum MobileNotificationClass: String, Codable, CaseIterable, Sendable {
    case informational = "INFORMATIONAL"
    case actionRequired = "ACTION_REQUIRED"
    case urgent = "URGENT"
}

/// A notification decision produced by ``NotificationPolicy``.
public struct MobileNotification: Codable, Hashable, Sendable {
    public let kind: MobileNotificationClass
    public let title: String
    public let body: String
    /// Deep link into the app (e.g. `nerv://incident/<id>`), nil for none.
    public let link: String?
    /// Whether the notification should interrupt (sound/badge) the device.
    public let interrupts: Bool

    public init(
        kind: MobileNotificationClass,
        title: String,
        body: String,
        link: String? = nil,
        interrupts: Bool = false
    ) {
        self.kind = kind
        self.title = title
        self.body = body
        self.link = link
        self.interrupts = interrupts
    }
}

/// Policy mapping NerveCenter events to the three §60 notification classes.
///
/// §60 names exactly the events that should notify and mandates *no*
/// notification for routine system events. ``evaluate(event:)`` is pure and
/// unit-testable; the platform layer (`UNUserNotificationCenter`) only
/// *renders* the returned ``MobileNotification``.
public enum NotificationPolicy {
    /// The event types §60 lists under "Notify for:".
    public static let notifyEventTypes: Set<String> = [
        "incident.detected",
        "incident.created",
        "task.failed",
        "goal.blocked",
        "approval.required",
        "investigation.completed",
        "deployment.failed",
        "benchmark.completed",
        "goal.completed",
    ]

    /// Routine event types that must never notify (spec §60: "Do not notify
    /// for routine system events").
    public static let routineEventTypes: Set<String> = [
        "heartbeat",
        "health.healthy",
        "task.queued",
        "task.scheduled",
        "agent.started",
        "agent.idle",
        "compute.heartbeat",
        "connector.connected",
        "entity.updated",
    ]

    /// Evaluate an event against the §60 policy.
    ///
    /// - Returns: `nil` when the event must not notify (routine or unlisted).
    public static func evaluate(event: Event) -> MobileNotification? {
        // Routine events are suppressed first, even if severity is high.
        if routineEventTypes.contains(event.eventType) { return nil }
        guard notifyEventTypes.contains(event.eventType) else { return nil }

        switch classify(event: event) {
        case .urgent:
            return MobileNotification(
                kind: .urgent,
                title: "NerveCenter — \(event.eventType)",
                body: eventSubject(event) ?? "Requires immediate attention",
                link: subjectLink(event),
                interrupts: true
            )
        case .actionRequired:
            return MobileNotification(
                kind: .actionRequired,
                title: "NerveCenter — \(event.eventType)",
                body: eventSubject(event) ?? "Action required",
                link: subjectLink(event),
                interrupts: true
            )
        case .informational:
            return MobileNotification(
                kind: .informational,
                title: "NerveCenter",
                body: eventSubject(event) ?? event.eventType,
                link: subjectLink(event),
                interrupts: false
            )
        }
    }

    /// Classify a §60-listed event into a notification class.
    public static func classify(event: Event) -> MobileNotificationClass {
        switch event.eventType {
        case "incident.detected", "incident.created", "deployment.failed":
            return event.severity == .critical ? .urgent : .actionRequired
        case "task.failed", "goal.blocked", "approval.required":
            return .actionRequired
        case "investigation.completed", "benchmark.completed", "goal.completed":
            return .informational
        default:
            return .informational
        }
    }

    private static func eventSubject(_ event: Event) -> String? {
        if let subject = event.subject, !subject.isEmpty { return subject }
        if let summary = event.payload["summary"]?.value.stringValue { return summary }
        return nil
    }

    private static func subjectLink(_ event: Event) -> String? {
        guard let subject = event.subject else { return nil }
        switch event.eventType {
        case "incident.detected", "incident.created":
            return "nerv://incident/\(subject)"
        case "approval.required":
            return "nerv://approval/\(subject)"
        case "goal.blocked", "goal.completed":
            return "nerv://goal/\(subject)"
        default:
            return nil
        }
    }
}
