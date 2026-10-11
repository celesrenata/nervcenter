"""C3: safe declarative event rule evaluation (backend/events/rules.py).

Coverage
--------
- safe field-path matching (equals / exists / prefix) on both the frozen
  :class:`~schemas.nc_platform.NCEventEnvelope` and legacy
  :class:`~schemas.events.Event` contracts;
- unsupported operators and unsafe paths are rejected at definition time;
- duplicate suppression (idempotency-key and configured-field dedup);
- cooldown windows;
- per-hour run caps (sliding window);
- recursion / cycle detection via correlation + causation chain;
- dry-run returns proposals without executing or consuming budgets;
- policy-check denial excludes actions;
- rules never execute side effects without an opt-in runner.
"""

from __future__ import annotations

from itertools import count

import pytest
from pydantic import ValidationError

from backend.events.rules import (
    REASON_COOLDOWN,
    REASON_CYCLE,
    REASON_DUPLICATE,
    REASON_MATCHED,
    REASON_NO_MATCH,
    REASON_RATE_LIMITED,
    ActionProposal,
    ActionSpec,
    EventRule,
    FieldMatch,
    PolicyVerdict,
    RuleDefinitionError,
    RuleEngine,
    extract_field,
    match_field,
    normalize_event,
)
from schemas.events import Event
from schemas.nc_platform import NCEventEnvelope, NcEventExtension

_ULID = "01ARZ3NDEKTSV4RRFFQ6JDG1JQ"  # 26-char Crockford body
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_EID_COUNTER = count(0)


def _unique_evt_id() -> str:
    """A valid ``evt_`` + ULID body id, unique per call."""
    seed = next(_EID_COUNTER)
    body = _ULID[:-2] + _CROCKFORD[seed % 32] + _CROCKFORD[(seed * 7) % 32]
    return "evt_" + body


def make_envelope(
    event_id: str | None = None,
    *,
    event_type: str = "nc.device.state.changed",
    source: str = "nc://personal/homeassistant/home/devices/bedroom-lamp",
    namespace: str = "personal",
    correlation_id: str | None = "corr-1",
    dedup_key: str | None = None,
    idempotency_key: str | None = None,
    data: dict | None = None,
) -> NCEventEnvelope:
    return NCEventEnvelope(
        id=event_id or _unique_evt_id(),
        source=source,
        type=event_type,
        subject="res_" + _ULID,
        data=data if data is not None else {"state": "on", "region": "us-east-1"},
        nc=NcEventExtension(
            namespace=namespace,
            classification="PUBLIC",
            correlation_id=correlation_id,
            dedup_key=dedup_key,
        ),
        idempotency_key=idempotency_key,
    )


def make_legacy_event(
    event_id: str | None = None,
    *,
    event_type: str = "task.completed",
    source: str = "orion.tasks",
    stream: str = "personal",
    correlation_id: str | None = None,
    parent_event_id: str | None = None,
    idempotency_key: str | None = None,
    payload: dict | None = None,
) -> Event:
    return Event(
        id=event_id or _unique_evt_id(),
        event_type=event_type,
        category="task",
        source=source,
        stream=stream,
        payload=payload if payload is not None else {"state": "done", "n": 1},
        correlation_id=correlation_id,
        parent_event_id=parent_event_id,
        idempotency_key=idempotency_key,
    )


def make_rule(
    rule_id: str = "r1",
    *,
    event_types: tuple[str, ...] = (),
    sources: tuple[str, ...] = (),
    namespaces: tuple[str, ...] = (),
    field_checks: tuple[FieldMatch, ...] = (),
    dedup_paths: tuple[str, ...] = (),
    dedup_ttl_seconds: float | None = None,
    cooldown_seconds: float | None = None,
    max_runs_per_hour: int | None = None,
    actions: tuple[ActionSpec, ...] = (ActionSpec(name="noop"),),
) -> EventRule:
    return EventRule(
        rule_id=rule_id,
        event_types=event_types,
        sources=sources,
        namespaces=namespaces,
        field_checks=field_checks,
        dedup_paths=dedup_paths,
        dedup_ttl_seconds=dedup_ttl_seconds,
        cooldown_seconds=cooldown_seconds,
        max_runs_per_hour=max_runs_per_hour,
        actions=actions,
    )


def _exists_check(path: str) -> FieldMatch:
    return FieldMatch(operator="exists", path=path)


# ---------------------------------------------------------------------------
# Safe matching
# ---------------------------------------------------------------------------


class TestSafeMatching:
    def test_equals_and_prefix_on_frozen_envelope(self) -> None:
        engine = RuleEngine()
        engine.add_rule(
            make_rule(
                field_checks=(
                    FieldMatch(operator="equals", path="payload.state", value="on"),
                    FieldMatch(operator="prefix", path="payload.region", value="us-"),
                )
            )
        )
        result = engine.evaluate(make_envelope())
        assert result.matched
        assert result.reason == REASON_MATCHED
        assert result.proposals[0].action_name == "noop"

    def test_legacy_event_payload_matches(self) -> None:
        engine = RuleEngine()
        engine.add_rule(
            make_rule(
                event_types=("task.*",),
                field_checks=(FieldMatch(operator="equals", path="payload.state", value="done"),)
            )
        )
        result = engine.evaluate(make_legacy_event())
        assert result.matched

    def test_exists_true_and_false(self) -> None:
        view = {"payload": {"a": 1}}
        assert match_field(view, _exists_check("payload.a"))
        assert not match_field(view, _exists_check("payload.b"))
        # exists must reject an explicit value at definition time
        with pytest.raises(ValidationError):
            FieldMatch(operator="exists", path="payload.a", value=1)

    def test_missing_path_never_matches(self) -> None:
        missing = FieldMatch(operator="equals", path="payload.missing", value="x")
        assert not match_field({"payload": {}}, missing)
        oob = FieldMatch(operator="equals", path="payload.items.5", value="x")
        assert not match_field({"payload": {"items": [1, 2]}}, oob)
        hit = FieldMatch(operator="equals", path="payload.items.1", value=2)
        assert match_field({"payload": {"items": [1, 2]}}, hit)

    def test_type_filters_and_prefix_allowlists(self) -> None:
        engine = RuleEngine()
        engine.add_rule(
            make_rule(
                event_types=("nc.device.*",),
                sources=("nc://personal/*",),
                namespaces=("personal",),
            )
        )
        assert engine.evaluate(make_envelope()).matched
        assert engine.evaluate(make_envelope(event_type="nc.other.x")).reason == REASON_NO_MATCH
        assert engine.evaluate(make_envelope(namespace="shared")).reason == REASON_NO_MATCH

    def test_unsupported_operator_rejected_at_definition(self) -> None:
        for bad in ("regex", "contains", "eval", "eq", ">", "python"):
            with pytest.raises(ValidationError):
                FieldMatch(operator=bad, path="payload.state", value="on")  # type: ignore[arg-type]

    def test_unsafe_paths_rejected_at_definition(self) -> None:
        for bad in ("payload.__class__", "payload.items[0]", "payload..x", ".lead", "trail.", ""):
            with pytest.raises((ValidationError, RuleDefinitionError)):
                make_rule(field_checks=(_exists_check(bad),))
        # over-long paths
        with pytest.raises((ValidationError, RuleDefinitionError)):
            make_rule(field_checks=(_exists_check("a." * 200 + "b"),))

    def test_prefix_requires_strings(self) -> None:
        prefix = FieldMatch(operator="prefix", path="payload.n", value="us-")
        assert not match_field({"payload": {"n": 42}}, prefix)
        with pytest.raises(ValidationError):
            FieldMatch(operator="prefix", path="payload.x", value=42)  # type: ignore[arg-type]

    def test_extract_field_never_escapes_data(self) -> None:
        class Obj:  # non-container values are opaque
            @property
            def evil(self) -> str:
                return "escaped"

        import backend.events.rules as rules_mod

        data = {"payload": {"obj": Obj()}}
        # attribute chains do not resolve through opaque values
        assert extract_field(data, "payload.obj.evil") is rules_mod._MISSING
        # plain dict lookups and list indexes work
        assert extract_field({"payload": {"x": "y"}}, "payload.x") == "y"
        assert extract_field({"payload": {"items": [10, 20]}}, "payload.items.1") == 20

    def test_normalize_event_rejects_unknown_types(self) -> None:
        with pytest.raises(TypeError):
            normalize_event(object())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------------


class TestDuplicateSuppression:
    def test_same_idempotency_key_suppressed(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        first = engine.evaluate(make_envelope(idempotency_key="k-1"))
        assert first.matched
        second = engine.evaluate(make_envelope(idempotency_key="k-1"))
        assert not second.matched
        assert second.reason == REASON_DUPLICATE
        # distinct key still fires
        assert engine.evaluate(make_envelope(idempotency_key="k-2")).matched

    def test_configured_field_dedup_paths(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule(dedup_paths=("payload.state",)))
        a = make_envelope(idempotency_key="a", data={"state": "on", "region": "us-east-1"})
        b = make_envelope(idempotency_key="b", data={"state": "on", "region": "eu-west-1"})
        assert engine.evaluate(a).matched
        # same state, different idempotency key
        assert engine.evaluate(b).reason == REASON_DUPLICATE
        c = make_envelope(idempotency_key="c", data={"state": "off"})
        assert engine.evaluate(c).matched

    def test_dedup_ttl_expiry_allows_refire(self) -> None:
        now = [1000.0]
        engine = RuleEngine(clock=lambda: now[0])
        engine.add_rule(make_rule(dedup_paths=("payload.state",), dedup_ttl_seconds=60.0))
        assert engine.evaluate(make_envelope(idempotency_key="a")).matched
        assert engine.evaluate(make_envelope(idempotency_key="b")).reason == REASON_DUPLICATE
        now[0] += 61.0
        assert engine.evaluate(make_envelope(idempotency_key="b")).matched

    def test_dedup_table_is_bounded(self) -> None:
        engine = RuleEngine(dedup_max_entries=10)
        engine.add_rule(make_rule())
        for i in range(50):
            engine.evaluate(make_envelope(idempotency_key=f"k-{i}"))
        assert len(engine._dedup) <= 10


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


class TestCooldown:
    def test_cooldown_blocks_within_window(self) -> None:
        # Rule-wide cooldown (no dedup_paths -> cooldown key is the rule id).
        now = [1000.0]
        engine = RuleEngine(clock=lambda: now[0])
        engine.add_rule(make_rule(cooldown_seconds=30.0))
        assert engine.evaluate(make_envelope(idempotency_key="a")).matched
        now[0] += 10.0
        assert engine.evaluate(make_envelope(idempotency_key="b")).reason == REASON_COOLDOWN
        now[0] += 25.0
        assert engine.evaluate(make_envelope(idempotency_key="c")).matched

    def test_rule_wide_cooldown_without_dedup_paths(self) -> None:
        now = [1000.0]
        engine = RuleEngine(clock=lambda: now[0])
        engine.add_rule(make_rule(cooldown_seconds=100.0))
        assert engine.evaluate(make_envelope(idempotency_key="a")).matched
        now[0] += 5.0
        assert engine.evaluate(make_envelope(idempotency_key="b")).reason == REASON_COOLDOWN


# ---------------------------------------------------------------------------
# Rate limiting (max runs per hour)
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_hourly_cap_blocks_after_budget_spent(self) -> None:
        now = [1000.0]
        engine = RuleEngine(clock=lambda: now[0])
        engine.add_rule(make_rule(max_runs_per_hour=3))
        for i in range(3):
            now[0] += 1.0
            assert engine.evaluate(make_envelope(idempotency_key=f"a{i}")).matched
        assert engine.evaluate(make_envelope(idempotency_key="x")).reason == REASON_RATE_LIMITED
        # window slides: after 3600s the budget refills
        now[0] += 3700.0
        assert engine.evaluate(make_envelope(idempotency_key="y")).matched


# ---------------------------------------------------------------------------
# Cycle / recursion detection
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_replayed_event_in_same_chain_is_a_cycle(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        first = engine.evaluate(make_envelope(event_id="evt_" + _ULID, correlation_id="corr-9"))
        assert first.matched
        # same event id reappears in the same correlation chain -> cycle
        replayed = make_envelope(
            event_id="evt_" + _ULID, correlation_id="corr-9", idempotency_key="k2"
        )
        assert engine.evaluate(replayed).reason == REASON_CYCLE

    def test_causal_loop_a_b_a_is_a_cycle(self) -> None:
        # A -> B -> A: by the time the second A is evaluated, the chain already
        # contains A's id -> cycle, even though every event id is unique.
        engine = RuleEngine()
        engine.add_rule(make_rule())
        a = make_legacy_event(event_id="evt-a", correlation_id="corr-loop")
        b = make_legacy_event(event_id="evt-b", correlation_id="corr-loop", parent_event_id="evt-a")
        a_again = make_legacy_event(
            event_id="evt-a2", correlation_id="corr-loop", parent_event_id="evt-b"
        )
        assert engine.evaluate(a).matched
        assert engine.evaluate(b).matched
        assert engine.evaluate(a_again).matched  # first time A2 is seen -> fine
        # Replaying an event whose id already sits in the chain -> cycle
        replay = make_legacy_event(
            event_id="evt-a2", correlation_id="corr-loop", parent_event_id="evt-a2"
        )
        assert engine.evaluate(replay).reason == REASON_CYCLE
        assert a_again is not None and b is not None

    def test_linear_chain_not_a_cycle(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        a = make_legacy_event(event_id="evt-a", correlation_id="corr-l")
        b = make_legacy_event(event_id="evt-b", correlation_id="corr-l", parent_event_id="evt-a")
        c = make_legacy_event(event_id="evt-c", correlation_id="corr-l", parent_event_id="evt-b")
        assert engine.evaluate(a).matched
        assert engine.evaluate(b).matched
        assert engine.evaluate(c).matched

    def test_distinct_correlation_ids_do_not_intersect(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        assert engine.evaluate(make_envelope(correlation_id="c1")).matched
        # a different correlation chain with a *different* id is not a cycle
        assert engine.evaluate(make_envelope(correlation_id="c2", idempotency_key="k9")).matched


# ---------------------------------------------------------------------------
# Dry-run and policy check
# ---------------------------------------------------------------------------


class TestDryRunAndPolicy:
    def test_dry_run_returns_proposals_without_executing(self) -> None:
        engine = RuleEngine()
        executed: list[str] = []
        engine.add_rule(make_rule(actions=(ActionSpec(name="reindex"),)))
        engine.set_action_runner(lambda p: executed.append(p.action_name))
        result = engine.evaluate(make_envelope(), dry_run=True)
        assert result.matched
        assert result.dry_run
        assert [p.action_name for p in result.proposals] == ["reindex"]
        assert executed == []  # dry-run never runs the runner
        # and the dry run consumed no dedup budget: real eval still fires
        assert engine.evaluate(make_envelope()).matched
        assert executed == ["reindex"]

    def test_policy_denial_excludes_action(self) -> None:
        engine = RuleEngine()
        actions = (ActionSpec(name="allowed-act"), ActionSpec(name="denied-act"))
        engine.add_rule(make_rule(actions=actions))
        calls: list[ActionProposal] = []

        def check(proposal: ActionProposal) -> PolicyVerdict:
            calls.append(proposal)
            if proposal.action_name == "denied-act":
                return PolicyVerdict(allowed=False, reason="policy: no-op zone")
            return True  # bool coerces

        result = engine.evaluate(make_envelope(), policy_check=check)
        assert result.matched
        assert [p.action_name for p in result.proposals] == ["allowed-act"]
        assert result.denied == (("denied-act", "policy: no-op zone"),)
        assert len(calls) == 2

    def test_policy_denying_everything_reports_denied(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        result = engine.evaluate(make_envelope(), policy_check=lambda p: False)
        assert not result.matched
        assert result.reason == "policy_denied_all"
        assert result.proposals == ()

    def test_dry_run_skips_policy_check(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        seen: list[bool] = []
        result = engine.evaluate(
            make_envelope(), dry_run=True, policy_check=lambda p: seen.append(False)
        )
        assert result.matched
        assert seen == []  # policy callback is not invoked in dry-run

    def test_broken_policy_check_denies_without_crashing(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())

        def boom(p: ActionProposal) -> PolicyVerdict:
            raise RuntimeError("nope")

        result = engine.evaluate(make_envelope(), policy_check=boom)
        assert not result.matched
        assert "policy check raised" in result.denied[0][1]

    def test_runner_is_never_called_without_opt_in(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule())
        result = engine.evaluate(make_envelope())
        assert result.matched
        assert result.executed == ()

    def test_runner_exceptions_are_reported_not_raised(self) -> None:
        engine = RuleEngine()
        engine.add_rule(make_rule(actions=(ActionSpec(name="act"),)))

        def runner(p: ActionProposal) -> None:
            raise RuntimeError("runner exploded")

        engine.set_action_runner(runner)
        result = engine.evaluate(make_envelope())
        assert result.matched
        assert result.denied == (("act", "runner raised: runner exploded"),)

    def test_add_rule_rejects_non_rules(self) -> None:
        engine = RuleEngine()
        with pytest.raises(RuleDefinitionError):
            engine.add_rule("not a rule")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Normalization compatibility
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_envelope_normalization(self) -> None:
        env = make_envelope(event_id="evt_" + _ULID, dedup_key="dk-1", idempotency_key="ik-1")
        norm = normalize_event(env)
        assert norm.event_id == "evt_" + _ULID
        assert norm.namespace == "personal"
        assert norm.correlation_id == "corr-1"
        assert norm.dedup_key == "dk-1"
        assert norm.data == env.data

    def test_legacy_normalization(self) -> None:
        legacy = make_legacy_event()
        norm = normalize_event(legacy)
        assert norm.event_type == "task.completed"
        assert norm.namespace == "personal"
        assert norm.data == legacy.payload
