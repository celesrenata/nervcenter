import Foundation

/// A JSON-native value, `Sendable` and losslessly round-trippable.
///
/// The v0 contracts contain opaque JSON document fields (event payloads,
/// attribute bags, diffs). `NerveJSONValue` models them exhaustively so the
/// Swift SDK can round-trip them losslessly, hash them deterministically,
/// and send them across concurrency domains.
public enum NerveJSONValue: Codable, Hashable, Sendable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([NerveJSONValue])
    case object([String: NerveJSONValue])

    // MARK: - Convenience inits

    public init(_ value: Bool) { self = .bool(value) }
    public init(_ value: Int) { self = .int(value) }
    public init(_ value: Double) { self = .double(value) }
    public init(_ value: String) { self = .string(value) }
    public init(_ value: [NerveJSONValue]) { self = .array(value) }
    public init(_ value: [String: NerveJSONValue]) { self = .object(value) }

    // MARK: - Projections

    /// The string content, if this value is `.string`.
    public var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    /// The integer content, if this value is `.int`.
    public var intValue: Int? {
        if case .int(let i) = self { return i }
        return nil
    }

    /// The double content (`.double`, or an integral `.int`).
    public var doubleValue: Double? {
        switch self {
        case .double(let d): return d
        case .int(let i): return Double(i)
        default: return nil
        }
    }

    /// The array content, if this value is `.array`.
    public var arrayValue: [NerveJSONValue]? {
        if case .array(let a) = self { return a }
        return nil
    }

    /// The object content, if this value is `.object`.
    public var objectValue: [String: NerveJSONValue]? {
        if case .object(let o) = self { return o }
        return nil
    }
}

/// A type-erased JSON value used by the v0 record contracts.
///
/// Wraps ``NerveJSONValue`` so call sites can write `AnyCodable("hello")`,
/// `AnyCodable(3)`, `AnyCodable(["k": AnyCodable(1)])`, etc.
public struct AnyCodable {
    /// The wrapped JSON-native value.
    public let value: NerveJSONValue

    public init(_ value: NerveJSONValue) { self.value = value }
    public init(wrapping value: NerveJSONValue) { self.value = value }

    public init(_ value: Bool) { self = AnyCodable(NerveJSONValue(value)) }
    public init(_ value: Int) { self = AnyCodable(NerveJSONValue(value)) }
    public init(_ value: Double) { self = AnyCodable(NerveJSONValue(value)) }
    public init(_ value: String) { self = AnyCodable(NerveJSONValue(value)) }
    public init(_ value: [AnyCodable]) { self = AnyCodable(NerveJSONValue(value.map(\.value))) }
    public init(_ value: [String: AnyCodable]) {
        self = AnyCodable(NerveJSONValue(value.mapValues(\.value)))
    }

    /// The string content, if this value is a string.
    public var stringValue: String? { value.stringValue }

    /// The integer content, if this value is an integer.
    public var intValue: Int? { value.intValue }

    /// The double content of the value.
    public var doubleValue: Double? { value.doubleValue }

    /// The array content, if this value is an array.
    public var arrayValue: [AnyCodable]? { value.arrayValue.map { $0.map(AnyCodable.init(wrapping:)) } }

    /// The object content, if this value is an object.
    public var objectValue: [String: AnyCodable]? { value.objectValue?.mapValues(AnyCodable.init(wrapping:)) }
}

extension AnyCodable: Codable {
    public init(from decoder: any Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self.value = .null
        } else if let bool = try? container.decode(Bool.self) {
            self.value = .bool(bool)
        } else if let int = try? container.decode(Int.self) {
            self.value = .int(int)
        } else if let double = try? container.decode(Double.self) {
            self.value = .double(double)
        } else if let string = try? container.decode(String.self) {
            self.value = .string(string)
        } else if let array = try? container.decode([NerveJSONValue].self) {
            self.value = .array(array)
        } else if let object = try? container.decode([String: NerveJSONValue].self) {
            self.value = .object(object)
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "AnyCodable: unsupported JSON value"
            )
        }
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case .null:
            try container.encodeNil()
        case .bool(let b):
            try container.encode(b)
        case .int(let i):
            try container.encode(i)
        case .double(let d):
            try container.encode(d)
        case .string(let s):
            try container.encode(s)
        case .array(let a):
            try container.encode(a)
        case .object(let o):
            try container.encode(o)
        }
    }
}

extension AnyCodable: ExpressibleByStringLiteral, ExpressibleByIntegerLiteral,
    ExpressibleByBooleanLiteral, ExpressibleByArrayLiteral, ExpressibleByDictionaryLiteral
{
    public init(stringLiteral value: String) { self = AnyCodable(NerveJSONValue(value)) }
    public init(integerLiteral value: Int) { self = AnyCodable(NerveJSONValue(value)) }
    public init(booleanLiteral value: Bool) { self = AnyCodable(NerveJSONValue(value)) }
    public init(arrayLiteral elements: AnyCodable...) { self = AnyCodable(elements) }
    public init(dictionaryLiteral elements: (String, AnyCodable)...) {
        self = AnyCodable(Dictionary(uniqueKeysWithValues: elements))
    }
}

extension AnyCodable: Hashable, Sendable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(value)
    }

    public static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        anyCodableEqual(lhs.value, rhs.value)
    }
}

/// Structural equality for type-erased JSON values (used by ``AnyCodable``).
private func anyCodableEqual(_ a: NerveJSONValue, _ b: NerveJSONValue) -> Bool {
    switch (a, b) {
    case (.null, .null): return true
    case (.bool(let x), .bool(let y)): return x == y
    case (.int(let x), .int(let y)): return x == y
    case (.double(let x), .double(let y)): return x == y
    case (.string(let x), .string(let y)): return x == y
    case (.array(let x), .array(let y)):
        return x.count == y.count && zip(x, y).allSatisfy { anyCodableEqual($0, $1) }
    case (.object(let x), .object(let y)):
        guard x.keys.sorted() == y.keys.sorted() else { return false }
        return x.keys.allSatisfy { key in
            guard let a = x[key], let b = y[key] else { return false }
            return anyCodableEqual(a, b)
        }
    default: return false
    }
}
