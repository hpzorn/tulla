"""Baseline tests for AristotlePhase.

These tests verify the Aristotelian Four Causes mode, which replaced the
original ``IdeaPhase``.

Requirement: prd:req-83-3-2
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.idea import AristotlePhase

# ---------------------------------------------------------------------------
# Sample output constant — minimal valid markdown matching Aristotle mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Aristotle Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Material Cause, Formal Cause, Efficient Cause, Final Cause

## Material Cause
The idea is composed of structured ontology management, natural-language \
ideation workflows, and graph-based knowledge representation. Its raw \
ingredients include RDF triples, SHACL shapes, and CLI interaction patterns.

## Formal Cause
The defining structure is a pipeline that transforms unstructured creative \
input into ontology-backed idea graphs. The organizing principle is that \
each idea node carries typed semantic relationships.

## Efficient Cause
The idea was triggered by the gap between existing knowledge management \
tools (wikis, note apps) and the need for structured, queryable ideation. \
The proximate cause was a research session on semantic web technologies.

## Final Cause
The telos is a system where every idea is a first-class semantic object — \
queryable, composable, and traceable. Full realization looks like an \
autonomous ideation partner that surfaces non-obvious connections.

## Causal Integration
**Gaps**: The formal cause is underdeveloped — the pipeline structure is \
assumed but not validated against real creative workflows.
**Conflicts**: The efficient cause (quick research spike) conflicts with \
the final cause (robust autonomous system) — the origin was expedient but \
the goal is ambitious.
**Surprises**: The material cause revealed that SHACL shapes are load-bearing \
for the formal cause — without them, the organizing principle collapses.

## Idea 1: Workflow-Validated Pipeline Schema
**Framework**: Formal Cause
**Causal Origin**: Gap in formal cause — pipeline structure assumed not validated
**Source Ideas**: idea-42
**Description**: Design and validate the pipeline's formal structure against \
real creative workflow data. Map actual ideation sessions to identify which \
pipeline stages users naturally follow versus which are imposed by the system.
**Novelty**: Grounds the formal architecture in empirical workflow evidence \
rather than theoretical design.

## Idea 2: Ambition-Calibrated Roadmap
**Framework**: Efficient Cause
**Causal Origin**: Conflict between efficient and final cause
**Source Ideas**: idea-42
**Description**: Create a staged roadmap that bridges the gap between the \
expedient origin (research spike) and the ambitious telos (autonomous partner). \
Each stage must be independently valuable while advancing toward the final cause.
**Novelty**: Explicitly addresses the origin-goal tension rather than ignoring it.

## Idea 3: SHACL as Structural Backbone
**Framework**: Material Cause
**Causal Origin**: Surprise from material cause — SHACL is load-bearing
**Source Ideas**: idea-42
**Description**: Elevate SHACL shapes from validation layer to primary \
structural component. If SHACL is truly load-bearing for the formal cause, \
it should be a first-class design concern, not an afterthought.
**Novelty**: Inverts the typical relationship where shapes validate structure — \
here, shapes DEFINE structure.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by AristotlePhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = AristotlePhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = AristotlePhase().build_prompt(ctx)
        assert "ep-aristotle-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = AristotlePhase().build_prompt(ctx)
        phase_markers = [
            "Phase 1: Material Cause",
            "Phase 2: Formal Cause",
            "Phase 3: Efficient Cause",
            "Phase 4: Final Cause",
            "Phase 5: Causal Integration",
            "Phase 6: Idea Generation",
            "Phase 7: Save and Report",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert len(found) == 7, f"All 7 phase markers must appear, found: {found}"

    def test_prompt_contains_aristotle(self, ctx: PhaseContext) -> None:
        prompt = AristotlePhase().build_prompt(ctx)
        assert "Aristotle" in prompt

    def test_prompt_contains_four_independent_causal(self, ctx: PhaseContext) -> None:
        prompt = AristotlePhase().build_prompt(ctx)
        assert "four independent causal" in prompt

    def test_prompt_contains_anti_collapse_efficient(self, ctx: PhaseContext) -> None:
        prompt = AristotlePhase().build_prompt(ctx)
        assert "do not skip to efficient cause" in prompt.lower()


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by AristotlePhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AristotlePhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AristotlePhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_get_related_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = AristotlePhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_related_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = AristotlePhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = AristotlePhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify AristotlePhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = AristotlePhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-aristotle-ideas.md", SAMPLE_OUTPUT)
        phase = AristotlePhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "aristotle"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedAristotlePhase(AristotlePhase):
    """AristotlePhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-aristotle-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedAristotlePhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "aristotle"
