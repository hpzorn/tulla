"""pyshacl validation test for isaqb:ADRScopeCoherenceShape.

Verification criteria (prd:req-69-3-1):
  Create a test graph with 3 ADRs:
    1. One project-scope addressing Maintainability
    2. One idea-scope addressing Maintainability WITHOUT refinesDecision/supersedes
       (should trigger warning)
    3. One idea-scope with refinesDecision link (should NOT trigger warning)
  Run pyshacl validation.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

ISAQB = Namespace("http://impl-ralph.io/isaqb#")
SH = Namespace("http://www.w3.org/ns/shacl#")

SHAPES_PATH = "ontologies/isaqb-ontology.ttl"


def _build_shapes_graph() -> Graph:
    """Load the isaqb-ontology.ttl as the SHACL shapes graph."""
    g = Graph()
    g.parse(SHAPES_PATH, format="turtle")
    return g


def _build_data_graph() -> Graph:
    """Build a test data graph with 3 ADRs per the verification criteria."""
    g = Graph()
    g.bind("isaqb", ISAQB)
    g.bind("rdfs", RDFS)

    maintainability = ISAQB["Maintainability"]
    g.add((maintainability, RDF.type, ISAQB["QualityAttribute"]))
    g.add((maintainability, RDFS.label, Literal("Maintainability")))

    # ADR 1: project-scope, addresses Maintainability
    adr_project = ISAQB["adr-project-maint"]
    g.add((adr_project, RDF.type, ISAQB["ArchitectureDecision"]))
    g.add((adr_project, RDFS.label, Literal("Use Layered Architecture")))
    g.add((adr_project, ISAQB["scope"], Literal("project")))
    g.add((adr_project, ISAQB["addresses"], maintainability))
    g.add((adr_project, ISAQB["context"], Literal("Project needs maintainability")))
    g.add((adr_project, ISAQB["rationale"], Literal("Layered arch is proven")))
    g.add((adr_project, ISAQB["consequences"], Literal("(+) Clear boundaries")))
    g.add((adr_project, ISAQB["decisionStatus"], ISAQB["Accepted"]))
    opt1 = ISAQB["opt-project-1"]
    opt2 = ISAQB["opt-project-2"]
    g.add((opt1, RDF.type, ISAQB["DecisionOption"]))
    g.add((opt2, RDF.type, ISAQB["DecisionOption"]))
    g.add((adr_project, ISAQB["hasOption"], opt1))
    g.add((adr_project, ISAQB["hasOption"], opt2))

    # ADR 2: idea-scope, addresses Maintainability, NO refinesDecision/supersedes
    # -> Should trigger ADRScopeCoherenceShape warning
    adr_idea_unlinked = ISAQB["adr-idea-unlinked"]
    g.add((adr_idea_unlinked, RDF.type, ISAQB["ArchitectureDecision"]))
    g.add((adr_idea_unlinked, RDFS.label, Literal("Use Plugin Pattern")))
    g.add((adr_idea_unlinked, ISAQB["scope"], Literal("idea")))
    g.add((adr_idea_unlinked, ISAQB["addresses"], maintainability))
    g.add((adr_idea_unlinked, ISAQB["context"], Literal("Feature needs extensibility")))
    g.add((adr_idea_unlinked, ISAQB["rationale"], Literal("Plugins are flexible")))
    g.add((adr_idea_unlinked, ISAQB["consequences"], Literal("(+) Easy to extend")))
    g.add((adr_idea_unlinked, ISAQB["decisionStatus"], ISAQB["Accepted"]))
    opt3 = ISAQB["opt-idea-unlinked-1"]
    opt4 = ISAQB["opt-idea-unlinked-2"]
    g.add((opt3, RDF.type, ISAQB["DecisionOption"]))
    g.add((opt4, RDF.type, ISAQB["DecisionOption"]))
    g.add((adr_idea_unlinked, ISAQB["hasOption"], opt3))
    g.add((adr_idea_unlinked, ISAQB["hasOption"], opt4))

    # ADR 3: idea-scope, addresses Maintainability, WITH refinesDecision link
    # -> Should NOT trigger ADRScopeCoherenceShape warning
    adr_idea_linked = ISAQB["adr-idea-linked"]
    g.add((adr_idea_linked, RDF.type, ISAQB["ArchitectureDecision"]))
    g.add((adr_idea_linked, RDFS.label, Literal("Use Adapter Pattern")))
    g.add((adr_idea_linked, ISAQB["scope"], Literal("idea")))
    g.add((adr_idea_linked, ISAQB["addresses"], maintainability))
    g.add((adr_idea_linked, ISAQB["refinesDecision"], adr_project))
    g.add((adr_idea_linked, ISAQB["context"], Literal("Feature needs adapters")))
    g.add((adr_idea_linked, ISAQB["rationale"], Literal("Adapters decouple")))
    g.add((adr_idea_linked, ISAQB["consequences"], Literal("(+) Loose coupling")))
    g.add((adr_idea_linked, ISAQB["decisionStatus"], ISAQB["Accepted"]))
    opt5 = ISAQB["opt-idea-linked-1"]
    opt6 = ISAQB["opt-idea-linked-2"]
    g.add((opt5, RDF.type, ISAQB["DecisionOption"]))
    g.add((opt6, RDF.type, ISAQB["DecisionOption"]))
    g.add((adr_idea_linked, ISAQB["hasOption"], opt5))
    g.add((adr_idea_linked, ISAQB["hasOption"], opt6))

    return g


class TestADRScopeCoherenceShape:
    """Validate ADRScopeCoherenceShape using pyshacl."""

    def test_shape_exists_in_ontology(self) -> None:
        """ADRScopeCoherenceShape is defined as a sh:NodeShape."""
        shapes = _build_shapes_graph()
        shape_uri = ISAQB["ADRScopeCoherenceShape"]
        assert (shape_uri, RDF.type, SH["NodeShape"]) in shapes

    def test_shape_severity_is_warning_on_nodeshape(self) -> None:
        """sh:severity sh:Warning is on the NodeShape itself, not the sparql bnode."""
        shapes = _build_shapes_graph()
        shape_uri = ISAQB["ADRScopeCoherenceShape"]
        assert (shape_uri, SH["severity"], SH["Warning"]) in shapes

    def test_unlinked_idea_adr_triggers_warning(self) -> None:
        """An idea-scope ADR sharing a quality attribute with a project-scope ADR
        but having no refinesDecision/supersedes link triggers a warning."""
        import pyshacl

        shapes = _build_shapes_graph()
        data = _build_data_graph()

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        # The unlinked idea-scope ADR should produce a violation
        unlinked_uri = ISAQB["adr-idea-unlinked"]
        violations_for_unlinked = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            if focus and focus[0] == unlinked_uri:
                violations_for_unlinked.append(result)

        assert len(violations_for_unlinked) >= 1, (
            f"Expected at least 1 warning for unlinked idea-scope ADR, "
            f"got {len(violations_for_unlinked)}.\n"
            f"Full results:\n{results_text}"
        )

        # Verify the violation message mentions the project ADR title
        for v in violations_for_unlinked:
            msgs = list(results_graph.objects(v, SH["resultMessage"]))
            msg_text = str(msgs[0]) if msgs else ""
            assert "Use Layered Architecture" in msg_text, (
                f"Warning message should include project ADR title, got: {msg_text}"
            )

    def test_linked_idea_adr_does_not_trigger_warning(self) -> None:
        """An idea-scope ADR with a refinesDecision link does NOT trigger
        the ADRScopeCoherenceShape warning."""
        import pyshacl

        shapes = _build_shapes_graph()
        data = _build_data_graph()

        _conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        linked_uri = ISAQB["adr-idea-linked"]
        violations_for_linked = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            source = list(results_graph.objects(result, SH["sourceShape"]))
            if (
                focus
                and focus[0] == linked_uri
                and source
                and source[0] == ISAQB["ADRScopeCoherenceShape"]
            ):
                violations_for_linked.append(result)

        assert len(violations_for_linked) == 0, (
            f"Expected no warnings for linked idea-scope ADR, "
            f"got {len(violations_for_linked)}.\n"
            f"Full results:\n{results_text}"
        )

    def test_project_adr_does_not_trigger_warning(self) -> None:
        """A project-scope ADR does NOT trigger the ADRScopeCoherenceShape warning."""
        import pyshacl

        shapes = _build_shapes_graph()
        data = _build_data_graph()

        _conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        project_uri = ISAQB["adr-project-maint"]
        violations_for_project = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            source = list(results_graph.objects(result, SH["sourceShape"]))
            if (
                focus
                and focus[0] == project_uri
                and source
                and source[0] == ISAQB["ADRScopeCoherenceShape"]
            ):
                violations_for_project.append(result)

        assert len(violations_for_project) == 0, (
            f"Expected no warnings for project-scope ADR, "
            f"got {len(violations_for_project)}.\n"
            f"Full results:\n{results_text}"
        )
