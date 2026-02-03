"""Manual intent preservation verification for D5Output (prd:req-67-7-2).

Runs a discovery pipeline with a D5 phase using real D5Output annotations,
then uses recall_facts(context="phase-idea-{id}-d5") to verify that the
mode and recommendation values are stored as A-Box facts with exact,
verbatim values — no summarization or lossy transformation.

Quality focus: isaqb:FunctionalCorrectness
Architecture decision: arch:adr-67-5
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from tulla.core.intent import IntentField, extract_intent_fields
from tulla.core.phase import Phase, PhaseContext, PhaseResult, PhaseStatus
from tulla.core.pipeline import Pipeline
from tulla.phases.discovery.models import D5Output
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Mock ontology port that records stores and replays them on recall
# ---------------------------------------------------------------------------


class _RecordingOntologyPort(OntologyPort):
    """Ontology port that records store_fact calls and returns them on recall.

    Unlike a simple mock, this port faithfully stores facts in memory and
    returns them when recall_facts is called with a matching context,
    simulating the real ontology-server round-trip.
    """

    def __init__(self) -> None:
        self._facts: list[dict[str, Any]] = []
        self._next_id = 0
        self.store_fact_calls: list[dict[str, Any]] = []
        self.forget_by_context_calls: list[str] = []

    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        fact = {
            "fact_id": str(self._next_id),
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "context": context,
            "confidence": confidence,
        }
        self._next_id += 1
        self._facts.append(fact)
        self.store_fact_calls.append(fact)
        return {"stored": True, "fact_id": fact["fact_id"]}

    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        matched = [
            f
            for f in self._facts
            if (subject is None or f["subject"] == subject)
            and (predicate is None or f["predicate"] == predicate)
            and (context is None or f["context"] == context)
        ]
        return {"facts": matched[:limit]}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        self._facts = [f for f in self._facts if f["fact_id"] != fact_id]
        return {"deleted": True}

    def forget_by_context(self, context: str) -> int:
        self.forget_by_context_calls.append(context)
        before = len(self._facts)
        self._facts = [f for f in self._facts if f.get("context") != context]
        return before - len(self._facts)

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {"conforms": True, "violations": []}

    # --- Unused abstract methods ---

    def query_ideas(self, **kwargs: Any) -> dict[str, Any]:
        return {"ideas": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def sparql_query(
        self, query: str, *, validate: bool = True,
    ) -> dict[str, Any]:
        return {}

    def update_idea(self, idea_id: str, **kwargs: Any) -> dict[str, Any]:
        return {}

    def set_lifecycle(
        self, idea_id: str, new_state: str, *, reason: str = "",
    ) -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Stub phase that emits a real D5Output with known field values
# ---------------------------------------------------------------------------


class _D5StubPhase(Phase[D5Output]):
    """Phase that returns a real D5Output with predetermined field values.

    Uses the actual D5Output model from discovery/models.py so that the
    IntentField annotations on ``mode`` and ``recommendation`` are exercised
    in the pipeline's persistence hook.
    """

    def __init__(self, d5_output: D5Output) -> None:
        self._output = d5_output

    def build_prompt(self, ctx: PhaseContext) -> str:
        return "stub"

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return []

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D5Output:
        return raw  # pragma: no cover

    def execute(self, ctx: PhaseContext) -> PhaseResult[D5Output]:
        return PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=self._output,
            metadata={"cost_usd": 0.01},
        )


# ---------------------------------------------------------------------------
# Test: Manual Intent Preservation Verification
# ---------------------------------------------------------------------------


class TestD5IntentPreservation:
    """Verify that D5Output intent fields are persisted as verbatim A-Box
    facts and can be recalled with exact values."""

    # Canonical D5 field values used across all tests in this class.
    D5_MODE = "upstream"
    D5_RECOMMENDATION = (
        "Proceed with research phase; the idea has strong alignment "
        "with existing MCP infrastructure but needs persona validation "
        "before committing to implementation."
    )
    IDEA_ID = "idea-772"

    @pytest.fixture()
    def _pipeline_result(self, tmp_path: Path) -> tuple[
        _RecordingOntologyPort, D5Output,
    ]:
        """Run a pipeline with a D5 stub phase and return the ontology port."""
        d5_output = D5Output(
            output_file=tmp_path / "d5-research-brief.md",
            mode=self.D5_MODE,
            recommendation=self.D5_RECOMMENDATION,
        )

        ontology = _RecordingOntologyPort()
        phase = _D5StubPhase(d5_output)

        pipeline = Pipeline(
            phases=[("d5", phase)],
            claude_port=object(),
            work_dir=tmp_path,
            idea_id=self.IDEA_ID,
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()
        assert result.final_status == PhaseStatus.SUCCESS

        return ontology, d5_output

    def test_recall_facts_returns_d5_mode_verbatim(
        self, _pipeline_result: tuple[_RecordingOntologyPort, D5Output],
    ) -> None:
        """recall_facts for D5 context returns mode with exact original value."""
        ontology, d5_output = _pipeline_result
        context = f"phase-idea-{self.IDEA_ID}-d5"

        recalled = ontology.recall_facts(context=context)
        facts = recalled["facts"]

        mode_facts = [
            f for f in facts if f["predicate"] == "phase:preserves-mode"
        ]
        assert len(mode_facts) == 1, (
            f"Expected exactly 1 mode fact, got {len(mode_facts)}"
        )
        assert mode_facts[0]["object"] == self.D5_MODE, (
            f"Mode value mismatch: stored={mode_facts[0]['object']!r}, "
            f"expected={self.D5_MODE!r}"
        )

    def test_recall_facts_returns_d5_recommendation_verbatim(
        self, _pipeline_result: tuple[_RecordingOntologyPort, D5Output],
    ) -> None:
        """recall_facts for D5 context returns recommendation with exact value."""
        ontology, d5_output = _pipeline_result
        context = f"phase-idea-{self.IDEA_ID}-d5"

        recalled = ontology.recall_facts(context=context)
        facts = recalled["facts"]

        rec_facts = [
            f
            for f in facts
            if f["predicate"] == "phase:preserves-recommendation"
        ]
        assert len(rec_facts) == 1, (
            f"Expected exactly 1 recommendation fact, got {len(rec_facts)}"
        )
        assert rec_facts[0]["object"] == self.D5_RECOMMENDATION, (
            f"Recommendation value mismatch: "
            f"stored={rec_facts[0]['object']!r}, "
            f"expected={self.D5_RECOMMENDATION!r}"
        )

    def test_no_lossy_transformation_on_multiline_recommendation(
        self, tmp_path: Path,
    ) -> None:
        """A multi-line recommendation with special characters survives
        the persist-recall round trip with zero transformation."""
        raw_recommendation = (
            "Phase 1: Research existing MCP tools\n"
            "Phase 2: Build prototype with <tool_use> patterns\n"
            "Phase 3: Validate with users — ensure 95% satisfaction\n"
            "Budget: $500 | Timeline: 2 sprints"
        )
        d5_output = D5Output(
            output_file=tmp_path / "d5-output.md",
            mode="downstream",
            recommendation=raw_recommendation,
        )

        ontology = _RecordingOntologyPort()
        phase = _D5StubPhase(d5_output)

        pipeline = Pipeline(
            phases=[("d5", phase)],
            claude_port=object(),
            work_dir=tmp_path,
            idea_id="idea-773",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )

        result = pipeline.run()
        assert result.final_status == PhaseStatus.SUCCESS

        # Recall via the documented context pattern
        context = "phase-idea-idea-773-d5"
        recalled = ontology.recall_facts(context=context)
        facts = recalled["facts"]

        rec_facts = [
            f
            for f in facts
            if f["predicate"] == "phase:preserves-recommendation"
        ]
        assert len(rec_facts) == 1
        assert rec_facts[0]["object"] == raw_recommendation, (
            "Multi-line recommendation was transformed during persist/recall"
        )

        mode_facts = [
            f for f in facts if f["predicate"] == "phase:preserves-mode"
        ]
        assert len(mode_facts) == 1
        assert mode_facts[0]["object"] == "downstream"

    def test_d5output_intent_fields_are_exactly_mode_and_recommendation(
        self,
    ) -> None:
        """D5Output has exactly two IntentField annotations: mode and
        recommendation.  output_file must NOT be an intent field."""
        d5 = D5Output(
            output_file=Path("/tmp/test.md"),
            mode="upstream",
            recommendation="test",
        )
        intent_fields = extract_intent_fields(d5)

        assert set(intent_fields.keys()) == {"mode", "recommendation"}, (
            f"Expected intent fields {{'mode', 'recommendation'}}, "
            f"got {set(intent_fields.keys())}"
        )
        # output_file must NOT leak into intent fields
        assert "output_file" not in intent_fields

    def test_recalled_facts_include_metadata_alongside_intent(
        self, _pipeline_result: tuple[_RecordingOntologyPort, D5Output],
    ) -> None:
        """Recalled facts include both intent fields and metadata
        (producedBy, forRequirement) — the full A-Box record."""
        ontology, _ = _pipeline_result
        context = f"phase-idea-{self.IDEA_ID}-d5"

        recalled = ontology.recall_facts(context=context)
        facts = recalled["facts"]
        predicates = {f["predicate"] for f in facts}

        # Intent fields
        assert "phase:preserves-mode" in predicates
        assert "phase:preserves-recommendation" in predicates
        # Metadata
        assert "phase:producedBy" in predicates
        assert "phase:forRequirement" in predicates

    def test_idempotent_rerun_preserves_latest_values(
        self, tmp_path: Path,
    ) -> None:
        """Running the pipeline twice with different D5 values results in
        only the latest values being recalled — idempotent write pattern."""
        ontology = _RecordingOntologyPort()

        # First run
        d5_v1 = D5Output(
            output_file=tmp_path / "d5-v1.md",
            mode="upstream",
            recommendation="Initial recommendation",
        )
        pipeline_v1 = Pipeline(
            phases=[("d5", _D5StubPhase(d5_v1))],
            claude_port=object(),
            work_dir=tmp_path / "run1",
            idea_id="idea-774",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )
        (tmp_path / "run1").mkdir()
        pipeline_v1.run()

        # Second run with updated values
        d5_v2 = D5Output(
            output_file=tmp_path / "d5-v2.md",
            mode="downstream",
            recommendation="Revised recommendation after new data",
        )
        pipeline_v2 = Pipeline(
            phases=[("d5", _D5StubPhase(d5_v2))],
            claude_port=object(),
            work_dir=tmp_path / "run2",
            idea_id="idea-774",
            config={"ontology_port": ontology},
            total_budget_usd=1.00,
        )
        (tmp_path / "run2").mkdir()
        pipeline_v2.run()

        # Recall should return only the latest values
        context = "phase-idea-idea-774-d5"
        recalled = ontology.recall_facts(context=context)
        facts = recalled["facts"]

        mode_facts = [
            f for f in facts if f["predicate"] == "phase:preserves-mode"
        ]
        rec_facts = [
            f
            for f in facts
            if f["predicate"] == "phase:preserves-recommendation"
        ]

        assert len(mode_facts) == 1
        assert mode_facts[0]["object"] == "downstream"

        assert len(rec_facts) == 1
        assert rec_facts[0]["object"] == "Revised recommendation after new data"
