"""Live SHACL validation: LightweightTraceResult through PhaseFactPersister.

# @pattern:PortsAndAdapters -- Tests inject OntologyMCPAdapter through OntologyPort ABC so the persister never knows the concrete adapter
# @principle:DependencyInversion -- PhaseFactPersister constructor accepts OntologyPort; live vs. wrapper adapter chosen at test boundary
# @pattern:MVC -- LightweightTraceResult (Model) validated independently of phase controllers and CLI view layer
# @pattern:LayeredArchitecture -- Test imports cross layers: models (domain), phase_facts (core), ontology port (ports), adapter (infra)
# @principle:SeparationOfConcerns -- Helper _make_trace_result isolates test-data construction from persistence and validation assertions
# @principle:InformationHiding -- get_shape_for_phase hides the SHACL registry lookup; tests never reference shape URIs directly
# @principle:LooseCoupling -- _FailingValidationWrapper delegates all calls except validate_instance, proving persister has no hidden adapter dependencies
# @quality:Testability -- @pytest.mark.manual marker allows CI to skip server-dependent tests while enabling explicit local validation

Verification criteria (prd:req-53-5-3):
  Test that a LightweightTraceResult persisted through PhaseFactPersister
  passes LWTraceOutputShape validation against a running ontology-server.

  Happy path: all required fields present, validation passes.
  Failure path: missing a required field, validation fails and triggers rollback.

Architecture decision: arch:adr-53-4
Quality focus: isaqb:Testability

Run with: ``pytest -m manual tests/phases/lightweight/test_shacl.py``
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import PhaseFactPersister
from tulla.namespaces import PHASE_NS, RDF_TYPE
from tulla.ontology.phase_shapes import get_shape_for_phase
from tulla.phases.lightweight.models import LightweightTraceResult
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The 7 predicates required by LWTraceOutputShape (phase-ontology.ttl)
_LW_TRACE_REQUIRED_PREDICATES = {
    f"{PHASE_NS}producedBy",
    f"{PHASE_NS}preserves-change_type",
    f"{PHASE_NS}preserves-affected_files",
    f"{PHASE_NS}preserves-conformance_assertion",
    f"{PHASE_NS}preserves-commit_ref",
    f"{PHASE_NS}preserves-change_summary",
    f"{PHASE_NS}preserves-timestamp",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trace_result(**overrides: Any) -> LightweightTraceResult:
    """Build a LightweightTraceResult with all 6 required fields populated."""
    defaults: dict[str, Any] = {
        "change_type": "bugfix",
        "affected_files": "src/parser.py,tests/test_parser.py",
        "conformance_assertion": "structural-only:clean",
        "commit_ref": "abc1234",
        "change_summary": "Fixed parser edge case for nested brackets",
        "timestamp": "2025-06-15T10:30:00+00:00",
    }
    defaults.update(overrides)
    return LightweightTraceResult(**defaults)


def _violations_for_focus_node(
    validation_result: dict[str, Any],
    focus_node: str,
) -> list[str]:
    """Extract violations whose focus_node matches the given URI.

    The live ontology-server returns violations from ALL SHACL shapes
    targeting phase:PhaseOutput.  This helper filters to violations
    relevant to a specific instance so tests can assert on only the
    LWTraceOutputShape constraints for their own test subject.
    """
    violations = validation_result.get("violations", [])
    relevant: list[str] = []
    for v in violations:
        v_str = str(v)
        if focus_node in v_str:
            relevant.append(v_str)
    return relevant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Custom marker for tests requiring a running ontology-server
manual = pytest.mark.manual


@pytest.fixture()
def ontology() -> OntologyPort:
    """Create a live OntologyMCPAdapter, skip if server unavailable."""
    try:
        from tulla.adapters.ontology_mcp import OntologyMCPAdapter
        adapter = OntologyMCPAdapter()
        # Health check — light query to confirm server is reachable
        adapter.recall_facts(predicate="rdf:type", limit=1)
        return adapter
    except Exception as exc:
        pytest.skip(f"ontology-server not available: {exc}")


@pytest.fixture()
def persister(ontology: OntologyPort) -> PhaseFactPersister:
    """Create a PhaseFactPersister backed by the live ontology adapter."""
    return PhaseFactPersister(ontology)


# ---------------------------------------------------------------------------
# Tests: live SHACL validation via ontology-server
# ---------------------------------------------------------------------------


@manual
class TestLiveSHACLValidation:
    """Integration test: LightweightTraceResult triples pass LWTraceOutputShape
    validation against a running ontology-server.

    Requires: ontology-server running at http://localhost:8100 (default)
    with the phase-ontology loaded (including LWTraceOutputShape).
    """

    # --- Happy path ---

    def test_complete_trace_result_passes_live_validation(
        self,
        ontology: OntologyPort,
        persister: PhaseFactPersister,
    ) -> None:
        """A fully-populated LightweightTraceResult passes LWTraceOutputShape
        on the live ontology-server SHACL engine.

        The server validates against all shapes targeting phase:PhaseOutput,
        so we filter violations to our test subject to check LW-trace conformance."""
        subject = f"{PHASE_NS}test-shacl-53-lw-trace"
        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        shape_uri = get_shape_for_phase("lw-trace")
        assert shape_uri is not None, "LWTraceOutputShape must be registered"

        # Persist with validation — server may report non-conformance due to
        # other shapes' violations on other instances in the graph.
        # We validate ourselves by checking violations for OUR focus_node.
        persister.persist(
            idea_id="test-shacl-53",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,  # persist without automated validation first
        )

        try:
            # Now validate directly and filter to our instance
            result = ontology.validate_instance(subject, shape_uri)
            our_violations = _violations_for_focus_node(result, subject)

            # Our instance should have no LW-trace-required-property violations
            lw_violations = [
                v for v in our_violations
                if any(pred.split("#")[-1] in v for pred in _LW_TRACE_REQUIRED_PREDICATES)
            ]
            assert len(lw_violations) == 0, (
                f"Expected no LWTraceOutputShape violations for our instance, "
                f"got: {lw_violations}"
            )
        finally:
            # Cleanup: always remove test triples
            ontology.remove_triples_by_subject(subject)

    def test_complete_trace_with_optional_fields_passes(
        self,
        ontology: OntologyPort,
        persister: PhaseFactPersister,
    ) -> None:
        """Optional fields (issue_ref, sprint_id, story_points) do not
        invalidate LWTraceOutputShape — extra triples are ignored by SHACL."""
        subject = f"{PHASE_NS}test-shacl-53-opt-lw-trace"
        trace_result = _make_trace_result(
            issue_ref="PROJ-42",
            sprint_id="sprint-7",
            story_points="3",
        )
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        persister.persist(
            idea_id="test-shacl-53-opt",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        try:
            shape_uri = get_shape_for_phase("lw-trace")
            result = ontology.validate_instance(subject, shape_uri)
            our_violations = _violations_for_focus_node(result, subject)

            lw_violations = [
                v for v in our_violations
                if any(pred.split("#")[-1] in v for pred in _LW_TRACE_REQUIRED_PREDICATES)
            ]
            assert len(lw_violations) == 0, (
                f"Optional fields should not cause LW-trace violations: {lw_violations}"
            )
        finally:
            ontology.remove_triples_by_subject(subject)

    def test_persisted_triples_include_all_required_predicates(
        self,
        ontology: OntologyPort,
        persister: PhaseFactPersister,
    ) -> None:
        """PhaseFactPersister stores triples covering all 7 predicates
        required by LWTraceOutputShape (producedBy + 6 preserves-* fields)."""
        subject = f"{PHASE_NS}test-shacl-53-pred-lw-trace"
        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        result = persister.persist(
            idea_id="test-shacl-53-pred",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        try:
            # stored_count = 1 (rdf:type) + 9 (all intent fields incl. optional)
            #              + 2 (producedBy + forRequirement) = 12
            assert result.stored_count >= 9, (
                f"Expected at least 9 triples, got {result.stored_count}"
            )

            # Verify via SPARQL that all required predicates are present
            query = (
                f"PREFIX phase: <{PHASE_NS}>\n"
                f"SELECT ?p WHERE {{\n"
                f"  <{subject}> ?p ?o .\n"
                f"}}"
            )
            sparql_result = ontology.sparql_query(query)
            predicates = {
                b.get("p", "") for b in sparql_result.get("results", [])
            }

            for required in _LW_TRACE_REQUIRED_PREDICATES:
                assert required in predicates, (
                    f"Missing required predicate {required} in persisted triples"
                )
        finally:
            ontology.remove_triples_by_subject(subject)

    # --- Failure path ---

    def test_missing_required_field_fails_validation(
        self,
        ontology: OntologyPort,
    ) -> None:
        """When a required triple is absent, SHACL validation reports
        non-conformance for that instance.

        Strategy: manually construct a minimal set of triples with ONLY
        rdf:type (to activate shape targeting) but NO preserves-* fields
        and NO producedBy — so every LWTraceOutputShape property constraint
        is violated.  The server validates against all shapes targeting
        phase:PhaseOutput; we confirm our focus_node has violations."""
        subject = f"{PHASE_NS}test-shacl-53-fail-lw-trace"

        # Ensure clean slate
        ontology.remove_triples_by_subject(subject)

        try:
            # Add ONLY rdf:type — all required properties are missing
            ontology.add_triple(subject, RDF_TYPE, f"{PHASE_NS}PhaseOutput")

            # Validate the incomplete instance
            shape_uri = get_shape_for_phase("lw-trace")
            result = ontology.validate_instance(subject, shape_uri)

            # The server must report non-conformance
            assert result.get("conforms") is False, (
                "Expected validation to fail for instance missing all required fields"
            )

            # Our focus_node must appear in at least one violation
            our_violations = _violations_for_focus_node(result, subject)
            assert len(our_violations) >= 1, (
                f"Expected violations for {subject}, got none"
            )
        finally:
            ontology.remove_triples_by_subject(subject)

    def test_persister_rollback_on_validation_failure(
        self,
        ontology: OntologyPort,
    ) -> None:
        """PhaseFactPersister rolls back triples when validate_instance reports
        non-conformance. Uses a thin wrapper to inject a validation failure."""

        class _FailingValidationWrapper(OntologyPort):
            """Delegates all calls to the real adapter except validate_instance,
            which always returns a non-conforming result to trigger rollback."""

            def __init__(self, delegate: OntologyPort) -> None:
                self._delegate = delegate
                self.removed_subjects: list[str] = []

            def add_triple(self, subject: str, predicate: str, object: str,
                           *, is_literal: bool = False,
                           ontology: str | None = None) -> dict[str, Any]:
                return self._delegate.add_triple(
                    subject, predicate, object,
                    is_literal=is_literal, ontology=ontology,
                )

            def remove_triples_by_subject(self, subject: str,
                                          *, ontology: str | None = None) -> int:
                self.removed_subjects.append(subject)
                return self._delegate.remove_triples_by_subject(
                    subject, ontology=ontology,
                )

            def validate_instance(self, instance_uri: str, shape_uri: str,
                                  *, ontology: str | None = None) -> dict[str, Any]:
                return {
                    "conforms": False,
                    "violation_count": 1,
                    "violations": ["Injected failure: missing required field"],
                    "report": "Injected failure",
                }

            # --- pass-through stubs for unused ABC methods ---
            def query_ideas(self, **kw: Any) -> dict[str, Any]:
                return self._delegate.query_ideas(**kw)

            def get_idea(self, idea_id: str) -> dict[str, Any]:
                return self._delegate.get_idea(idea_id)

            def store_fact(self, subject: str, predicate: str, object: str,
                           *, context: str | None = None,
                           confidence: float = 1.0) -> dict[str, Any]:
                return self._delegate.store_fact(
                    subject, predicate, object,
                    context=context, confidence=confidence,
                )

            def forget_fact(self, fact_id: str) -> dict[str, Any]:
                return self._delegate.forget_fact(fact_id)

            def recall_facts(self, *, subject: str | None = None,
                             predicate: str | None = None,
                             context: str | None = None,
                             limit: int = 100) -> dict[str, Any]:
                return self._delegate.recall_facts(
                    subject=subject, predicate=predicate,
                    context=context, limit=limit,
                )

            def sparql_query(self, query: str,
                             *, validate: bool = True) -> dict[str, Any]:
                return self._delegate.sparql_query(query, validate=validate)

            def sparql_update(self, query: str,
                              *, validate: bool = True) -> dict[str, Any]:
                return self._delegate.sparql_update(query, validate=validate)

            def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
                return self._delegate.update_idea(idea_id, **kw)

            def forget_by_context(self, context: str) -> int:
                return self._delegate.forget_by_context(context)

            def set_lifecycle(self, idea_id: str, new_state: str,
                              *, reason: str = "") -> dict[str, Any]:
                return self._delegate.set_lifecycle(
                    idea_id, new_state, reason=reason,
                )

        subject = f"{PHASE_NS}test-shacl-53-rb-lw-trace"
        wrapper = _FailingValidationWrapper(ontology)
        persister = PhaseFactPersister(wrapper)

        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        shape_uri = get_shape_for_phase("lw-trace")
        result = persister.persist(
            idea_id="test-shacl-53-rb",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=shape_uri,
        )

        # Persister must detect failure and roll back
        assert result.validation_passed is False
        assert result.rolled_back is True
        assert len(result.validation_errors) >= 1

        # Verify rollback was called (remove_triples_by_subject invoked
        # twice: once for idempotent cleanup, once for rollback)
        assert subject in wrapper.removed_subjects, (
            f"Expected rollback for {subject}, got: {wrapper.removed_subjects}"
        )

        # Final cleanup in case anything leaked
        ontology.remove_triples_by_subject(subject)
