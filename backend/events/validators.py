"""Event validation middleware for the NerveCenter event bus.

This module provides the validation pipeline that every consumed event passes
through before it is handed to a handler or persisted. Validation is
intentionally layered so each concern can be tested in isolation:

1. **Structural validation** — the payload parses into a canonical
   :class:`~schemas.events.Event` (schema Section 10).
2. **Integrity validation** — the event's SHA-256 hash matches its content
   (via :meth:`schemas.base.Record.verify_integrity`).
3. **Lineage validation** — ``trace_id`` / ``correlation_id`` /
   ``parent_event_id`` are well-formed UUIDs when present.
4. **Payload contract validation** — a pluggable registry of per
   ``event_type`` validators for type-specific payload rules.

The central entry point is :func:`validate_event`, which returns a
:class:`ValidationResult`. The :class:`EventValidator` class composes all
checks and can be registered as middleware in the subscriber.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import structlog

from schemas.events import Event

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Validation types
# ---------------------------------------------------------------------------

#: A single validation check name, e.g. ``"integrity"``.
CheckName = str

#: A payload validator receives the raw payload dict and returns a list of
#: human-readable error strings (empty list means the payload is valid).
PayloadValidator = Callable[[dict[str, Any]], list[str]]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating a single event.

    Attributes
    ----------
    valid:
        ``True`` when every check passed.
    errors:
        List of human-readable error messages (empty when valid).
    warnings:
        Non-fatal observations (e.g. a missing-but-optional field).
    event:
        The decoded :class:`Event`, or ``None`` when the payload could not
        even be parsed into a structural record.
    checks:
        Mapping of check name to a list of its individual failure messages,
        useful for structured logging.
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    event: Event | None = None
    checks: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Alias for :attr:`valid` (matches ``middleware`` naming)."""
        return self.valid


def _result(
    *,
    valid: bool,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    event: Event | None = None,
    checks: dict[str, list[str]] | None = None,
) -> ValidationResult:
    return ValidationResult(
        valid=valid,
        errors=errors or [],
        warnings=warnings or [],
        event=event,
        checks=checks or {},
    )


# ---------------------------------------------------------------------------
# UUID validation
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_valid_uuid(value: str | None) -> bool:
    """Return ``True`` when ``value`` is a well-formed UUID string."""
    if value is None:
        return True
    return bool(_UUID_RE.match(value))


def _validate_lineage(event: Event) -> tuple[list[str], list[str]]:
    """Validate the tracing lineage fields on ``event``.

    Returns
    -------
    (errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    for name in ("trace_id", "correlation_id", "parent_event_id", "id"):
        if not is_valid_uuid(getattr(event, name)):
            errors.append(f"Field {name!r} is not a valid UUID: {getattr(event, name)!r}")

    # Sequence must be non-negative when present (enforced by pydantic too).
    if event.sequence is not None and event.sequence < 0:
        errors.append(f"sequence must be >= 0, got {event.sequence}")

    # If a stream is set but sequence is not, that is a mild inconsistency.
    if event.stream is not None and event.sequence is None:
        warnings.append("stream set but sequence is None")

    # occurred_at must not be in the far future relative to created_at.
    if event.occurred_at > event.created_at:
        warnings.append("occurred_at is later than created_at")

    return errors, warnings


def _validate_integrity(event: Event) -> tuple[list[str], list[str]]:
    """Validate the event's integrity hash.

    If no hash is stored, that is a warning (not an error), because events
    published without fingerprinting are still usable. If a hash *is*
    stored and does not match, that is a hard integrity failure.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if event.hash is None:
        warnings.append("event has no integrity hash; skipping verification")
        return errors, warnings

    if not event.verify_integrity():
        errors.append(
            "integrity check failed: stored hash "
            f"{event.hash} != computed {event.fingerprint()}"
        )
    return errors, warnings


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def validate_structural(raw: dict[str, Any]) -> ValidationResult:
    """Validate that ``raw`` can be parsed into a canonical :class:`Event`.

    This is the first gate in the pipeline; if it fails the remaining checks
    cannot run.

    Parameters
    ----------
    raw:
        The decoded JSON object from the wire.

    Returns
    -------
    ValidationResult
    """
    try:
        event = Event.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError and friends
        messages = []
        if hasattr(exc, "errors"):
            for err in exc.errors():  # type: ignore[union-attr]
                loc = ".".join(str(p) for p in err.get("loc", ()))
                messages.append(f"{loc or '<root>'}: {err.get('msg', 'invalid')}")
        else:
            messages.append(str(exc))
        return _result(valid=False, errors=[f"structural: {m}" for m in messages])

    return _result(valid=True, event=event)


# ---------------------------------------------------------------------------
# Payload contract registry
# ---------------------------------------------------------------------------


class PayloadValidatorRegistry:
    """Registry of per-``event_type`` payload validators.

    A payload validator is a callable ``(payload: dict) -> list[str]`` where
    the returned list is empty when the payload is acceptable. Validators can
    be registered individually or in bulk.

    Example::

        registry = PayloadValidatorRegistry()
        registry.register("task.completed", lambda p: [] if "duration_ms" in p else ["missing duration_ms"])
    """

    def __init__(self) -> None:
        self._validators: dict[str, PayloadValidator] = {}

    def register(self, event_type: str, validator: PayloadValidator) -> None:
        """Register ``validator`` for ``event_type`` (replaces any existing)."""
        self._validators[event_type] = validator

    def register_many(self, mapping: dict[str, PayloadValidator]) -> None:
        """Register multiple payload validators at once."""
        self._validators.update(mapping)

    def get(self, event_type: str) -> PayloadValidator | None:
        """Return the validator for ``event_type``, or ``None``."""
        return self._validators.get(event_type)

    def has(self, event_type: str) -> bool:
        return event_type in self._validators

    def validate_payload(self, event: Event) -> list[str]:
        """Run the registered validator for ``event.event_type`` (if any).

        Returns a list of error strings; empty means valid.
        """
        validator = self._validators.get(event.event_type)
        if validator is None:
            return []
        try:
            return list(validator(event.payload or {}))
        except Exception as exc:  # noqa: BLE001
            log.warning("events.payload_validator_error", event_type=event.event_type, error=str(exc))
            return [f"payload validator raised: {exc}"]

    def __len__(self) -> int:
        return len(self._validators)


# ---------------------------------------------------------------------------
# Composite validator / middleware
# ---------------------------------------------------------------------------


class EventValidator:
    """Composable validation middleware for consumed events.

    :class:`EventValidator` runs the full pipeline (structural → lineage →
    integrity → payload) and returns a single :class:`ValidationResult`.
    It is designed to be dropped into the subscriber as a middleware hook.

    Parameters
    ----------
    verify_integrity:
        When ``True`` (default) the integrity-hash check is enforced. Set
        ``False`` for trusted internal producers that skip fingerprinting.
    payload_registry:
        Optional :class:`PayloadValidatorRegistry` for per-type payload rules.
    """

    def __init__(
        self,
        *,
        verify_integrity: bool = True,
        payload_registry: PayloadValidatorRegistry | None = None,
    ) -> None:
        self._verify_integrity = verify_integrity
        self._payload_registry = payload_registry or PayloadValidatorRegistry()

    @property
    def payload_registry(self) -> PayloadValidatorRegistry:
        return self._payload_registry

    # -- pipeline -----------------------------------------------------------

    def validate(self, raw: dict[str, Any]) -> ValidationResult:
        """Validate a raw decoded event dict and return the result.

        This is the primary entry point for the validation middleware.
        """
        # 1. Structural
        structural = validate_structural(raw)
        if not structural.valid:
            return _result(
                valid=False,
                errors=structural.errors,
                checks={"structural": structural.errors},
            )

        event = structural.event
        assert event is not None  # guaranteed by validate_structural

        all_errors: list[str] = []
        all_warnings: list[str] = []
        checks: dict[str, list[str]] = {}

        # 2. Lineage
        lineage_errors, lineage_warnings = _validate_lineage(event)
        if lineage_errors:
            checks["lineage"] = lineage_errors
        all_errors.extend(lineage_errors)
        all_warnings.extend(lineage_warnings)

        # 3. Integrity
        if self._verify_integrity:
            integrity_errors, integrity_warnings = _validate_integrity(event)
            if integrity_errors:
                checks["integrity"] = integrity_errors
            all_errors.extend(integrity_errors)
            all_warnings.extend(integrity_warnings)

        # 4. Payload contract
        payload_errors = self._payload_registry.validate_payload(event)
        if payload_errors:
            checks["payload"] = payload_errors
            all_errors.extend(payload_errors)

        valid = not all_errors
        log.debug(
            "events.validated",
            event_type=event.event_type,
            valid=valid,
            errors=len(all_errors),
            warnings=len(all_warnings),
        )
        return _result(
            valid=valid,
            errors=all_errors,
            warnings=all_warnings,
            event=event,
            checks=checks,
        )

    # -- convenience --------------------------------------------------------

    def validate_event(self, event: Event) -> ValidationResult:
        """Validate an already-decoded :class:`Event` (skips structural).

        Useful when a publisher wants to sanity-check an event before sending
        it onto the bus.
        """
        raw = event.model_dump(mode="json")
        return self.validate(raw)

    def __call__(self, raw: dict[str, Any]) -> ValidationResult:
        """Allow the validator to be used as a plain callable middleware."""
        return self.validate(raw)


# ---------------------------------------------------------------------------
# Module-level default validator
# ---------------------------------------------------------------------------

#: A shared default validator, convenient for one-off use and tests.
_default_validator = EventValidator()


def validate_event(raw: dict[str, Any]) -> ValidationResult:
    """Validate a raw decoded event dict using the default validator.

    Thin wrapper around the shared :data:`_default_validator` for call sites
    that do not need custom configuration.
    """
    return _default_validator.validate(raw)


__all__ = [
    "ValidationResult",
    "PayloadValidatorRegistry",
    "EventValidator",
    "validate_structural",
    "validate_event",
    "is_valid_uuid",
]
