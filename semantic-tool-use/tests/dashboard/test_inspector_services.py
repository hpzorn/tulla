"""Unit tests for Inspector-specific DashboardService methods.

Tests the six methods added to DashboardService for the Inspector feature:
get_phase_facts, get_phase_detail, resolve_uri, get_triples_for_uri,
get_iteration_facts, and get_requirement_phase_history.

# @pattern:DependencyInversion -- Tests inject mock kg_store via constructor, decoupling from Oxigraph
# @pattern:PortsAndAdapters -- Mock KnowledgeGraphStore acts as test double for the A-Box adapter port
# @pattern:SeparationOfConcerns -- Inspector service tests are isolated from existing dashboard tests
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ontology_server.dashboard.services import DashboardService, KNOWN_PHASES, PHASE_NS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
# @pattern:LooseCoupling -- Fixtures provide reusable mock wiring without coupling to concrete stores


@pytest.fixture()
def kg() -> MagicMock:
    """A mock KnowledgeGraphStore for A-Box queries."""
    return MagicMock()


@pytest.fixture()
def svc(kg: MagicMock) -> DashboardService:
    """DashboardService wired with mock backing stores."""
    return DashboardService(
        ontology_store=MagicMock(),
        kg_store=kg,
        agent_memory=MagicMock(),
        ideas_store=MagicMock(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sparql_result(phases: list[str]) -> SimpleNamespace:
    """Fake SPARQL result with .bindings for single-variable ``phase`` rows."""
    return SimpleNamespace(bindings=[{"phase": p} for p in phases])


def _spo_bindings(triples: list[tuple[str, str, str]]) -> SimpleNamespace:
    """Fake SPARQL result with .bindings for ``s, p, o`` rows."""
    return SimpleNamespace(
        bindings=[{"s": s, "p": p, "o": o} for s, p, o in triples],
    )


def _po_bindings(pairs: list[tuple[str, str]]) -> SimpleNamespace:
    """Fake SPARQL result with .bindings for ``p, o`` rows."""
    return SimpleNamespace(bindings=[{"p": p, "o": o} for p, o in pairs])


def _type_bindings(types: list[str]) -> SimpleNamespace:
    """Fake SPARQL result with .bindings for ``type`` rows."""
    return SimpleNamespace(bindings=[{"type": t} for t in types])


# ===================================================================
# get_phase_facts
# ===================================================================


class TestGetPhaseFacts:
    """Tests for DashboardService.get_phase_facts()."""

    def test_groups_by_phase_and_field(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Triples with preserves-* predicates group into {phase: {field: value}}."""
        kg.query.return_value = _spo_bindings([
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}preserves-tools_found", "8"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}forRequirement", "idea10"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea10-d3", f"{PHASE_NS}preserves-quadrant", "Quick Win"),
            (f"{PHASE_NS}idea10-d3", f"{PHASE_NS}forRequirement", "idea10"),
            (f"{PHASE_NS}idea10-d3", f"{PHASE_NS}producedBy", "d3"),
        ])

        result = svc.get_phase_facts("idea10")

        assert result == {
            "d1": {"tools_found": 8},
            "d3": {"quadrant": "Quick Win"},
        }

    def test_empty_results(self, kg: MagicMock, svc: DashboardService) -> None:
        """No matching triples returns an empty dict."""
        kg.query.return_value = _spo_bindings([])

        assert svc.get_phase_facts("idea-none") == {}

    def test_sparql_exception_returns_empty(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """On SPARQL error, return empty dict."""
        kg.query.side_effect = RuntimeError("Oxigraph unavailable")

        assert svc.get_phase_facts("idea-broken") == {}

    def test_query_includes_idea_id(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """The SPARQL query embeds the idea_id in forRequirement filter."""
        kg.query.return_value = _spo_bindings([])

        svc.get_phase_facts("idea-77")

        sparql_arg = kg.query.call_args[0][0]
        assert "idea-77" in sparql_arg


# ===================================================================
# get_phase_detail
# ===================================================================


class TestGetPhaseDetail:
    """Tests for DashboardService.get_phase_detail()."""

    def test_separates_intent_from_metadata(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """preserves-* predicates become intent_fields; others become metadata."""
        kg.query.side_effect = [
            _po_bindings([
                (f"{PHASE_NS}preserves-tools_found", "16"),
                (f"{PHASE_NS}forRequirement", "idea20"),
                (f"{PHASE_NS}producedBy", "d1"),
            ]),
            # traverse_chain: no ancestors
            SimpleNamespace(bindings=[]),
            # traverse_chain: facts for starting subject
            SimpleNamespace(bindings=[]),
        ]

        result = svc.get_phase_detail("idea20", "d1")

        assert result is not None
        assert result["intent_fields"] == {"tools_found": "16"}
        assert f"{PHASE_NS}forRequirement" in result["metadata"]
        assert f"{PHASE_NS}producedBy" in result["metadata"]

    def test_returns_none_when_no_triples(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Return None if no triples exist for the subject."""
        kg.query.return_value = _po_bindings([])

        assert svc.get_phase_detail("idea-missing", "d1") is None

    def test_returns_none_on_exception(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """On SPARQL error, return None."""
        kg.query.side_effect = RuntimeError("Oxigraph unavailable")

        assert svc.get_phase_detail("idea-broken", "d2") is None

    def test_traverse_chain_error_gives_empty_ancestors(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """If traverse_chain fails, trace_ancestors is empty list."""
        kg.query.side_effect = [
            _po_bindings([
                (f"{PHASE_NS}preserves-gaps_found", "5"),
                (f"{PHASE_NS}producedBy", "d4"),
            ]),
            RuntimeError("traverse query failed"),
        ]

        result = svc.get_phase_detail("idea30", "d4")

        assert result is not None
        assert result["trace_ancestors"] == []
        assert result["intent_fields"] == {"gaps_found": "5"}

    def test_includes_phase_and_idea_ids(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Result dict contains phase_id and idea_id from the arguments."""
        kg.query.side_effect = [
            _po_bindings([
                (f"{PHASE_NS}preserves-persona_count", "3"),
                (f"{PHASE_NS}producedBy", "d2"),
            ]),
            SimpleNamespace(bindings=[]),
            SimpleNamespace(bindings=[]),
        ]

        result = svc.get_phase_detail("idea40", "d2")

        assert result is not None
        assert result["phase_id"] == "d2"
        assert result["idea_id"] == "idea40"


# ===================================================================
# resolve_uri
# ===================================================================
# @pattern:InformationHiding -- resolve_uri encapsulates rdf:type dispatch logic behind a simple tuple API


class TestResolveUri:
    """Tests for DashboardService.resolve_uri()."""

    def test_phase_output_dispatch(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """phase:PhaseOutput type maps to phase_detail route."""
        kg.query.return_value = _type_bindings([f"{PHASE_NS}PhaseOutput"])

        route, params = svc.resolve_uri(f"{PHASE_NS}idea10-d1")

        assert route == "phase_detail"
        assert params == {"uri": f"{PHASE_NS}idea10-d1"}

    def test_skos_concept_dispatch(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """skos:Concept type maps to idea_detail with extracted idea_id."""
        kg.query.return_value = _type_bindings(
            ["http://www.w3.org/2004/02/skos/core#Concept"],
        )

        route, params = svc.resolve_uri("http://example.org/ideas/idea-42")

        assert route == "idea_detail"
        assert params == {"idea_id": "idea-42"}

    def test_prd_type_dispatch(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """prd: namespace type maps to requirement_detail with context/subject."""
        kg.query.return_value = _type_bindings(
            ["http://impl-ralph.io/prd#Requirement"],
        )

        route, params = svc.resolve_uri(
            "http://example.org/prd-idea-10/req-10-1-1",
        )

        assert route == "requirement_detail"
        assert params == {"context": "prd-idea-10", "subject": "req-10-1-1"}

    def test_unknown_type_fallback(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """An unrecognized rdf:type returns generic_detail."""
        kg.query.return_value = _type_bindings(
            ["http://example.org/UnknownClass"],
        )

        route, params = svc.resolve_uri("http://example.org/something")

        assert route == "generic_detail"
        assert params == {"uri": "http://example.org/something"}

    def test_no_type_found_fallback(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """When no rdf:type triples exist, return generic_detail."""
        kg.query.return_value = _type_bindings([])

        route, params = svc.resolve_uri("http://example.org/orphan")

        assert route == "generic_detail"
        assert params == {"uri": "http://example.org/orphan"}

    def test_query_exception_fallback(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """On SPARQL error, return generic_detail."""
        kg.query.side_effect = RuntimeError("Oxigraph unavailable")

        route, params = svc.resolve_uri("http://example.org/broken")

        assert route == "generic_detail"
        assert params == {"uri": "http://example.org/broken"}

    def test_self_referential_guard(self, svc: DashboardService) -> None:
        """URIs starting with /resolve/ are rejected to prevent loops."""
        route, params = svc.resolve_uri("/resolve/http://example.org/foo")

        assert route == "generic_detail"
        svc._kg_store.query.assert_not_called()


# ===================================================================
# get_triples_for_uri
# ===================================================================


class TestGetTriplesForUri:
    """Tests for DashboardService.get_triples_for_uri()."""

    def test_returns_predicate_object_pairs(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Normal operation: returns list of {predicate, object} dicts."""
        kg.query.return_value = _po_bindings([
            (f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}forRequirement", "idea10"),
            (f"{PHASE_NS}preserves-tools_found", "8"),
        ])

        result = svc.get_triples_for_uri(f"{PHASE_NS}idea10-d1")

        assert len(result) == 3
        assert result[0] == {
            "predicate": f"{PHASE_NS}producedBy",
            "object": "d1",
        }
        assert result[2] == {
            "predicate": f"{PHASE_NS}preserves-tools_found",
            "object": "8",
        }

    def test_empty_results(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """No matching triples returns an empty list."""
        kg.query.return_value = _po_bindings([])

        assert svc.get_triples_for_uri("http://example.org/missing") == []

    def test_sparql_exception_returns_empty_list(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """On SPARQL error, return empty list."""
        kg.query.side_effect = RuntimeError("Oxigraph unavailable")

        assert svc.get_triples_for_uri("http://example.org/broken") == []

    def test_query_includes_uri_as_subject(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """The SPARQL query uses the URI as the subject in the WHERE clause."""
        kg.query.return_value = _po_bindings([])

        svc.get_triples_for_uri("http://example.org/my-resource")

        sparql_arg = kg.query.call_args[0][0]
        assert "http://example.org/my-resource" in sparql_arg


# ===================================================================
# get_iteration_facts
# ===================================================================


class TestGetIterationFacts:
    """Tests for DashboardService.get_iteration_facts()."""

    def test_extracts_intent_fields(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Known intent fields are extracted from iteration triples."""
        kg.query.return_value = _spo_bindings([
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-requirement_id", "req-5-1-1"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-passed", "true"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-commit_hash", "abc1234"),
        ])

        result = svc.get_iteration_facts("idea5")

        assert len(result) == 1
        assert result[0] == {
            "requirement_id": "req-5-1-1",
            "passed": "true",
            "commit_hash": "abc1234",
        }

    def test_multiple_iterations_ordered_by_subject(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Multiple iterations ordered alphabetically by subject URI."""
        kg.query.return_value = _spo_bindings([
            (f"{PHASE_NS}idea5-impl-2", f"{PHASE_NS}preserves-requirement_id", "req-5-1-2"),
            (f"{PHASE_NS}idea5-impl-2", f"{PHASE_NS}preserves-passed", "false"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-requirement_id", "req-5-1-1"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-passed", "true"),
        ])

        result = svc.get_iteration_facts("idea5")

        assert len(result) == 2
        assert result[0]["requirement_id"] == "req-5-1-1"
        assert result[1]["requirement_id"] == "req-5-1-2"

    def test_non_intent_predicates_excluded(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Non-intent predicates (forRequirement, producedBy, unknown) excluded."""
        kg.query.return_value = _spo_bindings([
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-requirement_id", "req-5-1-1"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}forRequirement", "idea5"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}producedBy", "impl-1"),
            (f"{PHASE_NS}idea5-impl-1", f"{PHASE_NS}preserves-unknown_field", "dropped"),
        ])

        result = svc.get_iteration_facts("idea5")

        assert len(result) == 1
        assert set(result[0].keys()) == {"requirement_id"}

    def test_empty_results(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """No matching triples returns an empty list."""
        kg.query.return_value = _spo_bindings([])

        assert svc.get_iteration_facts("idea-none") == []

    def test_sparql_exception_returns_empty_list(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """On SPARQL error, return empty list."""
        kg.query.side_effect = RuntimeError("Oxigraph unavailable")

        assert svc.get_iteration_facts("idea-broken") == []

    def test_query_uses_impl_filter(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """The SPARQL query includes STRSTARTS filter for impl- phases."""
        kg.query.return_value = _spo_bindings([])

        svc.get_iteration_facts("idea-5")

        sparql_arg = kg.query.call_args[0][0]
        assert "STRSTARTS" in sparql_arg
        assert '"impl-"' in sparql_arg


# ===================================================================
# get_requirement_phase_history
# ===================================================================
# @pattern:MVC -- Phase history is a service-layer concern; routes only render the result
# @pattern:LayeredArchitecture -- Service queries A-Box store then transforms into view-ready dicts


class TestGetRequirementPhaseHistory:
    """Tests for DashboardService.get_requirement_phase_history()."""

    def test_multiple_phase_outputs_ordered(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Phase outputs are returned ordered by subject URI with correct fields."""
        kg.query.return_value = _spo_bindings([
            # d1 output
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}forRequirement", "req-10-1-1"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}preserves-tools_found", "8"),
            # d2 output
            (f"{PHASE_NS}idea10-d2", f"{PHASE_NS}producedBy", "d2"),
            (f"{PHASE_NS}idea10-d2", f"{PHASE_NS}forRequirement", "req-10-1-1"),
            (f"{PHASE_NS}idea10-d2", f"{PHASE_NS}preserves-persona_count", "4"),
            (f"{PHASE_NS}idea10-d2", f"{PHASE_NS}preserves-timestamp", "2026-02-04T10:00:00"),
        ])

        result = svc.get_requirement_phase_history("prd-idea-10", "req-10-1-1")

        assert len(result) == 2
        assert result[0]["phase_id"] == "d1"
        assert result[0]["intent_fields"] == {"tools_found": "8"}
        assert result[0]["timestamp"] is None
        assert result[1]["phase_id"] == "d2"
        assert result[1]["intent_fields"] == {"persona_count": "4"}
        assert result[1]["timestamp"] == "2026-02-04T10:00:00"

    def test_follows_traces_to_chain(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Ancestors linked via trace:tracesTo are included in results."""
        trace_pred = "http://impl-ralph.io/trace#tracesTo"
        kg.query.side_effect = [
            # First query: forRequirement match — only d3 with tracesTo d2
            _spo_bindings([
                (f"{PHASE_NS}idea10-d3", f"{PHASE_NS}producedBy", "d3"),
                (f"{PHASE_NS}idea10-d3", f"{PHASE_NS}forRequirement", "req-10-1-1"),
                (f"{PHASE_NS}idea10-d3", f"{PHASE_NS}preserves-quadrant", "Major"),
                (f"{PHASE_NS}idea10-d3", trace_pred, f"{PHASE_NS}idea10-d2"),
            ]),
            # Second query: ancestor d2's triples
            _po_bindings([
                (f"{PHASE_NS}producedBy", "d2"),
                (f"{PHASE_NS}preserves-persona_count", "4"),
            ]),
        ]

        result = svc.get_requirement_phase_history("prd-idea-10", "req-10-1-1")

        assert len(result) == 2
        assert result[0]["phase_id"] == "d2"
        assert result[0]["intent_fields"] == {"persona_count": "4"}
        assert result[1]["phase_id"] == "d3"
        assert result[1]["intent_fields"] == {"quadrant": "Major"}

    def test_empty_results(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """No matching triples returns an empty list."""
        kg.query.return_value = _spo_bindings([])

        assert svc.get_requirement_phase_history("prd-idea-999", "req-none") == []

    def test_sparql_exception_returns_empty_list(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """On SPARQL error, return empty list."""
        kg.query.side_effect = RuntimeError("Oxigraph unavailable")

        assert svc.get_requirement_phase_history("prd-broken", "req-broken") == []

    def test_result_contains_required_keys(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Every item has phase_id, produced_by, intent_fields, and timestamp."""
        kg.query.return_value = _spo_bindings([
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}forRequirement", "req-10-1-1"),
        ])

        result = svc.get_requirement_phase_history("prd-idea-10", "req-10-1-1")

        assert len(result) == 1
        assert set(result[0].keys()) == {
            "phase_id", "produced_by", "intent_fields", "timestamp",
        }

    def test_metadata_excluded_from_intent_fields(
        self, kg: MagicMock, svc: DashboardService,
    ) -> None:
        """Non-preserves predicates (rdf:type, forRequirement) excluded from intent_fields."""
        rdf_type = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        kg.query.return_value = _spo_bindings([
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}forRequirement", "req-10-1-1"),
            (f"{PHASE_NS}idea10-d1", f"{PHASE_NS}preserves-tools_found", "8"),
            (f"{PHASE_NS}idea10-d1", rdf_type, f"{PHASE_NS}PhaseOutput"),
        ])

        result = svc.get_requirement_phase_history("prd-idea-10", "req-10-1-1")

        assert len(result) == 1
        assert result[0]["intent_fields"] == {"tools_found": "8"}
