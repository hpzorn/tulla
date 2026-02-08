"""Integration test: LightweightTraceResult triples pass LWTraceOutputShape validation.

# @pattern:EventSourcing -- Validates that the immutable trace event (LightweightTraceResult) produces triples conforming to the SHACL structural contract
# @pattern:PortsAndAdapters -- Mock OntologyPort verifies triple structure at the port boundary without requiring a live ontology-server
# @principle:DependencyInversion -- Test depends on OntologyPort ABC; mock performs structural SHACL-like validation in-process

Verification criteria (prd:req-53-5-2):
  Integration test against ontology-server validates that a
  LightweightTraceResult-shaped set of triples passes LWTraceOutputShape
  validation.

The test uses a mock OntologyPort that performs structural validation
equivalent to what the ontology-server's SHACL engine would do: it
checks that the persisted triples include all properties required by
LWTraceOutputShape (producedBy exactly 1, and each preserves-* field
at least once).
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.intent import extract_intent_fields
from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import PhaseFactPersister
from tulla.namespaces import PHASE_NS
from tulla.ontology.phase_shapes import get_shape_for_phase
from tulla.phases.lightweight.models import LightweightTraceResult
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# SHACL-validating mock OntologyPort
# ---------------------------------------------------------------------------

# Required properties from LWTraceOutputShape (phase-ontology.ttl)
_LW_TRACE_REQUIRED_PROPERTIES: dict[str, tuple[int | None, int | None]] = {
    # path -> (minCount, maxCount) — None means unbounded
    f"{PHASE_NS}producedBy": (1, 1),
    f"{PHASE_NS}preserves-change_type": (1, None),
    f"{PHASE_NS}preserves-affected_files": (1, None),
    f"{PHASE_NS}preserves-conformance_assertion": (1, None),
    f"{PHASE_NS}preserves-commit_ref": (1, None),
    f"{PHASE_NS}preserves-change_summary": (1, None),
    f"{PHASE_NS}preserves-timestamp": (1, None),
}


class _SHACLValidatingOntologyPort(OntologyPort):
    """Mock OntologyPort that structurally validates triples against LWTraceOutputShape.

    Tracks all add_triple calls and, when validate_instance is called,
    checks that the persisted triples satisfy the shape constraints.
    """

    def __init__(self) -> None:
        self.triples: list[dict[str, Any]] = []
        self.validate_calls: list[dict[str, str]] = []

    # --- Tracking methods ---

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.triples.append({
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "is_literal": is_literal,
        })
        return {"status": "added"}

    def remove_triples_by_subject(
        self, subject: str, *, ontology: str | None = None,
    ) -> int:
        before = len(self.triples)
        self.triples = [t for t in self.triples if t["subject"] != subject]
        return before - len(self.triples)

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.validate_calls.append({
            "instance_uri": instance_uri,
            "shape_uri": shape_uri,
        })

        # Perform structural SHACL-like validation
        instance_triples = [
            t for t in self.triples if t["subject"] == instance_uri
        ]
        predicate_counts: dict[str, int] = {}
        for t in instance_triples:
            p = t["predicate"]
            predicate_counts[p] = predicate_counts.get(p, 0) + 1

        violations: list[str] = []
        for prop, (min_count, max_count) in _LW_TRACE_REQUIRED_PROPERTIES.items():
            actual = predicate_counts.get(prop, 0)
            if min_count is not None and actual < min_count:
                violations.append(
                    f"{prop}: expected minCount {min_count}, got {actual}"
                )
            if max_count is not None and actual > max_count:
                violations.append(
                    f"{prop}: expected maxCount {max_count}, got {actual}"
                )

        return {
            "conforms": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
            "report": "; ".join(violations) if violations else "",
        }

    # --- Unused ABC methods (required by OntologyPort) ---

    def query_ideas(self, **kwargs: Any) -> dict[str, Any]:
        return {"ideas": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(
        self, subject: str, predicate: str, object: str,
        *, context: str | None = None, confidence: float = 1.0,
    ) -> dict[str, Any]:
        return {"stored": True}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(
        self, *, subject: str | None = None, predicate: str | None = None,
        context: str | None = None, limit: int = 100,
    ) -> dict[str, Any]:
        return {"facts": []}

    def sparql_query(
        self, query: str, *, validate: bool = True,
    ) -> dict[str, Any]:
        return {"results": []}

    def sparql_update(
        self, query: str, *, validate: bool = True,
    ) -> dict[str, Any]:
        return {"status": "ok"}

    def update_idea(self, idea_id: str, **kwargs: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(
        self, idea_id: str, new_state: str, *, reason: str = "",
    ) -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Fixtures
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


# ---------------------------------------------------------------------------
# Tests: LWTraceOutputShape structural validation
# ---------------------------------------------------------------------------


class TestLWTraceOutputShapeValidation:
    """Integration test: LightweightTraceResult triples pass LWTraceOutputShape."""

    def test_shape_uri_is_registered(self) -> None:
        """LWTraceOutputShape is registered in the phase shapes registry."""
        shape_uri = get_shape_for_phase("lw-trace")
        assert shape_uri == f"{PHASE_NS}LWTraceOutputShape"

    def test_complete_trace_result_passes_validation(self) -> None:
        """A fully-populated LightweightTraceResult passes LWTraceOutputShape."""
        ontology = _SHACLValidatingOntologyPort()
        persister = PhaseFactPersister(ontology)

        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        shape_uri = get_shape_for_phase("lw-trace")
        result = persister.persist(
            idea_id="test-53",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id="lw-execute",
            shacl_shape_id=shape_uri,
        )

        assert result.validation_passed is True
        assert result.rolled_back is False
        assert result.validation_errors == []
        assert result.stored_count > 0

    def test_validate_instance_called_with_correct_shape(self) -> None:
        """PhaseFactPersister calls validate_instance with LWTraceOutputShape URI."""
        ontology = _SHACLValidatingOntologyPort()
        persister = PhaseFactPersister(ontology)

        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        shape_uri = get_shape_for_phase("lw-trace")
        persister.persist(
            idea_id="test-53",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=shape_uri,
        )

        assert len(ontology.validate_calls) == 1
        assert ontology.validate_calls[0]["shape_uri"] == f"{PHASE_NS}LWTraceOutputShape"
        assert ontology.validate_calls[0]["instance_uri"] == f"{PHASE_NS}test-53-lw-trace"

    def test_all_required_predicates_persisted(self) -> None:
        """All 7 required predicates from LWTraceOutputShape are present in persisted triples."""
        ontology = _SHACLValidatingOntologyPort()
        persister = PhaseFactPersister(ontology)

        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        persister.persist(
            idea_id="test-53",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,  # skip validation, just persist
        )

        predicates = {t["predicate"] for t in ontology.triples}
        for required_prop in _LW_TRACE_REQUIRED_PROPERTIES:
            assert required_prop in predicates, (
                f"Missing required predicate: {required_prop}"
            )

    def test_produced_by_appears_exactly_once(self) -> None:
        """phase:producedBy appears exactly 1 time (sh:minCount 1, sh:maxCount 1)."""
        ontology = _SHACLValidatingOntologyPort()
        persister = PhaseFactPersister(ontology)

        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        subject_uri = f"{PHASE_NS}test-53-lw-trace"
        persister.persist(
            idea_id="test-53",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        produced_by_count = sum(
            1 for t in ontology.triples
            if t["subject"] == subject_uri
            and t["predicate"] == f"{PHASE_NS}producedBy"
        )
        assert produced_by_count == 1

    def test_missing_required_field_fails_validation(self) -> None:
        """A trace result missing a required field fails LWTraceOutputShape validation."""
        ontology = _SHACLValidatingOntologyPort()
        persister = PhaseFactPersister(ontology)

        # Create a trace result with empty change_type — IntentField still
        # extracts it (as empty string), so the triple is stored. Instead,
        # we test a scenario where validate_instance detects a structural gap
        # by removing the change_type triple after persist but before validation.
        trace_result = _make_trace_result()
        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        # First persist without validation to populate triples
        persister.persist(
            idea_id="test-53-fail",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        # Manually remove a required triple to simulate a gap
        subject_uri = f"{PHASE_NS}test-53-fail-lw-trace"
        ontology.triples = [
            t for t in ontology.triples
            if not (
                t["subject"] == subject_uri
                and t["predicate"] == f"{PHASE_NS}preserves-change_type"
            )
        ]

        # Now validate — should fail
        result = ontology.validate_instance(
            subject_uri,
            f"{PHASE_NS}LWTraceOutputShape",
        )
        assert result["conforms"] is False
        assert result["violation_count"] >= 1
        assert any("change_type" in v for v in result["violations"])

    def test_optional_fields_do_not_affect_validation(self) -> None:
        """Optional fields (issue_ref, sprint_id, story_points) don't affect shape validation."""
        ontology = _SHACLValidatingOntologyPort()
        persister = PhaseFactPersister(ontology)

        # No optional fields — should still pass
        trace_result = _make_trace_result()
        assert trace_result.issue_ref is None
        assert trace_result.sprint_id is None
        assert trace_result.story_points is None

        phase_result = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=trace_result,
        )

        shape_uri = get_shape_for_phase("lw-trace")
        result = persister.persist(
            idea_id="test-53-opt",
            phase_id="lw-trace",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=shape_uri,
        )

        assert result.validation_passed is True
        assert result.rolled_back is False
