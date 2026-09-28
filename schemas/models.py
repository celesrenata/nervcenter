"""Model descriptor records (NerveCenter spec Section 10-16).

A *ModelDescriptor* is the registry entry for an inference model: who offers
it, which modalities and capabilities it supports, its token limits, and its
cost/quality profile. Inference routing consumes descriptors when building
:class:`InferenceRoute` objects.

Assumptions (spec not present in the repository):
    - ``capabilities`` and ``input_modalities`` / ``output_modalities`` are
      classification literals over the common model capabilities
      (chat, embedding, image, audio, video, rerank, moderation).
    - Cost is expressed per 1M tokens; optional and local models may omit
      it.
"""

from typing import Any, Literal

from pydantic import Field

from .base import Record

#: Capability a model can perform.
ModelCapability = Literal[
    "chat",
    "embedding",
    "image_generation",
    "image_understanding",
    "transcription",
    "speech_synthesis",
    "rerank",
    "moderation",
]

#: Modality a model consumes or produces.
ModelModality = Literal["text", "image", "audio", "video"]

#: Operational status of a model in the registry.
ModelStatus = Literal["available", "degraded", "disabled", "unknown"]


class ModelDescriptor(Record):
    """Registry entry describing a routable inference model."""

    model_id: str = Field(
        ...,
        description="Provider-unique model identifier (e.g. 'provider/model-name').",
    )
    provider: str = Field(
        ...,
        description="Provider that offers this model (e.g. 'local', 'openai', 'anthropic').",
    )
    family: str | None = Field(
        default=None,
        description="Model family (e.g. 'haiku', 'sonnet', 'llama'), when known.",
    )
    version: str | None = Field(
        default=None,
        description="Model version/revision string.",
    )
    capabilities: list[ModelCapability] = Field(
        default_factory=lambda: ["chat"],
        description="Capabilities this model supports.",
    )
    input_modalities: list[ModelModality] = Field(
        default_factory=lambda: ["text"],
        description="Input modalities accepted.",
    )
    output_modalities: list[ModelModality] = Field(
        default_factory=lambda: ["text"],
        description="Output modalities produced.",
    )
    context_window: int | None = Field(
        default=None,
        ge=16,
        description="Context window size in tokens, when known.",
    )
    max_output_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Maximum output tokens per call, when known.",
    )
    cost_per_million_input: float | None = Field(
        default=None,
        ge=0.0,
        description="Cost in USD per 1M input tokens, when billed.",
    )
    cost_per_million_output: float | None = Field(
        default=None,
        ge=0.0,
        description="Cost in USD per 1M output tokens, when billed.",
    )
    status: ModelStatus = Field(
        default="unknown",
        description="Current operational status in the registry.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Default generation parameters applied when calling this model.",
    )
