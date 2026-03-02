"""Tests for SPARQL-based annotation resolution in FindPhase.

Covers:
- FindPhase._expand_uri() — compact URI → full URI expansion
- FindPhase._resolve_patterns_via_sparql() — three chained SPARQL queries
- FindPhase._load_requirement() — wiring resolved fields into FindOutput

Architecture decisions tested:
- arch:adr-65-2: Three separate SPARQL queries (no OPTIONAL)
- arch:adr-65-1: Resolution in _load_requirement(), per-requirement quality_focus
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from tulla.phases.implementation.find import _REVERSE_PREFIXES, FindPhase
from tulla.phases.implementation.models import FindOutput
from tulla.ports.ontology import OntologyPort

# ---------------------------------------------------------------------------
# Test double: SPARQL-aware ontology stub
# ---------------------------------------------------------------------------


class SparqlStubOntology(OntologyPort):
    """Ontology stub that dispatches sparql_query() based on captured bindings."""

    def __init__(
        self,
        facts_by_key: dict[str, list[dict[str, str]]] | None = None,
        sparql_responses: list[dict[str, Any]] | None = None,
    ):
        self._facts = facts_by_key or {}
        self._sparql_responses = list(sparql_responses or [])
        self._sparql_call_index = 0
        self.sparql_queries: list[str] = []

    def _key(self, **kw: Any) -> str:
        parts = []
        for k in ("subject", "predicate", "context"):
            if kw.get(k):
                parts.append(f"{k}={kw[k]}")
        return "|".join(sorted(parts))

    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        key = self._key(subject=subject, predicate=predicate, context=context)
        return {"result": self._facts.get(key, [])}

    def sparql_query(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        self.sparql_queries.append(query)
        if self._sparql_call_index < len(self._sparql_responses):
            resp = self._sparql_responses[self._sparql_call_index]
            self._sparql_call_index += 1
            if isinstance(resp, Exception):
                raise resp
            return resp
        return {"results": []}

    def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        return {"status": "ok"}

    # -- abstract method stubs --
    def query_ideas(self, **kw: Any) -> dict[str, Any]:
        return {}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(self, subject: str, predicate: str, object: str, **kw: Any) -> dict[str, Any]:
        return {"status": "ok"}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
        return {}

    def set_lifecycle(self, idea_id: str, new_state: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {}

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {"status": "added"}

    def remove_triples_by_subject(self, subject: str, *, ontology: str | None = None) -> int:
        return 0


# ---------------------------------------------------------------------------
# _expand_uri
# ---------------------------------------------------------------------------


class TestExpandUri:
    """FindPhase._expand_uri() compact → full URI expansion."""

    def test_isaqb_prefix(self) -> None:
        assert (
            FindPhase._expand_uri("isaqb:Maintainability")
            == "http://tulla.dev/isaqb#Maintainability"
        )

    def test_prd_prefix(self) -> None:
        assert FindPhase._expand_uri("prd:qualityFocus") == "http://tulla.dev/prd#qualityFocus"

    def test_unknown_prefix_returns_unchanged(self) -> None:
        assert FindPhase._expand_uri("foo:Bar") == "foo:Bar"

    def test_already_full_uri_returns_unchanged(self) -> None:
        full = "http://tulla.dev/isaqb#Testability"
        assert FindPhase._expand_uri(full) == full

    def test_empty_string(self) -> None:
        assert FindPhase._expand_uri("") == ""

    def test_all_known_prefixes(self) -> None:
        for prefix, full_ns in _REVERSE_PREFIXES.items():
            compact = f"{prefix}TestLocal"
            assert FindPhase._expand_uri(compact) == f"{full_ns}TestLocal"


# ---------------------------------------------------------------------------
# _resolve_patterns_via_sparql
# ---------------------------------------------------------------------------


class TestResolvePatternsViaSparql:
    """FindPhase._resolve_patterns_via_sparql() — three chained SPARQL queries."""

    def test_empty_quality_focus_returns_empty(self) -> None:
        ontology = SparqlStubOntology()
        phase = FindPhase()
        patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(ontology, "")
        assert patterns == []
        assert principles == []
        assert design_patterns == []
        assert len(ontology.sparql_queries) == 0

    def test_full_resolution_chain(self) -> None:
        """Three queries resolve quality → patterns → principles → design patterns."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                # Query 1: quality → architectural patterns
                {
                    "results": [
                        {
                            "pattern": "isaqb:LayeredArchitecture",
                            "quality": "isaqb:Maintainability",
                        },
                        {"pattern": "isaqb:PortsAndAdapters", "quality": "isaqb:Testability"},
                    ]
                },
                # Query 2: patterns → principles
                {
                    "results": [
                        {
                            "principle": "isaqb:SeparationOfConcerns",
                            "pattern": "isaqb:LayeredArchitecture",
                        },
                        {
                            "principle": "isaqb:DependencyInversion",
                            "pattern": "isaqb:PortsAndAdapters",
                        },
                    ]
                },
                # Query 3: principles → design patterns
                {
                    "results": [
                        {
                            "designPattern": "isaqb:AdapterPattern",
                            "principle": "isaqb:DependencyInversion",
                        },
                        {
                            "designPattern": "isaqb:StrategyPattern",
                            "principle": "isaqb:SeparationOfConcerns",
                        },
                    ]
                },
            ]
        )
        phase = FindPhase()
        patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
            ontology, "isaqb:Maintainability"
        )

        assert patterns == ["isaqb:LayeredArchitecture", "isaqb:PortsAndAdapters"]
        assert principles == ["isaqb:SeparationOfConcerns", "isaqb:DependencyInversion"]
        assert design_patterns == ["isaqb:AdapterPattern", "isaqb:StrategyPattern"]
        assert len(ontology.sparql_queries) == 3

    def test_three_separate_queries_not_optional(self) -> None:
        """Verifies arch:adr-65-2 — three separate queries, no OPTIONAL clauses."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {"results": [{"principle": "isaqb:SeparationOfConcerns", "pattern": "isaqb:MVC"}]},
                {"results": []},
            ]
        )
        phase = FindPhase()
        phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")

        assert len(ontology.sparql_queries) == 3
        for q in ontology.sparql_queries:
            assert "OPTIONAL" not in q

    def test_query1_contains_union_for_sub_attributes(self) -> None:
        """Query 1 uses UNION to include direct + hasSubAttribute paths."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {"results": []},
            ]
        )
        phase = FindPhase()
        phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")

        q1 = ontology.sparql_queries[0]
        assert "UNION" in q1
        assert "isaqb:hasSubAttribute" in q1
        assert "isaqb:addresses" in q1

    def test_query2_uses_values_from_query1(self) -> None:
        """Query 2 uses VALUES clause with patterns discovered in query 1."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {
                    "results": [
                        {
                            "pattern": "isaqb:LayeredArchitecture",
                            "quality": "isaqb:Maintainability",
                        },
                        {"pattern": "isaqb:MVC", "quality": "isaqb:Testability"},
                    ]
                },
                {"results": []},
            ]
        )
        phase = FindPhase()
        phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")

        q2 = ontology.sparql_queries[1]
        assert "VALUES ?pattern" in q2
        assert "isaqb#LayeredArchitecture" in q2
        assert "isaqb#MVC" in q2
        assert "isaqb:embodies" in q2

    def test_query3_uses_values_from_query2(self) -> None:
        """Query 3 uses VALUES clause with principles from query 2."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {
                    "results": [
                        {"principle": "isaqb:SeparationOfConcerns", "pattern": "isaqb:MVC"},
                        {"principle": "isaqb:LooseCoupling", "pattern": "isaqb:MVC"},
                    ]
                },
                {
                    "results": [
                        {
                            "designPattern": "isaqb:ObserverPattern",
                            "principle": "isaqb:LooseCoupling",
                        }
                    ]
                },
            ]
        )
        phase = FindPhase()
        phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")

        q3 = ontology.sparql_queries[2]
        assert "VALUES ?principle" in q3
        assert "isaqb#SeparationOfConcerns" in q3
        assert "isaqb#LooseCoupling" in q3
        assert "isaqb:DesignPattern" in q3

    def test_no_patterns_found_skips_query2_and_query3(self) -> None:
        """When query 1 returns no patterns, queries 2 and 3 are not issued."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": []},
            ]
        )
        phase = FindPhase()
        patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
            ontology, "isaqb:FunctionalSuitability"
        )

        assert patterns == []
        assert principles == []
        assert design_patterns == []
        assert len(ontology.sparql_queries) == 1

    def test_no_principles_found_skips_query3(self) -> None:
        """When query 2 returns no principles, query 3 is not issued."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {"results": []},
            ]
        )
        phase = FindPhase()
        patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
            ontology, "isaqb:Maintainability"
        )

        assert patterns == ["isaqb:MVC"]
        assert principles == []
        assert design_patterns == []
        assert len(ontology.sparql_queries) == 2

    def test_deduplicates_patterns(self) -> None:
        """Duplicate patterns in query 1 results are deduplicated."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {
                    "results": [
                        {"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"},
                        {"pattern": "isaqb:MVC", "quality": "isaqb:Testability"},
                    ]
                },
                {"results": []},
            ]
        )
        phase = FindPhase()
        patterns, _, _ = phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")
        assert patterns == ["isaqb:MVC"]

    def test_deduplicates_principles(self) -> None:
        """Duplicate principles in query 2 results are deduplicated."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {
                    "results": [
                        {"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"},
                        {
                            "pattern": "isaqb:LayeredArchitecture",
                            "quality": "isaqb:Maintainability",
                        },
                    ]
                },
                {
                    "results": [
                        {"principle": "isaqb:SeparationOfConcerns", "pattern": "isaqb:MVC"},
                        {
                            "principle": "isaqb:SeparationOfConcerns",
                            "pattern": "isaqb:LayeredArchitecture",
                        },
                    ]
                },
                {"results": []},
            ]
        )
        phase = FindPhase()
        _, principles, _ = phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")
        assert principles == ["isaqb:SeparationOfConcerns"]

    def test_deduplicates_design_patterns(self) -> None:
        """Duplicate design patterns in query 3 results are deduplicated."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {
                    "results": [
                        {"principle": "isaqb:SeparationOfConcerns", "pattern": "isaqb:MVC"},
                        {"principle": "isaqb:LooseCoupling", "pattern": "isaqb:MVC"},
                    ]
                },
                {
                    "results": [
                        {
                            "designPattern": "isaqb:VisitorPattern",
                            "principle": "isaqb:SeparationOfConcerns",
                        },
                        {
                            "designPattern": "isaqb:VisitorPattern",
                            "principle": "isaqb:LooseCoupling",
                        },
                    ]
                },
            ]
        )
        phase = FindPhase()
        _, _, design_patterns = phase._resolve_patterns_via_sparql(
            ontology, "isaqb:Maintainability"
        )
        assert design_patterns == ["isaqb:VisitorPattern"]

    def test_query1_failure_returns_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        """SPARQL query 1 failure returns three empty lists gracefully."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                RuntimeError("connection refused"),
            ]
        )
        phase = FindPhase()
        with caplog.at_level(logging.WARNING):
            patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
                ontology, "isaqb:Maintainability"
            )

        assert patterns == []
        assert principles == []
        assert design_patterns == []

    def test_query2_failure_returns_partial(self, caplog: pytest.LogCaptureFixture) -> None:
        """SPARQL query 2 failure returns patterns from query 1 only."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                RuntimeError("timeout"),
            ]
        )
        phase = FindPhase()
        with caplog.at_level(logging.WARNING):
            patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
                ontology, "isaqb:Maintainability"
            )

        assert patterns == ["isaqb:MVC"]
        assert principles == []
        assert design_patterns == []

    def test_query3_failure_returns_partial(self, caplog: pytest.LogCaptureFixture) -> None:
        """SPARQL query 3 failure returns patterns and principles only."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {"results": [{"principle": "isaqb:SeparationOfConcerns", "pattern": "isaqb:MVC"}]},
                RuntimeError("server error"),
            ]
        )
        phase = FindPhase()
        with caplog.at_level(logging.WARNING):
            patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
                ontology, "isaqb:Maintainability"
            )

        assert patterns == ["isaqb:MVC"]
        assert principles == ["isaqb:SeparationOfConcerns"]
        assert design_patterns == []

    def test_empty_binding_values_filtered(self) -> None:
        """Empty string values in bindings are filtered out."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {
                    "results": [
                        {"pattern": "", "quality": "isaqb:Maintainability"},
                        {"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"},
                    ]
                },
                {
                    "results": [
                        {"principle": "", "pattern": "isaqb:MVC"},
                        {"principle": "isaqb:DRY", "pattern": "isaqb:MVC"},
                    ]
                },
                {
                    "results": [
                        {"designPattern": "", "principle": "isaqb:DRY"},
                        {"designPattern": "isaqb:TemplateMethodPattern", "principle": "isaqb:DRY"},
                    ]
                },
            ]
        )
        phase = FindPhase()
        patterns, principles, design_patterns = phase._resolve_patterns_via_sparql(
            ontology, "isaqb:Maintainability"
        )

        assert patterns == ["isaqb:MVC"]
        assert principles == ["isaqb:DRY"]
        assert design_patterns == ["isaqb:TemplateMethodPattern"]

    def test_uri_expansion_in_sparql_queries(self) -> None:
        """SPARQL queries use expanded full URIs, not compact prefixes."""
        ontology = SparqlStubOntology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {"results": []},
            ]
        )
        phase = FindPhase()
        phase._resolve_patterns_via_sparql(ontology, "isaqb:Maintainability")

        q1 = ontology.sparql_queries[0]
        assert "http://tulla.dev/isaqb#Maintainability" in q1


# ---------------------------------------------------------------------------
# _load_requirement integration — resolved fields on FindOutput
# ---------------------------------------------------------------------------


class TestLoadRequirementResolution:
    """FindPhase._load_requirement() populates resolved_* fields via SPARQL."""

    def _make_ontology(
        self,
        quality_focus: str = "isaqb:Maintainability",
        sparql_responses: list[dict[str, Any]] | None = None,
    ) -> SparqlStubOntology:
        facts = {
            "context=prd-idea-65|subject=prd:req-65-1-3": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "Add SPARQL resolution"},
                {
                    "predicate": "prd:description",
                    "object": (
                        "Add _expand_uri helper and _resolve_patterns_via_sparql method "
                        "to FindPhase for resolving quality focus to patterns"
                    ),
                },
                {"predicate": "prd:files", "object": "src/tulla/phases/implementation/find.py"},
                {"predicate": "prd:action", "object": "modify"},
                {"predicate": "prd:verification", "object": "pytest tests/"},
                {"predicate": "prd:relatedADR", "object": "arch:adr-65-2"},
                {"predicate": "prd:qualityFocus", "object": quality_focus},
            ],
        }
        return SparqlStubOntology(
            facts_by_key=facts,
            sparql_responses=sparql_responses,
        )

    def test_resolved_fields_populated(self) -> None:
        """_load_requirement populates resolved_patterns, resolved_principles, etc."""
        ontology = self._make_ontology(
            sparql_responses=[
                {
                    "results": [
                        {
                            "pattern": "isaqb:LayeredArchitecture",
                            "quality": "isaqb:Maintainability",
                        },
                    ]
                },
                {
                    "results": [
                        {
                            "principle": "isaqb:SeparationOfConcerns",
                            "pattern": "isaqb:LayeredArchitecture",
                        },
                    ]
                },
                {
                    "results": [
                        {
                            "designPattern": "isaqb:AdapterPattern",
                            "principle": "isaqb:SeparationOfConcerns",
                        },
                    ]
                },
            ]
        )
        phase = FindPhase()
        result = phase._load_requirement(ontology, "prd:req-65-1-3", "prd-idea-65")

        assert result.quality_focus == "isaqb:Maintainability"
        assert result.resolved_patterns == ["isaqb:LayeredArchitecture"]
        assert result.resolved_principles == ["isaqb:SeparationOfConcerns"]
        assert result.resolved_design_patterns == ["isaqb:AdapterPattern"]

    def test_empty_quality_focus_no_resolution(self) -> None:
        """Empty quality_focus → all resolved lists empty, no SPARQL calls."""
        ontology = self._make_ontology(quality_focus="")
        phase = FindPhase()
        result = phase._load_requirement(ontology, "prd:req-65-1-3", "prd-idea-65")

        assert result.quality_focus == ""
        assert result.resolved_patterns == []
        assert result.resolved_principles == []
        assert result.resolved_design_patterns == []
        assert len(ontology.sparql_queries) == 0

    def test_sparql_failure_does_not_break_load(self) -> None:
        """SPARQL failure still returns a valid FindOutput with empty resolved fields."""
        ontology = self._make_ontology(
            sparql_responses=[
                RuntimeError("ontology server unavailable"),
            ]
        )
        phase = FindPhase()
        result = phase._load_requirement(ontology, "prd:req-65-1-3", "prd-idea-65")

        assert result.requirement_id == "prd:req-65-1-3"
        assert result.title == "Add SPARQL resolution"
        assert result.quality_focus == "isaqb:Maintainability"
        assert result.resolved_patterns == []
        assert result.resolved_principles == []
        assert result.resolved_design_patterns == []

    def test_other_fields_unaffected(self) -> None:
        """Adding resolution does not affect existing FindOutput fields."""
        ontology = self._make_ontology(
            sparql_responses=[
                {"results": [{"pattern": "isaqb:MVC", "quality": "isaqb:Maintainability"}]},
                {"results": []},
            ]
        )
        phase = FindPhase()
        result = phase._load_requirement(ontology, "prd:req-65-1-3", "prd-idea-65")

        assert result.requirement_id == "prd:req-65-1-3"
        assert result.title == "Add SPARQL resolution"
        assert result.files == ["src/tulla/phases/implementation/find.py"]
        assert result.action == "modify"
        assert result.related_adrs == ["arch:adr-65-2"]
        assert result.all_complete is False


# ---------------------------------------------------------------------------
# FindOutput model — resolved fields defaults
# ---------------------------------------------------------------------------


class TestFindOutputResolvedFields:
    """FindOutput model resolved_* fields have correct defaults."""

    def test_defaults_empty_lists(self) -> None:
        out = FindOutput()
        assert out.resolved_patterns == []
        assert out.resolved_principles == []
        assert out.resolved_design_patterns == []

    def test_can_set_resolved_fields(self) -> None:
        out = FindOutput(
            resolved_patterns=["isaqb:LayeredArchitecture"],
            resolved_principles=["isaqb:SeparationOfConcerns"],
            resolved_design_patterns=["isaqb:AdapterPattern"],
        )
        assert out.resolved_patterns == ["isaqb:LayeredArchitecture"]
        assert out.resolved_principles == ["isaqb:SeparationOfConcerns"]
        assert out.resolved_design_patterns == ["isaqb:AdapterPattern"]
