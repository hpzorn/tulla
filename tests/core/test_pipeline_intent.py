"""Integration tests for pipeline intent preservation (prd:req-67-6-4).

Exercises the full pipeline loop with mocked OntologyPort and minimal
test phases to verify that fact persistence, SHACL validation, upstream
fact injection, checkpoint resume, and the no-ontology fallback all
behave correctly end-to-end.

Architecture decision: arch:adr-67-2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from tulla.core.checkpoint import CheckpointStore
from tulla.core.intent import IntentField
from tulla.core.phase import Phase, PhaseContext, PhaseResult, PhaseStatus
from tulla.core.pipeline import Pipeline, PipelineResult
from tulla.namespaces import PHASE_NS, TRACE_NS, RDF_TYPE
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Helpers – annotated & unannotated outputs, minimal phases, mock port
# ---------------------------------------------------------------------------


class _AnnotatedOutput(BaseModel):
    """Pydantic model with an IntentField for integration testing."""

    summary: str = IntentField(
        default="", description="Intent-annotated summary",
    )


class _UnannotatedOutput(BaseModel):
    """Pydantic model with NO IntentField annotations."""

    plain_value: str = ""


class _AnnotatedPhase(Phase[_AnnotatedOutput]):
    """Phase returning an IntentField-annotated Pydantic model."""

    def __init__(self, output: _AnnotatedOutput) -> None:
        self._output = output
        self._received_ctx: PhaseContext | None = None

    def build_prompt(self, ctx: PhaseContext) -> str:
        return "stub"

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return []

    def parse_output(self, ctx: PhaseContext, raw: Any) -> _AnnotatedOutput:
        return raw  # pragma: no cover

    def execute(self, ctx: PhaseContext) -> PhaseResult[_AnnotatedOutput]:
        self._received_ctx = ctx
        return PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=self._output,
            metadata={"cost_usd": 0.01},
        )


class _UnannotatedPhase(Phase[_UnannotatedOutput]):
    """Phase returning a Pydantic model WITHOUT intent annotations."""

    def __init__(self, output: _UnannotatedOutput) -> None:
        self._output = output

    def build_prompt(self, ctx: PhaseContext) -> str:
        return "stub"

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return []

    def parse_output(self, ctx: PhaseContext, raw: Any) -> _UnannotatedOutput:
        return raw  # pragma: no cover

    def execute(self, ctx: PhaseContext) -> PhaseResult[_UnannotatedOutput]:
        return PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=self._output,
            metadata={"cost_usd": 0.01},
        )


class _StubClaudePort:
    """Placeholder claude port."""


class _MockOntologyPort(OntologyPort):
    """Concrete mock recording all calls for assertion."""

    def __init__(
        self,
        *,
        validate_conforms: bool = True,
        validate_violations: list[str] | None = None,
        sparql_results: list[dict[str, Any]] | None = None,
    ) -> None:
        self.add_triple_calls: list[dict[str, Any]] = []
        self.remove_triples_by_subject_calls: list[str] = []
        self.validate_instance_calls: list[dict[str, Any]] = []
        self.sparql_query_calls: list[str] = []
        self._validate_conforms = validate_conforms
        self._validate_violations = validate_violations or []
        self._sparql_results = sparql_results

    # -- required abstract methods --

    def query_ideas(self, **kwargs: Any) -> dict[str, Any]:
        return {"ideas": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        return {"stored": True}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        return {"facts": []}

    def sparql_query(
        self, query: str, *, validate: bool = True,
    ) -> dict[str, Any]:
        self.sparql_query_calls.append(query)
        if self._sparql_results is not None:
            return {"results": self._sparql_results}
        return {"results": []}

    def update_idea(self, idea_id: str, **kwargs: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(
        self, idea_id: str, new_state: str, *, reason: str = "",
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
        self.add_triple_calls.append({
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
        self.remove_triples_by_subject_calls.append(subject)
        return 0

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.validate_instance_calls.append(
            {"instance_uri": instance_uri, "shape_uri": shape_uri},
        )
        return {
            "conforms": self._validate_conforms,
            "violations": self._validate_violations,
        }


# ---------------------------------------------------------------------------
# Case 1: Annotated phase persists triples after execute, before checkpoint
# ---------------------------------------------------------------------------


class TestAnnotatedPhasePersistsTriples:
    """Pipeline with one annotated phase persists triples after execute
    and before checkpoint save."""

    def test_triples_stored_and_checkpoint_exists(self, tmp_path: Path) -> None:
        ontology = _MockOntologyPort()
        output = _AnnotatedOutput(summary="integration-test-summary")
        phase = _AnnotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("d5", phase)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-100",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        # Pipeline succeeds
        assert result.final_status == PhaseStatus.SUCCESS

        # Idempotent cleanup was called before storing
        expected_subject = f"{PHASE_NS}idea-100-d5"
        assert expected_subject in ontology.remove_triples_by_subject_calls

        # Intent field was persisted via add_triple
        predicates = [c["predicate"] for c in ontology.add_triple_calls]
        assert f"{PHASE_NS}preserves-summary" in predicates

        # Metadata triples stored (producedBy, forRequirement)
        assert f"{PHASE_NS}producedBy" in predicates
        assert f"{PHASE_NS}forRequirement" in predicates

        # rdf:type triple stored
        assert RDF_TYPE in predicates

        # Checkpoint was saved AFTER persistence
        store = CheckpointStore(tmp_path)
        assert store.exists("d5")
        saved = store.load("d5")
        assert saved is not None
        assert saved["status"] == "SUCCESS"

    def test_add_triple_receives_correct_subject(
        self, tmp_path: Path,
    ) -> None:
        """Subject follows the full-URI naming convention."""
        ontology = _MockOntologyPort()
        output = _AnnotatedOutput(summary="check-naming")
        phase = _AnnotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("r5", phase)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-200",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )
        pipeline.run()

        expected_subject = f"{PHASE_NS}idea-200-r5"

        for call in ontology.add_triple_calls:
            assert call["subject"] == expected_subject


# ---------------------------------------------------------------------------
# Case 2: Unannotated phase persists no triples, completes normally
# ---------------------------------------------------------------------------


class TestUnannotatedPhaseNoTriples:
    """Pipeline with one unannotated phase persists no triples and
    completes normally."""

    def test_no_add_triple_calls(self, tmp_path: Path) -> None:
        ontology = _MockOntologyPort()
        output = _UnannotatedOutput(plain_value="no-intent")
        phase = _UnannotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("plain", phase)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-300",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 1
        # No intent fields → no add_triple calls
        assert ontology.add_triple_calls == []
        # Checkpoint still saved
        store = CheckpointStore(tmp_path)
        assert store.exists("plain")


# ---------------------------------------------------------------------------
# Case 3: SHACL validation failure stops pipeline with FAILURE status
# ---------------------------------------------------------------------------


class TestShaclValidationFailureStopsPipeline:
    """SHACL validation failure stops pipeline at that phase with
    FAILURE status."""

    def test_validation_failure_marks_failure_and_stops(
        self, tmp_path: Path,
    ) -> None:
        ontology = _MockOntologyPort(
            validate_conforms=False,
            validate_violations=["sh:MinCountConstraintComponent"],
        )
        output = _AnnotatedOutput(summary="will-fail-shacl")
        phase_a = _AnnotatedPhase(output=output)
        phase_b = _AnnotatedPhase(output=_AnnotatedOutput(summary="unreachable"))

        pipeline = Pipeline(
            phases=[("d5", phase_a), ("r5", phase_b)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-400",
            config={
                "ontology_port": ontology,
                "shape_registry": {"d5": f"{PHASE_NS}D5OutputShape"},
            },
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        # Pipeline stopped at d5 with FAILURE
        assert result.final_status == PhaseStatus.FAILURE
        assert len(result.phase_results) == 1
        assert result.phase_results[0][0] == "d5"
        assert result.phase_results[0][1].status == PhaseStatus.FAILURE

        # validate_instance was called
        assert len(ontology.validate_instance_calls) == 1
        assert ontology.validate_instance_calls[0]["shape_uri"] == f"{PHASE_NS}D5OutputShape"

        # Triples were rolled back (remove_triples_by_subject called twice:
        # once for idempotent cleanup, once for rollback)
        expected_subject = f"{PHASE_NS}idea-400-d5"
        rollback_count = ontology.remove_triples_by_subject_calls.count(expected_subject)
        assert rollback_count == 2  # cleanup + rollback

    def test_second_phase_never_executes(self, tmp_path: Path) -> None:
        """When SHACL fails at phase A, phase B is never reached."""
        ontology = _MockOntologyPort(
            validate_conforms=False,
            validate_violations=["missing field"],
        )
        phase_a = _AnnotatedPhase(
            output=_AnnotatedOutput(summary="fails-validation"),
        )
        phase_b = _AnnotatedPhase(
            output=_AnnotatedOutput(summary="should-not-run"),
        )

        pipeline = Pipeline(
            phases=[("first", phase_a), ("second", phase_b)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-401",
            config={
                "ontology_port": ontology,
                "shape_registry": {"first": "shape:TestShape"},
            },
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.FAILURE
        executed_ids = [pid for pid, _ in result.phase_results]
        assert "second" not in executed_ids


# ---------------------------------------------------------------------------
# Case 4: upstream_facts injected into phase context for second phase
# ---------------------------------------------------------------------------


class TestUpstreamFactsInjected:
    """upstream_facts from phase A are injected into phase B context."""

    def test_second_phase_receives_upstream_facts(
        self, tmp_path: Path,
    ) -> None:
        upstream_fact = {
            "s": f"{PHASE_NS}idea-500-pa",
            "p": f"{PHASE_NS}preserves-summary",
            "o": "from-phase-a",
        }

        ontology = _MockOntologyPort(sparql_results=[upstream_fact])
        output_a = _AnnotatedOutput(summary="from-phase-a")
        output_b = _AnnotatedOutput(summary="from-phase-b")
        phase_a = _AnnotatedPhase(output=output_a)
        phase_b = _AnnotatedPhase(output=output_b)

        pipeline = Pipeline(
            phases=[("pa", phase_a), ("pb", phase_b)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-500",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS

        # Phase A (first phase) receives empty upstream_facts
        assert phase_a._received_ctx is not None
        assert phase_a._received_ctx.config["upstream_facts"] == []

        # Phase B receives upstream_facts from phase A via SPARQL
        assert phase_b._received_ctx is not None
        upstream = phase_b._received_ctx.config["upstream_facts"]
        assert len(upstream) == 1
        assert upstream[0]["predicate"] == f"{PHASE_NS}preserves-summary"
        assert upstream[0]["object"] == "from-phase-a"


# ---------------------------------------------------------------------------
# Case 5: Pipeline resume from checkpoint still collects upstream facts
# ---------------------------------------------------------------------------


class TestResumeCollectsUpstreamFacts:
    """Pipeline resume from checkpoint still collects upstream facts
    via SPARQL."""

    def test_resume_injects_upstream_from_prior_phase(
        self, tmp_path: Path,
    ) -> None:
        # Pre-create checkpoint for phase-a so pipeline can skip it.
        store = CheckpointStore(tmp_path)
        store.save("pa", {
            "status": "SUCCESS",
            "data": {"summary": "persisted-earlier"},
            "metadata": {"cost_usd": 0.01},
        })

        prior_fact = {
            "s": f"{PHASE_NS}idea-600-pa",
            "p": f"{PHASE_NS}preserves-summary",
            "o": "persisted-earlier",
        }

        ontology = _MockOntologyPort(sparql_results=[prior_fact])
        output_b = _AnnotatedOutput(summary="resumed-phase-b")
        phase_a = _AnnotatedPhase(output=_AnnotatedOutput(summary="skipped"))
        phase_b = _AnnotatedPhase(output=output_b)

        pipeline = Pipeline(
            phases=[("pa", phase_a), ("pb", phase_b)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-600",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run(start_from="pb")

        assert result.final_status == PhaseStatus.SUCCESS
        # Only pb was executed
        assert len(result.phase_results) == 1
        assert result.phase_results[0][0] == "pb"

        # Phase B received upstream facts from SPARQL query
        assert phase_b._received_ctx is not None
        upstream = phase_b._received_ctx.config["upstream_facts"]
        assert len(upstream) == 1
        assert upstream[0]["object"] == "persisted-earlier"


# ---------------------------------------------------------------------------
# Case 6: Pipeline without ontology_port skips hook entirely
# ---------------------------------------------------------------------------


class TestNoOntologyPortSkipsHook:
    """Pipeline without ontology_port in config skips hook entirely
    and runs as before."""

    def test_no_ontology_port_runs_normally(self, tmp_path: Path) -> None:
        output = _AnnotatedOutput(summary="no-ontology")
        phase = _AnnotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("solo", phase)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-700",
            # No ontology_port in config
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 1
        # No persister was created
        assert pipeline._persister is None

        # Phase still received upstream_facts key (empty list fallback)
        assert phase._received_ctx is not None
        assert phase._received_ctx.config["upstream_facts"] == []

        # Checkpoint was still saved
        store = CheckpointStore(tmp_path)
        assert store.exists("solo")

    def test_no_ontology_multi_phase_completes(self, tmp_path: Path) -> None:
        """Multiple phases without ontology_port all complete normally."""
        phase_a = _AnnotatedPhase(output=_AnnotatedOutput(summary="a"))
        phase_b = _AnnotatedPhase(output=_AnnotatedOutput(summary="b"))

        pipeline = Pipeline(
            phases=[("pa", phase_a), ("pb", phase_b)],
            claude_port=_StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-701",
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 2
        assert pipeline._persister is None
