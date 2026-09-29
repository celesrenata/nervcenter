import Foundation

/// What a connector can do on the NerveCenter side.
public enum ConnectorCapability: String, Codable, CaseIterable, Sendable {
    case push
    case pull
    case subscribe
    case mutate
    case search
    case stream
    case authOnly = "auth_only"
}

/// Delivery mechanism.
public enum ConnectorTransport: String, Codable, CaseIterable, Sendable {
    case http
    case grpc
    case websocket
    case webhook
    case localApi = "local_api"
    case other
}

/// Credential scheme.
public enum ConnectorAuthScheme: String, Codable, CaseIterable, Sendable {
    case none
    case basic
    case bearer
    case oauth2
    case apiKey = "api_key"
    case mtls
    case appSpecific = "app_specific"
}

/// Operational state of a connector.
public enum ConnectorStatus: String, Codable, CaseIterable, Sendable {
    case disconnected
    case connecting
    case connected
    case degraded
    case disabled
}

/// Descriptor/interface contract for an external-system integration.
///
/// Mirrors `schemas.connectors.Connector`.
public struct Connector: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Connector kind identifier (e.g. 'email.imap', 'calendar.ics', 'im.slack').
    public var connectorType: String

    /// Human-readable name for this connector instance.
    public var name: String

    /// Current operational state.
    public var status: ConnectorStatus

    /// Capabilities this connector offers to the core.
    public var capabilities: [ConnectorCapability]

    /// Delivery mechanism.
    public var transport: ConnectorTransport

    /// Credential mechanism in use.
    public var authScheme: ConnectorAuthScheme

    /// Endpoint / URI the connector talks to.
    public var endpoint: String?

    /// Non-secret configuration (secrets live in the credential store).
    public var config: [String: NerveJSONValue]

    /// Reference to the stored credential, if auth is required.
    public var credentialRef: String?

    /// Last successful sync (UTC).
    public var lastSyncedAt: Date?

    /// Most recent error, if the connector is not healthy.
    public var error: String?

    /// Event types this connector can emit on the NerveCenter event bus.
    public var emittedEventTypes: [String]

    public init(
        id: String,
        connectorType: String,
        name: String,
        status: ConnectorStatus = .disconnected,
        capabilities: [ConnectorCapability] = [],
        transport: ConnectorTransport = .http,
        authScheme: ConnectorAuthScheme = .none,
        endpoint: String? = nil,
        config: [String: NerveJSONValue] = [:],
        credentialRef: String? = nil,
        lastSyncedAt: Date? = nil,
        error: String? = nil,
        emittedEventTypes: [String] = [],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.connectorType = connectorType
        self.name = name
        self.status = status
        self.capabilities = capabilities
        self.transport = transport
        self.authScheme = authScheme
        self.endpoint = endpoint
        self.config = config
        self.credentialRef = credentialRef
        self.lastSyncedAt = lastSyncedAt
        self.error = error
        self.emittedEventTypes = emittedEventTypes
    }
}
