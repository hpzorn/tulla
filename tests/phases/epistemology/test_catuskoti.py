"""Tests for CatuskotiPhase (Nāgārjuna's four-cornered logic).

Follows the standard 4-test-class pattern: TestBuildPrompt, TestGetTools,
TestParseOutput, TestExecuteWithMock.

Requirement: prd:req-83-2-4
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.epistemology.catuskoti import CatuskotiPhase
from tulla.phases.epistemology.models import EpistemologyOutput

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Catuskoti mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Catuṣkoṭi Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Tetralemma Navigation, Paradox Exploitation, Category-Error Reframing

## Extracted Claims
C1: Epistemology modes produce structurally distinct outputs when given \
distinct philosophical grounding.
C2: Anti-collapse guards are necessary for maintaining mode distinctness.
C3: A solo ideator benefits more from mode quantity than mode quality.

## Claims Table
| # | Claim | True | False | Both True and False | Neither True nor False |
|---|-------|------|-------|---------------------|------------------------|
| C1 | Distinct outputs | True: 5-layer | False: Layer 1 | Both | [empirical] |
| C2 | Guards needed | True: dims degrade | False: grounding | Both | Neither |
| C3 | Quantity vs quality | True: breadth | False: attention | Both | Neither |

## Paradox Map
**P1: The Structural-Surface Paradox** (from C1)
- True-framing: Different reasoning topologies (chain, tree, DAG, cyclic, lattice) \
produce genuinely different traversal patterns, yielding structurally distinct outputs.
- False-framing: LLM outputs converge to similar surface patterns regardless of \
underlying reasoning topology, because the language model's training distribution \
dominates prompt-level framing.
- Standing: Both framings are legitimate because structural distinctness operates \
at a level (reasoning graph shape) that is not directly observable in output text. \
The paradox is productive — it motivates anti-collapse guards as a bridge between \
structural intent and surface expression.

**P2: The Necessity-Contingency Paradox** (from C2)
- True-framing: Current LLMs demonstrably collapse without anti-collapse guards, \
making them practically necessary.
- False-framing: The need for guards is a contingent fact about current model \
capabilities, not a necessary feature of the system.
- Standing: Both framings hold because 'necessary' is ambiguous between logical \
necessity (which guards lack) and practical necessity (which they possess). The \
paradox reveals that anti-collapse engineering is a transitional technology.

**P3: The Divergence-Convergence Paradox** (from C3)
- True-framing: More modes serves the divergent phase of ideation where breadth \
of starting points increases breakthrough probability.
- False-framing: Fewer, better modes serves the convergent phase where attention \
is the binding constraint.
- Standing: Both framings are legitimate because ideation inherently requires \
both phases. The paradox is not resolvable — it must be held open.

## Category Error Map
**E1: The Capability Baseline Error** (from C2)
- Failed assumption: The question 'are guards necessary?' assumes a fixed model \
capability level against which necessity can be evaluated.
- Why it fails: Model capabilities change across versions and contexts, making \
the necessity boundary a moving target rather than a fixed property.
- Better question: At what capability threshold do anti-collapse guards become \
redundant, and how do we detect when that threshold is reached?

**E2: The Quantity-Quality False Dichotomy** (from C3)
- Failed assumption: 'Mode quantity vs quality' assumes these are opposing ends \
of a single dimension.
- Why it fails: Topological distinctness is orthogonal to both quantity and \
quality — 9 modes can be both numerous AND high-quality if each occupies a \
unique position in reasoning-topology space.
- Better question: What is the minimum set of topologically distinct reasoning \
modes that covers the ideation space without redundancy?

## Idea 1: Test Idea
**Protocol**: Tetralemma Navigation
**Source Paradox**: P3 from C3
**Non-Binary Insight**: The divergence-convergence paradox cannot be resolved — \
it must be held open. What becomes possible if we design a system that is \
simultaneously divergent and convergent?
**Description**: Build an epistemology pipeline that runs all 9 modes in parallel \
(maximum divergence) but uses the 6-dimension structural rubric to automatically \
cluster and prune outputs in real-time (ruthless convergence). The paradox becomes \
a design principle: the system is both maximally broad and maximally focused.

## Idea 2: Paradox-Driven Guard Calibration
**Protocol**: Paradox Exploitation
**Source Paradox**: P2 from C2
**Design Principle**: Anti-collapse guards are both necessary and unnecessary — \
use this paradox to build guards that measure their own necessity.
**Description**: Implement self-calibrating anti-collapse guards that track how \
often they fire (prevent a collapse) vs how often the mode would have been \
distinct anyway. Over time, the guard learns its own necessity level and can \
report when it has become redundant — a guard that knows when to retire.

## Idea 3: Topology-First Mode Selection
**Protocol**: Category-Error Reframing
**Source Error**: E2 from C3
**Reframed Question**: Instead of asking 'how many modes?' or 'how good are \
the modes?', ask 'what reasoning topologies are missing from the current set?'
**Description**: Build a topology coverage map that visualises which reasoning \
graph structures (chain, tree, DAG, cyclic, lattice, etc.) are represented by \
the current mode set. New modes are added not by philosophical interest but by \
topological gap analysis — ensuring each addition covers a genuinely new \
reasoning structure.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by CatuskotiPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = CatuskotiPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = CatuskotiPhase().build_prompt(ctx)
        assert "ep-catuskoti-ideas.md" in prompt

    def test_prompt_contains_philosopher_name(self, ctx: PhaseContext) -> None:
        prompt = CatuskotiPhase().build_prompt(ctx)
        assert "Nagarjuna" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = CatuskotiPhase().build_prompt(ctx)
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_anti_collapse_guard(self, ctx: PhaseContext) -> None:
        prompt = CatuskotiPhase().build_prompt(ctx)
        assert "DO NOT COLLAPSE TO BINARY" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by CatuskotiPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = CatuskotiPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = CatuskotiPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = CatuskotiPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = CatuskotiPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify CatuskotiPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = CatuskotiPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-catuskoti-ideas.md", SAMPLE_OUTPUT)
        phase = CatuskotiPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "catuskoti"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedCatuskotiPhase(CatuskotiPhase):
    """CatuskotiPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "ep-catuskoti-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedCatuskotiPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "catuskoti"
