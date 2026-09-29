"""OmniRoute adapter for inference request routing.

This module implements the ``OmniRouteAdapter`` that routes inference
requests to appropriate backends based on routing decisions according
to Section 28 (OmniRoute Adapter) of the NerveCenter specification.

The adapter:
- Converts routing decisions into backend calls
- Handles provider-specific authentication
- Manages request/response translation
- Collects telemetry for policy refinement
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from schemas.routes import InferenceRoute, OmniRouteTelemetry


class InferenceRequest(BaseModel):
    """An inference request to be routed."""

    model_config = {"extra": "forbid"}

    route_key: str = Field(..., description="Key identifying the route to use.")
    prompt: str = Field(..., description="Input prompt for the model.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Model generation parameters.",
    )
    timeout_ms: int | None = Field(
        default=None,
        ge=1,
        description="Request timeout in milliseconds.",
    )


class InferenceResponse(BaseModel):
    """Response from an inference call."""

    model_config = {"extra": "forbid"}

    provider: str = Field(..., description="Provider that handled the request.")
    model: str = Field(..., description="Model that generated the response.")
    content: str = Field(..., description="Generated content.")
    input_tokens: int = Field(..., description="Number of input tokens.")
    output_tokens: int = Field(..., description="Number of output tokens.")
    ttft_ms: float | None = Field(
        default=None,
        description="Time to first token in milliseconds.",
    )
    e2e_latency_ms: float | None = Field(
        default=None,
        description="End-to-end latency in milliseconds.",
    )


class OmniRouteAdapter(BaseModel):
    """Routes inference requests to appropriate backends.

    The adapter translates routing decisions into actual calls to
    inference providers. It handles provider-specific authentication,
    request formatting, and response parsing.

    Usage
    -----
    >>> adapter = OmniRouteAdapter(
    ...     clients={
    ...         "openai": OpenAIClient(api_key="..."),
    ...         "anthropic": AnthropicClient(api_key="...")
    ...     }
    ... )
    >>> response = adapter.route(route, request)
    """

    model_config = {"extra": "forbid"}

    clients: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific HTTP clients.",
    )
    default_timeout: int = Field(
        default=30000,
        ge=1,
        description="Default timeout in milliseconds.",
    )

    def add_provider(self, name: str, client: Any) -> None:
        """Add or replace a provider client."""
        self.clients[name] = client

    def route(self, route: InferenceRoute, request: InferenceRequest) -> InferenceResponse:
        """Route an inference request through the fallback chain.

        Args:
            route: The routing decision to use.
            request: The inference request to route.

        Returns:
            The response from the successful provider.

        Raises:
            RuntimeError: If all providers in the fallback chain fail.
        """
        providers_tried = []

        # Try primary provider first
        result = self._call_provider(
            route.primary_provider,
            route.primary_model,
            request,
        )
        if result:
            self._record_telemetry(route.primary_provider, route.primary_model, result, True)
            return result

        providers_tried.append((route.primary_provider, route.primary_model))

        # Try fallback hops
        for hop in route.hops:
            result = self._call_provider(hop.provider, hop.model, request)
            if result:
                self._record_telemetry(hop.provider, hop.model, result, True)
                return result
            providers_tried.append((hop.provider, hop.model))

        self._record_telemetry(
            route.primary_provider,
            route.primary_model,
            None,
            False,
            providers_tried,
        )
        raise RuntimeError(
            f"All providers exhausted: {providers_tried}"
        )

    def _call_provider(
        self, provider: str, model: str, request: InferenceRequest
    ) -> InferenceResponse | None:
        """Call a single provider. Returns None on failure."""
        if provider not in self.clients:
            return None

        client = self.clients[provider]
        timeout = request.timeout_ms or self.default_timeout

        try:
            result = client.generate(
                model=model,
                prompt=request.prompt,
                parameters=request.parameters,
                timeout=timeout,
            )
            return InferenceResponse(
                provider=provider,
                model=model,
                content=result["content"],
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                ttft_ms=result.get("ttft_ms"),
                e2e_latency_ms=result.get("e2e_latency_ms"),
            )
        except Exception:
            return None

    def _record_telemetry(
        self,
        provider: str,
        model: str,
        response: InferenceResponse | None,
        success: bool,
        providers_tried: list[tuple[str, str]] | None = None,
    ) -> None:
        """Record telemetry for policy refinement."""
        sample = OmniRouteTelemetry(
            provider=provider,
            model=model,
            sample_at=datetime.now(UTC),
            requests=1,
            success_rate=1.0 if success else 0.0,
            ttft_ms=response.ttft_ms if response else None,
            tokens_per_second=None,
            e2e_latency_ms=response.e2e_latency_ms if response else None,
            p95_latency_ms=None,
            errors=0 if success else 1,
            circuit_state="open" if not success else "closed",
        )

        # Store telemetry for policy engine to consume
        if not hasattr(self, "_telemetry_history"):
            self._telemetry_history: dict[tuple[str, str], list[OmniRouteTelemetry]] = {}
        key = (provider, model)
        if key not in self._telemetry_history:
            self._telemetry_history[key] = []
        self._telemetry_history[key].append(sample)

    def get_telemetry(self) -> dict[tuple[str, str], list[OmniRouteTelemetry]]:
        """Get accumulated telemetry samples."""
        if not hasattr(self, "_telemetry_history"):
            self._telemetry_history = {}
        return self._telemetry_history
