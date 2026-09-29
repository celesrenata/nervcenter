"""Inference policy engine for model selection.

This module implements the ``InferencePolicyEngine`` class that makes
routing decisions based on task requirements, model capabilities,
and historical performance metrics according to Section 27 (Inference
Policy Engine) of the NerveCenter specification.

The policy engine:
- Matches tasks to models based on required capabilities
- Selects models based on latency/cost constraints
- Uses historical telemetry for smart routing
- Supports fallback chains and retry policies
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from schemas.routes import (
    CircuitState,
    InferenceRoute,
    OmniRouteTelemetry,
    RouteHop,
)


class TaskRequirements(BaseModel):
    """Description of inference task requirements."""

    model_config = {"extra": "forbid"}

    capabilities: list[str] = Field(
        default_factory=list,
        description="Required model capabilities (e.g., 'chat', 'embedding').",
    )
    input_modalities: list[str] = Field(
        default_factory=list,
        description="Required input modalities.",
    )
    output_modalities: list[str] = Field(
        default_factory=list,
        description="Required output modalities.",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Maximum token budget for the request.",
    )
    context_window: int | None = Field(
        default=None,
        ge=1,
        description="Required minimum context window.",
    )
    latency_budget_ms: float | None = Field(
        default=None,
        ge=1.0,
        description="Maximum acceptable latency in milliseconds.",
    )
    cost_budget_usd: float | None = Field(
        default=None,
        ge=0.0,
        description="Maximum acceptable cost in USD.",
    )
    tier: int | None = Field(
        default=None,
        description="Preferred route tier (0=free, 1=local, 2=economical, 3=moderate, 4=high).",
    )


class PolicyRule(BaseModel):
    """A single routing policy rule."""

    model_config = {"extra": "forbid"}

    name: str = Field(..., description="Rule identifier.")
    priority: int = Field(
        default=0,
        description="Rule priority (higher runs first).",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions that must match for rule to apply.",
    )
    action: str = Field(
        default="route",
        description="Action to take ('route', 'reject', 'fallback').",
    )
    target: str | None = Field(
        default=None,
        description="Target model or policy action.",
    )


class InferencePolicyEngine(BaseModel):
    """Makes model routing decisions based on capabilities and metrics.

    The engine evaluates tasks against a policy and selects appropriate
    models from the model registry. It uses historical telemetry to make
    intelligent routing decisions.

    Usage
    -----
    >>> engine = InferencePolicyEngine(
    ...     rules=[
    ...         PolicyRule(
    ...             name="chat-high-quality",
    ...             conditions={"capabilities": ["chat"]},
    ...             target="anthropic/sonnet"
    ...         )
    ...     ]
    ... )
    >>> route = engine.select_route(
    ...     task_id="task-123",
    ...     requirements=TaskRequirements(capabilities=["chat"])
    ... )
    """

    model_config = {"extra": "forbid"}

    rules: list[PolicyRule] = Field(
        default_factory=list,
        description="Ordered routing rules to evaluate.",
    )
    telemetry: dict[tuple[str, str], list[OmniRouteTelemetry]] = Field(
        default_factory=dict,
        description="Historical telemetry per (provider, model).",
    )
    default_tier: int = Field(
        default=1,
        description="Default tier when not specified.",
    )
    default_strategy: str = Field(
        default="auto",
        description="Default routing strategy.",
    )

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a routing rule."""
        self.rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        for i, r in enumerate(self.rules):
            if r.name == name:
                self.rules.pop(i)
                return True
        return False

    def select_route(
        self,
        task_id: str,
        requirements: TaskRequirements,
    ) -> InferenceRoute:
        """Select an inference route for a task.

        Args:
            task_id: The task being routed.
            requirements: The task's inference requirements.

        Returns:
            An InferenceRoute with model selection and fallback chain.
        """
        matched_rules = self._match_rules(requirements)
        if matched_rules:
            target = matched_rules[0].target
            provider, model = self._parse_target(target)
        else:
            provider, model = "local", "default"

        route = InferenceRoute(
            request_key=task_id,
            primary_model=model,
            primary_provider=provider,
            tier=requirements.tier or self.default_tier,
            strategy="auto",
            latency_budget_ms=requirements.latency_budget_ms,
            cost_budget_usd=requirements.cost_budget_usd,
            resolved_at=datetime.now(UTC),
        )

        if route.tier is not None and route.tier >= 0:
            fallbacks = self._build_fallback_chain(
                requirements, route.primary_provider, route.primary_model
            )
            route.hops = fallbacks

        return route

    def _match_rules(self, requirements: TaskRequirements) -> list[PolicyRule]:
        """Find rules that match the requirements."""
        matched = []
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            if self._rule_matches(rule, requirements):
                matched.append(rule)
        return matched

    def _rule_matches(self, rule: PolicyRule, requirements: TaskRequirements) -> bool:
        """Check if a rule matches the given requirements."""
        for key, value in rule.conditions.items():
            req_value = getattr(requirements, key, None)
            if isinstance(req_value, list) and isinstance(value, list):
                if not all(v in req_value for v in value):
                    return False
            elif req_value != value:
                return False
        return True

    def _parse_target(self, target: str | None) -> tuple[str, str]:
        """Parse a model target string into provider and model."""
        if not target or "/" not in target:
            return "local", target or "default"
        provider, model = target.split("/", 1)
        return provider, model

    def _build_fallback_chain(
        self,
        requirements: TaskRequirements,
        primary_provider: str,
        primary_model: str,
    ) -> list[RouteHop]:
        """Build a fallback chain based on requirements."""
        hops = [RouteHop(provider=primary_provider, model=primary_model)]

        if requirements.latency_budget_ms is not None:
            faster_models = self._find_faster_models(requirements)
            for model in faster_models[:2]:
                hops.append(RouteHop(**model))

        return hops

    def _find_faster_models(self, requirements: TaskRequirements) -> list[dict]:
        """Find models with better latency metrics."""
        faster = []
        for key, telemetry_list in self.telemetry.items():
            if not telemetry_list:
                continue
            avg_ttft = sum(t.ttft_ms or 0 for t in telemetry_list) / len(telemetry_list)
            if avg_ttft < (requirements.latency_budget_ms or float("inf")):
                provider, model = key
                faster.append({"provider": provider, "model": model, "weight": 0.5})
        return faster

    def record_telemetry(self, sample: OmniRouteTelemetry) -> None:
        """Record a telemetry sample for routing decisions."""
        key = (sample.provider, sample.model)
        if key not in self.telemetry:
            self.telemetry[key] = []
        self.telemetry[key].append(sample)

    def get_model_health(
        self, provider: str, model: str
    ) -> CircuitState | None:
        """Get the circuit state for a model."""
        key = (provider, model)
        samples = self.telemetry.get(key, [])
        if not samples:
            return None
        latest = samples[-1]
        return latest.circuit_state

    def score_model(
        self,
        provider: str,
        model: str,
        requirements: TaskRequirements,
    ) -> float:
        """Score a model for the given requirements (higher is better)."""
        key = (provider, model)
        samples = self.telemetry.get(key, [])

        score = 100.0

        if requirements.capabilities:
            score -= 20
        if requirements.latency_budget_ms and samples:
            avg_ttft = sum(s.ttft_ms or 0 for s in samples) / len(samples)
            if avg_ttft > requirements.latency_budget_ms:
                score -= 30
        if requirements.cost_budget_usd:
            score -= 10

        if samples:
            success_rate = sum(s.success_rate for s in samples) / len(samples)
            score += success_rate * 50

        return max(0.0, score)
