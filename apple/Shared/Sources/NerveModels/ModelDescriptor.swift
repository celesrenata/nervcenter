import Foundation

/// Capability a model can perform.
public enum ModelCapability: String, Codable, CaseIterable, Sendable {
    case chat
    case embedding
    case imageGeneration = "image_generation"
    case imageUnderstanding = "image_understanding"
    case transcription
    case speechSynthesis = "speech_synthesis"
    case rerank
    case moderation
}

/// Modality a model consumes or produces.
public enum ModelModality: String, Codable, CaseIterable, Sendable {
    case text
    case image
    case audio
    case video
}

/// Operational status of a model in the registry.
public enum ModelStatus: String, Codable, CaseIterable, Sendable {
    case available
    case degraded
    case disabled
    case unknown
}

/// Registry entry describing a routable inference model.
///
/// Mirrors `schemas.models.ModelDescriptor`.
public struct ModelDescriptor: Codable, Hashable, Sendable {
    public var id: String
    public var createdAt: Date
    public var schemaVersion: String
    public var hash: String?

    /// Provider-unique model identifier (e.g. 'provider/model-name').
    public var modelId: String

    /// Provider that offers this model (e.g. 'local', 'openai', 'anthropic').
    public var provider: String

    /// Model family (e.g. 'haiku', 'sonnet', 'llama'), when known.
    public var family: String?

    /// Model version/revision string.
    public var version: String?

    /// Capabilities this model supports.
    public var capabilities: [ModelCapability]

    /// Input modalities accepted.
    public var inputModalities: [ModelModality]

    /// Output modalities produced.
    public var outputModalities: [ModelModality]

    /// Context window size in tokens, when known.
    public var contextWindow: Int?

    /// Maximum output tokens per call, when known.
    public var maxOutputTokens: Int?

    /// Cost in USD per 1M input tokens, when billed.
    public var costPerMillionInput: Double?

    /// Cost in USD per 1M output tokens, when billed.
    public var costPerMillionOutput: Double?

    /// Current operational status in the registry.
    public var status: ModelStatus

    /// Default generation parameters applied when calling this model.
    public var parameters: [String: AnyCodable]

    public init(
        id: String,
        modelId: String,
        provider: String,
        family: String? = nil,
        version: String? = nil,
        capabilities: [ModelCapability] = [.chat],
        inputModalities: [ModelModality] = [.text],
        outputModalities: [ModelModality] = [.text],
        contextWindow: Int? = nil,
        maxOutputTokens: Int? = nil,
        costPerMillionInput: Double? = nil,
        costPerMillionOutput: Double? = nil,
        status: ModelStatus = .unknown,
        parameters: [String: AnyCodable] = [:],
        createdAt: Date = Date(),
        schemaVersion: String = RecordBase.schemaVersion,
        hash: String? = nil
    ) {
        self.id = id
        self.createdAt = createdAt
        self.schemaVersion = schemaVersion
        self.hash = hash
        self.modelId = modelId
        self.provider = provider
        self.family = family
        self.version = version
        self.capabilities = capabilities
        self.inputModalities = inputModalities
        self.outputModalities = outputModalities
        self.contextWindow = contextWindow
        self.maxOutputTokens = maxOutputTokens
        self.costPerMillionInput = costPerMillionInput
        self.costPerMillionOutput = costPerMillionOutput
        self.status = status
        self.parameters = parameters
    }
}
