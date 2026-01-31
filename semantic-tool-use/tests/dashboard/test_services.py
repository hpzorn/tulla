"""Unit tests for DashboardService.get_prd_requirements().

Tests use mock AgentMemory with sample fact data matching
the real ontology-server fact structure.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from ontology_server.dashboard.services import DashboardService


def _make_fact(subject: str, predicate: str, obj: str) -> dict:
    """Create a fact dict matching AgentMemory.recall() output."""
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
    }


SAMPLE_FACTS = [
    # Requirement 1: prd:req-1 — a full requirement
    _make_fact("prd:req-1", "rdf:type", "prd:Requirement"),
    _make_fact("prd:req-1", "prd:title", "Create Dashboard Services Layer"),
    _make_fact("prd:req-1", "prd:status", "prd:Pending"),
    _make_fact("prd:req-1", "prd:priority", "prd:P0"),
    _make_fact("prd:req-1", "prd:phase", "1"),
    _make_fact("prd:req-1", "prd:files", "dashboard/services.py"),
    _make_fact("prd:req-1", "prd:action", "create"),
    _make_fact("prd:req-1", "prd:description", "Create the services layer"),
    # Requirement 2: prd:req-2 — minimal requirement
    _make_fact("prd:req-2", "rdf:type", "prd:Requirement"),
    _make_fact("prd:req-2", "prd:title", "Create Dashboard Routes"),
    _make_fact("prd:req-2", "prd:status", "prd:Pending"),
    # A non-requirement fact (should be ignored)
    _make_fact("prd:component-1", "rdf:type", "prd:Component"),
    _make_fact("prd:component-1", "prd:title", "Dashboard Package"),
    # A requirement with a multi-valued predicate
    _make_fact("prd:req-3", "rdf:type", "prd:Requirement"),
    _make_fact("prd:req-3", "prd:title", "Add Dependencies"),
    _make_fact("prd:req-3", "prd:dependsOn", "prd:req-1"),
    _make_fact("prd:req-3", "prd:dependsOn", "prd:req-2"),
]

CONTEXT = "prd-idea-50"


class MockAgentMemory:
    """Minimal mock of AgentMemory that supports recall() with filters."""

    def __init__(self, facts: list[dict]) -> None:
        self._facts = facts

    def recall(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        result = self._facts
        if subject is not None:
            result = [f for f in result if f["subject"] == subject]
        if predicate is not None:
            result = [f for f in result if f["predicate"] == predicate]
        return result[:limit]


class TestGetPrdRequirements(unittest.TestCase):
    """Test DashboardService.get_prd_requirements() with sample fact data."""

    def setUp(self) -> None:
        self.memory = MockAgentMemory(SAMPLE_FACTS)
        self.service = DashboardService(
            ontology_store=MagicMock(),
            kg_store=MagicMock(),
            agent_memory=self.memory,
            ideas_store=MagicMock(),
        )

    def test_returns_only_requirements(self) -> None:
        """Only facts with rdf:type=prd:Requirement should be returned."""
        reqs = self.service.get_prd_requirements(CONTEXT)
        subjects = {r["subject"] for r in reqs}
        self.assertEqual(subjects, {"prd:req-1", "prd:req-2", "prd:req-3"})
        # prd:component-1 should NOT appear
        self.assertNotIn("prd:component-1", subjects)

    def test_requirement_count(self) -> None:
        """Should return exactly 3 requirements from sample data."""
        reqs = self.service.get_prd_requirements(CONTEXT)
        self.assertEqual(len(reqs), 3)

    def test_properties_populated(self) -> None:
        """Each requirement should have its properties collected."""
        reqs = self.service.get_prd_requirements(CONTEXT)
        req1 = next(r for r in reqs if r["subject"] == "prd:req-1")
        self.assertEqual(req1["prd:title"], "Create Dashboard Services Layer")
        self.assertEqual(req1["prd:status"], "prd:Pending")
        self.assertEqual(req1["prd:priority"], "prd:P0")
        self.assertEqual(req1["prd:phase"], "1")
        self.assertEqual(req1["prd:files"], "dashboard/services.py")
        self.assertEqual(req1["prd:action"], "create")

    def test_multi_valued_predicate_becomes_list(self) -> None:
        """When a predicate appears multiple times, values become a list."""
        reqs = self.service.get_prd_requirements(CONTEXT)
        req3 = next(r for r in reqs if r["subject"] == "prd:req-3")
        depends = req3["prd:dependsOn"]
        self.assertIsInstance(depends, list)
        self.assertEqual(sorted(depends), ["prd:req-1", "prd:req-2"])

    def test_minimal_requirement(self) -> None:
        """A requirement with only type and title should still work."""
        reqs = self.service.get_prd_requirements(CONTEXT)
        req2 = next(r for r in reqs if r["subject"] == "prd:req-2")
        self.assertEqual(req2["prd:title"], "Create Dashboard Routes")
        self.assertEqual(req2["prd:status"], "prd:Pending")

    def test_empty_context_returns_empty(self) -> None:
        """If there are no facts matching, return empty list."""
        empty_memory = MockAgentMemory([])
        service = DashboardService(
            ontology_store=MagicMock(),
            kg_store=MagicMock(),
            agent_memory=empty_memory,
            ideas_store=MagicMock(),
        )
        reqs = service.get_prd_requirements("nonexistent-context")
        self.assertEqual(reqs, [])

    def test_subject_key_always_present(self) -> None:
        """Every returned requirement dict must contain 'subject'."""
        reqs = self.service.get_prd_requirements(CONTEXT)
        for req in reqs:
            self.assertIn("subject", req)


if __name__ == "__main__":
    unittest.main()
