"""Tests for tulla.core.pipeline — Pipeline executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from pydantic import BaseModel

from tulla.core.checkpoint import CheckpointStore
from tulla.core.intent import IntentField
from tulla.namespaces import PHASE_NS, TRACE_NS, RDF_TYPE
from tulla.core.phase import (
    Phase,
    PhaseContext,
    PhaseResult,
    PhaseStatus,
)
from tulla.core.pipeline import Pipeline, PipelineResult
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubPhase(Phase[str]):
    """Minimal concrete phase for testing.

    Returns a deterministic result based on constructor args.
    """

    def __init__(
        self,
        output: str = "ok",
        status: PhaseStatus = PhaseStatus.SUCCESS,
        cost: float = 0.0,
    ) -> None:
        self._output = output
        self._status = status
        self._cost = cost

    def build_prompt(self, ctx: PhaseContext) -> str:
        return "stub-prompt"

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return []

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        return self._output

    def parse_output(self, ctx: PhaseContext, raw: Any) -> str:
        return raw

    def execute(self, ctx: PhaseContext) -> PhaseResult[str]:
        """Override execute to honour configured status and cost."""
        if self._status == PhaseStatus.SUCCESS:
            return PhaseResult(
                status=PhaseStatus.SUCCESS,
                data=self._output,
                metadata={"cost_usd": self._cost},
            )
        return PhaseResult(
            status=self._status,
            error="stub failure",
            metadata={"cost_usd": self._cost},
        )


class StubClaudePort:
    """Placeholder claude port for pipeline tests."""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPipelineThreePhaseSuccess:
    """Pipeline runs three phases to completion and aggregates results."""

    def test_all_phases_succeed(self, tmp_path: Path) -> None:
        phases = [
            ("phase-a", StubPhase(output="result-a", cost=0.10)),
            ("phase-b", StubPhase(output="result-b", cost=0.20)),
            ("phase-c", StubPhase(output="result-c", cost=0.30)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-1",
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 3
        ids = [pid for pid, _ in result.phase_results]
        assert ids == ["phase-a", "phase-b", "phase-c"]
        assert result.total_cost_usd == pytest.approx(0.60)

    def test_phase_data_propagated(self, tmp_path: Path) -> None:
        """Each phase result carries its own data."""
        phases = [
            ("p1", StubPhase(output="one")),
            ("p2", StubPhase(output="two")),
            ("p3", StubPhase(output="three")),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-2",
            total_budget_usd=1.00,
        )
        result = pipeline.run()

        data = [pr.data for _, pr in result.phase_results]
        assert data == ["one", "two", "three"]


class TestPipelineStopOnFailure:
    """Pipeline stops immediately when a phase fails."""

    def test_stops_at_failing_phase(self, tmp_path: Path) -> None:
        phases = [
            ("p1", StubPhase(output="ok", cost=0.10)),
            ("p2", StubPhase(status=PhaseStatus.FAILURE, cost=0.05)),
            ("p3", StubPhase(output="should-not-run")),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-3",
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.FAILURE
        assert len(result.phase_results) == 2
        assert result.phase_results[0][0] == "p1"
        assert result.phase_results[1][0] == "p2"
        assert result.total_cost_usd == pytest.approx(0.15)

    def test_timeout_also_stops(self, tmp_path: Path) -> None:
        phases = [
            ("p1", StubPhase(status=PhaseStatus.TIMEOUT)),
            ("p2", StubPhase(output="unreachable")),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-4",
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.TIMEOUT
        assert len(result.phase_results) == 1


class TestPipelineStartFromResume:
    """Pipeline resumes execution from a specified phase."""

    def test_skips_earlier_phases(self, tmp_path: Path) -> None:
        # Pre-create a checkpoint for p1 so prev_output can be loaded.
        store = CheckpointStore(tmp_path)
        store.save("p1", {"status": "SUCCESS", "data": "saved-data"})

        phases = [
            ("p1", StubPhase(output="should-skip")),
            ("p2", StubPhase(output="resumed", cost=0.10)),
            ("p3", StubPhase(output="final", cost=0.05)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-5",
            total_budget_usd=1.00,
        )

        result = pipeline.run(start_from="p2")

        assert result.final_status == PhaseStatus.SUCCESS
        # Only p2 and p3 executed.
        assert len(result.phase_results) == 2
        ids = [pid for pid, _ in result.phase_results]
        assert ids == ["p2", "p3"]
        assert result.total_cost_usd == pytest.approx(0.15)

    def test_start_from_first_phase(self, tmp_path: Path) -> None:
        """start_from the first phase is equivalent to a full run."""
        phases = [
            ("p1", StubPhase(output="a")),
            ("p2", StubPhase(output="b")),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-6",
            total_budget_usd=1.00,
        )

        result = pipeline.run(start_from="p1")

        assert len(result.phase_results) == 2


class TestPipelineBudgetDecrement:
    """Budget is decremented after each phase based on cost_usd metadata."""

    def test_budget_decreases_per_phase(self, tmp_path: Path) -> None:
        phases = [
            ("p1", StubPhase(output="a", cost=0.30)),
            ("p2", StubPhase(output="b", cost=0.20)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-7",
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.total_cost_usd == pytest.approx(0.50)
        assert result.final_status == PhaseStatus.SUCCESS


class TestPipelineBudgetExhaustion:
    """Pipeline stops when budget is exhausted."""

    def test_stops_when_budget_zero(self, tmp_path: Path) -> None:
        """With zero budget, no phases execute."""
        phases = [
            ("p1", StubPhase(output="a", cost=0.10)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-8",
            total_budget_usd=0.0,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.FAILURE
        assert len(result.phase_results) == 0

    def test_stops_when_budget_consumed(self, tmp_path: Path) -> None:
        """Budget consumed by first phase prevents second from running."""
        phases = [
            ("p1", StubPhase(output="a", cost=0.50)),
            ("p2", StubPhase(output="b", cost=0.10)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-9",
            total_budget_usd=0.50,
        )

        result = pipeline.run()

        # p1 succeeds but consumes all budget; p2 never runs.
        assert len(result.phase_results) == 1
        assert result.phase_results[0][0] == "p1"
        assert result.final_status == PhaseStatus.FAILURE
        assert result.total_cost_usd == pytest.approx(0.50)


class TestPipelineCheckpointWriting:
    """Pipeline writes checkpoints after each executed phase."""

    def test_checkpoints_created(self, tmp_path: Path) -> None:
        phases = [
            ("alpha", StubPhase(output="data-a", cost=0.01)),
            ("beta", StubPhase(output="data-b", cost=0.02)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-10",
            total_budget_usd=1.00,
        )

        pipeline.run()

        store = CheckpointStore(tmp_path)
        assert store.exists("alpha")
        assert store.exists("beta")

        alpha_data = store.load("alpha")
        assert alpha_data is not None
        assert alpha_data["status"] == "SUCCESS"
        assert alpha_data["data"] == "data-a"

        beta_data = store.load("beta")
        assert beta_data is not None
        assert beta_data["data"] == "data-b"

    def test_checkpoint_on_failure(self, tmp_path: Path) -> None:
        """Failing phase still gets its checkpoint saved."""
        phases = [
            ("ok", StubPhase(output="fine")),
            ("bad", StubPhase(status=PhaseStatus.FAILURE)),
        ]
        pipeline = Pipeline(
            phases=phases,
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-11",
            total_budget_usd=1.00,
        )

        pipeline.run()

        store = CheckpointStore(tmp_path)
        assert store.exists("ok")
        assert store.exists("bad")
        bad_data = store.load("bad")
        assert bad_data is not None
        assert bad_data["status"] == "FAILURE"


# ---------------------------------------------------------------------------
# Integration tests for pre-phase / post-phase hooks (prd:req-67-3-1)
# ---------------------------------------------------------------------------


class _AnnotatedOutput(BaseModel):
    """Pydantic model with an IntentField for integration testing."""

    summary: str = IntentField(default="", description="Intent-annotated summary")


class AnnotatedPhase(Phase[_AnnotatedOutput]):
    """Phase that returns an IntentField-annotated Pydantic model."""

    def __init__(self, output: _AnnotatedOutput) -> None:
        self._output = output
        self._received_ctx: PhaseContext | None = None

    def build_prompt(self, ctx: PhaseContext) -> str:
        return "stub"

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return []

    def parse_output(self, ctx: PhaseContext, raw: Any) -> _AnnotatedOutput:
        return raw

    def execute(self, ctx: PhaseContext) -> PhaseResult[_AnnotatedOutput]:
        self._received_ctx = ctx
        return PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=self._output,
            metadata={"cost_usd": 0.01},
        )


class MockOntologyPort(OntologyPort):
    """Concrete mock that tracks calls for assertion."""

    def __init__(self) -> None:
        self.add_triple_calls: list[tuple[str, str, str]] = []
        self.remove_triples_by_subject_calls: list[str] = []
        self.sparql_query_calls: list[str] = []

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

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {"conforms": True, "violations": []}

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.add_triple_calls.append((subject, predicate, object))
        return {"status": "added"}

    def remove_triples_by_subject(self, subject: str, *, ontology: str | None = None) -> int:
        self.remove_triples_by_subject_calls.append(subject)
        return 0


class TestPipelinePhaseHooks:
    """Integration tests for pre-phase and post-phase hooks."""

    def test_add_triple_called_after_execute(self, tmp_path: Path) -> None:
        """add_triple is called after phase.execute for annotated output."""
        ontology = MockOntologyPort()
        output = _AnnotatedOutput(summary="test summary")
        phase = AnnotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("annotated", phase)],
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-42",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        # add_triple must have been called (at least for the intent field)
        predicates = [p for _, p, _ in ontology.add_triple_calls]
        assert f"{PHASE_NS}preserves-summary" in predicates

    def test_checkpoint_saved_after_persistence(self, tmp_path: Path) -> None:
        """Checkpoint file exists after persistence completes."""
        ontology = MockOntologyPort()
        output = _AnnotatedOutput(summary="persisted")
        phase = AnnotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("cp-phase", phase)],
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-43",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        pipeline.run()

        store = CheckpointStore(tmp_path)
        assert store.exists("cp-phase")
        saved = store.load("cp-phase")
        assert saved is not None
        assert saved["status"] == "SUCCESS"

    def test_upstream_facts_in_phase_context(self, tmp_path: Path) -> None:
        """upstream_facts key is present in the phase context config."""
        ontology = MockOntologyPort()
        output = _AnnotatedOutput(summary="hello")
        phase = AnnotatedPhase(output=output)

        pipeline = Pipeline(
            phases=[("uf-phase", phase)],
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-44",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        pipeline.run()

        # The phase captured the context it received.
        assert phase._received_ctx is not None
        assert "upstream_facts" in phase._received_ctx.config
        # First phase has no upstream facts.
        assert phase._received_ctx.config["upstream_facts"] == []

    def test_rollback_stops_pipeline(self, tmp_path: Path) -> None:
        """When persist rolls back, phase status becomes FAILURE and pipeline stops."""
        ontology = MockOntologyPort()
        # Make validate_instance return non-conforming to trigger rollback.
        ontology.validate_instance = lambda *a, **kw: {  # type: ignore[assignment]
            "conforms": False,
            "violations": ["missing required field"],
        }

        output = _AnnotatedOutput(summary="will-fail-validation")
        phase_a = AnnotatedPhase(output=output)
        phase_b = AnnotatedPhase(output=_AnnotatedOutput(summary="unreachable"))

        pipeline = Pipeline(
            phases=[("val-phase", phase_a), ("next", phase_b)],
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-45",
            config={
                "ontology_port": ontology,
                "shape_registry": {"val-phase": "shape:TestShape"},
            },
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.FAILURE
        assert len(result.phase_results) == 1
        assert result.phase_results[0][0] == "val-phase"

    def test_predecessor_tracking_across_phases(self, tmp_path: Path) -> None:
        """Predecessor phase_id is passed to the second phase's persist call."""
        ontology = MockOntologyPort()
        output_a = _AnnotatedOutput(summary="from-a")
        output_b = _AnnotatedOutput(summary="from-b")
        phase_a = AnnotatedPhase(output=output_a)
        phase_b = AnnotatedPhase(output=output_b)

        pipeline = Pipeline(
            phases=[("pa", phase_a), ("pb", phase_b)],
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-46",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        # Phase B should have a trace:tracesTo pointing to Phase A's subject
        trace_calls = [
            (s, p, o)
            for s, p, o in ontology.add_triple_calls
            if p == f"{TRACE_NS}tracesTo"
        ]
        # Phase A has no predecessor, Phase B traces to Phase A
        assert len(trace_calls) == 1
        subject_b = f"{PHASE_NS}idea-46-pb"
        predecessor_a = f"{PHASE_NS}idea-46-pa"
        assert trace_calls[0] == (subject_b, f"{TRACE_NS}tracesTo", predecessor_a)

    def test_no_persister_without_ontology_port(self, tmp_path: Path) -> None:
        """Pipeline works normally without ontology_port in config."""
        phase = AnnotatedPhase(output=_AnnotatedOutput(summary="plain"))

        pipeline = Pipeline(
            phases=[("simple", phase)],
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-47",
            total_budget_usd=1.00,
        )

        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert pipeline._persister is None
        # upstream_facts still in context as empty list
        assert phase._received_ctx is not None
        assert phase._received_ctx.config["upstream_facts"] == []
