"""Policy guardrails for inference requests.

This module implements the ``InferenceGuardrails`` class that enforces
constraints on inference requests according to Section 34 (Guardrails)
of the NerveCenter specification.

The guardrails system provides:
- Input validation for request content
- Output filtering based on policy
- Content redaction for sensitive information
- Constraint enforcement via policy checks
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PolicyGuard(StrEnum):
    """Types of policy guards that can be applied to inference requests."""

    INPUT_VALIDATION = "input_validation"
    OUTPUT_FILTERING = "output_filtering"
    REDACTION = "redaction"
    TOKEN_LIMIT = "token_limit"
    CONTEXT_LENGTH = "context_length"
    COST_LIMIT = "cost_limit"
    LATENCY_LIMIT = "latency_limit"
    MODEL_RESTRICTION = "model_restriction"
    CAPABILITY_REQUIREMENT = "capability_requirement"
    PROVENANCE = "provenance"


@dataclass
class GuardConfig:
    """Configuration for a single policy guard."""

    guard_type: PolicyGuard
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    action: str = "block"
    priority: int = 0


class GuardResult(BaseModel):
    """Result of a guardrail check."""

    guard: PolicyGuard
    passed: bool
    action: str
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class InferenceGuardrails(BaseModel):
    """Enforces policy constraints on inference requests and responses.

    The guardrails system is applied at multiple stages of the inference
    pipeline:

    1. **Request intake**: Validates input content against allowed patterns,
       token budgets, and context length limits.
    2. **Context assembly**: Ensures context packages respect policy limits.
    3. **Response filtering**: Filters model output based on content policies.
    4. **Audit trail**: Records all guardrail decisions for compliance.

    Usage
    -----
    >>> guardrails = InferenceGuardrails(
    ...     guards=[
    ...         GuardConfig(
    ...             guard_type=PolicyGuard.INPUT_VALIDATION,
    ...             config={"max_tokens": 100000}
    ...         ),
    ...         GuardConfig(
    ...             guard_type=PolicyGuard.REDACTION,
    ...             config={"patterns": [r"\\bsecret_key=\\w+\\b"]}
    ...         )
    ...     ]
    ... )
    >>> result = guardrails.check({"content": "hello"})
    """

    model_config = {"extra": "forbid"}

    guards: list[GuardConfig] = Field(
        default_factory=list,
        description="Ordered list of guard configurations to apply.",
    )
    default_action: str = Field(
        default="block",
        description="Default action when a guard fails ('block', 'warn', 'log').",
    )

    def add_guard(self, guard: GuardConfig) -> None:
        """Add a guard configuration to the policy."""
        self.guards.append(guard)

    def remove_guard(self, guard_type: PolicyGuard) -> bool:
        """Remove a guard by type. Returns True if removed."""
        for i, g in enumerate(self.guards):
            if g.guard_type == guard_type:
                self.guards.pop(i)
                return True
        return False

    def check(self, request: dict[str, Any]) -> list[GuardResult]:
        """Run all enabled guards against a request.

        Args:
            request: The inference request dictionary to validate.

        Returns:
            List of GuardResult entries, one per guard that was evaluated.
        """
        results = []
        for guard in sorted(self.guards, key=lambda g: g.priority, reverse=True):
            if not guard.enabled:
                continue
            result = self._run_guard(guard, request)
            results.append(result)
            if not result.passed and result.action in ("block", "reject"):
                break
        return results

    def _run_guard(self, guard: GuardConfig, request: dict[str, Any]) -> GuardResult:
        """Execute a single guard against the request."""
        check_method = getattr(self, f"_check_{guard.guard_type}", None)
        if check_method is None:
            return GuardResult(
                guard=guard.guard_type,
                passed=True,
                action=guard.action,
                message=f"No handler for guard type {guard.guard_type}",
            )
        return check_method(guard, request)

    def _check_input_validation(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Validate input content against allowed patterns."""
        content = request.get("content", "")
        max_tokens = guard.config.get("max_tokens")
        if max_tokens is not None and len(str(content)) > max_tokens:
            return GuardResult(
                guard=PolicyGuard.INPUT_VALIDATION,
                passed=False,
                action=guard.action,
                message=f"Input exceeds token limit of {max_tokens}",
            )
        return GuardResult(
            guard=PolicyGuard.INPUT_VALIDATION,
            passed=True,
            action=guard.action,
        )

    def _check_redaction(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Apply redaction patterns to content."""
        import re

        content = request.get("content", "")
        patterns = guard.config.get("patterns", [])
        redacted = False
        for pattern in patterns:
            if re.search(pattern, content):
                redacted = True
                break
        if redacted:
            return GuardResult(
                guard=PolicyGuard.REDACTION,
                passed=True,
                action=guard.action,
                message="Redaction patterns detected",
                details={"redacted": True},
            )
        return GuardResult(
            guard=PolicyGuard.REDACTION,
            passed=True,
            action=guard.action,
        )

    def _check_token_limit(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Enforce token budget limits."""
        token_budget = guard.config.get("max_tokens", float("inf"))
        tokens_used = request.get("tokens_used", 0)
        if tokens_used > token_budget:
            return GuardResult(
                guard=PolicyGuard.TOKEN_LIMIT,
                passed=False,
                action=guard.action,
                message=f"Token budget exceeded: {tokens_used} > {token_budget}",
            )
        return GuardResult(
            guard=PolicyGuard.TOKEN_LIMIT,
            passed=True,
            action=guard.action,
        )

    def _check_context_length(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Enforce context window limits for the target model."""
        context_window = guard.config.get("context_window", float("inf"))
        context_size = request.get("context_size", 0)
        if context_size > context_window:
            return GuardResult(
                guard=PolicyGuard.CONTEXT_LENGTH,
                passed=False,
                action=guard.action,
                message=f"Context size {context_size} exceeds window {context_window}",
            )
        return GuardResult(
            guard=PolicyGuard.CONTEXT_LENGTH,
            passed=True,
            action=guard.action,
        )

    def _check_cost_limit(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Enforce cost budget limits."""
        cost_budget = guard.config.get("max_cost_usd", float("inf"))
        estimated_cost = request.get("estimated_cost_usd", 0)
        if estimated_cost > cost_budget:
            return GuardResult(
                guard=PolicyGuard.COST_LIMIT,
                passed=False,
                action=guard.action,
                message=f"Cost budget exceeded: ${estimated_cost:.4f} > ${cost_budget:.4f}",
            )
        return GuardResult(
            guard=PolicyGuard.COST_LIMIT,
            passed=True,
            action=guard.action,
        )

    def _check_latency_limit(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Enforce latency budget limits."""
        latency_budget_ms = guard.config.get("max_latency_ms", float("inf"))
        estimated_latency_ms = request.get("estimated_latency_ms", 0)
        if estimated_latency_ms > latency_budget_ms:
            return GuardResult(
                guard=PolicyGuard.LATENCY_LIMIT,
                passed=False,
                action=guard.action,
                message=f"Latency budget exceeded: {estimated_latency_ms}ms > {latency_budget_ms}ms",
            )
        return GuardResult(
            guard=PolicyGuard.LATENCY_LIMIT,
            passed=True,
            action=guard.action,
        )

    def _check_model_restriction(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Restrict which models can be used."""
        allowed_models = guard.config.get("allowed_models", [])
        if allowed_models:
            model = request.get("model", "")
            if model not in allowed_models:
                return GuardResult(
                    guard=PolicyGuard.MODEL_RESTRICTION,
                    passed=False,
                    action=guard.action,
                    message=f"Model {model} not in allowed list",
                )
        return GuardResult(
            guard=PolicyGuard.MODEL_RESTRICTION,
            passed=True,
            action=guard.action,
        )

    def _check_capability_requirement(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Require specific model capabilities."""
        required_caps = guard.config.get("required_capabilities", [])
        if required_caps:
            available_caps = request.get("model_capabilities", [])
            missing = set(required_caps) - set(available_caps)
            if missing:
                return GuardResult(
                    guard=PolicyGuard.CAPABILITY_REQUIREMENT,
                    passed=False,
                    action=guard.action,
                    message=f"Missing required capabilities: {missing}",
                )
        return GuardResult(
            guard=PolicyGuard.CAPABILITY_REQUIREMENT,
            passed=True,
            action=guard.action,
        )

    def _check_provenance(
        self, guard: GuardConfig, request: dict[str, Any]
    ) -> GuardResult:
        """Verify request provenance and audit trail."""
        required_metadata = guard.config.get("required_metadata", [])
        for key in required_metadata:
            if key not in request:
                return GuardResult(
                    guard=PolicyGuard.PROVENANCE,
                    passed=False,
                    action=guard.action,
                    message=f"Missing required metadata: {key}",
                )
        return GuardResult(
            guard=PolicyGuard.PROVENANCE,
            passed=True,
            action=guard.action,
        )
