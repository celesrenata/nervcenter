"""C4: Policy decision point (NC-SPEC-2026-010 Phase 2, ADR-0003).

Focused tests for :class:`backend.policy.pdp.PolicyDecisionPoint` — a
framework-neutral, auditable PDP over the frozen C1 contracts
(``NCPrincipal`` / ``NCPolicy`` / ``NCApproval`` from
``schemas/nc_platform.py``).

Covered behaviour:

- **default deny**: no policies / no matching policy -> DENY with
  ``policy_id=None`` and a reason;
- **allow**: exact + pattern matches ALLOW, naming the deciding policy,
  priority and version;
- **explicit deny precedence**: DENY wins over any ALLOW, regardless of
  scope or priority;
- **namespace isolation**: principal namespace != resource namespace ->
  DENY even when an ALLOW policy matches;
- **classification context**: context conditions gate ALLOW (e.g.
  ``classification == "HOME_PRIVATE"``);
- **malformed / unsupported condition**: out-of-subset condition on an
  ALLOW policy is skipped (default deny); on a matching DENY policy it
  fails closed to DENY with ``unsupported_expression``;
- **malformed request/context**: fail closed;
- **deterministic ordering**: priority desc, version desc, policy_id asc;
- **agent wildcard rejection**: ``*`` / ``kind:*`` never expand to
  ``kind:agent`` / ``kind:function``; exact id matches still work;
- **approval binding**: immutable payload hash, exact target, exact
  action, expiry, and APPROVED state; a verified binding elevates
  default-deny only; expired/mismatched approvals are rejected;
- **simulation mode**: tagged ``simulated`` decisions, no side effects
  (repeatable, stateless, approvals not consumed).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from backend.policy.pdp import (
    ApprovalBinding,
    Decision,
    PolicyDecisionPoint,
    REASON_ALLOW,
    REASON_APPROVAL_GRANTED,
    REASON_APPROVAL_MALFORMED,
    REASON_APPROVAL_REJECTED,
    REASON_DEFAULT_DENY,
    REASON_EXPLICIT_DENY,
    REASON_MALFORMED_CONTEXT,
    REASON_MALFORMED_REQUEST,
    REASON_NAMESPACE_MISMATCH,
    REASON_UNSUPPORTED_EXPRESSION,
    verify_approval_binding,
)
from schemas.base import content_hash
from schemas.nc_platform import NCApproval, NCPrincipal, NCPolicy

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

#: 26-char Crockford-style body matching nc_platform's ULID id patterns.
_ULID_BODY = "0123456789ABCDEFGHJKMNPTWX"
assert len(_ULID_BODY) == 26

#: A fixed evaluation clock so expiry tests are deterministic.
NOW = datetime(2026, 10, 11, 8, 0, 0, tzinfo=UTC)


def _id(prefix: str, tail: str = _ULID_BODY) -> str:
    return f"{prefix}_{tail}"


def _principal(
    kind: str = "human",
    namespace: str = "personal",
    principal_id: str | None = None,
) -> NCPrincipal:
    return NCPrincipal(
        id=f"row-{kind}",
        principal_id=principal_id or _id("prn"),
        kind=kind,
        display_name=f"{kind}-principal",
        namespace=namespace,
    )


def _policy(
    effect: str,
    principal_match: str,
    action_match: str,
    resource_match: str,
    condition: str | None = None,
    priority: int = 0,
    version: int = 1,
    policy_id: str | None = None,
) -> NCPolicy:
    return NCPolicy(
        id=f"row-{policy_id or 'pol'}",
        policy_id=policy_id or _id("pol"),
        effect=effect,
        principal_match=principal_match,
        action_match=action_match,
        resource_match=resource_match,
        condition=condition,
        priority=priority,
        version=version,
    )


def _approval(
    *,
    payload: Mapping[str, Any] | None,
    target: str = "nc://personal/homeassistant/home/devices/bedroom-lamp",
    action: str = "resource.write:devices.turn_on",
    expires_at: datetime | None = None,
    state: str = "APPROVED",
    proposed_action: Mapping[str, Any] | None = None,
    approval_id: str | None = None,
) -> NCApproval:
    if payload is None:
        raise ValueError("helper requires a payload to hash")
    return NCApproval(
        id="row-app",
        approval_id=approval_id or _id("app"),
        execution_id="exec-test-1",
        proposed_action=dict(proposed_action if proposed_action is not None else {"action": action}),
        target=target,
        payload_hash=content_hash(payload),
        expires_at=expires_at or (NOW + timedelta(hours=1)),
        state=state,
    )


PAYLOAD = {"command": "turn_on", "level": 50}
RESOURCE = "nc://personal/homeassistant/home/devices/bedroom-lamp"
ACTION = "resource.write:devices.turn_on"
HUMAN = _principal("human")
AGENT = _principal("agent", principal_id=_id("prn", _ULID_BODY[::-1]))


def _pdp(*policies: NCPolicy) -> PolicyDecisionPoint:
    return PolicyDecisionPoint(list(policies), clock=lambda: NOW)


def _decide(
    pdp: PolicyDecisionPoint,
    *,
    principal: NCPrincipal = HUMAN,
    action: str = ACTION,
    resource: str = RESOURCE,
    context: Any = None,
    **kwargs: Any,
) -> Decision:
    return pdp.evaluate(principal, action, resource, context, **kwargs)


# ---------------------------------------------------------------------------
# default deny
# ---------------------------------------------------------------------------


class TestDefaultDeny:
    def test_no_policies_default_deny(self):
        decision = _decide(_pdp())
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert decision.policy_id is None
        assert decision.reason  # non-empty, auditable

    def test_no_matching_policy_default_deny(self):
        allow = _policy(
            "ALLOW",
            "kind:human,namespace:personal",
            "resource.read:*",
            RESOURCE,
        )
        decision = _decide(_pdp(allow))  # write action not covered by read allow
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert decision.policy_id is None

    def test_unmatched_resource_default_deny(self):
        allow = _policy("ALLOW", HUMAN.principal_id, ACTION, "nc://personal/gmail/mail/threads/*")
        decision = _decide(_pdp(allow))
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY


# ---------------------------------------------------------------------------
# allow
# ---------------------------------------------------------------------------


class TestAllow:
    def test_exact_match_allow(self):
        allow = _policy("ALLOW", HUMAN.principal_id, ACTION, RESOURCE)
        decision = _decide(_pdp(allow))
        assert decision.effect == "ALLOW"
        assert decision.reason_code == REASON_ALLOW
        assert decision.policy_id == allow.policy_id
        assert allow.policy_id in decision.matched_policy_ids

    def test_allow_names_priority_and_version(self):
        allow = _policy("ALLOW", "kind:human", "resource.write:devices.*", RESOURCE, priority=7, version=3)
        decision = _decide(_pdp(allow))
        assert decision.effect == "ALLOW"
        assert "7" in decision.reason  # priority in the audit reason
        assert "3" in decision.reason  # version in the audit reason
        assert decision.policy_id == allow.policy_id

    def test_resource_prefix_wildcard_allows_subresource(self):
        allow = _policy("ALLOW", "kind:human", "resource.write:*", "nc://personal/homeassistant/home/devices/*")
        decision = _decide(_pdp(allow))
        assert decision.effect == "ALLOW"

    def test_resource_prefix_wildcard_does_not_leak_siblings(self):
        allow = _policy("ALLOW", "kind:human", "resource.write:*", "nc://personal/homeassistant/home/devices/*")
        other = "nc://personal/homeassistant/home/departments/lamp"  # 'devices' != 'departments'
        decision = _decide(_pdp(allow), resource=other)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY


# ---------------------------------------------------------------------------
# explicit deny precedence
# ---------------------------------------------------------------------------


class TestExplicitDenyPrecedence:
    def test_deny_overrides_allow(self):
        allow = _policy("ALLOW", "kind:human", "resource.write:*", "nc://personal/homeassistant/*")
        deny = _policy("DENY", "kind:human", "resource.write:devices.turn_on", RESOURCE)
        decision = _decide(_pdp(allow, deny))
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_EXPLICIT_DENY
        assert decision.policy_id == deny.policy_id

    def test_deny_wins_even_with_lower_priority(self):
        allow = _policy("ALLOW", "kind:human", "resource.write:*", RESOURCE, priority=100)
        deny = _policy("DENY", "kind:human", "resource.write:devices.turn_on", RESOURCE, priority=1)
        decision = _decide(_pdp(allow, deny))
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_EXPLICIT_DENY
        assert decision.policy_id == deny.policy_id

    def test_deny_with_false_condition_does_not_override(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE)
        deny = _policy(
            "DENY",
            "kind:human",
            ACTION,
            RESOURCE,
            condition="classification == \"SECRET\"",
        )
        decision = _decide(_pdp(allow, deny), context={"classification": "HOME_PRIVATE"})
        assert decision.effect == "ALLOW"
        assert decision.policy_id == allow.policy_id
        assert any("condition evaluated false" in note for note in decision.notes)

    def test_deny_with_true_condition_overrides(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE)
        deny = _policy(
            "DENY", "kind:human", ACTION, RESOURCE, condition="classification == \"SECRET\""
        )
        decision = _decide(_pdp(allow, deny), context={"classification": "SECRET"})
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_EXPLICIT_DENY
        assert decision.policy_id == deny.policy_id


# ---------------------------------------------------------------------------
# namespace isolation
# ---------------------------------------------------------------------------


class TestNamespaceIsolation:
    def test_namespace_mismatch_denies_even_with_allow(self):
        allow = _policy("ALLOW", "kind:human", "resource.write:*", "nc://shared/*/mail/threads/*")
        decision = _decide(_pdp(allow), resource="nc://shared/gmail/mail/threads/42")
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_NAMESPACE_MISMATCH
        assert decision.policy_id is None

    def test_agent_cross_namespace_denied(self):
        allow = _policy("ALLOW", "kind:agent", "*", "nc://shared/*")
        agent = _principal("agent")
        decision = _decide(_pdp(allow), principal=agent, resource="nc://shared/gmail/mail/threads/1")
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_NAMESPACE_MISMATCH


# ---------------------------------------------------------------------------
# classification context
# ---------------------------------------------------------------------------


class TestClassificationContext:
    def test_allow_only_for_matching_classification(self):
        allow = _policy(
            "ALLOW",
            "kind:human",
            ACTION,
            RESOURCE,
            condition="classification == \"HOME_PRIVATE\"",
        )
        denied = _decide(_pdp(allow), context={"classification": "FINANCIAL"})
        assert denied.effect == "DENY"
        assert denied.reason_code == REASON_DEFAULT_DENY

        allowed = _decide(_pdp(allow), context={"classification": "HOME_PRIVATE"})
        assert allowed.effect == "ALLOW"
        assert allowed.policy_id == allow.policy_id

    def test_context_membership_condition(self):
        allow = _policy(
            "ALLOW",
            "kind:human",
            ACTION,
            RESOURCE,
            condition="classification in [\"PUBLIC\", \"HOME_PRIVATE\"]",
        )
        assert _decide(_pdp(allow), context={"classification": "PUBLIC"}).effect == "ALLOW"
        assert _decide(_pdp(allow), context={"classification": "BIOMETRIC"}).effect == "DENY"

    def test_compound_context_condition(self):
        allow = _policy(
            "ALLOW",
            "kind:human",
            ACTION,
            RESOURCE,
            condition="classification == \"HOME_PRIVATE\" && scope == \"home\"",
        )
        ok = _decide(_pdp(allow), context={"classification": "HOME_PRIVATE", "scope": "home"})
        assert ok.effect == "ALLOW"
        wrong_scope = _decide(_pdp(allow), context={"classification": "HOME_PRIVATE", "scope": "shared"})
        assert wrong_scope.effect == "DENY"

    def test_undefined_context_key_fail_closed(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE, condition="classification == \"PUBLIC\"")
        decision = _decide(_pdp(allow), context={})
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert any("unresolvable" in note for note in decision.notes)


# ---------------------------------------------------------------------------
# malformed / unsupported condition
# ---------------------------------------------------------------------------


class TestMalformedAndUnsupported:
    def test_unsupported_condition_allow_policy_not_applied(self):
        # '+' is outside the documented Cedar-style subset.
        allow = _policy(
            "ALLOW", "kind:human", ACTION, RESOURCE, condition="classification == \"PUBLIC\" + \"x\""
        )
        decision = _decide(_pdp(allow), context={"classification": "PUBLIC"})
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert any("unsupported condition" in note for note in decision.notes)

    def test_unsupported_condition_on_matching_deny_fails_closed(self):
        # Patterns match; the unreadable condition cannot be treated as false.
        deny = _policy(
            "DENY",
            "kind:human",
            "resource.write:*",
            "nc://personal/homeassistant/*",
            condition="+5 == 5",  # unary plus is outside the documented subset
        )
        decision = _decide(_pdp(deny), context={"level": 1})
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_UNSUPPORTED_EXPRESSION
        assert decision.policy_id is None
        assert any("fail closed" in note for note in decision.notes)

    def test_malformed_context_type_fail_closed(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE)
        decision = _decide(_pdp(allow), context=["not", "a", "mapping"])
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_MALFORMED_CONTEXT

    def test_malformed_policy_pattern_skipped_fail_closed(self):
        bad = _policy("ALLOW", "bogus-clause", ACTION, RESOURCE)
        decision = _decide(_pdp(bad))
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert any("malformed principal_match" in note for note in decision.notes)

    def test_malformed_resource_pattern_skipped(self):
        bad = _policy("ALLOW", "kind:human", ACTION, "personal/homeassistant/home/devices/*")
        decision = _decide(_pdp(bad))
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert any("malformed resource_match" in note for note in decision.notes)

    def test_malformed_request_bad_uri(self):
        decision = _decide(_pdp(), resource="not-a-uri")
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_MALFORMED_REQUEST

    def test_malformed_request_empty_action(self):
        decision = _decide(_pdp(), action="")
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_MALFORMED_REQUEST

    def test_malformed_request_wrong_principal_type(self):
        decision = _pdp().evaluate("i-am-not-a-principal", ACTION, RESOURCE)  # type: ignore[arg-type]
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_MALFORMED_REQUEST

    def test_condition_type_mismatch_fail_closed(self):
        # well-formed subset syntax, but comparing a string to a number
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE, condition="level > 5")
        decision = _decide(_pdp(allow), context={"level": "loud"})
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert any("unresolvable" in note for note in decision.notes)


# ---------------------------------------------------------------------------
# deterministic ordering
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_higher_priority_allow_is_deciding(self):
        low = _policy("ALLOW", "kind:human", "resource.write:*", RESOURCE, priority=1)
        high = _policy("ALLOW", "kind:human", ACTION, RESOURCE, priority=10)
        decision = _decide(_pdp(low, high))
        assert decision.policy_id == high.policy_id

    def test_same_priority_higher_version_wins(self):
        old = _policy("ALLOW", "kind:human", ACTION, RESOURCE, version=1)
        new = _policy("ALLOW", "kind:human", ACTION, RESOURCE, version=2)
        decision = _decide(_pdp(old, new))
        assert decision.policy_id == new.policy_id

    def test_tie_broken_deterministically_by_policy_id(self):
        a = _policy("ALLOW", "kind:human", ACTION, RESOURCE, policy_id=_id("pol", _ULID_BODY[:13] + "A" * 13))
        b = _policy("ALLOW", "kind:human", ACTION, RESOURCE, policy_id=_id("pol", _ULID_BODY[:13] + "B" * 13))
        first = _decide(_pdp(a, b))
        second = _decide(_pdp(b, a))  # order-independence
        assert first.policy_id == second.policy_id == a.policy_id  # 'A'... < 'B'... lexicographic

    def test_denies_ordered_by_priority_too(self):
        deny_low = _policy("DENY", "kind:human", "resource.write:*", RESOURCE, priority=1)
        deny_high = _policy("DENY", "kind:human", ACTION, RESOURCE, priority=9)
        decision = _decide(_pdp(deny_low, deny_high))
        assert decision.reason_code == REASON_EXPLICIT_DENY
        assert decision.policy_id == deny_high.policy_id


# ---------------------------------------------------------------------------
# agent / function wildcard rejection
# ---------------------------------------------------------------------------


class TestAgentWildcardRejection:
    def test_star_principal_never_matches_agent(self):
        allow = _policy("ALLOW", "*", "resource.write:*", "nc://personal/homeassistant/*")
        decision = _decide(_pdp(allow), principal=AGENT)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY

    def test_kind_wildcard_never_matches_agent(self):
        allow = _policy("ALLOW", "kind:*", "resource.write:*", "nc://personal/homeassistant/*")
        decision = _decide(_pdp(allow), principal=AGENT)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY

    def test_function_wildcard_rejected_too(self):
        allow = _policy("ALLOW", "*", "resource.read:*", RESOURCE)
        fn = _principal("function", principal_id=_id("prn", _ULID_BODY[::-1]))
        decision = _decide(_pdp(allow), principal=fn, action="resource.read:devices.state")
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY

    def test_agent_exact_id_still_matches(self):
        allow = _policy("ALLOW", AGENT.principal_id, ACTION, RESOURCE)
        decision = _decide(_pdp(allow), principal=AGENT)
        assert decision.effect == "ALLOW"
        assert decision.policy_id == allow.policy_id

    def test_agent_kind_clause_still_matches(self):
        allow = _policy("ALLOW", "kind:agent,namespace:personal", ACTION, RESOURCE)
        decision = _decide(_pdp(allow), principal=AGENT)
        assert decision.effect == "ALLOW"

    def test_wildcard_still_matches_humans(self):
        allow = _policy("ALLOW", "*", "resource.write:devices.turn_on", RESOURCE)
        decision = _decide(_pdp(allow), principal=HUMAN)
        assert decision.effect == "ALLOW"


# ---------------------------------------------------------------------------
# approval binding
# ---------------------------------------------------------------------------


class TestApprovalBinding:
    def test_verified_approval_elevates_default_deny(self):
        approval = _approval(payload=PAYLOAD)
        decision = _decide(_pdp(), approval=approval, payload=PAYLOAD)
        assert decision.effect == "ALLOW"
        assert decision.reason_code == REASON_APPROVAL_GRANTED
        assert decision.policy_id == approval.approval_id
        assert decision.simulated is False

    def test_approval_hash_mismatch_denied(self):
        approval = _approval(payload=PAYLOAD)
        decision = _decide(_pdp(), approval=approval, payload={"command": "turn_on", "level": 99})
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_REJECTED
        assert any("payload hash mismatch" in note for note in decision.notes)

    def test_approval_target_mismatch_denied(self):
        approval = _approval(payload=PAYLOAD, target="nc://personal/homeassistant/home/devices/kitchen-light")
        decision = _decide(_pdp(), approval=approval, payload=PAYLOAD)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_REJECTED
        assert any("target mismatch" in note for note in decision.notes)

    def test_approval_action_mismatch_denied(self):
        approval = _approval(payload=PAYLOAD, action="resource.write:devices.turn_off")
        decision = _decide(_pdp(), approval=approval, payload=PAYLOAD)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_REJECTED
        assert any("action mismatch" in note for note in decision.notes)

    def test_expired_approval_denied(self):
        approval = _approval(payload=PAYLOAD, expires_at=NOW - timedelta(seconds=1))
        decision = _decide(_pdp(), approval=approval, payload=PAYLOAD)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_REJECTED
        assert any("expired" in note for note in decision.notes)

    def test_approval_at_exact_expiry_denied(self):
        approval = _approval(payload=PAYLOAD, expires_at=NOW)
        decision = _decide(_pdp(), approval=approval, payload=PAYLOAD)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_REJECTED

    def test_non_approved_state_denied(self):
        approval = _approval(payload=PAYLOAD, state="WAITING_FOR_APPROVAL")
        decision = _decide(_pdp(), approval=approval, payload=PAYLOAD)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_REJECTED
        assert any("state" in note for note in decision.notes)

    def test_missing_payload_is_malformed_binding(self):
        approval = _approval(payload=PAYLOAD)
        decision = _decide(_pdp(), approval=approval)  # no payload presented
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_APPROVAL_MALFORMED

    def test_approval_cannot_override_explicit_deny(self):
        deny = _policy("DENY", "kind:human", ACTION, RESOURCE)
        approval = _approval(payload=PAYLOAD)
        decision = _decide(_pdp(deny), approval=approval, payload=PAYLOAD)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_EXPLICIT_DENY
        assert decision.policy_id == deny.policy_id

    def test_verify_helper_unit_check(self):
        approval = _approval(payload=PAYLOAD)
        ok = verify_approval_binding(approval, action={"action": ACTION}, target=RESOURCE, payload=PAYLOAD, now=NOW)
        assert ok.verified is True
        assert isinstance(ok, ApprovalBinding)
        assert ok.approval_id == approval.approval_id

        bad = verify_approval_binding(
            "not-an-approval", action={"action": ACTION}, target=RESOURCE, payload=PAYLOAD, now=NOW  # type: ignore[arg-type]
        )
        assert bad.verified is False
        assert bad.reason_code == REASON_APPROVAL_MALFORMED


# ---------------------------------------------------------------------------
# simulation mode + purity
# ---------------------------------------------------------------------------


class TestSimulationAndPurity:
    def test_simulate_tags_decision(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE)
        decision = _decide(_pdp(allow), simulate=True)
        assert decision.effect == "ALLOW"
        assert decision.simulated is True

    def test_simulate_default_deny_tags(self):
        decision = _decide(_pdp(), simulate=True)
        assert decision.effect == "DENY"
        assert decision.reason_code == REASON_DEFAULT_DENY
        assert decision.simulated is True

    def test_evaluation_is_stateless_and_repeatable(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE)
        pdp = _pdp(allow)
        first = pdp.evaluate(HUMAN, ACTION, RESOURCE)
        second = pdp.evaluate(HUMAN, ACTION, RESOURCE)
        assert first == second
        assert pdp.policies[0].policy_id == allow.policy_id  # policy set untouched

    def test_approval_is_not_consumed_by_evaluation(self):
        approval = _approval(payload=PAYLOAD)
        pdp = _pdp()
        first = pdp.evaluate(HUMAN, ACTION, RESOURCE, approval=approval, payload=PAYLOAD)
        second = pdp.evaluate(HUMAN, ACTION, RESOURCE, approval=approval, payload=PAYLOAD)
        assert first.effect == "ALLOW"
        assert second.effect == "ALLOW"
        assert approval.state == "APPROVED"  # untouched

    def test_policies_callable_adapter(self):
        policies: list[NCPolicy] = []
        pdp = PolicyDecisionPoint(lambda: list(policies), clock=lambda: NOW)
        assert _decide(pdp).effect == "DENY"
        policies.append(_policy("ALLOW", "kind:human", ACTION, RESOURCE))
        assert _decide(pdp).effect == "ALLOW"

    def test_no_secrets_in_decisions(self):
        allow = _policy("ALLOW", "kind:human", ACTION, RESOURCE)
        decision = _decide(_pdp(allow), context={"token_like_field": "tok-secret-123"})
        rendered = repr(decision)
        assert "tok-secret-123" not in rendered
        assert decision.policy_id == allow.policy_id
