"""Safe declarative event-rule evaluation for the NerveCenter event fabric.

NC-SPEC-2026-010 Phase 2 / C3 (event rules & fabric hardening). This module is
integration-neutral: it evaluates *declarative* rules against events and
returns matched **action proposals**; it never executes side effects on its
own (an opt-in ``action_runner`` is the only execution hook, and it only
ever runs *after* the policy check has approved a proposal).

Guarantees
----------
- No ``eval`` / ``exec`` / Python-expression evaluation anywhere. Rule
  conditions are a closed, typed set: event-type / source / namespace
  filters plus field-path checks with the operators ``equals``, ``exists``
  and ``prefix`` only. Unknown operators are rejected at rule-definition
  time (pydantic ``Literal``), before any event is evaluated.
- Field paths are dotted identifiers (``payload.state``) with optional
  integer list indexes (``payload.items.0``). Anything else (``__``
  segments, ``[]``, empty segments, over-long paths) is rejected at
  definition time with :class:`RuleDefinitionError`.
- Duplicate suppression on configured field paths (bounded, TTL-aware).
- Per-rule cooldown windows and sliding per-hour run caps (bounded state).
- Recursion / cycle detection using the correlation + causation chain
  (``correlation_id`` / ``parent_event_id`` lineage).
- Dry-run / preview mode: returns the same proposals an execution would,
  without consuming rate/cooldown/dedup budgets and without invoking the
  runner or the policy check.
- A policy-check callback runs for **every** proposed action (non-dry-run
  mode); denied actions are excluded from the result.

The evaluator accepts both the frozen
:class:`~schemas.nc_platform.NCEventEnvelope` contract and the legacy
:class:`~schemas.events.Event` model (see :func:`normalize_event`).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.events import Event
from schemas.nc_platform import NCEventEnvelope

__all__ = [
    "RuleDefinitionError",
    "PolicyVerdict",
    "ActionSpec",
    "FieldMatch",
    "EventRule",
    "ActionProposal",
    "RuleEvaluationResult",
    "NormalizedEvent",
    "RuleEngine",
    "normalize_event",
    "extract_field",
    "match_field",
    "PolicyCheck",
    "ActionRunner",
    "REDACTED_PATH_SEGMENTS",
    "SUPPORTED_OPERATORS",
    "REASON_MATCHED",
    "REASON_NO_MATCH",
    "REASON_DUPLICATE",
    "REASON_COOLDOWN",
    "REASON_RATE_LIMITED",
    "REASON_CYCLE",
    "REASON_POLICY_DENIED",
]

#: Field-path segments that are always forbidden in rule conditions, even
#: though they would be legal dotted identifiers (defense in depth against
#: dunder / wire-internal lookups).
REDACTED_PATH_SEGMENTS = frozenset({"__delivery", "__class__", "model_extra"})

#: Operators a :class:`FieldMatch` may use. Anything else is rejected at
#: definition time (no eval, no regex, no Python expressions).
SUPPORTED_OPERATORS: frozenset[str] = frozenset({"equals", "exists", "prefix"})

#: Result reasons (closed set).
REASON_MATCHED = "matched"
REASON_NO_MATCH = "no_match"
REASON_DUPLICATE = "duplicate"
REASON_COOLDOWN = "cooldown_active"
REASON_RATE_LIMITED = "rate_limited"
REASON_CYCLE = "cycle_detected"
REASON_POLICY_DENIED = "policy_denied_all"

_SEGMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INT_RE = re.compile(r"^\d{1,9}$")
_MAX_PATH_LENGTH = 256
_MAX_LIST_INDEX = 1_000_000


class RuleDefinitionError(ValueError):
    """A rule definition is structurally unsafe or unsupported.

    Raised for unknown operators, unsafe field paths, or contradictory
    configuration. Rule definitions are validated *before* any event is
    evaluated, so a bad rule can never reach the matching hot path.
    """


# ---------------------------------------------------------------------------
# Path extraction (safe, bounded, no attribute access)
# ---------------------------------------------------------------------------

#: Sentinel returned when a path does not resolve.
_MISSING = object()


def _validate_path(path: str) -> None:
    """Reject any path that is not a chain of safe dotted identifiers."""
    if not isinstance(path, str) or not path:
        raise RuleDefinitionError(f"field path must be a non-empty string, got {path!r}")
    if len(path) > _MAX_PATH_LENGTH:
        raise RuleDefinitionError(f"field path exceeds {_MAX_PATH_LENGTH} characters")
    if path.startswith(".") or path.endswith(".") or ".." in path:
        raise RuleDefinitionError(f"field path {path!r} contains a malformed segment")
    for segment in path.split("."):
        if not _SEGMENT_RE.fullmatch(segment) and not _INT_RE.fullmatch(segment):
            raise RuleDefinitionError(
                f"field path segment {segment!r} in {path!r} is not a safe identifier"
            )
        if segment in REDACTED_PATH_SEGMENTS:
            raise RuleDefinitionError(
                f"field path segment {segment!r} in {path!r} is reserved"
            )
        if _INT_RE.fullmatch(segment) and int(segment) > _MAX_LIST_INDEX:
            raise RuleDefinitionError(
                f"list index {segment!r} in {path!r} exceeds the bound"
            )


def extract_field(data: Any, path: str) -> Any:
    """Resolve ``path`` against ``data`` using dict keys and list indexes only.

    Returns the :data:`_MISSING` sentinel when the path does not resolve.
    Attribute access, ``__getitem__`` on arbitrary objects, and nested
    attribute chains are never used, so extraction cannot escape the data
    structure.

    Raises:
        RuleDefinitionError: if the path is structurally unsafe.
    """
    _validate_path(path)
    current: Any = data
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return _MISSING
            current = current[segment]
        elif isinstance(current, (list, tuple)) and _INT_RE.fullmatch(segment):
            index = int(segment)
            if index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def has_field(data: Any, path: str) -> bool:
    """``True`` when ``path`` resolves to a value that is not ``None``."""
    value = extract_field(data, path)
    return value is not _MISSING and value is not None


def match_field(data: Any, check: FieldMatch) -> bool:
    """Evaluate one :class:`FieldMatch` against ``data`` (pure, no mutation)."""
    if check.operator == "exists":
        return has_field(data, check.path)
    value = extract_field(data, check.path)
    if value is _MISSING:
        return False
    if check.operator == "equals":
        return value == check.value
    if check.operator == "prefix":
        if not isinstance(value, str) or not isinstance(check.value, str):
            return False
        return value.startswith(check.value)
    # Unreachable: pydantic Literal rejects anything else at definition time.
    raise RuleDefinitionError(f"operator {check.operator!r} was rejected at definition time")


# ---------------------------------------------------------------------------
# Rule definition (typed, validated, frozen)
# ---------------------------------------------------------------------------


class FieldMatch(BaseModel):
    """One safe field-path check: ``equals`` | ``exists`` | ``prefix``.

    ``value`` is required for ``equals`` / ``prefix`` and must be ``None``
    for ``exists``. Unknown operators raise a pydantic ``ValidationError``
    before the rule can be used.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    operator: Literal["equals", "exists", "prefix"]
    path: str = Field(min_length=1, max_length=_MAX_PATH_LENGTH)
    value: Any = None

    @field_validator("path")
    @classmethod
    def _check_path(cls, value: str) -> str:
        _validate_path(value)
        return value

    @model_validator(mode="after")
    def _check_value(self) -> FieldMatch:
        if self.operator == "exists":
            if self.value is not None:
                raise ValueError("'exists' checks take no value")
        elif self.value is None:
            raise ValueError(f"'{self.operator}' requires a non-None value")
        if self.operator == "prefix" and not isinstance(self.value, str):
            raise ValueError("'prefix' requires a string value")
        return self


class ActionSpec(BaseModel):
    """A declarative, named action with static parameters.

    Actions are *data*, not code: the rule engine only proposes them. The
    integrator decides what (if anything) an action name means.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    params: dict[str, Any] = Field(default_factory=dict)


def _pattern_matches(value: str | None, patterns: tuple[str, ...]) -> bool:
    """Empty allow-list matches everything; entries may end with ``*``."""
    if not patterns:
        return True
    if value is None:
        return False
    for pattern in patterns:
        if pattern.endswith("*"):
            if value.startswith(pattern[:-1]):
                return True
        elif value == pattern:
            return True
    return False


class EventRule(BaseModel):
    """A declarative event rule.

    Filters (all optional; empty = no constraint):

    - ``event_types`` / ``sources`` / ``namespaces`` — allow-lists, entries
      may be exact or end with ``*`` for prefix matching.
    - ``field_checks`` — safe field-path checks (AND semantics).

    Guard rails:

    - ``dedup_paths`` — field paths whose combined value forms the
      duplicate-suppression key (empty = suppress by the event's own
      idempotency/dedup key, then by event id).
    - ``dedup_ttl_seconds`` — how long a dedup key is remembered (``None``
      = until the bounded table evicts it).
    - ``cooldown_seconds`` — minimum interval between fires of this rule.
      Keyed by the dedup key when ``dedup_paths`` is set, else rule-wide.
    - ``max_runs_per_hour`` — sliding-window cap on fires per hour.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1, max_length=128)
    name: str | None = None
    event_types: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    namespaces: tuple[str, ...] = ()
    field_checks: tuple[FieldMatch, ...] = ()
    dedup_paths: tuple[str, ...] = ()
    dedup_ttl_seconds: float | None = Field(default=None, ge=0)
    cooldown_seconds: float | None = Field(default=None, ge=0)
    max_runs_per_hour: int | None = Field(default=None, ge=1)
    actions: tuple[ActionSpec, ...] = Field(min_length=1)

    @field_validator("dedup_paths")
    @classmethod
    def _check_dedup_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            _validate_path(path)
        return value

    @model_validator(mode="after")
    def _check_action_names(self) -> EventRule:
        names = [a.name for a in self.actions]
        if len(set(names)) != len(names):
            raise ValueError("action names must be unique within a rule")
        return self


# ---------------------------------------------------------------------------
# Normalized event view (frozen envelope + legacy Event)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    """A transport-neutral view of either event contract.

    ``data`` is the opaque body the field-path checks read from: the
    envelope's ``data`` reference document for
    :class:`~schemas.nc_platform.NCEventEnvelope`, or the legacy
    :class:`~schemas.events.Event` ``payload``.
    """

    event_id: str
    event_type: str
    source: str
    namespace: str | None
    subject: str | None
    correlation_id: str | None
    parent_event_id: str | None
    dedup_key: str | None
    data: dict[str, Any]


def normalize_event(event: NCEventEnvelope | Event) -> NormalizedEvent:
    """Project a frozen envelope or legacy event onto :class:`NormalizedEvent`.

    Raises:
        TypeError: for anything that is not one of the two known contracts.
    """
    if isinstance(event, NCEventEnvelope):
        return NormalizedEvent(
            event_id=event.id,
            event_type=event.type,
            source=event.source,
            namespace=event.nc.namespace,
            subject=event.subject,
            correlation_id=event.nc.correlation_id,
            parent_event_id=None,
            dedup_key=event.nc.dedup_key or event.idempotency_key,
            data=event.data,
        )
    if isinstance(event, Event):
        return NormalizedEvent(
            event_id=event.id,
            event_type=event.event_type,
            source=event.source,
            namespace=event.stream,
            subject=event.subject,
            correlation_id=event.correlation_id,
            parent_event_id=event.parent_event_id,
            dedup_key=event.idempotency_key,
            data=event.payload,
        )
    raise TypeError(
        f"unsupported event type {type(event).__name__}: expected "
        "NCEventEnvelope or Event"
    )


def _matching_view(norm: NormalizedEvent) -> dict[str, Any]:
    """The flat dict that field-path checks read from.

    Both ``payload`` and ``data`` address the same body so rules written
    against either contract style work unchanged.
    """
    return {
        "id": norm.event_id,
        "event_type": norm.event_type,
        "source": norm.source,
        "namespace": norm.namespace,
        "subject": norm.subject,
        "correlation_id": norm.correlation_id,
        "parent_event_id": norm.parent_event_id,
        "dedup_key": norm.dedup_key,
        "payload": norm.data,
        "data": norm.data,
    }


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PolicyVerdict:
    """Outcome of one policy check for one proposed action."""

    allowed: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """A proposed action produced by a matched rule (never executed here)."""

    rule_id: str
    action_name: str
    params: dict[str, Any]
    event_id: str
    correlation_id: str | None
    dry_run: bool


#: Policy check: called once per proposed action (non-dry-run mode); a bare
#: ``bool`` is coerced to :class:`PolicyVerdict`. Must be side-effect free.
PolicyCheck = Callable[["ActionProposal"], PolicyVerdict | bool]
#: Optional execution hook used only in non-dry-run mode, after the policy
#: check has approved the proposal. ``None`` (the default) means the engine
#: proposes but never executes.
ActionRunner = Callable[["ActionProposal"], Any]


@dataclass(frozen=True, slots=True)
class RuleEvaluationResult:
    """Outcome of evaluating one event against all registered rules.

    ``matched`` is ``True`` when at least one rule matched and produced an
    action proposal. ``reason`` is the most specific outcome code (see the
    ``REASON_*`` constants). ``proposals`` lists the actions that cleared
    every guard *and* the policy check; ``denied`` lists ``(action, reason)``
    pairs the policy callback refused.
    """

    matched: bool
    reason: str
    rule_id: str | None = None
    proposals: tuple[ActionProposal, ...] = ()
    denied: tuple[tuple[str, str], ...] = ()
    executed: tuple[str, ...] = ()
    dry_run: bool = False
    evaluated_rules: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ChainEntry:
    event_id: str
    parent_event_id: str | None


class RuleEngine:
    """Evaluates declarative rules against events, with bounded guard state.

    The engine is single-threaded by design (one consumer task per engine).
    All guard state (dedup, cooldown, rate window, causal chains) is
    bounded and lazily pruned, so a long-lived engine cannot grow without
    limit.

    Parameters
    ----------
    clock:
        Monotonic-ish clock for deterministic tests (default: ``time.time``).
    dedup_max_entries:
        Upper bound on remembered dedup keys (oldest entries evicted).
    rate_window_seconds:
        Sliding window length for the per-hour run cap (default 3600).
    chain_max_entries:
        Upper bound on events remembered per correlation chain.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        dedup_max_entries: int = 10_000,
        rate_window_seconds: float = 3600.0,
        chain_max_entries: int = 1000,
    ) -> None:
        if dedup_max_entries < 1:
            raise RuleDefinitionError("dedup_max_entries must be >= 1")
        if rate_window_seconds <= 0:
            raise RuleDefinitionError("rate_window_seconds must be > 0")
        self._clock = clock or time.time
        self._dedup_max_entries = dedup_max_entries
        self._rate_window_seconds = rate_window_seconds
        self._chain_max_entries = chain_max_entries

        self._rules: dict[str, EventRule] = {}
        self._dedup: dict[str, float] = {}  # key -> first-seen timestamp
        self._last_fired: dict[str, float] = {}  # cooldown key -> last fire
        self._fires: dict[str, deque[float]] = {}  # rule_id -> fire timestamps
        # correlation_id -> ordered event ids in the current causal chain
        self._chains: dict[str, list[_ChainEntry]] = {}
        self._action_runner: ActionRunner | None = None

    # -- rule management ---------------------------------------------------

    def add_rule(self, rule: EventRule) -> None:
        """Register a rule (validated at construction; replaces same id)."""
        if not isinstance(rule, EventRule):
            raise RuleDefinitionError("add_rule() expects an EventRule")
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> None:
        self._rules.pop(rule_id, None)

    @property
    def rules(self) -> tuple[EventRule, ...]:
        return tuple(self._rules.values())

    # -- action runner (opt-in execution hook) ------------------------------

    def set_action_runner(self, runner: ActionRunner | None) -> None:
        """Install (or clear) the opt-in execution hook.

        The default (``None``) engine only *proposes* actions; installing a
        runner is how an integrator opts in to executing approved proposals
        after the policy check has cleared them.
        """
        self._action_runner = runner

    # -- guard state (bounded) ---------------------------------------------

    def _now(self) -> float:
        return float(self._clock())

    def _dedup_ttl_for(self, key: str) -> float | None:
        # Key format: "{rule_id}:{dedup_hash}"; look up the rule's TTL.
        rule_id = key.split(":", 1)[0]
        rule = self._rules.get(rule_id)
        if rule is None:
            return 0.0  # rule gone -> forget the key
        return rule.dedup_ttl_seconds

    def _prune_dedup(self, now: float) -> None:
        expired = [
            key
            for key, first_seen in self._dedup.items()
            if (ttl := self._dedup_ttl_for(key)) is not None
            and (now - first_seen) > ttl
        ]
        for key in expired:
            self._dedup.pop(key, None)

    def _dedup_seen(self, key: str, now: float) -> bool:
        self._prune_dedup(now)
        return key in self._dedup

    def _observe_dedup(self, key: str, now: float) -> None:
        self._prune_dedup(now)
        if key in self._dedup:
            return
        if len(self._dedup) >= self._dedup_max_entries:
            # Evict a quarter of the oldest entries to stay bounded.
            oldest = sorted(self._dedup.items(), key=lambda kv: kv[1])
            for old_key, _ in oldest[: self._dedup_max_entries // 4]:
                self._dedup.pop(old_key, None)
        self._dedup[key] = now

    def _chain_contains(self, correlation_id: str | None, event_id: str) -> bool:
        if correlation_id is None:
            return False
        chain = self._chains.get(correlation_id)
        if not chain:
            return False
        return any(entry.event_id == event_id for entry in chain)

    def _observe_chain(self, norm: NormalizedEvent) -> None:
        """Record the event in its correlation chain (observation only)."""
        if norm.correlation_id is None:
            return
        chain = self._chains.setdefault(norm.correlation_id, [])
        if any(entry.event_id == norm.event_id for entry in chain):
            return  # already recorded (idempotent replay)
        if norm.parent_event_id is None:
            chain.append(_ChainEntry(norm.event_id, None))
        elif any(entry.event_id == norm.parent_event_id for entry in chain):
            chain.append(_ChainEntry(norm.event_id, norm.parent_event_id))
        else:
            # Parent not in the chain: start a fresh chain from the parent.
            del self._chains[norm.correlation_id]
            fresh = self._chains.setdefault(norm.correlation_id, [])
            fresh.append(_ChainEntry(norm.parent_event_id, None))
            fresh.append(_ChainEntry(norm.event_id, norm.parent_event_id))
        if len(chain) > self._chain_max_entries:
            del chain[: len(chain) - self._chain_max_entries]

    def _rate_allows(self, rule: EventRule, now: float) -> bool:
        if rule.max_runs_per_hour is None:
            return True
        window = self._fires.setdefault(rule.rule_id, deque())
        cutoff = now - self._rate_window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        return len(window) < rule.max_runs_per_hour

    def _cooldown_allows(self, rule: EventRule, cooldown_key: str, now: float) -> bool:
        if rule.cooldown_seconds is None:
            return True
        last = self._last_fired.get(cooldown_key)
        if last is None:
            return True
        return (now - last) >= rule.cooldown_seconds

    def _record_fire(self, rule: EventRule, cooldown_key: str, now: float) -> None:
        self._last_fired[cooldown_key] = now
        window = self._fires.setdefault(rule.rule_id, deque())
        window.append(now)
        # Keep the last-fire map bounded: drop entries outside the window.
        if len(self._last_fired) > self._dedup_max_entries:
            cutoff = now - self._rate_window_seconds
            for key in [k for k, v in self._last_fired.items() if v <= cutoff]:
                self._last_fired.pop(key, None)

    # -- evaluation ---------------------------------------------------------

    def evaluate(
        self,
        event: NCEventEnvelope | Event,
        *,
        dry_run: bool = False,
        policy_check: PolicyCheck | None = None,
    ) -> RuleEvaluationResult:
        """Evaluate one event against all registered rules.

        Side effects: none by default. In non-dry-run mode, guard budgets
        (dedup / cooldown / rate window) are consumed for the first matching
        rule and an opt-in ``action_runner`` may run approved proposals.
        Dry-run evaluates everything read-only: no budget is consumed, and
        neither the runner nor the policy check is invoked.

        Parameters
        ----------
        event:
            A frozen :class:`~schemas.nc_platform.NCEventEnvelope` or a
            legacy :class:`~schemas.events.Event`.
        dry_run:
            Preview mode: proposals are returned but nothing executes and
            no guard budget is spent.
        policy_check:
            Optional callback run once per proposed action (skipped in
            dry-run). Returning ``False`` or a denying
            :class:`PolicyVerdict` excludes that action.
        """
        norm = normalize_event(event)
        now = self._now()
        evaluated = 0
        first_rejection: RuleEvaluationResult | None = None

        for rule in self._rules.values():
            evaluated += 1
            if not self._rule_matches(rule, norm):
                continue

            # Cycle / recursion detection on the correlation chain.
            if self._chain_contains(norm.correlation_id, norm.event_id):
                return self._result(
                    rule, matched=False, reason=REASON_CYCLE,
                    dry_run=dry_run, evaluated=evaluated,
                )

            dedup_key = self._dedup_key_for(rule, norm)
            if self._dedup_seen(dedup_key, now):
                if not dry_run:
                    self._observe_dedup(dedup_key, now)
                return self._result(
                    rule, matched=False, reason=REASON_DUPLICATE,
                    dry_run=dry_run, evaluated=evaluated,
                )

            cooldown_key = dedup_key if rule.dedup_paths else rule.rule_id
            if not self._cooldown_allows(rule, cooldown_key, now):
                return self._result(
                    rule, matched=False, reason=REASON_COOLDOWN,
                    dry_run=dry_run, evaluated=evaluated,
                )
            if not self._rate_allows(rule, now):
                return self._result(
                    rule, matched=False, reason=REASON_RATE_LIMITED,
                    dry_run=dry_run, evaluated=evaluated,
                )

            # Build proposals and run the policy check on each.
            proposals: list[ActionProposal] = []
            denied: list[tuple[str, str]] = []
            for action in rule.actions:
                proposal = ActionProposal(
                    rule_id=rule.rule_id,
                    action_name=action.name,
                    params=dict(action.params),
                    event_id=norm.event_id,
                    correlation_id=norm.correlation_id,
                    dry_run=dry_run,
                )
                if policy_check is not None and not dry_run:
                    verdict = self._policy_verdict(policy_check, proposal)
                    if not verdict.allowed:
                        denied.append((action.name, verdict.reason))
                        continue
                proposals.append(proposal)

            executed: list[str] = []
            if not dry_run:
                self._observe_dedup(dedup_key, now)
                self._observe_chain(norm)
                if proposals:
                    self._record_fire(rule, cooldown_key, now)
                    runner = self._action_runner
                    if runner is not None:
                        for proposal in proposals:
                            try:
                                runner(proposal)
                            except Exception as exc:  # noqa: BLE001 - report, don't crash
                                denied.append((proposal.action_name, f"runner raised: {exc}"))
                            else:
                                executed.append(proposal.action_name)

            if not proposals and denied:
                result = self._result(
                    rule,
                    matched=False,
                    reason=REASON_POLICY_DENIED,
                    denied=tuple(denied),
                    dry_run=dry_run,
                    evaluated=evaluated,
                )
                if first_rejection is None:
                    first_rejection = result
                return result
            result = self._result(
                rule,
                matched=True,
                reason=REASON_MATCHED,
                proposals=tuple(proposals),
                denied=tuple(denied),
                executed=tuple(executed),
                dry_run=dry_run,
                evaluated=evaluated,
            )
            if first_rejection is None:
                first_rejection = result
            return result

        if first_rejection is not None:
            return first_rejection
        return RuleEvaluationResult(
            matched=False,
            reason=REASON_NO_MATCH,
            dry_run=dry_run,
            evaluated_rules=evaluated,
        )

    # -- internals -----------------------------------------------------------

    def _rule_matches(self, rule: EventRule, norm: NormalizedEvent) -> bool:
        if not _pattern_matches(norm.event_type, rule.event_types):
            return False
        if not _pattern_matches(norm.source, rule.sources):
            return False
        if not _pattern_matches(norm.namespace, rule.namespaces):
            return False
        view = _matching_view(norm)
        for check in rule.field_checks:
            if not match_field(view, check):
                return False
        return True

    def _dedup_key_for(self, rule: EventRule, norm: NormalizedEvent) -> str:
        if rule.dedup_paths:
            view = _matching_view(norm)
            values = [extract_field(view, path) for path in rule.dedup_paths]
            canonical = json.dumps(
                [v if v is not _MISSING else None for v in values],
                sort_keys=True,
                default=str,
            )
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            return f"{rule.rule_id}:{digest}"
        return f"{rule.rule_id}:{norm.dedup_key or norm.event_id}"

    @staticmethod
    def _policy_verdict(check: PolicyCheck, proposal: ActionProposal) -> PolicyVerdict:
        try:
            outcome = check(proposal)
        except Exception as exc:  # noqa: BLE001 - a broken check denies, never crashes
            return PolicyVerdict(allowed=False, reason=f"policy check raised: {exc}")
        if isinstance(outcome, bool):
            return PolicyVerdict(allowed=outcome, reason="" if outcome else "denied")
        if isinstance(outcome, PolicyVerdict):
            return outcome
        raise RuleDefinitionError(
            f"policy check returned unsupported type {type(outcome).__name__}"
        )

    @staticmethod
    def _result(
        rule: EventRule | None,
        *,
        matched: bool,
        reason: str,
        dry_run: bool,
        evaluated: int,
        proposals: tuple[ActionProposal, ...] = (),
        denied: tuple[tuple[str, str], ...] = (),
        executed: tuple[str, ...] = (),
    ) -> RuleEvaluationResult:
        return RuleEvaluationResult(
            matched=matched,
            reason=reason,
            rule_id=rule.rule_id if rule is not None else None,
            proposals=proposals,
            denied=denied,
            executed=executed,
            dry_run=dry_run,
            evaluated_rules=evaluated,
        )
