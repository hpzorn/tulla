"""Tests for AbductionPhase (Peircean abductive inference).

Follows the standard 4-test-class pattern: TestBuildPrompt, TestGetTools,
TestParseOutput, TestExecuteWithMock.

Requirement: prd:req-83-2-3
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.abduction import AbductionPhase
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Abduction mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Abduction Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Hypothesis Generation, Explanatory Ranking, Predictive Testing

## The Surprising Observation
**Observation**: It is surprising that idea-42's epistemology modes produce \
structurally similar outputs despite claiming distinct reasoning strategies, \
because we would expect topologically different reasoning graphs to yield \
recognisably different artefacts given that each mode targets a different \
philosophical tradition.
**Source**: idea-42 in context of epistemology cluster (idea-44, idea-51, idea-55)

## Competing Hypotheses
| # | Hypothesis | Explanatory Scope | Predictive Novelty | Simplicity | Falsifiability | Rank |
|---|-----------|-------------------|-------------------|------------|----------------|------|
| H1 | Anti-collapse guards are missing, so prompts converge to default CoT | High | High | High | High | 1 |
| H2 | Output format constraints force structural similarity regardless of reasoning | Medium | Medium | High | Medium | 2 |
| H3 | The LLM's training distribution overwhelms prompt-level philosophical framing | Medium | Low | Low | Low | 3 |

## Top Hypothesis
**Selected**: H1 — Anti-collapse guards are missing, so prompts converge to default CoT
**Prediction 1**: If H1 is true, then adding anti-collapse guards to a single \
mode should produce measurably different outputs on the 6-dimension rubric.
**Prediction 2**: If H1 is true, then NOT observing improvement after adding \
guards would indicate the problem is deeper than prompt engineering.
**Falsification**: H1 is refuted if adding anti-collapse guards to all modes \
fails to increase inter-mode distinctness scores.

## Runner-Up Differentiators
**H2**: Would predict that changing output format templates while keeping \
prompts identical produces greater distinctness than changing prompts while \
keeping format identical.
**H3**: Would predict that no prompt-level intervention (guards, format, or \
philosophical framing) produces persistent distinctness across multiple runs.

## Investigation Protocol
1. Select one mode (e.g., Pool). Add anti-collapse guards per the 5-layer \
encoding pattern. Run 3 times. Score on 6-dimension rubric.
2. Compare rubric scores pre/post guard addition. If 4+ dimensions improve, \
H1 is strongly supported.
3. Run the same test with output format changes only (H2 test) and with a \
different base model (H3 test) to triangulate.

## Idea 1: Test Idea
**Protocol**: Hypothesis Generation
**Hypothesis Pursued**: H1
**What to Test**: Add anti-collapse guards to PoolPhase and measure rubric \
score changes across 3 independent runs.
**Expected Outcome**: At least 4 of 6 rubric dimensions should show \
improvement (score increase >= 1 point on 6-point scale).
**Description**: Directly tests the top hypothesis by implementing the \
simplest possible intervention — adding the missing anti-collapse guards to \
one mode — and measuring whether it produces the predicted effect. This is \
the critical first experiment in the abductive cycle.

## Idea 2: Format vs Framing Experiment
**Protocol**: Explanatory Ranking
**Hypotheses Distinguished**: H1 vs H2
**Crucial Experiment**: Run PoolPhase with (a) guards but same format, \
(b) new format but no guards, (c) both. Compare 6-dimension rubric scores \
across all three conditions.
**Description**: Disentangles the contribution of anti-collapse guards from \
output format constraints. If condition (a) outperforms (b), H1 is favoured \
over H2. If (c) shows no additional benefit over (a), format is secondary.

## Idea 3: Cross-Model Abductive Probe
**Protocol**: Predictive Testing
**Novel Prediction**: If anti-collapse guards are the key mechanism (H1), then \
the same guards should produce mode distinctness even when the underlying model \
changes — the effect should transfer across model versions.
**Why Visible Only Through Abduction**: Standard testing would compare modes \
within a single model. The abductive cycle reveals that the transferability of \
guard effectiveness is a novel testable prediction that distinguishes \
prompt-level causation from model-level causation.
**Description**: Run the guard-enhanced PoolPhase on two different model \
versions (e.g., Claude 3 vs Claude 4). If distinctness transfers, the guards \
are genuinely load-bearing. If it collapses on one model, the explanation is \
model-dependent, weakening H1.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by AbductionPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = AbductionPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = AbductionPhase().build_prompt(ctx)
        assert "ep-abduction-ideas.md" in prompt

    def test_prompt_contains_philosopher_name(self, ctx: PhaseContext) -> None:
        prompt = AbductionPhase().build_prompt(ctx)
        assert "Peirce" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = AbductionPhase().build_prompt(ctx)
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_anti_collapse_guard(self, ctx: PhaseContext) -> None:
        prompt = AbductionPhase().build_prompt(ctx)
        assert "Do NOT start from principles" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by AbductionPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AbductionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AbductionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AbductionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = AbductionPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify AbductionPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = AbductionPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-abduction-ideas.md", SAMPLE_OUTPUT)
        phase = AbductionPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "abduction"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedAbductionPhase(AbductionPhase):
    """AbductionPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-abduction-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedAbductionPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "abduction"
