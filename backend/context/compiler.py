"""Context compiler for assembling inference context packages.

This module implements the ``ContextCompiler`` that turns engineering
reality into bounded task context according to Section 31 (Context
Compiler) of the NerveCenter specification.

The context compiler:
- Assembles context from knowledge graph records
- Enforces token budgets and content limits
- Prioritizes content based on relevance
- Produces bounded ContextPackage for inference
"""

from typing import Any

from pydantic import BaseModel, Field

from schemas.context import ContextPackage, ContextPurpose, ContextSection, ContextSectionKind


class ContextSource(BaseModel):
    """Source of context for compilation."""

    model_config = {"extra": "forbid"}

    id: str = Field(..., description="Unique identifier for the source.")
    kind: ContextSectionKind = Field(..., description="Kind of records in this source.")
    query: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters to fetch records.",
    )
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relevance score for prioritization.",
    )


class BudgetConfig(BaseModel):
    """Token budget configuration."""

    model_config = {"extra": "forbid"}

    total_tokens: int = Field(
        ...,
        ge=1,
        description="Total token budget for the context package.",
    )
    section_limits: dict[ContextSectionKind, int] = Field(
        default_factory=dict,
        description="Per-section token limits.",
    )
    max_sections: int = Field(
        default=10,
        ge=1,
        description="Maximum number of sections to include.",
    )


class CompiledSection(BaseModel):
    """A section that has been compiled with estimated tokens."""

    model_config = {"extra": "forbid"}

    kind: ContextSectionKind = Field(..., description="Kind of records in this section.")
    record_ids: list[str] = Field(
        default_factory=list,
        description="Ids of records included.",
    )
    tokens: int = Field(..., ge=0, description="Estimated token count.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Compilation metadata.",
    )


class ContextCompiler(BaseModel):
    """Assembles bounded context packages from knowledge graph records.

    The compiler takes high-level context needs and produces a
    ContextPackage with bounded token usage. It handles:

    - Record selection and deduplication
    - Token budget enforcement
    - Content prioritization
    - Metadata tracking

    Usage
    -----
    >>> compiler = ContextCompiler()
    >>> package = compiler.compile(
    ...     purpose=ContextPurpose.INFERENCE,
    ...     goal_id="goal-123",
    ...     sources=[...],
    ...     budget=BudgetConfig(total_tokens=50000)
    ... )
    """

    model_config = {"extra": "forbid"}

    max_records_per_section: int = Field(
        default=1000,
        ge=1,
        description="Maximum records per section.",
    )

    def compile(
        self,
        purpose: ContextPurpose,
        goal_id: str | None = None,
        task_id: str | None = None,
        sources: list[ContextSource] | None = None,
        budget: BudgetConfig | None = None,
    ) -> ContextPackage:
        """Compile a context package from sources within budget.

        Args:
            purpose: The intended use of the context package.
            goal_id: The goal driving this context, if any.
            task_id: The task this context is for, if any.
            sources: List of context sources to compile.
            budget: Token budget configuration.

        Returns:
            A ContextPackage with prioritized, bounded content.
        """
        sources = sources or []
        budget = budget or BudgetConfig(total_tokens=50000)

        sections = self._compile_sections(sources, budget)
        tokens_used = sum(s.tokens for s in sections)

        package = ContextPackage(
            id=self._generate_id(purpose, goal_id, task_id),
            purpose=purpose,
            goal_id=goal_id,
            task_id=task_id,
            token_budget=budget.total_tokens,
            tokens_used=tokens_used,
            sections=[self._to_context_section(s) for s in sections],
            context_hash=None,  # Will be computed by consumer
        )

        return package

    def _generate_id(
        self,
        purpose: ContextPurpose,
        goal_id: str | None,
        task_id: str | None,
    ) -> str:
        """Generate a unique ID for the context package."""
        suffix = f"-{task_id}" if task_id else f"-{goal_id}" if goal_id else "-default"
        return f"context-{purpose}{suffix}"

    def _compile_sections(
        self, sources: list[ContextSource], budget: BudgetConfig
    ) -> list[CompiledSection]:
        """Compile sources into sections within budget."""
        sections = []
        remaining_budget = budget.total_tokens

        # Sort by relevance score (highest first)
        sorted_sources = sorted(
            sources, key=lambda s: s.relevance_score, reverse=True
        )[: budget.max_sections]

        for source in sorted_sources:
            if remaining_budget <= 0:
                break

            section = self._compile_section(source, budget, remaining_budget)
            if section.tokens > 0:
                sections.append(section)
                remaining_budget -= section.tokens

        return sections

    def _compile_section(
        self,
        source: ContextSource,
        budget: BudgetConfig,
        available_budget: int,
    ) -> CompiledSection:
        """Compile a single source into a section."""
        section_limit = budget.section_limits.get(source.kind, available_budget)
        tokens_budget = min(section_limit, available_budget)

        # Estimate records that fit in budget (assuming ~4 tokens per record)
        max_records = min(
            self.max_records_per_section,
            tokens_budget // 4,
        )

        # For now, generate synthetic record IDs based on query
        record_ids = self._fetch_records(source, max_records)

        # Estimate token count
        tokens = self._estimate_tokens(record_ids)

        return CompiledSection(
            kind=source.kind,
            record_ids=record_ids,
            tokens=tokens,
            metadata={
                "source_id": source.id,
                "query": source.query,
                "relevance_score": source.relevance_score,
            },
        )

    def _fetch_records(self, source: ContextSource, limit: int) -> list[str]:
        """Fetch record IDs from a source.

        In production, this would query the knowledge graph store.
        """
        # For testing, generate synthetic IDs
        return [f"{source.kind}-{i:04d}" for i in range(min(limit, 100))]

    def _estimate_tokens(self, record_ids: list[str]) -> int:
        """Estimate token count for a set of record IDs."""
        # Each record ID represents ~4 tokens of content
        return len(record_ids) * 4

    def _to_context_section(self, compiled: CompiledSection) -> ContextSection:
        """Convert a compiled section to a ContextSection."""
        return ContextSection(
            id=f"section-{compiled.kind}",
            kind=compiled.kind,
            record_ids=compiled.record_ids,
            metadata=compiled.metadata,
            budget_tokens=None,  # Not specified per-section
        )

    def estimate_tokens(self, content: str) -> int:
        """Estimate token count for content."""
        # Rough estimate: 4 characters per token
        return len(content) // 4
