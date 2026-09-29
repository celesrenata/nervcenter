"""Tests for backend persistence subsystem."""
import pytest


class TestPersistence:
    """Tests for persistence module."""

    def test_base_import(self):
        """Test that Base can be imported."""
        from backend.persistence.models import Base

        assert Base is not None

    def test_evidence_model_import(self):
        """Test that Evidence model can be imported."""
        from backend.persistence.models import Evidence

        assert Evidence is not None
