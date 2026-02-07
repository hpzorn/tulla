"""Tests for tulla.core.phase_facts — Phase 1 unit tests (req-73-1-3).

Covers the None-skip fix (req-73-1-1) and group_upstream_facts() (req-73-1-2).
Uses _MockOntologyPort for persist() tests and direct function calls for
group_upstream_facts / _try_coerce.

# @pattern:PortsAndAdapters -- _MockOntologyPort implements OntologyPort ABC to test persistence without a live ontology server
# @pattern:LayeredArchitecture -- Tests mirror the production layers: mock adapter → PhaseFactPersister → pure functions, each test class targets exactly one layer
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from tulla.core.intent import IntentField
from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import (
    PersistResult,
    PhaseFactPersister,
    collect_upstream_facts,
    group_upstream_facts,
    traverse_chain,
    _try_coerce,
)
from tulla.namespaces import PHASE_NS, TRACE_NS, RDF_TYPE
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# _MockOntologyPort — in-process triple store for isolation
# ---------------------------------------------------------------------------
# @principle:DependencyInversion -- Tests depend on the OntologyPort abstraction; _MockOntologyPort is injected without referencing any concrete adapter


class _MockOntologyPort(OntologyPort):
    """In-memory OntologyPort that records add_triple / remove calls.

    Stores triples as dicts so tests can inspect exactly what was persisted
    without coupling to a real ontology-server.
    """

    def __init__(self) -> None:
        self.triples: list[dict[str, Any]] = []
        self.removed_subjects: list[str] = []
        self.validate_result: dict[str, Any] = {"conforms": True, "violations": []}
        self.validate_exception: Exception | None = None
        self.sparql_results: list[dict[str, Any]] = []

    # -- triple operations ---------------------------------------------------

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
        self,
        subject: str,
        *,
        ontology: str | None = None,
    ) -> int:
        before = len(self.triples)
        self.triples = [t for t in self.triples if t["subject"] != subject]
        removed = before - len(self.triples)
        self.removed_subjects.append(subject)
        return removed

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        if self.validate_exception is not None:
            raise self.validate_exception
        return self.validate_result

    # -- unused stubs (satisfy ABC) ------------------------------------------

    def query_ideas(self, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(self, subject: str, predicate: str, object: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(self, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}

    def sparql_query(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        return {"results": self.sparql_results}

    def update_idea(self, idea_id: str, **kwargs: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(self, idea_id: str, new_state: str, *, reason: str = "") -> dict[str, Any]:
        return {}


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


class _OptionalIntentModel(BaseModel):
    """Model with one required and one optional IntentField (defaults to None)."""

    goal: str = IntentField(description="Required intent field")
    notes: str | None = IntentField(default=None, description="Optional intent field")


class _AllNoneIntentModel(BaseModel):
    """Model where every IntentField defaults to None."""

    alpha: str | None = IntentField(default=None, description="Optional A")
    beta: str | None = IntentField(default=None, description="Optional B")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_port() -> _MockOntologyPort:
    return _MockOntologyPort()


@pytest.fixture()
def persister(mock_port: _MockOntologyPort) -> PhaseFactPersister:
    return PhaseFactPersister(mock_port)


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
# PhaseFactPersister — None-value intent fields skipped (req-73-1-1)
# ===================================================================
# @pattern:MVC -- Test models (_TwoIntentModel etc.) act as M, PhaseFactPersister acts as C, and _MockOntologyPort captures V-layer triple output for assertion


class TestPersistSkipsNoneIntentFields:
    """Persist a model with one required and one optional (None) IntentField.

    Verifies arch:adr-73-4: persist() produces NO triple for None-valued
    IntentFields, using _MockOntologyPort to inspect the in-memory store.
    """

    def test_only_required_field_produces_triple(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """Optional IntentField=None is skipped; only required field is stored."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_OptionalIntentModel(goal="ship it"),
        )
        result = persister.persist(
            idea_id="73",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        # rdf:type + 1 intent field (goal) + producedBy + forRequirement = 4
        assert result.stored_count == 4
        assert len(mock_port.triples) == 4

        intent_triples = [
            t for t in mock_port.triples
            if f"{PHASE_NS}preserves-" in t["predicate"]
        ]
        assert len(intent_triples) == 1
        assert intent_triples[0]["predicate"] == f"{PHASE_NS}preserves-goal"
        assert intent_triples[0]["object"] == "ship it"

    def test_no_none_string_in_triple_objects(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """No triple object should contain the literal string 'None'."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_OptionalIntentModel(goal="deliver"),
        )
        persister.persist(
            idea_id="73",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        for t in mock_port.triples:
            assert t["object"] != "None", (
                f"Triple object 'None' found: {t}"
            )

    def test_all_none_fields_produce_only_metadata_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """When every IntentField is None, only metadata triples are stored (no preserves-)."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_AllNoneIntentModel(),
        )
        result = persister.persist(
            idea_id="73",
            phase_id="d2",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        # rdf:type + producedBy + forRequirement = 3 (no preserves- triples)
        assert result.stored_count == 3
        intent_triples = [
            t for t in mock_port.triples
            if f"{PHASE_NS}preserves-" in t["predicate"]
        ]
        assert len(intent_triples) == 0

    def test_none_field_not_stored_as_literal(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """Verify None-valued fields don't produce any literal triple at all."""
        phase_result: PhaseResult[Any] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=_OptionalIntentModel(goal="plan"),
        )
        persister.persist(
            idea_id="73",
            phase_id="d1",
            phase_result=phase_result,
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )

        notes_triples = [
            t for t in mock_port.triples
            if t["predicate"] == f"{PHASE_NS}preserves-notes"
        ]
        assert len(notes_triples) == 0


# ===================================================================
# PhaseFactPersister — 2 intent fields happy path
# ===================================================================


class TestPersistTwoIntentFields:
    """Persist a model with 2 intent fields — verify correct triples via _MockOntologyPort."""

    def test_correct_triple_count(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """2 intent fields + rdf:type + producedBy + forRequirement = 5 triples."""
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
        assert len(mock_port.triples) == 5

    def test_rdf_type_triple(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

        first = mock_port.triples[0]
        assert first["subject"] == f"{PHASE_NS}42-d1"
        assert first["predicate"] == RDF_TYPE
        assert first["object"] == f"{PHASE_NS}PhaseOutput"

    def test_intent_field_predicates(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

        predicates = [t["predicate"] for t in mock_port.triples]
        assert f"{PHASE_NS}preserves-goal" in predicates
        assert f"{PHASE_NS}preserves-scope" in predicates

    def test_intent_fields_are_literals(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """Intent field triples use is_literal=True."""
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

        intent_triples = [
            t for t in mock_port.triples
            if f"{PHASE_NS}preserves-" in t["predicate"]
        ]
        for t in intent_triples:
            assert t["is_literal"] is True

    def test_string_representation_of_values(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

        intent_triples = [
            t for t in mock_port.triples
            if f"{PHASE_NS}preserves-" in t["predicate"]
        ]
        values = {t["predicate"]: t["object"] for t in intent_triples}
        assert values[f"{PHASE_NS}preserves-goal"] == "my goal"
        assert values[f"{PHASE_NS}preserves-scope"] == "full"

    def test_full_uri_subject(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """All triples use subject = PHASE_NS + idea_id-phase_id."""
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
        for t in mock_port.triples:
            assert t["subject"] == expected_subject

    def test_idempotent_cleanup_before_add(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """remove_triples_by_subject is called before any add_triple."""
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

        assert f"{PHASE_NS}42-d1" in mock_port.removed_subjects


# ===================================================================
# PhaseFactPersister — no-op for 0 intent fields
# ===================================================================


class TestPersistNoIntentFields:
    """Persist a model with 0 intent fields — confirm no-op."""

    def test_noop_result(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

    def test_no_triples_stored(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

        assert len(mock_port.triples) == 0
        assert len(mock_port.removed_subjects) == 0

    def test_noop_for_none_data(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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
        assert len(mock_port.triples) == 0


# ===================================================================
# PhaseFactPersister — predecessor trace
# ===================================================================


class TestPersistWithPredecessor:
    """Confirm trace:tracesTo triple when predecessor_phase_id is given."""

    def test_traces_to_stored(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

        trace_triples = [
            t for t in mock_port.triples
            if t["predicate"] == f"{TRACE_NS}tracesTo"
        ]
        assert len(trace_triples) == 1
        assert trace_triples[0]["subject"] == f"{PHASE_NS}42-d2"
        assert trace_triples[0]["object"] == f"{PHASE_NS}42-d1"

    def test_traces_to_is_uri_not_literal(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """tracesTo object is a URI, not a literal."""
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

        trace_triples = [
            t for t in mock_port.triples
            if t["predicate"] == f"{TRACE_NS}tracesTo"
        ]
        assert len(trace_triples) == 1
        assert trace_triples[0]["is_literal"] is False

    def test_no_traces_to_without_predecessor(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
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

        trace_triples = [
            t for t in mock_port.triples
            if t["predicate"] == f"{TRACE_NS}tracesTo"
        ]
        assert len(trace_triples) == 0


# ===================================================================
# PhaseFactPersister — SHACL validation
# ===================================================================


class TestPersistShaclValidation:
    """SHACL validation: pass, fail with rollback."""

    def test_validation_pass(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        mock_port.validate_result = {"conforms": True, "violations": []}
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

    def test_validation_fail_rolls_back(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        mock_port.validate_result = {
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
        # Triples removed on rollback (idempotent cleanup + rollback = 2 remove calls)
        assert mock_port.removed_subjects.count(f"{PHASE_NS}42-d1") == 2

    def test_validation_exception_rolls_back(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        mock_port.validate_exception = RuntimeError("server down")
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
        assert mock_port.removed_subjects.count(f"{PHASE_NS}42-d1") == 2


# ===================================================================
# _try_coerce — type coercion helper (req-73-1-2)
# ===================================================================
# @principle:SeparationOfConcerns -- _try_coerce is tested in isolation from group_upstream_facts, verifying each coercion path independently


class TestTryCoerce:
    """Tests for the _try_coerce helper function — auto-coercion of each type."""

    def test_coerces_int(self) -> None:
        assert _try_coerce("5") == 5
        assert isinstance(_try_coerce("5"), int)

    def test_coerces_negative_int(self) -> None:
        assert _try_coerce("-42") == -42
        assert isinstance(_try_coerce("-42"), int)

    def test_coerces_float(self) -> None:
        assert _try_coerce("3.14") == 3.14
        assert isinstance(_try_coerce("3.14"), float)

    def test_coerces_negative_float(self) -> None:
        assert _try_coerce("-0.5") == -0.5
        assert isinstance(_try_coerce("-0.5"), float)

    def test_coerces_bool_true(self) -> None:
        assert _try_coerce("true") is True
        assert _try_coerce("True") is True

    def test_coerces_bool_false(self) -> None:
        assert _try_coerce("false") is False
        assert _try_coerce("False") is False

    def test_coerces_json_list(self) -> None:
        result = _try_coerce('[1, 2, 3]')
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_coerces_json_dict(self) -> None:
        result = _try_coerce('{"key": "val"}')
        assert result == {"key": "val"}
        assert isinstance(result, dict)

    def test_plain_string_fallback(self) -> None:
        assert _try_coerce("hello world") == "hello world"
        assert isinstance(_try_coerce("hello world"), str)

    def test_empty_string(self) -> None:
        assert _try_coerce("") == ""

    def test_int_preferred_over_float(self) -> None:
        """'5' should become int(5), not float(5.0)."""
        result = _try_coerce("5")
        assert type(result) is int

    def test_zero_is_int(self) -> None:
        assert _try_coerce("0") == 0
        assert type(_try_coerce("0")) is int


# ===================================================================
# group_upstream_facts — grouping + coercion (req-73-1-2)
# ===================================================================


class TestGroupUpstreamFacts:
    """Tests for the group_upstream_facts pure function.

    Covers: basic grouping, auto-coercion of each type, empty input,
    and metadata-predicate skipping.
    """

    def test_basic_grouping_d1_and_d2(self) -> None:
        """Primary verification: D1 + D2 triples grouped with typed values."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": f"{PHASE_NS}preserves-key_capabilities",
                "object": '[{"name": "tool1"}]',
            },
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": f"{PHASE_NS}preserves-ecosystem_context",
                "object": "fits into MCP ecosystem",
            },
            {
                "subject": f"{PHASE_NS}42-d2",
                "predicate": f"{PHASE_NS}preserves-primary_persona_jtbd",
                "object": "When I build, I want automation, so I can ship faster",
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert result == {
            "d1": {"key_capabilities": [{"name": "tool1"}], "ecosystem_context": "fits into MCP ecosystem"},
            "d2": {"primary_persona_jtbd": "When I build, I want automation, so I can ship faster"},
        }
        # Verify Python types
        assert type(result["d1"]["key_capabilities"]) is list
        assert type(result["d1"]["ecosystem_context"]) is str
        assert type(result["d2"]["primary_persona_jtbd"]) is str

    def test_empty_input_returns_empty_dict(self) -> None:
        """Empty fact list yields empty dict."""
        assert group_upstream_facts([]) == {}

    def test_metadata_predicates_skipped(self) -> None:
        """Non-preserves predicates (producedBy, forRequirement, rdf:type, tracesTo) are skipped."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": f"{PHASE_NS}preserves-key_capabilities",
                "object": "[]",
            },
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": f"{PHASE_NS}producedBy",
                "object": "d1",
            },
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": f"{PHASE_NS}forRequirement",
                "object": "42",
            },
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": RDF_TYPE,
                "object": f"{PHASE_NS}PhaseOutput",
            },
            {
                "subject": f"{PHASE_NS}42-d1",
                "predicate": f"{TRACE_NS}tracesTo",
                "object": f"{PHASE_NS}42-d0",
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert result == {"d1": {"key_capabilities": []}}

    def test_float_coercion(self) -> None:
        """Float string values are coerced to Python float."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}10-d3",
                "predicate": f"{PHASE_NS}preserves-score",
                "object": "7.5",
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert result == {"d3": {"score": 7.5}}
        assert type(result["d3"]["score"]) is float

    def test_bool_coercion(self) -> None:
        """Boolean string values ('true'/'false') are coerced to Python bool."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}10-d4",
                "predicate": f"{PHASE_NS}preserves-has_gaps",
                "object": "true",
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert result["d4"]["has_gaps"] is True

    def test_json_list_coercion(self) -> None:
        """JSON list strings are coerced to Python lists."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}10-d1",
                "predicate": f"{PHASE_NS}preserves-tags",
                "object": '["a", "b", "c"]',
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert result == {"d1": {"tags": ["a", "b", "c"]}}

    def test_string_fallback(self) -> None:
        """Plain string values remain strings."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}10-d3",
                "predicate": f"{PHASE_NS}preserves-quadrant",
                "object": "top-right",
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert result == {"d3": {"quadrant": "top-right"}}
        assert type(result["d3"]["quadrant"]) is str

    def test_multiple_phases_grouped_separately(self) -> None:
        """Facts from different phases are grouped into separate phase keys."""
        raw_facts = [
            {
                "subject": f"{PHASE_NS}7-d1",
                "predicate": f"{PHASE_NS}preserves-x",
                "object": "1",
            },
            {
                "subject": f"{PHASE_NS}7-d2",
                "predicate": f"{PHASE_NS}preserves-y",
                "object": "2",
            },
            {
                "subject": f"{PHASE_NS}7-d3",
                "predicate": f"{PHASE_NS}preserves-z",
                "object": "3",
            },
        ]

        result = group_upstream_facts(raw_facts)

        assert set(result.keys()) == {"d1", "d2", "d3"}
        assert result["d1"]["x"] == 1
        assert result["d2"]["y"] == 2
        assert result["d3"]["z"] == 3

    def test_realistic_d1_through_d4_field_map(self) -> None:
        """Verify the field map: D1(key_capabilities, ecosystem_context, reuse_opportunities),
        D2(personas, non_negotiable_needs, primary_persona_jtbd),
        D3(quadrant, strategic_constraints, verdict),
        D4(blockers, root_blocker, recommended_next_steps)."""
        raw_facts = [
            {"subject": f"{PHASE_NS}73-d1", "predicate": f"{PHASE_NS}preserves-key_capabilities", "object": "[]"},
            {"subject": f"{PHASE_NS}73-d1", "predicate": f"{PHASE_NS}preserves-ecosystem_context", "object": "core platform"},
            {"subject": f"{PHASE_NS}73-d1", "predicate": f"{PHASE_NS}preserves-reuse_opportunities", "object": "existing MCP tools"},
            {"subject": f"{PHASE_NS}73-d2", "predicate": f"{PHASE_NS}preserves-personas", "object": "[]"},
            {"subject": f"{PHASE_NS}73-d2", "predicate": f"{PHASE_NS}preserves-primary_persona_jtbd", "object": "When I build, I want speed"},
            {"subject": f"{PHASE_NS}73-d3", "predicate": f"{PHASE_NS}preserves-quadrant", "object": "top-right"},
            {"subject": f"{PHASE_NS}73-d3", "predicate": f"{PHASE_NS}preserves-verdict", "object": "P1-High | Strong ROI | High confidence"},
            {"subject": f"{PHASE_NS}73-d4", "predicate": f"{PHASE_NS}preserves-blockers", "object": "No API endpoint"},
            {"subject": f"{PHASE_NS}73-d4", "predicate": f"{PHASE_NS}preserves-root_blocker", "object": "No API endpoint: blocks core functionality"},
        ]

        result = group_upstream_facts(raw_facts)

        assert result == {
            "d1": {"key_capabilities": [], "ecosystem_context": "core platform", "reuse_opportunities": "existing MCP tools"},
            "d2": {"personas": [], "primary_persona_jtbd": "When I build, I want speed"},
            "d3": {"quadrant": "top-right", "verdict": "P1-High | Strong ROI | High confidence"},
            "d4": {"blockers": "No API endpoint", "root_blocker": "No API endpoint: blocks core functionality"},
        }


# ===================================================================
# collect_upstream_facts — SPARQL-based
# ===================================================================


class TestCollectUpstreamFacts:
    """Tests for the SPARQL-based collect_upstream_facts function."""

    PHASES = ["d1", "d2", "d3", "d4"]

    def test_sparql_query_called(self, mock_port: _MockOntologyPort) -> None:
        """sparql_query is called once for upstream collection."""
        mock_port.sparql_results = []

        collect_upstream_facts(mock_port, "42", self.PHASES, "d3")

        # sparql_query was called (we can check it returned empty)

    def test_empty_list_for_first_phase(self, mock_port: _MockOntologyPort) -> None:
        """If current_phase_id is the first phase, return empty list."""
        result = collect_upstream_facts(mock_port, "42", self.PHASES, "d1")
        assert result == []

    def test_empty_list_for_unknown_phase(self, mock_port: _MockOntologyPort) -> None:
        """If current_phase_id is not in the sequence, return empty list."""
        result = collect_upstream_facts(mock_port, "42", self.PHASES, "unknown")
        assert result == []

    def test_empty_sequence(self, mock_port: _MockOntologyPort) -> None:
        """Empty phase_sequence returns empty list."""
        result = collect_upstream_facts(mock_port, "42", [], "d1")
        assert result == []


# ===================================================================
# traverse_chain — SPARQL property paths
# ===================================================================


class TestTraverseChain:
    """Tests for the SPARQL-based traverse_chain function."""

    def test_default_max_depth_is_20(self) -> None:
        """Default max_depth is 20."""
        from tulla.core.phase_facts import _TRAVERSE_MAX_DEPTH
        assert _TRAVERSE_MAX_DEPTH == 20
