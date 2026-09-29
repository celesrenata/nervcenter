import Foundation

/// Kind of accelerator/device the node offers.
public enum DeviceType: String, Codable, CaseIterable, Sendable {
    case cpu
    case gpu
    case appleNe = "apple_ne"
    case metal
    case tpu
    case hybrid
    case other
}

/// Where the node runs relative to the user.
public enum NodeLocation: String, Codable, CaseIterable, Sendable {
    case onDevice = "on_device"
    case local
    case edge
    case cloud
}

/// Operational state of a compute node.
public enum NodeStatus: String, Codable, CaseIterable, Sendable {
    case online
    case offline
    case degraded
    case draining
}

/// A device or host that can serve inference workloads.
///
/// Mirrors `schemas.compute.ComputeNode`.
public struct ComputeNode: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Host label for the node (machine name or alias).
    public var host: String

    /// Primary accelerator class of this node.
    public var deviceType: DeviceType

    /// Where the node runs relative to the user.
    public var location: NodeLocation

    /// Current operational state.
    public var status: NodeStatus

    /// Model/identifier of the hardware (e.g. 'M3 Max', 'RTX 4090').
    public var hardware: String?

    /// Total usable memory in bytes, when known.
    public var memoryBytes: Int?

    /// Numeric capacity counters (concurrency, slots) by key.
    public var capacity: [String: Int]

    /// Ids of ``ModelDescriptor`` records this node can serve.
    public var supportedModels: [String]

    /// Last heartbeat from the node (UTC).
    public var lastHeartbeatAt: Date?

    /// Node-specific metadata.
    public var metadata: [String: AnyCodable]

    public init(
        id: String,
        host: String,
        deviceType: DeviceType,
        location: NodeLocation = .local,
        status: NodeStatus = .offline,
        hardware: String? = nil,
        memoryBytes: Int? = nil,
        capacity: [String: Int] = [:],
        supportedModels: [String] = [],
        lastHeartbeatAt: Date? = nil,
        metadata: [String: AnyCodable] = [:],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.host = host
        self.deviceType = deviceType
        self.location = location
        self.status = status
        self.hardware = hardware
        self.memoryBytes = memoryBytes
        self.capacity = capacity
        self.supportedModels = supportedModels
        self.lastHeartbeatAt = lastHeartbeatAt
        self.metadata = metadata
    }
}
