"""Tests for tulla.core.phase_facts — PersistResult and PhaseFactPersister."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from pydantic import BaseModel, Field

from tulla.core.intent import IntentField
from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import PersistResult, PhaseFactPersister, collect_upstream_facts, traverse_chain
from tulla.namespaces import PHASE_NS, TRACE_NS, RDF_TYPE
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class _TwoIntentModel(BaseModel):
    """Model with 2 intent fields and 1 plain field."""

    goal: str = IntentField(default="g", description="The goal")
    scope: str = IntentField(default="s", description="The scope")
    revision: int = Field(default=0)


class _NoIntentModel(BaseModel):
    """Model with zero intent fields."""

    name: str = Field(default="anon")
    count: int = Field(default=0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_port() -> MagicMock:
    """Create a mock OntologyPort."""
    port = MagicMock(spec=OntologyPort)
    port.remove_triples_by_subject.return_value = 0
    port.add_triple.return_value = {"status": "added"}
    port.validate_instance.return_value = {"conforms": True, "violations": []}
    port.sparql_query.return_value = {"results": []}
    return port


@pytest.fixture()
def port() -> MagicMock:
    return _make_port()


@pytest.fixture()
def persister(port: MagicMock) -> PhaseFactPersister:
    return PhaseFactPersister(port)


# ===================================================================
# PersistResult dataclass
# ===================================================================


class TestPersistResult:
    """Smoke tests for the PersistResult dataclass."""

    def test_defaults(self) -> None:
        r = PersistResult()
        assert r.stored_count == 0
        assert r.validation_passed is None
        assert r.validation_errors == []
        assert r.rolled_back is False

    def test_custom_values(self) -> None:
        r = PersistResult(
            stored_count=5,
            validation_passed=True,
            validation_errors=["e1"],
            rolled_back=True,
        )
        assert r.stored_count == 5
        assert r.validation_passed is True
        assert r.validation_errors == ["e1"]
        assert r.rolled_back is True


# ===================================================================
# PhaseFactPersister — 2 intent fields happy path
# ===================================================================


class TestPersistTwoIntentFields:
    """Persist a model with 2 intent fields — verify correct add_triple calls."""

    def test_correct_add_triple_count(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """2 intent fields + rdf:type + producedBy + forRequirement = 5 add_triple calls."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="ship it", scope="backend"),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.stored_count == 5
        assert port.add_triple.call_count == 5

    def test_rdf_type_triple(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """First triple is rdf:type phase:PhaseOutput."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        first_call = port.add_triple.call_args_list[0]
        assert first_call.args[0] == f"{PHASE_NS}42-d1"
        assert first_call.args[1] == RDF_TYPE
        assert first_call.args[2] == f"{PHASE_NS}PhaseOutput"

    def test_intent_field_predicates(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Each intent field becomes a phase:preserves-{name} triple."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="ship it", scope="backend"),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        stored_predicates = [c.args[1] for c in port.add_triple.call_args_list]
        assert f"{PHASE_NS}preserves-goal" in stored_predicates
        assert f"{PHASE_NS}preserves-scope" in stored_predicates

    def test_produced_by_triple(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        calls = port.add_triple.call_args_list
        produced_by = [c for c in calls if c.args[1] == f"{PHASE_NS}producedBy"]
        assert len(produced_by) == 1
        assert produced_by[0].args[0] == f"{PHASE_NS}42-d1"
        assert produced_by[0].args[2] == "d1"

    def test_for_requirement_triple(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        calls = port.add_triple.call_args_list
        for_req = [c for c in calls if c.args[1] == f"{PHASE_NS}forRequirement"]
        assert len(for_req) == 1
        assert for_req[0].args[0] == f"{PHASE_NS}42-d1"
        assert for_req[0].args[2] == "42"

    def test_full_uri_subject(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """All triples use subject = full URI (PHASE_NS + idea_id-phase_id)."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        expected_subject = f"{PHASE_NS}42-d1"
        for c in port.add_triple.call_args_list:
            assert c.args[0] == expected_subject

    def test_remove_triples_by_subject_called_before_add(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Idempotent cleanup: remove_triples_by_subject is called before any add_triple."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        port.remove_triples_by_subject.assert_called_once_with(
            f"{PHASE_NS}42-d1",
        )

    def test_validation_passed_none_without_shape(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """When no SHACL shape, validation_passed is None."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.validation_passed is None

    def test_intent_fields_are_literals(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Intent field add_triple calls use is_literal=True."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="my goal", scope="full"),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        intent_calls = [
            c for c in port.add_triple.call_args_list
            if f"{PHASE_NS}preserves-" in c.args[1]
        ]
        for c in intent_calls:
            assert c.kwargs.get("is_literal") is True

    def test_string_representation_of_values(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """Intent field values are stored as str(value)."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(goal="my goal", scope="full"),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        intent_calls = [
            c for c in port.add_triple.call_args_list
            if f"{PHASE_NS}preserves-" in c.args[1]
        ]
        values = {c.args[1]: c.args[2] for c in intent_calls}
        assert values[f"{PHASE_NS}preserves-goal"] == "my goal"
        assert values[f"{PHASE_NS}preserves-scope"] == "full"


# ===================================================================
# PhaseFactPersister — no-op for 0 intent fields
# ===================================================================


class TestPersistNoIntentFields:
    """Persist a model with 0 intent fields — confirm no-op."""

    def test_noop_result(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_NoIntentModel(name="test", count=5),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.stored_count == 0
        assert result.validation_passed is None
        assert result.rolled_back is False

    def test_no_add_triple_calls(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_NoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        port.add_triple.assert_not_called()
        port.remove_triples_by_subject.assert_not_called()

    def test_noop_for_none_data(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=None,
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        assert result.stored_count == 0
        port.add_triple.assert_not_called()


# ===================================================================
# PhaseFactPersister — predecessor trace
# ===================================================================


class TestPersistWithPredecessor:
    """Confirm trace:tracesTo triple is stored when predecessor_phase_id is given."""

    def test_traces_to_stored(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d2",
            phase_result=phase_result,
            predecessor_phase_id="d1",
            shacl_shape_id=None,
        )

        # rdf:type + 2 intent + producedBy + forRequirement + tracesTo = 6
        assert result.stored_count == 6
        assert port.add_triple.call_count == 6

        calls = port.add_triple.call_args_list
        trace_calls = [c for c in calls if c.args[1] == f"{TRACE_NS}tracesTo"]
        assert len(trace_calls) == 1
        assert trace_calls[0].args[0] == f"{PHASE_NS}42-d2"
        assert trace_calls[0].args[2] == f"{PHASE_NS}42-d1"

    def test_traces_to_is_uri_not_literal(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        """tracesTo object is a URI, not a literal (no is_literal kwarg)."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d2",
            phase_result=phase_result,
            predecessor_phase_id="d1",
            shacl_shape_id=None,
        )

        calls = port.add_triple.call_args_list
        trace_calls = [c for c in calls if c.args[1] == f"{TRACE_NS}tracesTo"]
        assert len(trace_calls) == 1
        # No is_literal kwarg means it defaults to False (URI reference)
        assert trace_calls[0].kwargs.get("is_literal", False) is False

    def test_no_traces_to_without_predecessor(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        persister.persist(
            idea_id="42",
            phase_id="d2",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        calls = port.add_triple.call_args_list
        trace_calls = [c for c in calls if c.args[1] == f"{TRACE_NS}tracesTo"]
        assert len(trace_calls) == 0


# ===================================================================
# PhaseFactPersister — SHACL validation
# ===================================================================


class TestPersistShaclValidation:
    """SHACL validation: pass, fail with rollback."""

    def test_validation_pass(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        port.validate_instance.return_value = {
            "conforms": True,
            "violations": [],
        }
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id="shapes:PhaseOutput",
        )

        assert result.validation_passed is True
        assert result.rolled_back is False
        assert result.validation_errors == []
        port.validate_instance.assert_called_once_with(
            f"{PHASE_NS}42-d1", "shapes:PhaseOutput",
        )

    def test_validation_fail_rolls_back(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        port.validate_instance.return_value = {
            "conforms": False,
            "violations": ["missing phase:preserves-goal"],
        }
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id="shapes:PhaseOutput",
        )

        assert result.validation_passed is False
        assert result.rolled_back is True
        assert "missing phase:preserves-goal" in result.validation_errors

        # remove_triples_by_subject called twice: idempotent cleanup + rollback
        assert port.remove_triples_by_subject.call_count == 2
        for c in port.remove_triples_by_subject.call_args_list:
            assert c.args[0] == f"{PHASE_NS}42-d1"

    def test_validation_exception_rolls_back(
        self, port: MagicMock, persister: PhaseFactPersister
    ) -> None:
        port.validate_instance.side_effect = RuntimeError("server down")
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_TwoIntentModel(),
        )
        result = persister.persist(
            idea_id="42",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id="shapes:PhaseOutput",
        )

        assert result.validation_passed is False
        assert result.rolled_back is True
        assert "server down" in result.validation_errors[0]
        # remove_triples_by_subject called twice: idempotent cleanup + rollback
        assert port.remove_triples_by_subject.call_count == 2


# ===================================================================
# collect_upstream_facts — SPARQL-based
# ===================================================================


class TestCollectUpstreamFacts:
    """Tests for the SPARQL-based collect_upstream_facts function."""

    PHASES = ["d1", "d2", "d3", "d4"]

    def test_sparql_query_called(self, port: MagicMock) -> None:
        """sparql_query is called once for upstream collection."""
        port.sparql_query.return_value = {"results": []}

        collect_upstream_facts(port, "42", self.PHASES, "d3")

        port.sparql_query.assert_called_once()
        query = port.sparql_query.call_args.args[0]
        assert 'forRequirement "42"' in query

    def test_filters_to_upstream_phases_only(self, port: MagicMock) -> None:
        """Only triples from upstream phases (d1, d2) are returned, not d3 or d4."""
        port.sparql_query.return_value = {"results": [
            {"s": f"{PHASE_NS}42-d1", "p": f"{PHASE_NS}preserves-goal", "o": "plan"},
            {"s": f"{PHASE_NS}42-d2", "p": f"{PHASE_NS}preserves-scope", "o": "full"},
            {"s": f"{PHASE_NS}42-d3", "p": f"{PHASE_NS}preserves-mode", "o": "auto"},
            {"s": f"{PHASE_NS}42-d4", "p": f"{PHASE_NS}preserves-x", "o": "y"},
        ]}

        result = collect_upstream_facts(port, "42", self.PHASES, "d3")

        subjects = {f["subject"] for f in result}
        assert f"{PHASE_NS}42-d1" in subjects
        assert f"{PHASE_NS}42-d2" in subjects
        assert f"{PHASE_NS}42-d3" not in subjects
        assert f"{PHASE_NS}42-d4" not in subjects

    def test_empty_list_for_first_phase(self, port: MagicMock) -> None:
        """If current_phase_id is the first phase, return empty list."""
        result = collect_upstream_facts(port, "42", self.PHASES, "d1")

        assert result == []
        port.sparql_query.assert_not_called()

    def test_empty_list_for_unknown_phase(self, port: MagicMock) -> None:
        """If current_phase_id is not in the sequence, return empty list."""
        result = collect_upstream_facts(port, "42", self.PHASES, "unknown")

        assert result == []
        port.sparql_query.assert_not_called()

    def test_sparql_exception_returns_empty(self, port: MagicMock) -> None:
        """If sparql_query raises, return empty list."""
        port.sparql_query.side_effect = RuntimeError("server timeout")

        result = collect_upstream_facts(port, "42", self.PHASES, "d3")

        assert result == []

    def test_empty_sequence(self, port: MagicMock) -> None:
        """Empty phase_sequence returns empty list."""
        result = collect_upstream_facts(port, "42", [], "d1")

        assert result == []
        port.sparql_query.assert_not_called()

    def test_returns_fact_dicts_with_spo(self, port: MagicMock) -> None:
        """Returned facts have subject, predicate, object keys."""
        port.sparql_query.return_value = {"results": [
            {"s": f"{PHASE_NS}42-d1", "p": f"{PHASE_NS}preserves-goal", "o": "plan"},
        ]}

        result = collect_upstream_facts(port, "42", self.PHASES, "d2")

        assert len(result) == 1
        assert result[0]["subject"] == f"{PHASE_NS}42-d1"
        assert result[0]["predicate"] == f"{PHASE_NS}preserves-goal"
        assert result[0]["object"] == "plan"


# ===================================================================
# traverse_chain — SPARQL property paths
# ===================================================================


class TestTraverseChain:
    """Tests for the SPARQL-based traverse_chain function."""

    def test_three_hop_chain(self, port: MagicMock) -> None:
        """3-hop chain: d3 -> d2 -> d1. Returned in reverse chronological order."""
        # Ancestor query returns d2 and d1
        port.sparql_query.side_effect = [
            # Ancestor query
            {"results": [
                {"ancestor": f"{PHASE_NS}42-d2"},
                {"ancestor": f"{PHASE_NS}42-d1"},
            ]},
            # Facts for d3
            {"results": [
                {"p": f"{PHASE_NS}preserves-scope", "o": "full"},
            ]},
            # Facts for d2
            {"results": [
                {"p": f"{PHASE_NS}preserves-goal", "o": "ship"},
            ]},
            # Facts for d1
            {"results": [
                {"p": f"{PHASE_NS}preserves-goal", "o": "plan"},
            ]},
        ]

        result = traverse_chain(port, "42", "d3")

        assert len(result) == 3
        assert result[0]["subject"] == f"{PHASE_NS}42-d3"
        assert result[1]["subject"] == f"{PHASE_NS}42-d2"
        assert result[2]["subject"] == f"{PHASE_NS}42-d1"

    def test_terminates_at_origin(self, port: MagicMock) -> None:
        """Chain terminates when no ancestors found (origin node)."""
        port.sparql_query.side_effect = [
            # No ancestors
            {"results": []},
            # Facts for d1
            {"results": [{"p": f"{PHASE_NS}preserves-goal", "o": "plan"}]},
        ]

        result = traverse_chain(port, "42", "d1")

        assert len(result) == 1
        assert result[0]["subject"] == f"{PHASE_NS}42-d1"

    def test_max_depth_uses_bounded_path(self, port: MagicMock) -> None:
        """Non-default max_depth uses trace:tracesTo{1,N} syntax."""
        port.sparql_query.side_effect = [
            {"results": []},
            {"results": []},
        ]

        traverse_chain(port, "42", "d10", max_depth=3)

        ancestor_query = port.sparql_query.call_args_list[0].args[0]
        assert "tracesTo{1,3}" in ancestor_query

    def test_ancestor_query_failure_returns_empty(self, port: MagicMock) -> None:
        """If ancestor SPARQL query raises, return empty list."""
        port.sparql_query.side_effect = RuntimeError("server down")

        result = traverse_chain(port, "42", "d2")

        assert result == []

    def test_facts_query_failure_returns_empty_facts(self, port: MagicMock) -> None:
        """If facts query fails for a subject, include it with empty facts."""
        port.sparql_query.side_effect = [
            # Ancestors
            {"results": [{"ancestor": f"{PHASE_NS}42-d1"}]},
            # Facts for d2 fails
            RuntimeError("query failed"),
            # Facts for d1
            {"results": [{"p": f"{PHASE_NS}preserves-goal", "o": "plan"}]},
        ]

        result = traverse_chain(port, "42", "d2")

        assert len(result) == 2
        assert result[0] == {"subject": f"{PHASE_NS}42-d2", "facts": []}
        assert len(result[1]["facts"]) == 1

    def test_default_max_depth_is_20(self, port: MagicMock) -> None:
        """Default max_depth is 20."""
        from tulla.core.phase_facts import _TRAVERSE_MAX_DEPTH

        assert _TRAVERSE_MAX_DEPTH == 20

    def test_deduplicates_ancestors(self, port: MagicMock) -> None:
        """Duplicate ancestor URIs in SPARQL results are deduplicated."""
        port.sparql_query.side_effect = [
            {"results": [
                {"ancestor": f"{PHASE_NS}42-d1"},
                {"ancestor": f"{PHASE_NS}42-d1"},  # duplicate
            ]},
            {"results": []},  # facts for d2
            {"results": []},  # facts for d1
        ]

        result = traverse_chain(port, "42", "d2")

        assert len(result) == 2  # d2 + d1, not d2 + d1 + d1
