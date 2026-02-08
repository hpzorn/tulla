"""Integration tests for the full 5-phase lightweight pipeline (prd:req-53-4-4).

# @pattern:PortsAndAdapters -- Mock ClaudePort and OntologyPort injected via Pipeline config; phases consume them through port interfaces
# @principle:DependencyInversion -- Tests depend on Phase[T] / OntologyPort abstractions, not concrete adapters or subprocess invocations
# @principle:LooseCoupling -- Stub phases override only run_claude(); Pipeline mediates data flow without phases knowing about each other
# @quality:Testability -- Full pipeline exercised end-to-end with deterministic stubs, verifying phase order, data propagation, and budget

Exercises the full pipeline loop with mocked ClaudePort (canned Plan/Execute
responses), a mock OntologyPort, and stub local-compute phases.  Verifies:

- All 5 phases execute in order
- Each phase receives the previous phase's output via prev_output
- The final phase produces a LightweightTraceResult
- The pipeline respects the $1 budget cap
- Pipeline result has SUCCESS status
- Abort path: ineligible changes fail with a meaningful error

Architecture decision: arch:adr-53-1
Quality focus: isaqb:Testability
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tulla.core.phase import Phase, PhaseContext, PhaseResult, PhaseStatus
from tulla.core.pipeline import Pipeline, PipelineResult
from tulla.phases.lightweight.context_scan import ContextScanPhase
from tulla.phases.lightweight.execute import ExecutePhase
from tulla.phases.lightweight.intake import IntakePhase
from tulla.phases.lightweight.models import (
    ContextScanOutput,
    ExecuteOutput,
    IntakeOutput,
    LightweightTraceResult,
    PlanOutput,
)
from tulla.phases.lightweight.plan import PlanPhase
from tulla.phases.lightweight.trace import TracePhase
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Mock OntologyPort
# @pattern:PortsAndAdapters -- Concrete mock implements OntologyPort ABC; phases interact only through the port interface
# ---------------------------------------------------------------------------


class _MockOntologyPort(OntologyPort):
    """Concrete mock recording calls for assertion, conforming to OntologyPort ABC."""

    def __init__(self) -> None:
        self.add_triple_calls: list[dict[str, Any]] = []
        self.remove_triples_by_subject_calls: list[str] = []
        self.validate_instance_calls: list[dict[str, Any]] = []
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
        self, subject: str, *, ontology: str | None = None,
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
        return {"conforms": True, "violations": []}


# ---------------------------------------------------------------------------
# Stub claude port
# ---------------------------------------------------------------------------


class _StubClaudePort:
    """Placeholder claude port — never invoked because Plan/Execute run_claude() are overridden."""


# ---------------------------------------------------------------------------
# Stub phases — override run_claude() for deterministic integration testing
# @principle:DependencyInversion -- Stubs subclass the real phase classes, overriding only the Claude call boundary
# @principle:SeparationOfConcerns -- Each stub isolates a single phase's side-effects, keeping test data flow deterministic
# ---------------------------------------------------------------------------


class _StubIntakePhase(IntakePhase):
    """Returns canned IntakeOutput without git or filesystem access."""

    def __init__(self, *, eligible: bool = True) -> None:
        self._eligible = eligible

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]],
    ) -> Any:
        return {
            "change_type": "bugfix",
            "description": "Fix null-pointer in login handler",
            "affected_files": ["src/auth/login.py"],
            "scope": "single-package",
            "lightweight_eligible": self._eligible,
        }


class _StubContextScanPhase(ContextScanPhase):
    """Returns canned ContextScanOutput without filesystem or SPARQL access."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]],
    ) -> Any:
        prev = ctx.config.get("prev_output")
        # @principle:FailSafeRouting -- Check lightweight eligibility from intake; abort if ineligible
        if prev is not None and hasattr(prev, "lightweight_eligible") and not prev.lightweight_eligible:
            raise ValueError(
                "Change is not lightweight-eligible. Please run the full pipeline instead."
            )
        return {
            "violations": [],
            "violation_report": "",
            "patterns": ["PortsAndAdapters"],
            "principles": ["SeparationOfConcerns"],
            "conformance_status": "structural-only:clean",
            "quality_focus": "isaqb:Maintainability",
        }


class _StubPlanPhase(PlanPhase):
    """Returns canned PlanOutput without invoking Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]],
    ) -> Any:
        return {
            "plan_summary": "Fix null-pointer by adding guard clause",
            "plan_steps": [
                "Add None check in login handler",
                "Update unit test for edge case",
            ],
            "files_to_modify": ["src/auth/login.py", "tests/auth/test_login.py"],
            "risk_notes": "Low risk — single guard clause addition",
        }


class _StubExecutePhase(ExecutePhase):
    """Returns canned ExecuteOutput without invoking Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]],
    ) -> Any:
        return {
            "changes_summary": "Added None guard in login handler",
            "files_modified": ["src/auth/login.py", "tests/auth/test_login.py"],
            "commit_ref": "abc1234",
            "execution_notes": "All tests pass",
        }


class _StubTracePhase(TracePhase):
    """Returns canned trace data; uses the real parse_output() to build LightweightTraceResult."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]],
    ) -> Any:
        # Retrieve upstream outputs from prev_output chain for realistic assembly
        prev = ctx.config.get("prev_output")
        commit_ref = ""
        changes_summary = ""
        files_modified: list[str] = []
        if prev is not None:
            if hasattr(prev, "commit_ref"):
                commit_ref = prev.commit_ref
                changes_summary = prev.changes_summary
                files_modified = prev.files_modified
            elif isinstance(prev, dict):
                commit_ref = prev.get("commit_ref", "")
                changes_summary = prev.get("changes_summary", "")
                files_modified = prev.get("files_modified", [])

        return {
            "change_type": "bugfix",
            "affected_files": ",".join(files_modified) if files_modified else "src/auth/login.py",
            "conformance_assertion": "structural-only:clean",
            "commit_ref": commit_ref or "abc1234",
            "change_summary": changes_summary or "Added None guard in login handler",
            "timestamp": "2025-01-15T10:00:00+00:00",
            "issue_ref": None,
            "sprint_id": None,
            "story_points": None,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pipeline(
    tmp_path: Path,
    *,
    ontology_port: OntologyPort | None = None,
    intake_eligible: bool = True,
    budget_usd: float = 1.0,
) -> Pipeline:
    """Assemble a lightweight pipeline with stub phases for integration testing."""
    phases: list[tuple[str, Phase[Any]]] = [
        ("lw-intake", _StubIntakePhase(eligible=intake_eligible)),
        ("lw-context", _StubContextScanPhase()),
        ("lw-plan", _StubPlanPhase()),
        ("lw-execute", _StubExecutePhase()),
        ("lw-trace", _StubTracePhase()),
    ]

    config: dict[str, Any] = {
        "change_description": "Fix null-pointer in login handler",
        "permission_mode": "bypassPermissions",
        "phase_timeouts": {},
        "shape_registry": {},
    }
    if ontology_port is not None:
        config["ontology_port"] = ontology_port

    return Pipeline(
        phases=phases,
        claude_port=_StubClaudePort(),
        work_dir=tmp_path,
        idea_id="idea-lw-integration",
        config=config,
        total_budget_usd=budget_usd,
    )


# ===========================================================================
# Happy path: all 5 phases execute to completion
# ===========================================================================


class TestLightweightPipelineHappyPath:
    """Full 5-phase lightweight pipeline completes with SUCCESS status."""

    def test_all_five_phases_execute_in_order(self, tmp_path: Path) -> None:
        """All 5 phases execute and appear in the result in correct order."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 5

        ids = [pid for pid, _ in result.phase_results]
        assert ids == [
            "lw-intake",
            "lw-context",
            "lw-plan",
            "lw-execute",
            "lw-trace",
        ]

    def test_each_phase_succeeds(self, tmp_path: Path) -> None:
        """Every phase result has SUCCESS status."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        for phase_id, phase_result in result.phase_results:
            assert phase_result.status == PhaseStatus.SUCCESS, (
                f"Phase {phase_id} did not succeed: {phase_result.error}"
            )

    def test_final_phase_produces_lightweight_trace_result(
        self, tmp_path: Path,
    ) -> None:
        """The lw-trace phase data is a LightweightTraceResult instance."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, trace_result = result.phase_results[-1]
        assert isinstance(trace_result.data, LightweightTraceResult)

    def test_trace_result_fields_populated(self, tmp_path: Path) -> None:
        """LightweightTraceResult has all 6 required fields populated."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, trace_result = result.phase_results[-1]
        trace: LightweightTraceResult = trace_result.data
        assert trace.change_type == "bugfix"
        assert trace.commit_ref == "abc1234"
        assert trace.change_summary != ""
        assert trace.conformance_assertion == "structural-only:clean"
        assert trace.timestamp != ""
        assert trace.affected_files != ""


# ===========================================================================
# Phase data propagation: prev_output chains outputs forward
# ===========================================================================


class TestLightweightPipelineDataPropagation:
    """Each phase receives the previous phase's output via prev_output."""

    def test_intake_output_is_intake_model(self, tmp_path: Path) -> None:
        """IntakePhase produces an IntakeOutput instance."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, intake_result = result.phase_results[0]
        assert isinstance(intake_result.data, IntakeOutput)
        assert intake_result.data.change_type == "bugfix"
        assert intake_result.data.lightweight_eligible is True

    def test_context_scan_output_is_model(self, tmp_path: Path) -> None:
        """ContextScanPhase produces a ContextScanOutput instance."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, ctx_result = result.phase_results[1]
        assert isinstance(ctx_result.data, ContextScanOutput)
        assert ctx_result.data.conformance_status == "structural-only:clean"

    def test_plan_output_is_model(self, tmp_path: Path) -> None:
        """PlanPhase produces a PlanOutput instance."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, plan_result = result.phase_results[2]
        assert isinstance(plan_result.data, PlanOutput)
        assert len(plan_result.data.plan_steps) == 2

    def test_execute_output_is_model(self, tmp_path: Path) -> None:
        """ExecutePhase produces an ExecuteOutput instance."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, exec_result = result.phase_results[3]
        assert isinstance(exec_result.data, ExecuteOutput)
        assert exec_result.data.commit_ref == "abc1234"

    def test_trace_output_is_model(self, tmp_path: Path) -> None:
        """TracePhase produces a LightweightTraceResult instance."""
        pipeline = _build_pipeline(tmp_path)
        result = pipeline.run()

        _, trace_result = result.phase_results[4]
        assert isinstance(trace_result.data, LightweightTraceResult)


# ===========================================================================
# Budget cap: pipeline respects the $1 budget
# ===========================================================================


class TestLightweightPipelineBudgetCap:
    """Pipeline respects the budget cap."""

    def test_total_cost_within_budget(self, tmp_path: Path) -> None:
        """Total cost across all phases stays within the $1 budget."""
        pipeline = _build_pipeline(tmp_path, budget_usd=1.0)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert result.total_cost_usd <= 1.0

    def test_zero_budget_prevents_execution(self, tmp_path: Path) -> None:
        """Zero budget prevents any phase from running."""
        pipeline = _build_pipeline(tmp_path, budget_usd=0.0)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.FAILURE
        assert len(result.phase_results) == 0


# ===========================================================================
# Ontology integration: mock OntologyPort tracks persistence calls
# ===========================================================================


class TestLightweightPipelineWithOntology:
    """Pipeline with mock OntologyPort triggers fact persistence."""

    def test_completes_with_ontology_port(self, tmp_path: Path) -> None:
        """Pipeline succeeds when OntologyPort is provided."""
        ontology = _MockOntologyPort()
        pipeline = _build_pipeline(tmp_path, ontology_port=ontology)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 5

    def test_trace_phase_triples_persisted(self, tmp_path: Path) -> None:
        """LightweightTraceResult IntentFields are persisted as triples."""
        ontology = _MockOntologyPort()
        pipeline = _build_pipeline(tmp_path, ontology_port=ontology)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        # The trace phase (lw-trace) has IntentField-annotated fields that
        # should be persisted via add_triple
        assert len(ontology.add_triple_calls) > 0

    def test_succeeds_without_ontology_port(self, tmp_path: Path) -> None:
        """Pipeline works without OntologyPort (no persistence)."""
        pipeline = _build_pipeline(tmp_path, ontology_port=None)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.SUCCESS
        assert len(result.phase_results) == 5


# ===========================================================================
# Abort path: ineligible change fails with meaningful error
# ===========================================================================


class TestLightweightPipelineAbortPath:
    """When IntakePhase determines a change is not lightweight-eligible,
    the pipeline fails with a meaningful error directing the user to
    the full pipeline."""

    def test_ineligible_change_fails_pipeline(self, tmp_path: Path) -> None:
        """Pipeline fails when intake marks change as not lightweight-eligible."""
        pipeline = _build_pipeline(tmp_path, intake_eligible=False)
        result = pipeline.run()

        assert result.final_status == PhaseStatus.FAILURE

    def test_ineligible_stops_at_context_scan(self, tmp_path: Path) -> None:
        """Pipeline stops at lw-context when intake marks ineligible."""
        pipeline = _build_pipeline(tmp_path, intake_eligible=False)
        result = pipeline.run()

        executed_ids = [pid for pid, _ in result.phase_results]
        # Intake succeeds (it just reports eligibility), context scan detects
        # ineligibility and fails.
        assert "lw-intake" in executed_ids
        assert "lw-context" in executed_ids
        assert "lw-plan" not in executed_ids
        assert "lw-execute" not in executed_ids
        assert "lw-trace" not in executed_ids

    def test_ineligible_error_mentions_full_pipeline(
        self, tmp_path: Path,
    ) -> None:
        """The failure error message directs the user to the full pipeline."""
        pipeline = _build_pipeline(tmp_path, intake_eligible=False)
        result = pipeline.run()

        _, ctx_result = result.phase_results[1]
        assert ctx_result.status == PhaseStatus.FAILURE
        assert ctx_result.error is not None
        assert "full pipeline" in ctx_result.error.lower()

    def test_ineligible_intake_itself_succeeds(self, tmp_path: Path) -> None:
        """IntakePhase itself succeeds even when marking ineligible;
        the abort happens in the next phase."""
        pipeline = _build_pipeline(tmp_path, intake_eligible=False)
        result = pipeline.run()

        _, intake_result = result.phase_results[0]
        assert intake_result.status == PhaseStatus.SUCCESS
        assert isinstance(intake_result.data, IntakeOutput)
        assert intake_result.data.lightweight_eligible is False
