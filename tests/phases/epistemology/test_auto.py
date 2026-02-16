"""Tests for the rewritten AutoPhase with topology-grounded diagnostics.

Verifies that ``AutoPhase.build_prompt`` uses the new philosopher-grounded
diagnostic dimension names (Contested Claims, Unexplained Anomaly, etc.),
includes the Peircean Abduction fallback, and enforces the Popper/Bacon
mutual exclusion rule.  Structural tests (tools, parse, mock execute) are
unchanged from the baseline.

Requirement: prd:req-83-4-2
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.auto import AutoPhase
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Sample output constant — Auto mode generates 12 ideas (4 per mode x 3)
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Auto Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Modes**: Peircean Abduction, Hegelian Dialectics, Popperian Falsification

## Diagnosis
| Diagnostic Question | Mode Indicated | Evidence | Strength |
|---------------------|---------------|----------|----------|
| Contested Claims | Pyrrhonian Skepticism | N/A | N/A |
| Unexplained Anomaly | Peircean Abduction | 5-layer encoding works but no explanation for why guard removal degrades 5-6 dimensions | strong |
| Genuine Contradiction | Hegelian Dialectics | Modes must be distinct yet share common Phase infrastructure | strong |
| Non-Binary Tension | Catuṣkoṭi | N/A | N/A |
| Unclear Purpose/Composition | Aristotelian Four Causes | N/A | N/A |
| Indeterminate Situation | Deweyan Inquiry | N/A | N/A |
| Untested Bold Claim | Popperian Falsification | Claim that topology determines distinctness has not been rigorously tested | strong |
| Observable Pattern | Baconian Inductivism | 9 modes with rubric scores could yield inductive patterns | moderate |

## Mode Prescription
| Mode | Diagnostic Basis | Selection Rationale |
|------|-----------------|---------------------|
| Peircean Abduction | Unexplained Anomaly — guard degradation unexplained | Cyclic hypothesis generation fits the anomaly |
| Hegelian Dialectics | Genuine Contradiction — distinct yet shared | Thesis-antithesis-synthesis resolves the tension |
| Popperian Falsification | Untested Bold Claim — topology claim untested | Severe testing needed for bold architectural claim |

## Idea 1: Guard Degradation Hypothesis
**Mode**: Peircean Abduction
**Diagnostic Basis**: Unexplained Anomaly — anti-collapse guard removal degrades 5-6 rubric dimensions
**Source Ideas**: idea-42
**Description**: Form an explanatory hypothesis for why guard removal causes such \
broad degradation. Hypothesis: guards act as cognitive scaffolding that prevents \
the LLM from collapsing distinct reasoning topologies into generic summarisation.
**Novelty**: Moves from empirical observation to mechanistic explanation.

## Idea 2: Topology Preservation Theory
**Mode**: Peircean Abduction
**Diagnostic Basis**: Unexplained Anomaly — topology determines distinctness but mechanism unclear
**Source Ideas**: idea-42, idea-55
**Description**: Hypothesize that prompt topology (chain, tree, DAG, cyclic, lattice) \
creates distinct attention patterns in the transformer. Each topology forces different \
information flow, making collapse structurally impossible.
**Novelty**: Connects prompt engineering to transformer attention mechanics.

## Idea 3: Encoding Layer Interaction Effects
**Mode**: Peircean Abduction
**Diagnostic Basis**: Unexplained Anomaly — 5 layers work together but interactions unknown
**Source Ideas**: idea-42, idea-44
**Description**: Hypothesize that the 5-layer encoding creates emergent interaction \
effects. Persona constrains rules, rules shape phases, phases determine format, and \
guards protect the entire stack. Test by selectively removing layer pairs.
**Novelty**: Layer interaction analysis rather than individual layer testing.

## Idea 4: Anti-Collapse Guard Taxonomy
**Mode**: Peircean Abduction
**Diagnostic Basis**: Unexplained Anomaly — guards work but no theory of guard types
**Source Ideas**: idea-42
**Description**: Abductively derive a taxonomy of guard types from observed failures. \
Classify guards by what they prevent (mode collapse, format drift, reasoning shortcut) \
and predict which guard types are essential vs. redundant.
**Novelty**: Theoretical framework for a previously ad-hoc mechanism.

## Idea 5: Infrastructure-Creativity Synthesis
**Mode**: Hegelian Dialectics
**Diagnostic Basis**: Genuine Contradiction — modes must be distinct yet share Phase infrastructure
**Source Ideas**: idea-42, idea-11
**Description**: Thesis: modes need maximum distinctness for creative value. Antithesis: \
modes need shared infrastructure for maintainability. Synthesis: a layered architecture \
where the shared Phase base provides structure while the 5-layer encoding provides distinctness.
**Novelty**: Resolves the infrastructure-creativity tension explicitly.

## Idea 6: Evaluation-Generation Dialectic
**Mode**: Hegelian Dialectics
**Diagnostic Basis**: Genuine Contradiction — evaluation constrains but generation requires freedom
**Source Ideas**: idea-42, idea-55
**Description**: Thesis: rigorous evaluation (rubric, SHACL) is essential for quality. \
Antithesis: creative generation requires unconstrained exploration. Synthesis: evaluation \
as a post-hoc lens, not a generative constraint — modes run freely, rubric scores after.
**Novelty**: Temporal separation as dialectical resolution.

## Idea 7: Simplicity-Depth Synthesis
**Mode**: Hegelian Dialectics
**Diagnostic Basis**: Genuine Contradiction — user wants simplicity but system has deep philosophy
**Source Ideas**: idea-42, idea-22
**Description**: Thesis: philosophical grounding must be deep (5-layer, anti-collapse). \
Antithesis: Solo Ideator wants invisible complexity. Synthesis: mode names imply the \
philosophy (Pyrrhon = skepticism) while the encoding does the heavy lifting silently.
**Novelty**: User experience design as dialectical resolution.

## Idea 8: Single-vs-Multi Mode Resolution
**Mode**: Hegelian Dialectics
**Diagnostic Basis**: Genuine Contradiction — each mode runs alone but auto selects three
**Source Ideas**: idea-42, idea-44
**Description**: Thesis: each mode is a complete epistemological framework. Antithesis: \
real ideas need multiple perspectives. Synthesis: auto mode as meta-epistemology that \
composes modes without mixing them — each section is pure, the composition is new.
**Novelty**: Composition without contamination as a design principle.

## Idea 9: Topology Falsification Battery
**Mode**: Popperian Falsification
**Diagnostic Basis**: Untested Bold Claim — topology determines distinctness
**Source Ideas**: idea-42
**Description**: Design a severe test: generate outputs from all 9 modes for the same \
idea, blind-label them, and check if evaluators can correctly classify by topology. \
If topology truly determines distinctness, classification accuracy should exceed 80%.
**Novelty**: Empirical falsification of the core architectural claim.

## Idea 10: Anti-Collapse Necessity Test
**Mode**: Popperian Falsification
**Diagnostic Basis**: Untested Bold Claim — guards are load-bearing
**Source Ideas**: idea-42, idea-55
**Description**: Test the claim that anti-collapse guards are load-bearing by running \
each mode with and without guards on 10 ideas. Measure rubric scores. If guards are \
truly load-bearing, the with-guard version must score higher on 4+ dimensions consistently.
**Novelty**: Quantified necessity testing for a specific prompt component.

## Idea 11: Mode Count Optimality Challenge
**Mode**: Popperian Falsification
**Diagnostic Basis**: Untested Bold Claim — 9 modes is the right number
**Source Ideas**: idea-42, idea-58
**Description**: Attempt to falsify the claim that 9 modes is optimal. Add a 10th mode \
(e.g., Kuhnian paradigm shift) and measure whether it produces genuinely distinct output \
or collapses into an existing mode. If it collapses, the 9-mode claim survives.
**Novelty**: Direct falsification attempt on the mode count decision.

## Idea 12: Philosopher Grounding Necessity Test
**Mode**: Popperian Falsification
**Diagnostic Basis**: Untested Bold Claim — philosopher grounding improves distinctness
**Source Ideas**: idea-42, idea-31
**Description**: Test whether philosopher grounding actually matters. Create a control \
set of 9 modes with identical topologies but generic names (Mode A, Mode B, ...). \
Compare rubric scores. If grounding matters, named modes must score higher.
**Novelty**: Isolating the effect of philosophical labeling from topology.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by AutoPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "ep-auto-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        # Auto mode defines 5 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_auto_mode_identity(self, ctx: PhaseContext) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Auto Mode" in prompt

    def test_timeout_is_1200(self) -> None:
        phase = AutoPhase()
        assert phase.timeout_s == 1200.0

    # -- New diagnostic dimension checks ------------------------------------

    def test_prompt_contains_contested_claims_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Contested Claims" in prompt

    def test_prompt_contains_unexplained_anomaly_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Unexplained Anomaly" in prompt

    def test_prompt_contains_genuine_contradiction_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Genuine Contradiction" in prompt

    def test_prompt_contains_non_binary_tension_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Non-Binary Tension" in prompt

    def test_prompt_contains_unclear_purpose_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Unclear Purpose" in prompt

    def test_prompt_contains_indeterminate_situation_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Indeterminate Situation" in prompt

    def test_prompt_contains_untested_bold_claim_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Untested Bold Claim" in prompt

    def test_prompt_contains_observable_pattern_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Observable Pattern" in prompt

    def test_prompt_does_not_contain_old_maturity_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "| Maturity |" not in prompt

    def test_prompt_does_not_contain_old_connectivity_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "| Connectivity |" not in prompt

    def test_prompt_does_not_contain_old_decomposability_dimension(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "| Decomposability |" not in prompt

    # -- Peircean Abduction fallback ----------------------------------------

    def test_prompt_contains_peircean_abduction_fallback(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Peircean Abduction" in prompt
        # The fallback rule must mention defaulting to Peircean Abduction
        assert "default" in prompt.lower() and "Peircean Abduction" in prompt

    # -- Popper/Bacon mutual exclusion --------------------------------------

    def test_prompt_contains_popper_bacon_mutual_exclusion(
        self, ctx: PhaseContext
    ) -> None:
        prompt = AutoPhase().build_prompt(ctx)
        assert "Popper" in prompt and "Bacon" in prompt
        # Must mention they cannot both be selected
        prompt_lower = prompt.lower()
        assert (
            "mutual exclusion" in prompt_lower
            or "may not both" in prompt_lower
            or "cannot both" in prompt_lower
        ), "Prompt must contain Popper/Bacon mutual exclusion rule"


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by AutoPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_get_related_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_related_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = AutoPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify AutoPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = AutoPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-auto-ideas.md", SAMPLE_OUTPUT)
        phase = AutoPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 12
        assert result.mode == "auto"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedAutoPhase(AutoPhase):
    """AutoPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-auto-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedAutoPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 12
        assert result.data.mode == "auto"
