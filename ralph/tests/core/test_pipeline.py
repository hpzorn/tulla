"""Tests for tulla.core.pipeline — Pipeline executor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tulla.core.checkpoint import CheckpointStore
from tulla.core.phase import (
    Phase,
    PhaseContext,
    PhaseResult,
    PhaseStatus,
)
from tulla.core.pipeline import Pipeline, PipelineResult


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
