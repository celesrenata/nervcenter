import Foundation

/// Capability/spending tier of a route; mirrors OmniRoute's tiering.
public enum RouteTier: Int, Codable, CaseIterable, Sendable {
    case free = 0
    case local = 1
    case economical = 2
    case moderate = 3
    case high = 4
}

/// Routing strategy that produced or consumes a route.
public enum RouteStrategy: String, Codable, CaseIterable, Sendable {
    case auto
    case latency
    case cost
    case quality
    case forced
    case policy
}

/// Circuit-breaker posture reported by the router.
public enum CircuitState: String, Codable, CaseIterable, Sendable {
    case open = "open"
    case openHalf = "open_half"
    case closed
}

/// Route lifecycle state.
public enum InferenceRouteStatus: String, Codable, CaseIterable, Sendable {
    case pending
    case routed
    case succeeded
    case failed
    case exhausted
}

/// One hop in a route's ordered fallback chain.
///
/// Mirrors `schemas.routes.RouteHop`.
public struct RouteHop: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Provider for this hop.
    public var provider: String

    /// Model identifier for this hop.
    public var model: String

    /// Id of the ``ComputeNode`` serving this hop, if pinned.
    public var nodeId: String?

    /// Relative weight used when multiple hops are eligible (0..1).
    public var weight: Double

    public init(
        id: String,
        provider: String,
        model: String,
        nodeId: String? = nil,
        weight: Double = 1.0,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.provider = provider
        self.model = model
        self.nodeId = nodeId
        self.weight = weight
    }
}

/// The resolved routing decision for one logical request.
///
/// Mirrors `schemas.routes.InferenceRoute`.
public struct InferenceRoute: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Stable key for the request this route resolves (e.g. a task id or trace id).
    public var requestKey: String

    /// The ``ModelDescriptor.id`` of the first-choice model.
    public var primaryModel: String

    /// Provider offering ``primaryModel``.
    public var primaryProvider: String

    /// Capability/spending tier the route targets.
    public var tier: RouteTier

    /// Routing strategy that produced this route.
    public var strategy: RouteStrategy

    /// Ordered fallback hops.
    public var hops: [RouteHop]

    /// End-to-end latency budget in milliseconds, if constrained.
    public var latencyBudgetMs: Double?

    /// Cost budget in USD, if constrained.
    public var costBudgetUsd: Double?

    /// Id of the ``ComputeNode`` the route intends, if pinned.
    public var nodeId: String?

    /// Route lifecycle state.
    public var status: InferenceRouteStatus

    /// When the route was resolved (UTC).
    public var resolvedAt: Date?

    public init(
        id: String,
        requestKey: String,
        primaryModel: String,
        primaryProvider: String,
        tier: RouteTier = .local,
        strategy: RouteStrategy = .auto,
        hops: [RouteHop] = [],
        latencyBudgetMs: Double? = nil,
        costBudgetUsd: Double? = nil,
        nodeId: String? = nil,
        status: InferenceRouteStatus = .pending,
        resolvedAt: Date? = nil,
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.requestKey = requestKey
        self.primaryModel = primaryModel
        self.primaryProvider = primaryProvider
        self.tier = tier
        self.strategy = strategy
        self.hops = hops
        self.latencyBudgetMs = latencyBudgetMs
        self.costBudgetUsd = costBudgetUsd
        self.nodeId = nodeId
        self.status = status
        self.resolvedAt = resolvedAt
    }
}

/// Per (provider, model) latency/throughput/health telemetry sample.
///
/// Mirrors `schemas.routes.OmniRouteTelemetry`.
public struct OmniRouteTelemetry: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Provider the telemetry sample is for.
    public var provider: String

    /// Model identifier the telemetry sample is for.
    public var model: String

    /// Id of the ``ComputeNode`` the sample comes from, if any.
    public var nodeId: String?

    /// When the telemetry sample was taken (UTC).
    public var sampleAt: Date

    /// Sampled request count in the window.
    public var requests: Int

    /// Fraction of sampled requests that succeeded.
    public var successRate: Double

    /// Mean time-to-first-token in milliseconds.
    public var ttftMs: Double?

    /// Mean tokens per second during generation.
    public var tokensPerSecond: Double?

    /// Mean end-to-end latency in milliseconds.
    public var e2eLatencyMs: Double?

    /// 95th-percentile latency in milliseconds.
    public var p95LatencyMs: Double?

    /// Error count in the sample window.
    public var errors: Int

    /// Circuit-breaker state for this provider/model pair.
    public var circuitState: CircuitState

    /// Router-specific counters (cache hit rate, retries, ...).
    public var extra: [String: NerveJSONValue]

    public init(
        id: String,
        provider: String,
        model: String,
        nodeId: String? = nil,
        sampleAt: Date = Date(),
        requests: Int = 1,
        successRate: Double = 1.0,
        ttftMs: Double? = nil,
        tokensPerSecond: Double? = nil,
        e2eLatencyMs: Double? = nil,
        p95LatencyMs: Double? = nil,
        errors: Int = 0,
        circuitState: CircuitState = .closed,
        extra: [String: NerveJSONValue] = [:],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.provider = provider
        self.model = model
        self.nodeId = nodeId
        self.sampleAt = sampleAt
        self.requests = requests
        self.successRate = successRate
        self.ttftMs = ttftMs
        self.tokensPerSecond = tokensPerSecond
        self.e2eLatencyMs = e2eLatencyMs
        self.p95LatencyMs = p95LatencyMs
        self.errors = errors
        self.circuitState = circuitState
        self.extra = extra
    }
}
