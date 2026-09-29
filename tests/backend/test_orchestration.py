"""Tests for backend orchestration subsystem."""


class TestOrchestration:
    """Tests for orchestration module."""

    def test_what_changed_engine_exists(self):
        """Test that WhatChangedEngine can be imported."""
        from backend.orchestration import WhatChangedEngine

        assert WhatChangedEngine is not None
