"""Context: assembly and budgeting of inference context.

This package implements context compilation and token budgeting:
- ContextCompiler: Assembles bounded context packages
- ContextPrioritizer: Ranks and prioritizes context content

Modules
-------
- ``compiler`` — ContextCompiler for context assembly
- ``prioritization`` — ContextPrioritizer for content ranking
"""

from .compiler import ContextCompiler, BudgetConfig, ContextSource, CompiledSection
from .prioritization import (
    ContextPrioritizer,
    PrioritizationConfig,
    PrioritizedSection,
)

__all__ = [
    "ContextCompiler",
    "BudgetConfig",
    "ContextSource",
    "CompiledSection",
    "ContextPrioritizer",
    "PrioritizationConfig",
    "PrioritizedSection",
]
