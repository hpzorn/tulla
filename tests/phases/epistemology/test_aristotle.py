"""Baseline tests for IdeaPhase (pre-rewrite).

These tests capture the current behavior of ``IdeaPhase`` so that the
philosopher-grounded rewrite (Aristotelian mode) can be validated
against a known baseline.  No prompt may be modified until these pass.

Requirement: prd:req-83-1-3
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.idea import IdeaPhase

# ---------------------------------------------------------------------------
# Sample output constant — minimal valid markdown matching Idea mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Idea Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Extension, Assumption Inversion, Synthesis

## Dissection
**Core Insight**: The fundamental value lies in bridging structured ontology \
management with natural-language ideation workflows.
**Key Assumptions**:
  - Users prefer CLI-driven workflows over GUI [testable]
  - Ontology structure can capture creative intent [foundational]
  - Idea graphs remain navigable below 500 nodes [testable]
**Boundaries**: Covers ideation and structuring; excludes execution planning \
and resource allocation. Touches project management but does not enter it.
**Internal Tensions**: The desire for structured ontology conflicts with the \
fluid nature of early-stage ideation.
**Maturity**: sapling

## Protocol Selection
- **Extension**: The idea has a clear growth direction toward richer semantic \
annotations — justified by the sapling maturity assessment.
- **Assumption Inversion**: The testable assumption that users prefer CLI \
workflows is heavily load-bearing — flipping it reveals a GUI-first variant.
- **Synthesis**: Neighbour idea-19 on self-sovereign identity has a \
complementary gap in knowledge attribution.

## Idea 1: Semantic Annotation Layer
**Protocol**: Extension
**Driven By**: Core insight on bridging ontology and ideation
**Source Ideas**: idea-42
**Description**: Extend the current idea graph with fine-grained semantic \
annotations that capture not just relationships but the nature of each \
connection. This enables richer querying and automated insight surfacing.
**Novelty**: Goes beyond flat tagging to typed, ontology-backed annotations.

## Idea 2: GUI-First Ideation Canvas
**Protocol**: Assumption Inversion
**Driven By**: Key assumption that users prefer CLI workflows
**Source Ideas**: idea-42
**Description**: Invert the CLI-first assumption and build a visual canvas \
where ideas are spatial objects that can be dragged, grouped, and linked. \
The ontology becomes an invisible persistence layer.
**Novelty**: Tests whether spatial manipulation unlocks ideation patterns \
that text-based workflows miss.

## Idea 3: Identity-Attributed Knowledge Graph
**Protocol**: Synthesis
**Driven By**: Neighbour idea-19 on self-sovereign identity
**Source Ideas**: idea-42, idea-19
**Description**: Combine the idea graph with DID-backed contributor identity \
so that every node carries verifiable authorship. This merges structured \
knowledge management with decentralised trust.
**Novelty**: Fuses two previously separate concerns — ideation and identity — \
into a single attributable graph.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by IdeaPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = IdeaPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = IdeaPhase().build_prompt(ctx)
        assert "ep-idea-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = IdeaPhase().build_prompt(ctx)
        # Idea mode defines 4 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by IdeaPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = IdeaPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = IdeaPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_get_related_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = IdeaPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_related_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = IdeaPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = IdeaPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify IdeaPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = IdeaPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-idea-ideas.md", SAMPLE_OUTPUT)
        phase = IdeaPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "idea"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedIdeaPhase(IdeaPhase):
    """IdeaPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-idea-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedIdeaPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "idea"
