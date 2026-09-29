"""Context prioritization for content ranking and token allocation.

This module implements the ``ContextPrioritizer`` that ranks and
prioritizes context content based on relevance, recency, and
importance according to Section 32 (Context Prioritization) of the
NerveCenter specification.

The prioritizer:
- Scores context sections by relevance
- Handles temporal decay for outdated content
- Supports weighted scoring for different criteria
- Produces prioritized orderings for context assembly
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class PrioritizedSection(BaseModel):
    """A context section with its priority score."""

    model_config = {"extra": "forbid"}

    section_id: str = Field(..., description="ID of the section.")
    kind: str = Field(..., description="Kind of records in the section.")
    score: float = Field(
        ...,
        ge=0.0,
        description="Priority score (higher = more important).",
    )
    record_count: int = Field(..., ge=0, description="Number of records.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Section metadata.",
    )


class PrioritizationConfig(BaseModel):
    """Configuration for context prioritization."""

    model_config = {"extra": "forbid"}

    relevance_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for relevance score.",
    )
    recency_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for recency score.",
    )
    importance_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for importance score.",
    )
    temporal_half_life_hours: float = Field(
        default=24.0,
        ge=1.0,
        description="Half-life for temporal decay in hours.",
    )


class ContextPrioritizer(BaseModel):
    """Ranks and prioritizes context sections.

    The prioritizer scores sections based on multiple criteria and
    produces an ordered list suitable for context assembly.

    Usage
    -----
    >>> prioritizer = ContextPrioritizer()
    >>> prioritized = prioritizer.rank(
    ...     sections=[...],
    ...     config=PrioritizationConfig()
    ... )
    """

    model_config = {"extra": "forbid"}

    default_relevance: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Default relevance score when not specified.",
    )
    importance_map: dict[str, float] = Field(
        default_factory=lambda: {
            "entities": 1.0,
            "claims": 0.9,
            "evidence": 0.8,
            "relationships": 0.7,
            "decisions": 1.0,
            "tasks": 0.85,
            "goals": 0.95,
        },
        description="Base importance scores by section kind.",
    )

    def rank(
        self,
        sections: list[dict[str, Any]],
        config: PrioritizationConfig | None = None,
        reference_time: datetime | None = None,
    ) -> list[PrioritizedSection]:
        """Rank sections by priority score.

        Args:
            sections: List of section dictionaries with metadata.
            config: Prioritization configuration.
            reference_time: Time to use for recency calculations.

        Returns:
            List of prioritized sections, sorted by score descending.
        """
        config = config or PrioritizationConfig()
        reference_time = reference_time or datetime.now(UTC)

        scored = []
        for section in sections:
            score = self._calculate_score(section, config, reference_time)
            prioritized = PrioritizedSection(
                section_id=section.get("id", "unknown"),
                kind=section.get("kind", "unknown"),
                score=score,
                record_count=len(section.get("record_ids", [])),
                metadata=section.get("metadata", {}),
            )
            scored.append(prioritized)

        return sorted(scored, key=lambda s: s.score, reverse=True)

    def _calculate_score(
        self,
        section: dict[str, Any],
        config: PrioritizationConfig,
        reference_time: datetime,
    ) -> float:
        """Calculate priority score for a section."""
        relevance = self._get_relevance(section)
        recency = self._get_recency(section, config, reference_time)
        importance = self._get_importance(section)

        weighted = (
            config.relevance_weight * relevance
            + config.recency_weight * recency
            + config.importance_weight * importance
        )
        return weighted

    def _get_relevance(self, section: dict[str, Any]) -> float:
        """Get relevance score for a section."""
        if "relevance_score" in section:
            return float(section["relevance_score"])
        return self.default_relevance

    def _get_recency(
        self, section: dict[str, Any], config: PrioritizationConfig, reference_time: datetime
    ) -> float:
        """Get temporal decay score for a section."""
        if "asserted_at" in section:
            asserted = section["asserted_at"]
            if isinstance(asserted, str):
                from datetime import datetime

                asserted = datetime.fromisoformat(
                    asserted.replace("Z", "+00:00")
                )

            age_hours = (reference_time - asserted).total_seconds() / 3600
            decay = 2 ** (-age_hours / config.temporal_half_life_hours)
            return decay

        return 1.0

    def _get_importance(self, section: dict[str, Any]) -> float:
        """Get importance score for a section."""
        kind = section.get("kind", "")
        return self.importance_map.get(kind, 0.5)

    def top_k(
        self,
        sections: list[dict[str, Any]],
        k: int,
        config: PrioritizationConfig | None = None,
    ) -> list[dict[str, Any]]:
        """Return the top-k sections by priority.

        Args:
            sections: List of sections to rank.
            k: Number of sections to return.
            config: Prioritization configuration.

        Returns:
            Top-k sections in priority order.
        """
        ranked = self.rank(sections, config)
        return [s.model_dump() for s in ranked[:k]]

    def filter_by_threshold(
        self,
        sections: list[dict[str, Any]],
        min_score: float,
        config: PrioritizationConfig | None = None,
    ) -> list[dict[str, Any]]:
        """Filter sections by minimum priority score.

        Args:
            sections: List of sections to filter.
            min_score: Minimum priority score threshold.
            config: Prioritization configuration.

        Returns:
            Sections with score >= min_score.
        """
        ranked = self.rank(sections, config)
        return [s.model_dump() for s in ranked if s.score >= min_score]
