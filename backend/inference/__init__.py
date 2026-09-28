"""Inference: model routing and inference adapters.

This package implements the inference pipeline:
- InferencePolicyEngine: Model selection based on capabilities and metrics
- ContextCompiler: Bounded context assembly
- OmniRouteAdapter: Inference request routing
- InferenceTelemetry: Performance tracking

Modules
-------
- ``policy`` — InferencePolicyEngine for model selection
- ``omniroute`` — OmniRouteAdapter for routing
- ``adapter`` — Inference adapters for model backends
- ``telemetry`` — Inference telemetry collection
"""

from .policy import InferencePolicyEngine, PolicyRule, TaskRequirements
from .omniroute import OmniRouteAdapter, InferenceRequest, InferenceResponse
from .adapter import (
    InferenceAdapter,
    InferenceResult,
    LocalAdapter,
    OpenAIAdapter,
    AnthropicAdapter,
    HuggingFaceAdapter,
    AdapterPool,
)
from .telemetry import (
    InferenceTelemetry,
    TelemetryCollector,
    LatencyWindow,
    LatencySnapshot,
)

__all__ = [
    "InferencePolicyEngine",
    "PolicyRule",
    "TaskRequirements",
    "OmniRouteAdapter",
    "InferenceRequest",
    "InferenceResponse",
    "InferenceAdapter",
    "InferenceResult",
    "LocalAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "HuggingFaceAdapter",
    "AdapterPool",
    "InferenceTelemetry",
    "TelemetryCollector",
    "LatencyWindow",
    "LatencySnapshot",
]
