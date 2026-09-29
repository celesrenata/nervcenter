"""Tests for backend agents subsystem."""
import pytest


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_registry_exists(self):
        """Test that AgentRegistry can be imported."""
        from backend.agents.registry import AgentRegistry

        assert AgentRegistry is not None

    def test_native_agent_count(self):
        """Test that all 14 native agent types are registered."""
        from backend.agents.registry import AgentRegistry

        registry = AgentRegistry()
        types = registry.get_native_types()
        assert len(types) == 14, f"Expected 14 native agents, got {len(types)}"
