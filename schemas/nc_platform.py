"""Canonical resource platform records (NC-SPEC-2026-010 Phase 1 contracts).

Frozen by the C1 contracts freeze (NC-WS-001, T002/T003). This module is the
normative Pydantic contract pack for the AWS-like platform surface:

- :class:`NcUriValidator` / :func:`validate_nc_uri` — the frozen ``nc://``
  grammar (``nc-grammar v1``; full production in
  ``docs/architecture/uri-grammar.md``). Parsing is a pure function and
  reserved-segment denial is enforced here, not at call sites.
- :class:`NCResource` — the canonical, policy-addressable unit (NC-CAP-001).
- :class:`NCConnectorInstance` — a deployed connector of a known kind
  (NC-CAP-002).
- :class:`NCEventEnvelope` — the CloudEvents-in-spirit event envelope
  (NC-CAP-003): immutable, frozen record.
- :class:`NCPrincipal` — a policy subject (NC-CAP-007).
- :class:`NCPolicy` — a Cedar-style policy document (NC-CAP-007).
- :class:`NCApproval` — an approval scoped to an immutable payload with
  expiry (NC-CAP-015).

Assumptions (frozen here, Phase 1):
    - Identity columns are platform-minted, ULID-style, prefixed ids
      (``res_`` / ``conn_`` / ``evt_`` / ``prn_`` / ``pol_`` / ``app_`` +
      26 Crockford-base32 characters). The base :class:`Record.id` remains
      the record row id (caller-supplied, typically a UUID); the prefixed
      id is the stable business identity (NC-REQ-001).
    - ``data`` on :class:`NCEventEnvelope` is a *reference* to the opaque raw
      payload in encrypted object storage, never the payload itself
      (NC-CAP-003).
    - ``condition`` on :class:`NCPolicy` is a CEL-spirit expression string;
      the evaluation engine is a C4 deliverable (ADR-0003).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .base import Record

#: Grammar version stamped by every consumer of the ``nc://`` production.
NC_GRAMMAR_VERSION = "nc-grammar v1"

# --------------------------------------------------------------------------
# Frozen nc:// grammar (nc-grammar v1) — see docs/architecture/uri-grammar.md
# --------------------------------------------------------------------------

#: RFC 3986 ``unreserved`` characters (used verbatim inside character classes).
_UNRESERVED = r"A-Za-z0-9\-._~"

#: RFC 3986 ``sub-delims`` characters (used verbatim inside character classes).
_SUB_DELIMS = r"!$&'()*+,;="

#: Single unreserved-only segment (namespace / provider / scope / kind).
_SEGMENT_RE = re.compile(rf"^[{_UNRESERVED}]+$")

#: One unit of a resource-id segment: a single legal character
#: (unreserved / sub-delims), or one uppercase percent-escape
#: (deterministic round-trip).
_RID_UNIT_RE = rf"([{_UNRESERVED}{_SUB_DELIMS}]|%[0-9A-F]{{2}})"

#: A resource-id segment: one or more units (unreserved / sub-delims /
#: pct-encoded; uppercase hex only, so the round-trip is deterministic).
_RID_SEGMENT_RE = re.compile(rf"^{_RID_UNIT_RE}+$")

#: Segments reserved by the platform; forbidden as provider / scope / kind
#: values and as any resource-id segment (uri-grammar.md §4).
RESERVED_SEGMENTS = frozenset({"nc", "*", "null", "undefined", "none", "__system"})

#: 26-character Crockford base32 (ULID) body, used by the prefixed id columns.
_ULID_BODY = r"[0-9A-HJKMNP-TV-Z]{26}"

#: ``res_`` + ULID body.
RESOURCE_ID_PATTERN = rf"^res_{_ULID_BODY}$"
#: ``conn_`` + ULID body.
CONNECTOR_INSTANCE_ID_PATTERN = rf"^conn_{_ULID_BODY}$"
#: ``evt_`` + ULID body.
EVENT_ID_PATTERN = rf"^evt_{_ULID_BODY}$"
#: ``prn_`` + ULID body.
PRINCIPAL_ID_PATTERN = rf"^prn_{_ULID_BODY}$"
#: ``pol_`` + ULID body.
POLICY_ID_PATTERN = rf"^pol_{_ULID_BODY}$"
#: ``app_`` + ULID body.
APPROVAL_ID_PATTERN = rf"^app_{_ULID_BODY}$"


class NcUriError(ValueError):
    """A canonical ``nc://`` URI that violates the frozen grammar.

    ``code`` names the exact failure class (uri-grammar.md §8) so callers
    can report *which* rule was broken instead of a generic "invalid URI".
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class NcUriParts:
    """Parsed components of a canonical ``nc://`` URI.

    ``resource_id`` preserves segment boundaries of the provider-native id
    (it may contain ``/``); rebuilding from these parts is lossless.
    """

    namespace: str
    provider: str
    scope: str
    kind: str
    resource_id: str


def escape_rid_segment(raw_segment: str) -> str:
    """Percent-encode one *raw* resource-id segment (uppercase hex, UTF-8).

    Characters in ``unreserved`` / ``sub-delims`` pass through unchanged;
    ``%`` itself is encoded as ``%25``. Use this only when minting a URI
    from a raw (unescaped) provider-native id. Round-trip rule 2 of
    uri-grammar.md §6: ``build()`` never re-encodes an already-escaped
    segment, so a double-encoded sequence such as ``%252F`` round-trips as
    itself.
    """
    out: list[str] = []
    for char in raw_segment:
        if _SEGMENT_RE.match(char) or char in _SUB_DELIMS:
            out.append(char)
        else:
            for byte in char.encode("utf-8"):
                out.append(f"%{byte:02X}")
    return "".join(out)


class NcUriValidator:
    """Parser/builder for the frozen ``nc://`` grammar (``nc-grammar v1``).

    Usage::

        parts = NcUriValidator.validate("nc://personal/homeassistant/home/devices/bedroom-lamp")
        uri = NcUriValidator.build(parts.namespace, parts.provider,
                                   parts.scope, parts.kind, parts.resource_id)

    Raises :class:`NcUriError` with a specific ``code`` on any violation
    (wrong scheme, wrong segment count, empty or reserved segment, malformed
    percent-encoding, invalid characters, query/fragment presence).
    """

    def parse(self, uri: str) -> NcUriParts:
        """Parse ``uri`` into components, enforcing the grammar production.

        Raises:
            NcUriError: with one of the error codes from uri-grammar.md §8.
        """
        if not isinstance(uri, str) or not uri:
            raise NcUriError("empty_uri", "URI must be a non-empty string")
        if uri.startswith("NC://") or uri.startswith("Nc://"):
            raise NcUriError(
                "wrong_scheme", "scheme must be exactly lowercase 'nc' (case-sensitive)"
            )
        if not uri.startswith("nc://"):
            raise NcUriError("wrong_scheme", "URI must start with 'nc://'")
        if "?" in uri or "#" in uri:
            raise NcUriError(
                "query_fragment_forbidden",
                "canonical URIs carry no query string or fragment",
            )
        path = uri[len("nc://"):]
        segments = path.split("/")
        if len(segments) < 5:
            raise NcUriError(
                "missing_segment",
                "expected nc://<namespace>/<provider>/<scope>/<kind>/<resource-id>",
            )
        namespace, provider, scope, kind = segments[:4]
        rid_segments = segments[4:]
        for name, value in (
            ("namespace", namespace),
            ("provider", provider),
            ("scope", scope),
            ("kind", kind),
        ):
            if not value:
                raise NcUriError("empty_segment", f"segment '{name}' is empty")
            if not _SEGMENT_RE.match(value):
                raise NcUriError(
                    "invalid_character",
                    f"segment '{name}'={value!r} uses characters outside unreserved",
                )
        for value in rid_segments:
            if not value:
                raise NcUriError("empty_segment", "resource-id segment is empty")
            if set(value) <= set(".~"):
                raise NcUriError(
                    "dot_segment",
                    f"dot/tilde-only segment {value!r} is rejected (normalization ambiguity)",
                )
            if not _RID_SEGMENT_RE.match(value):
                if "%" in value and re.search(r"%(?![0-9A-F]{2})", value):
                    raise NcUriError(
                        "malformed_encoding",
                        f"segment {value!r} contains a malformed percent-escape "
                        "(uppercase hex required)",
                    )
                raise NcUriError(
                    "invalid_character",
                    f"resource-id segment {value!r} contains forbidden characters",
                )
        parts = NcUriParts(
            namespace=namespace,
            provider=provider,
            scope=scope,
            kind=kind,
            resource_id="/".join(rid_segments),
        )
        return parts

    def validate(self, uri: str) -> NcUriParts:
        """Parse plus the reserved-segment denial list (uri-grammar.md §4)."""
        parts = self.parse(uri)
        for name, value in (
            ("namespace", parts.namespace),
            ("provider", parts.provider),
            ("scope", parts.scope),
            ("kind", parts.kind),
        ):
            if value in RESERVED_SEGMENTS:
                raise NcUriError(
                    "reserved_segment",
                    f"segment '{name}'={value!r} is reserved by the platform",
                )
        for rid_segment in parts.resource_id.split("/"):
            if rid_segment in RESERVED_SEGMENTS:
                raise NcUriError(
                    "reserved_segment",
                    f"resource-id segment {rid_segment!r} is reserved by the platform",
                )
        return parts

    def build(
        self,
        namespace: str,
        provider: str,
        scope: str,
        kind: str,
        resource_id: str,
    ) -> str:
        """Rebuild a canonical URI from already-escaped components.

        ``resource_id`` is taken verbatim (it may contain ``/`` boundaries
        and ``%XX`` escapes); this method validates but does not re-encode,
        so ``build(*parse(uri)) == uri`` holds for every valid URI. Provider
        ids are preserved exactly (no normalization, lowercasing, or alias
        substitution — round-trip rule 1). To mint a URI from a *raw*
        provider-native id, escape each segment with
        :func:`escape_rid_segment` first. Raises :class:`NcUriError` on any
        grammar violation of the components.
        """
        for name, value in (
            ("namespace", namespace),
            ("provider", provider),
            ("scope", scope),
            ("kind", kind),
        ):
            if not value or not _SEGMENT_RE.match(value):
                raise NcUriError(
                    "invalid_character", f"segment '{name}'={value!r} is not a valid segment"
                )
            if value in RESERVED_SEGMENTS:
                raise NcUriError(
                    "reserved_segment", f"segment '{name}'={value!r} is reserved"
                )
        if not resource_id:
            raise NcUriError("empty_segment", "resource-id is empty")
        rid_parts = resource_id.split("/")
        for piece in rid_parts:
            if not piece:
                raise NcUriError("empty_segment", "resource-id segment is empty")
            if set(piece) <= set(".~"):
                raise NcUriError(
                    "dot_segment", f"dot/tilde-only segment {piece!r} is rejected"
                )
            if not _RID_SEGMENT_RE.match(piece):
                raise NcUriError(
                    "invalid_character", f"resource-id segment {piece!r} is not escaped per grammar"
                )
            if piece in RESERVED_SEGMENTS:
                raise NcUriError("reserved_segment", f"resource-id segment {piece!r} is reserved")
        return f"nc://{namespace}/{provider}/{scope}/{kind}/{'/'.join(rid_parts)}"


#: Shared validator instance (pure stateless function object).
NC_URI_VALIDATOR = NcUriValidator()


def validate_nc_uri(uri: str) -> NcUriParts:
    """Validate ``uri`` against the frozen grammar and return its parts.

    Raises:
        NcUriError: with the specific failure code (uri-grammar.md §8).
    """
    return NC_URI_VALIDATOR.validate(uri)


# --------------------------------------------------------------------------
# Enumerations (frozen literals)
# --------------------------------------------------------------------------

#: Sensitivity classes; every resource carries exactly one (spec §3). Drives
#: storage encryption, redaction behavior, and policy context.
DataClassification = Literal[
    "PUBLIC",
    "HOME_PRIVATE",
    "PERSONAL_PRIVATE",
    "FINANCIAL",
    "HEALTH_SENSITIVE",
    "BIOMETRIC",
    "SECRET",
]

#: Registry sync state (NC-REQ-008: outage → stale status, not deletion;
#: a resource that left its provider is ``tombstoned`` — never deleted).
NcSyncStatus = Literal["current", "stale", "failed", "tombstoned"]

#: Connector health / integration-loss status (spec §4 ``health``).
NcConnectorHealth = Literal["healthy", "degraded", "unreachable", "lost"]

#: Policy effect (NC-CAP-007; explicit deny precedence over allow).
NcPolicyEffect = Literal["ALLOW", "DENY"]

#: Principal kinds (NC-CAP-007 / spec §3 ``Principal``).
NcPrincipalKind = Literal[
    "human",
    "agent",
    "workflow",
    "function",
    "connector",
    "device",
    "api_client",
]

#: Approval states (NC-CAP-015 provenance contract uses the uppercase
#: ``WAITING_FOR_APPROVAL`` spelling; terminal states are uppercase to match).
NcApprovalState = Literal[
    "WAITING_FOR_APPROVAL",
    "APPROVED",
    "DENIED",
    "EXPIRED",
    "INVALIDATED",
]

#: Single unreserved segment pattern (namespace / provider / scope / kind).
_NC_SEGMENT_PATTERN = r"^[A-Za-z0-9\-._~]+$"
#: SHA-256 hex digest (64 lowercase hex).
_SHA256_PATTERN = r"^[a-f0-9]{64}$"


# --------------------------------------------------------------------------
# Envelope sub-models
# --------------------------------------------------------------------------


class NcEventExtension(BaseModel):
    """The ``nc`` extension block of an :class:`NCEventEnvelope`.

    CloudEvents extensions must be namespaced; these are the frozen
    NerveCenter extensions (NC-CAP-003 normalization + NC-REQ-005
    provenance + dedup support for at-least-once delivery).
    """

    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(
        ...,
        pattern=_NC_SEGMENT_PATTERN,
        description="Namespace the source resource belongs to (isolation boundary).",
    )
    classification: DataClassification = Field(
        ...,
        description="Sensitivity class of the source resource; drives redaction.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="OTel correlation id grouping a logical unit of work (NC-REQ-006).",
    )
    dedup_key: str | None = Field(
        default=None,
        description="Key consumers use to deduplicate at-least-once deliveries.",
    )
    schema_version: str = Field(
        default="v1",
        description="Envelope contract version this record conforms to.",
    )


class NcEventProvenance(BaseModel):
    """Provenance of an event's raw payload (NC-REQ-005 / NC-CAP-003)."""

    model_config = ConfigDict(extra="forbid")

    connector_instance_id: str = Field(
        ...,
        pattern=CONNECTOR_INSTANCE_ID_PATTERN,
        description="Id of the :class:`NCConnectorInstance` that produced the event.",
    )
    raw_payload_hash: str = Field(
        ...,
        pattern=_SHA256_PATTERN,
        description="SHA-256 of the opaque raw payload in encrypted object storage.",
    )


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


class NCResource(Record):
    """A canonical resource: the policy-addressable unit of the platform.

    One row = one real-world thing = exactly one canonical ``nc://`` URI
    (NC-REQ-001). The ``uri`` must parse under the frozen grammar and its
    ``namespace`` / ``provider`` / ``kind`` / ``resource-id`` segments must
    agree with the dedicated fields (enforced by
    :meth:`_check_uri_consistency`). ``sync_status`` is the tombstone
    mechanism: a resource that leaves its provider is marked
    ``tombstoned`` and the row (plus its aliases) is never deleted.
    """

    resource_id: str = Field(
        ...,
        pattern=RESOURCE_ID_PATTERN,
        description="Stable registry id (res_ + 26-char Crockford-base32 ULID).",
    )
    uri: str = Field(
        ...,
        min_length=10,
        description="Canonical nc:// URI; the stable identity of the resource.",
    )
    namespace: str = Field(
        ...,
        pattern=_NC_SEGMENT_PATTERN,
        description="Isolation boundary (personal | shared | system | <task>).",
    )
    connector_instance_id: str = Field(
        ...,
        pattern=CONNECTOR_INSTANCE_ID_PATTERN,
        description="Id of the :class:`NCConnectorInstance` that registered this resource.",
    )
    provider: str = Field(
        ...,
        pattern=_NC_SEGMENT_PATTERN,
        description="Connector provider id (e.g. 'homeassistant', 'gmail').",
    )
    provider_resource_id: str = Field(
        ...,
        min_length=1,
        description="Provider-native id, path-escaped (may contain '/').",
    )
    kind: str = Field(
        ...,
        pattern=_NC_SEGMENT_PATTERN,
        description="Connector kind id (e.g. 'devices', 'threads', 'dashboards').",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable name; display only, never identity.",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Declared capabilities (declared, not inferred — NC-CAP-002).",
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Structured labels (user labels only for sensitive connectors).",
    )
    data_classification: DataClassification = Field(
        ...,
        description="Sensitivity class; drives encryption/redaction/policy context.",
    )
    observed_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Last observed state, as reported by the connector.",
    )
    observed_at: datetime | None = Field(
        default=None,
        description="When the observed state was last captured (UTC).",
    )
    desired_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Last approved desired state (empty when never set).",
    )
    sync_status: NcSyncStatus = Field(
        default="current",
        description="Registry sync state; 'tombstoned' = gone at provider, row kept.",
    )
    owner_principal_id: str | None = Field(
        default=None,
        description="Owning :class:`NCPrincipal` id, if any.",
    )
    source_evidence: list[str] = Field(
        default_factory=list,
        description="Ids of :class:`Evidence` records backing this resource.",
    )

    @model_validator(mode="after")
    def _check_uri_consistency(self) -> "NCResource":
        parts = validate_nc_uri(self.uri)
        mismatches = []
        if parts.namespace != self.namespace:
            mismatches.append("namespace")
        if parts.provider != self.provider:
            mismatches.append("provider")
        if parts.kind != self.kind:
            mismatches.append("kind")
        if parts.resource_id != self.provider_resource_id:
            mismatches.append("resource-id")
        if mismatches:
            raise ValueError(
                "uri segments do not match dedicated fields: " + ", ".join(mismatches)
            )
        return self


class NCConnectorInstance(Record):
    """A deployed connector of a known kind (NC-CAP-001 / NC-CAP-002).

    ``credentials_ref`` is a reference to vaulted material only — never the
    material itself (NC-CAP-008). ``rate_limit`` is the negotiated quota for
    this instance (§10 rule 3: rate quotas on all connector interactions).
    """

    instance_id: str = Field(
        ...,
        pattern=CONNECTOR_INSTANCE_ID_PATTERN,
        description="Stable instance id (conn_ + ULID body).",
    )
    provider: str = Field(
        ...,
        pattern=_NC_SEGMENT_PATTERN,
        description="Connector provider id (e.g. 'homeassistant', 'gmail').",
    )
    credentials_ref: str = Field(
        ...,
        min_length=1,
        description="Opaque reference to vaulted credentials (never the material).",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Granted provider scopes (identity-isolation units, e.g. 'account-work').",
    )
    rate_limit: dict[str, Any] = Field(
        default_factory=dict,
        description="Rate quota for this instance, e.g. {'requests_per_minute': 120}.",
    )
    read_only: bool = Field(
        default=False,
        description="True when the instance is degraded to read-only/stale (NC-REQ-008).",
    )
    health: NcConnectorHealth = Field(
        default="healthy",
        description="Liveness + integration-loss status.",
    )


class NCEventEnvelope(Record):
    """CloudEvents-in-spirit event envelope (NC-CAP-003).

    Immutable: :class:`ConfigDict(frozen=True)` mirrors
    :class:`~schemas.events.Event`. ``data`` is a *reference* to the opaque
    raw payload in encrypted object storage — the raw payload is never
    inlined on the bus. Delivery is at-least-once; consumers deduplicate on
    ``idempotency_key`` / ``nc.dedup_key``.
    """

    model_config = ConfigDict(frozen=True)

    specversion: str = Field(
        default="1.0",
        description="CloudEvents spec version ('1.0').",
    )
    id: str = Field(
        ...,
        pattern=EVENT_ID_PATTERN,
        description="Event id (evt_ + ULID body); also the replay identity.",
    )
    source: str = Field(
        ...,
        min_length=10,
        description="Canonical nc:// URI of the resource the event is about.",
    )
    type: str = Field(
        ...,
        min_length=1,
        description="Machine-readable event type, e.g. 'nc.device.state.changed'.",
    )
    subject: str | None = Field(
        default=None,
        description="Optional subject id the event is about (resource id or URI).",
    )
    time: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Event-time: when the underlying phenomenon occurred (UTC).",
    )
    datacontenttype: str = Field(
        default="application/json",
        description="MIME type of the ``data`` reference document.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Reference to the opaque raw payload in encrypted object storage "
            "(storage ref + hash); the raw payload is never inlined."
        ),
    )
    nc: NcEventExtension = Field(
        ...,
        description="Namespaced NerveCenter extensions block.",
    )
    observed_at: datetime | None = Field(
        default=None,
        description="Observed-time: when the event was captured by the fabric (UTC).",
    )
    partition_key: str | None = Field(
        default=None,
        description="Bus partition key (per-resource ordering).",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Key used by consumers to deduplicate at-least-once deliveries.",
    )
    provenance: NcEventProvenance | None = Field(
        default=None,
        description="Provenance (connector instance + raw payload hash, NC-REQ-005).",
    )

    @model_validator(mode="after")
    def _check_source_uri(self) -> "NCEventEnvelope":
        validate_nc_uri(self.source)
        return self


class NCPrincipal(Record):
    """A policy subject: user, agent, function, service, or connector.

    ``hashed_token_ref`` is a reference to the hashed scoped service token
    record — never the token itself (NC-CAP-007: hashed scoped service
    tokens, no wildcard issuance).
    """

    principal_id: str = Field(
        ...,
        pattern=PRINCIPAL_ID_PATTERN,
        description="Stable principal id (prn_ + ULID body).",
    )
    kind: NcPrincipalKind = Field(
        ...,
        description="What kind of policy subject this is.",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable name (display only, never identity).",
    )
    namespace: str = Field(
        ...,
        pattern=_NC_SEGMENT_PATTERN,
        description="Namespace this principal is scoped to (isolation boundary).",
    )
    hashed_token_ref: str | None = Field(
        default=None,
        description="Reference to the hashed scoped service token record (never the token).",
    )


class NCPolicy(Record):
    """A Cedar-style policy document (NC-CAP-007, ADR-0003).

    Match columns are pattern strings interpreted by the PDP (e.g. a
    principal match may be a kind+namespace expression, a resource match a
    URI prefix). ``condition`` is a CEL-spirit expression; no arbitrary
    Python. Explicit ``DENY`` precedence over ``ALLOW`` is enforced at the
    PDP, not by ordering here — ``priority`` only orders evaluation of
    otherwise-equivalent policies.
    """

    policy_id: str = Field(
        ...,
        pattern=POLICY_ID_PATTERN,
        description="Stable policy id (pol_ + ULID body).",
    )
    effect: NcPolicyEffect = Field(
        ...,
        description="ALLOW or DENY (default DENY when no policy matches).",
    )
    principal_match: str = Field(
        ...,
        min_length=1,
        description="Principal match expression (kind / id / namespace).",
    )
    action_match: str = Field(
        ...,
        min_length=1,
        description="Action match expression (e.g. 'resource.action:devices.turn_on').",
    )
    resource_match: str = Field(
        ...,
        min_length=1,
        description="Resource match: canonical nc:// URI or URI prefix pattern.",
    )
    condition: str | None = Field(
        default=None,
        description="Optional CEL-spirit condition (safe expression language).",
    )
    priority: int = Field(
        default=0,
        ge=0,
        description="Evaluation order among otherwise-equivalent policies (higher first).",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Policy document version; re-issued on every change.",
    )


class NCApproval(Record):
    """An approval scoped to an immutable payload with expiry (NC-CAP-015).

    Granting one approval never grants a class of actions: the approval is
    bound to ``execution_id`` + the exact ``proposed_action`` + ``target``
    and only while ``payload_hash`` (SHA-256 of the immutable payload at
    request time) still matches and ``expires_at`` has not passed. Every
    state transition writes an ``AuditEntry`` (NC-REQ-006).
    """

    approval_id: str = Field(
        ...,
        pattern=APPROVAL_ID_PATTERN,
        description="Stable approval id (app_ + ULID body).",
    )
    execution_id: str = Field(
        ...,
        min_length=1,
        description="Workflow execution id that requested this approval.",
    )
    proposed_action: dict[str, Any] = Field(
        ...,
        description="Exact action being proposed (action name + arguments).",
    )
    target: str = Field(
        ...,
        min_length=10,
        description="Canonical nc:// URI of the resource the action targets.",
    )
    payload_hash: str = Field(
        ...,
        pattern=_SHA256_PATTERN,
        description="SHA-256 of the immutable payload the approval is scoped to.",
    )
    expires_at: datetime = Field(
        ...,
        description="Approval validity window end; after this the approval is unusable.",
    )
    state: NcApprovalState = Field(
        default="WAITING_FOR_APPROVAL",
        description="Lifecycle state (uppercase per the NC-CAP-015 contract JSON).",
    )

    @model_validator(mode="after")
    def _check_target_uri(self) -> "NCApproval":
        validate_nc_uri(self.target)
        return self
