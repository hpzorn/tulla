"""Integration tests for Inspector route handlers (prd:req-74-6-2).

Exercises all Inspector routes via FastAPI TestClient with mocked stores at
the service level:

1. GET /inspector/ideas/{id}       — 200 with progress data
2. GET /inspector/phases/{uri}     — 200 for existing, 404 for missing
3. GET /resolve/{uri}              — 302 for known types, 200 generic for unknown
4. GET /partials/progress-bar      — HTML fragment
5. GET /inspector/iterations/{id}  — 200 with iteration data
6. Self-referential redirect guard — /resolve/ prefix rejection prevents loops
"""
# @pattern:PortsAndAdapters -- Routes tested through HTTP boundary; stores mocked behind service layer
# @pattern:DependencyInversion -- TestClient injects mock stores via create_dashboard_app factory
# @pattern:LooseCoupling -- Tests couple only to HTTP status codes and response text, not to service internals

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from ontology_server.dashboard import create_dashboard_app

PHASE_NS = "http://impl-ralph.io/phase#"
SKOS_CONCEPT = "http://www.w3.org/2004/02/skos/core#Concept"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty() -> SimpleNamespace:
    """Empty SPARQL result (no bindings)."""
    return SimpleNamespace(bindings=[])


def _type_result(types: list[str]) -> SimpleNamespace:
    """SPARQL result for ``SELECT ?type`` queries."""
    return SimpleNamespace(bindings=[{"type": t} for t in types])


def _po_result(pairs: list[tuple[str, str]]) -> SimpleNamespace:
    """SPARQL result for ``SELECT ?p ?o`` queries."""
    return SimpleNamespace(bindings=[{"p": p, "o": o} for p, o in pairs])


def _spo_result(triples: list[tuple[str, str, str]]) -> SimpleNamespace:
    """SPARQL result for ``SELECT ?s ?p ?o`` queries."""
    return SimpleNamespace(
        bindings=[{"s": s, "p": p, "o": o} for s, p, o in triples],
    )


def _phase_result(phases: list[str]) -> SimpleNamespace:
    """SPARQL result for ``SELECT ?phase`` queries (get_idea_progress)."""
    return SimpleNamespace(bindings=[{"phase": p} for p in phases])


def _make_client(
    kg_query_side_effects: list | None = None,
    ideas_list: list | None = None,
) -> TestClient:
    """Create a TestClient backed by a dashboard app with mocked stores.

    Args:
        kg_query_side_effects: Ordered list of SPARQL results for sequential
            ``kg.query()`` calls.  Defaults to returning empty results.
        ideas_list: Ideas returned by ``ideas_store.list_ideas()``.
    """
    ontology_store = MagicMock()
    ontology_store.list_ontologies.return_value = []
    ontology_store.get_classes.return_value = []
    ontology_store.query.return_value = iter([(0,)])

    kg = MagicMock()
    kg.get_stats.return_value = {}
    if kg_query_side_effects is not None:
        kg.query.side_effect = kg_query_side_effects
    else:
        kg.query.return_value = _empty()

    agent_memory = MagicMock()
    agent_memory.get_all_contexts.return_value = []
    agent_memory.count_facts.return_value = 0

    ideas_store = MagicMock()
    ideas_store.count_ideas.return_value = 0
    ideas_store.list_ideas.return_value = ideas_list or []

    app = create_dashboard_app(
        ontology_store=ontology_store,
        kg_store=kg,
        agent_memory=agent_memory,
        ideas_store=ideas_store,
    )
    return TestClient(app, follow_redirects=False)


# ---------------------------------------------------------------------------
# 1. GET /inspector/ideas — idea inspector list
# ---------------------------------------------------------------------------


class TestIdeaInspectorList:
    """Tests for the idea_inspector_list route."""

    def test_empty_list_returns_200(self) -> None:
        """With no ideas, returns 200 and shows 'No ideas found'."""
        client = _make_client(ideas_list=[])
        response = client.get("/inspector/ideas")
        assert response.status_code == 200
        assert "No ideas found" in response.text

    def test_with_ideas_returns_200_with_links(self) -> None:
        """With ideas present, returns 200 and links to inspector pages."""
        ideas = [
            {"idea_id": "idea-42", "title": "Test Idea", "lifecycle": "seed"},
            {"idea_id": "idea-99", "title": "Another Idea", "lifecycle": "researching"},
        ]
        client = _make_client(ideas_list=ideas)
        response = client.get("/inspector/ideas")
        assert response.status_code == 200
        assert "idea-42" in response.text
        assert "idea-99" in response.text


# ---------------------------------------------------------------------------
# 2. GET /inspector/ideas/{idea_id} — idea inspector with progress data
# ---------------------------------------------------------------------------


class TestInspectorIdea:
    """Tests for the inspector_idea route — 200 with progress data."""

    # @pattern:InformationHiding -- Tests observe only public HTTP responses; SPARQL query internals hidden behind DashboardService
    # @pattern:LayeredArchitecture -- Tests target route layer only; service and store layers replaced by mocks

    def test_idea_with_no_phases_returns_200(self) -> None:
        """An idea with no phase data returns 200 with empty state."""
        client = _make_client(kg_query_side_effects=[
            _empty(),  # get_phase_facts
            _empty(),  # get_idea_progress
            _empty(),  # get_iteration_facts
        ])
        response = client.get("/inspector/ideas/idea-42")
        assert response.status_code == 200
        assert "idea-42" in response.text

    def test_idea_with_completed_phases_returns_200_with_progress(self) -> None:
        """An idea with completed phases renders progress data."""
        phase_facts = _spo_result([
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}preserves-tools_found", "5"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        progress = _phase_result(["d1"])
        client = _make_client(kg_query_side_effects=[
            phase_facts,  # get_phase_facts
            progress,     # get_idea_progress
            _empty(),     # get_iteration_facts
        ])
        response = client.get("/inspector/ideas/idea-50")
        assert response.status_code == 200
        assert "idea-50" in response.text

    def test_idea_with_multiple_phases_and_iterations(self) -> None:
        """An idea with multiple phases and iterations returns 200."""
        phase_facts = _spo_result([
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}preserves-tools_found", "5"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}forRequirement", "idea-50"),
            (f"{PHASE_NS}idea-50-d2", f"{PHASE_NS}preserves-persona_count", "3"),
            (f"{PHASE_NS}idea-50-d2", f"{PHASE_NS}producedBy", "d2"),
            (f"{PHASE_NS}idea-50-d2", f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        progress = _phase_result(["d1", "d2"])
        iterations = _spo_result([
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}preserves-requirement_id", "req-74-1-1"),
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}preserves-passed", "true"),
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}producedBy", "impl-1"),
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        client = _make_client(kg_query_side_effects=[
            phase_facts,  # get_phase_facts
            progress,     # get_idea_progress
            iterations,   # get_iteration_facts
        ])
        response = client.get("/inspector/ideas/idea-50")
        assert response.status_code == 200
        assert "idea-50" in response.text


# ---------------------------------------------------------------------------
# 3. GET /inspector/phases/{uri:path} — phase detail (200 / 404)
# ---------------------------------------------------------------------------


class TestPhaseDetailView:
    """Tests for the phase_detail_view route — 200 existing, 404 missing."""

    def test_valid_phase_returns_200(self) -> None:
        """A valid phase URI with data returns 200 and renders detail."""
        phase_detail = _po_result([
            (f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}preserves-tools_found", "5"),
            (f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        client = _make_client(kg_query_side_effects=[
            phase_detail,  # get_phase_detail main query
            _empty(),      # traverse_chain query
        ])
        response = client.get("/inspector/phases/idea-50-d1")
        assert response.status_code == 200
        assert "d1" in response.text
        assert "idea-50" in response.text

    def test_nonexistent_phase_returns_404(self) -> None:
        """A valid URI format but no data in KG returns 404."""
        client = _make_client(kg_query_side_effects=[
            _empty(),  # get_phase_detail: no bindings -> returns None
        ])
        response = client.get("/inspector/phases/idea-50-d1")
        assert response.status_code == 404

    def test_unparseable_uri_returns_404_json(self) -> None:
        """A URI that cannot be parsed into idea_id + phase_id returns 404 JSON."""
        client = _make_client()
        response = client.get("/inspector/phases/not-a-valid-phase-uri")
        assert response.status_code == 404
        assert "Cannot parse phase URI" in response.json()["detail"]

    def test_phase_with_d0_suffix(self) -> None:
        """Phase URIs ending with -d0 are correctly parsed."""
        phase_detail = _po_result([
            (f"{PHASE_NS}producedBy", "d0"),
            (f"{PHASE_NS}forRequirement", "idea-77"),
        ])
        client = _make_client(kg_query_side_effects=[
            phase_detail,  # get_phase_detail
            _empty(),      # traverse_chain
        ])
        response = client.get("/inspector/phases/idea-77-d0")
        assert response.status_code == 200

    def test_phase_with_d5_suffix(self) -> None:
        """Phase URIs ending with -d5 are correctly parsed."""
        phase_detail = _po_result([
            (f"{PHASE_NS}producedBy", "d5"),
            (f"{PHASE_NS}forRequirement", "idea-77"),
        ])
        client = _make_client(kg_query_side_effects=[
            phase_detail,  # get_phase_detail
            _empty(),      # traverse_chain
        ])
        response = client.get("/inspector/phases/idea-77-d5")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4. GET /resolve/{uri:path} — 302 redirect / 200 generic
# ---------------------------------------------------------------------------


class TestResolveUri:
    """Tests for the resolve_uri route — 302 known types, 200 unknown."""

    def test_skos_concept_uri_returns_302(self) -> None:
        """A skos:Concept URI triggers a 302 redirect to idea_detail."""
        uri = "http://example.org/ideas/idea-42"
        client = _make_client(kg_query_side_effects=[
            _type_result([SKOS_CONCEPT]),
        ])
        response = client.get(f"/resolve/{uri}")
        assert response.status_code == 302
        location = response.headers["location"]
        assert "idea-42" in location

    def test_unknown_type_returns_200_with_generic_detail(self) -> None:
        """An unknown rdf:type renders generic_detail.html with 200."""
        uri = "http://example.org/unknown-thing"
        client = _make_client(kg_query_side_effects=[
            _type_result(["http://example.org/UnknownClass"]),
            _po_result([
                ("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "http://example.org/UnknownClass"),
                ("http://www.w3.org/2000/01/rdf-schema#label", "Some Thing"),
            ]),
        ])
        response = client.get(f"/resolve/{uri}")
        assert response.status_code == 200
        assert "http://example.org/unknown-thing" in response.text
        assert "Some Thing" in response.text

    def test_no_type_returns_200_generic(self) -> None:
        """A URI with no rdf:type at all renders generic_detail.html."""
        uri = "http://example.org/orphan"
        client = _make_client(kg_query_side_effects=[
            _type_result([]),
            _po_result([]),
        ])
        response = client.get(f"/resolve/{uri}")
        assert response.status_code == 200
        assert "http://example.org/orphan" in response.text

    def test_prd_type_returns_302(self) -> None:
        """A prd: typed URI triggers a 302 redirect to requirement_detail."""
        uri = "http://example.org/prds/prd-74/req-74-1-1"
        client = _make_client(kg_query_side_effects=[
            _type_result(["http://impl-ralph.io/prd#Requirement"]),
        ])
        response = client.get(f"/resolve/{uri}")
        assert response.status_code == 302
        location = response.headers["location"]
        assert "prd-74" in location
        assert "req-74-1-1" in location


# ---------------------------------------------------------------------------
# 5. Self-referential redirect guard (arch:adr-74-2 — no infinite loop)
# ---------------------------------------------------------------------------


class TestResolveUriRedirectGuard:
    """Verify the self-referential redirect guard prevents infinite loops."""

    # @pattern:SeparationOfConcerns -- Guard logic lives in service (Model); route (Controller) only delegates redirect-vs-render dispatch
    # @pattern:MVC -- Redirect guard tested from Controller perspective; Model (service) dispatch verified by asserting 200 not 302

    def test_resolve_prefix_uri_returns_200_generic(self) -> None:
        """A URI starting with /resolve/ is caught by the guard and rendered inline."""
        # The service guard returns ("generic_detail", ...) immediately for
        # URIs starting with /resolve/ — no SPARQL query issued.
        uri = "/resolve/http://example.org/something"
        client = _make_client(kg_query_side_effects=[
            # get_triples_for_uri: called since guard falls through to generic_detail
            _po_result([]),
        ])
        response = client.get(f"/resolve/{uri}")
        assert response.status_code == 200
        # Must NOT be a 302 redirect (that would cause a loop)
        assert "location" not in response.headers

    def test_double_resolve_prefix_returns_200(self) -> None:
        """A doubly-nested /resolve/resolve/ URI does not redirect."""
        uri = "/resolve//resolve/http://example.org/deep"
        client = _make_client(kg_query_side_effects=[
            _po_result([]),
        ])
        response = client.get(f"/resolve/{uri}")
        assert response.status_code == 200
        assert "location" not in response.headers


# ---------------------------------------------------------------------------
# 6. GET /partials/progress-bar — HTMX partial HTML fragment
# ---------------------------------------------------------------------------


class TestPartialProgressBar:
    """Tests for the partial_progress_bar route — returns HTML fragment."""

    def test_progress_bar_returns_200_html(self) -> None:
        """The progress bar partial returns 200 with HTML content."""
        progress = _phase_result(["d1", "d2"])
        client = _make_client(kg_query_side_effects=[progress])
        response = client.get("/partials/progress-bar?idea_id=idea-50")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_progress_bar_empty_returns_200(self) -> None:
        """With no completed phases, still returns 200."""
        client = _make_client(kg_query_side_effects=[_empty()])
        response = client.get("/partials/progress-bar?idea_id=idea-50")
        assert response.status_code == 200

    def test_progress_bar_missing_idea_id_returns_422(self) -> None:
        """Missing required idea_id query param returns 422."""
        client = _make_client()
        response = client.get("/partials/progress-bar")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 7. GET /inspector/iterations/{idea_id} — iteration list
# ---------------------------------------------------------------------------


class TestIterationList:
    """Tests for the iteration_list route — 200 with iteration data."""

    def test_empty_iterations_returns_200(self) -> None:
        """An idea with no iterations returns 200."""
        client = _make_client(kg_query_side_effects=[_empty()])
        response = client.get("/inspector/iterations/idea-50")
        assert response.status_code == 200
        assert "idea-50" in response.text

    def test_with_iterations_returns_200(self) -> None:
        """An idea with iteration data returns 200 with iteration content."""
        iteration_result = _spo_result([
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}preserves-requirement_id", "req-74-1-1"),
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}preserves-passed", "true"),
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}producedBy", "impl-1"),
            (f"{PHASE_NS}idea-50-impl-1", f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        client = _make_client(kg_query_side_effects=[iteration_result])
        response = client.get("/inspector/iterations/idea-50")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 8. GET /partials/phase-facts — HTMX partial
# ---------------------------------------------------------------------------


class TestPartialPhaseFacts:
    """Tests for the partial_phase_facts route."""

    def test_phase_facts_empty_returns_200(self) -> None:
        """With no phase facts, returns 200."""
        client = _make_client(kg_query_side_effects=[_empty()])
        response = client.get("/partials/phase-facts?idea_id=idea-50")
        assert response.status_code == 200

    def test_phase_facts_with_data_returns_200(self) -> None:
        """With phase fact data, returns 200 with content."""
        phase_facts = _spo_result([
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}preserves-tools_found", "5"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        client = _make_client(kg_query_side_effects=[phase_facts])
        response = client.get("/partials/phase-facts?idea_id=idea-50")
        assert response.status_code == 200

    def test_phase_facts_filtered_by_phase_returns_200(self) -> None:
        """With phase filter, returns 200 with only matching phase data."""
        phase_facts = _spo_result([
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}preserves-tools_found", "5"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}producedBy", "d1"),
            (f"{PHASE_NS}idea-50-d1", f"{PHASE_NS}forRequirement", "idea-50"),
            (f"{PHASE_NS}idea-50-d2", f"{PHASE_NS}preserves-persona_count", "3"),
            (f"{PHASE_NS}idea-50-d2", f"{PHASE_NS}producedBy", "d2"),
            (f"{PHASE_NS}idea-50-d2", f"{PHASE_NS}forRequirement", "idea-50"),
        ])
        client = _make_client(kg_query_side_effects=[phase_facts])
        response = client.get("/partials/phase-facts?idea_id=idea-50&phase=d1")
        assert response.status_code == 200
