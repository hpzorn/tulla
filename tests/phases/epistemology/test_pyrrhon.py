"""Tests for PyrrhonPhase (Pyrrhonian Skepticism mode).

These tests verify the philosopher-grounded ``PyrrhonPhase`` which replaces
the original ``SignalPhase``.  The prompt must encode Pyrrhonian Skepticism
via the 5-layer pattern (Persona → Operational Rules → Phase Markers →
Output Format → Anti-Collapse Guards).

Requirement: prd:req-83-3-1
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.signal import PyrrhonPhase

# ---------------------------------------------------------------------------
# Sample output constant — minimal valid markdown matching Pyrrhon mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Pyrrhon Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Equipollence, Epoche, Suspension

## The Claim
**Central Proposition**: Ontology-driven development produces better software than ad-hoc design
**Source**: idea 42

## Case FOR
Strong engineering tradition supports formal modelling. Ontologies reduce
ambiguity, enable automated validation, and produce machine-readable contracts.
Three decades of enterprise practice confirm that explicit schemas outperform
implicit ones at scale.

## Case AGAINST
Formal ontologies impose upfront costs that rarely pay off. Most successful
software (Linux, Git, the web) emerged from pragmatic iteration, not formal
modelling. Ontological rigidity penalises exploration — the most creative
breakthroughs come from breaking categories, not enforcing them.

## Equipollence
Neither case defeats the other. The FOR case assumes scale where ontologies
shine; the AGAINST case assumes exploration where they constrain. A rational
agent cannot prefer one without importing an assumption about what phase of
development matters most.

## What Suspension Reveals
When we stop trying to decide, we notice that the question itself presupposes
a false binary between "ontology-driven" and "ad-hoc." A third possibility
emerges: ontologies as retrospective sense-making tools rather than prospective
design constraints.

## Idea 1: Retrospective Ontology Crystallisation
**Framework**: Equipollence
**Emerged From**: The tension between upfront modelling and emergent design
**Why Invisible to the Decided**: Anyone who chose a side would optimise for \
either early or late formalisation, missing the dynamic transition.
**Description**: Build tooling that observes ad-hoc development patterns and \
gradually crystallises ontological structures from actual usage. The ontology \
emerges from practice rather than preceding it.

## Idea 2: Category-Breaking Detection
**Framework**: Epoche
**Hidden Assumption Surfaced**: Both sides assume categories are either \
imposed or absent — neither considers categories that actively resist \
themselves.
**Why Invisible to the Decided**: Choosing ontology-driven means enforcing \
categories; choosing ad-hoc means ignoring them. Neither watches for the \
moment a category breaks.
**Description**: A monitoring system that detects when an ontological category \
is being systematically violated by actual usage, surfacing these as creative \
signals rather than errors.

## Idea 3: Productive Ambiguity Zones
**Framework**: Suspension
**Value of Non-Resolution**: Some design spaces are more productive when \
left formally undecided — premature formalisation kills options.
**Why Invisible to the Decided**: Anyone committed to ontology-driven design \
would formalise these zones; anyone committed to ad-hoc would ignore them.
**Description**: Designate explicit zones in the architecture where ontological \
commitment is deliberately suspended, allowing competing interpretations to \
coexist until evidence forces a resolution.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by PyrrhonPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        assert "ep-pyrrhon-ideas.md" in prompt

    def test_prompt_contains_phase_markers(self, ctx: PhaseContext) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
            "Phase 6",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert len(found) == 6, "Prompt must contain all 6 Phase markers"

    def test_prompt_contains_sextus_empiricus(self, ctx: PhaseContext) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        assert "Sextus Empiricus" in prompt

    def test_prompt_contains_anti_collapse_do_not_resolve(
        self, ctx: PhaseContext
    ) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        assert "Do NOT resolve" in prompt

    def test_prompt_contains_equipollence_framework(
        self, ctx: PhaseContext
    ) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        assert "isostheneia" in prompt
        assert "Equipollence" in prompt

    def test_prompt_contains_all_anti_collapse_guards(
        self, ctx: PhaseContext
    ) -> None:
        prompt = PyrrhonPhase().build_prompt(ctx)
        assert "Do NOT pick a side" in prompt
        assert "both sides have valid points" in prompt
        assert "it depends on context" in prompt
        assert "REWRITE it until they match" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by PyrrhonPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = PyrrhonPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = PyrrhonPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = PyrrhonPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = PyrrhonPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names

    def test_web_tools_removed(self, ctx: PhaseContext) -> None:
        tools = PyrrhonPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "WebSearch" not in names
        assert "WebFetch" not in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify PyrrhonPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = PyrrhonPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-pyrrhon-ideas.md", SAMPLE_OUTPUT)
        phase = PyrrhonPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "pyrrhon"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedPyrrhonPhase(PyrrhonPhase):
    """PyrrhonPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-pyrrhon-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedPyrrhonPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "pyrrhon"
