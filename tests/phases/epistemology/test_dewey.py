"""Tests for DeweyPhase (Deweyan pragmatist inquiry mode).

These tests verify the philosopher-grounded DeweyPhase — the rewrite of the
former ProblemPhase.  The mode's distinctive process is experiential: genuine
inquiry begins from a FELT DIFFICULTY, not a stated problem.

Requirement: prd:req-83-3-4
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.problem import DeweyPhase

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Dewey mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Dewey Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Felt Difficulty, Problem Formulation, Experimental Testing

## Felt Difficulty
There is a pervasive sense of friction when interacting with the ontology \
query layer — not a specific bug or missing feature, but a qualitative \
feeling that the tool resists the user rather than inviting inquiry. Users \
approach with curiosity and leave with frustration, not because the system \
is broken but because the interaction feels adversarial.

## Problem Formulation
**Stated Problem (idea's own)**: The SPARQL interface is too complex for \
non-technical users.
**Formulated Problem (from felt difficulty)**: The query experience lacks \
progressive invitation — there is no path from tentative exploration to \
confident mastery, so users never develop a working relationship with the \
system.
**The Gap**: The stated problem treats complexity as the obstacle; the felt \
difficulty reveals that the real obstacle is the absence of an inviting \
on-ramp. Complexity is fine if the journey toward it feels supported.

## Hypotheses
### Hypothesis 1: Conversational Query Apprenticeship
**Plan of Action**: If we build a conversational layer that translates \
natural-language questions into progressively more complex SPARQL, showing \
users what their question looks like in the system's language, then the \
felt difficulty resolves because users develop fluency through use rather \
than study.
**Imaginative Rehearsal**: A user asks 'what ideas relate to caching?' The \
system translates this to a simple SPARQL query, shows both the answer and \
the query, and offers to refine. Over 10 interactions the user begins \
recognizing patterns and eventually writes fragments themselves. The \
difficulty — adversarial interaction — dissolves into collaborative inquiry.
**Experimental Test**: Build a prototype conversational wrapper for the 5 \
most common query patterns. Have 3 users attempt 10 queries each. Measure \
whether they begin modifying the shown SPARQL by session end.

### Hypothesis 2: Query Templates as Training Wheels
**Plan of Action**: If we provide task-oriented templates (find related \
ideas, trace lineage, surface contradictions) that users can fill in and \
inspect, then the difficulty resolves because the entry point becomes a \
familiar form rather than a blank SPARQL editor.
**Imaginative Rehearsal**: A user selects 'find related ideas', fills in \
their idea ID, and gets results plus the underlying query. They notice they \
can change the relationship type and re-run. Next time they start from the \
template but modify it. The friction of facing a blank query editor is gone.
**Experimental Test**: Create 5 templates covering 80% of use cases. Deploy \
for 2 weeks. Track template usage vs. raw SPARQL usage. If templates account \
for >60% of queries and raw SPARQL increases (not decreases), the hypothesis \
holds — templates are on-ramps, not crutches.

### Hypothesis 3: Ambient Query Suggestions
**Plan of Action**: If we surface contextual query suggestions based on the \
user's current idea (e.g., 'see what contradicts this', 'find the origin \
of this concept'), then the difficulty resolves because the system initiates \
inquiry rather than waiting passively for the user to formulate a question.
**Imaginative Rehearsal**: While viewing an idea, the sidebar shows 3 \
suggested queries. The user clicks one out of curiosity, sees unexpected \
connections, and clicks another. The interaction shifts from 'I must query' \
to 'the system invites me to explore.' The adversarial feeling vanishes \
because the system is now a collaborator.
**Experimental Test**: Implement suggestion generation for 10 ideas. A/B \
test: 5 users with suggestions, 5 without. Measure query frequency, \
exploration depth (number of ideas visited per session), and self-reported \
satisfaction.

## Idea 1: Conversational Query Apprenticeship
**Framework**: Felt Difficulty
**From Hypothesis**: Hypothesis 1
**Description**: Build a conversational query layer that translates \
natural-language questions into SPARQL, shows both answer and query, and \
offers progressive refinement. Users develop fluency through use. Deploy \
as a prototype wrapper over the existing endpoint.

## Idea 2: Task-Oriented Query Templates
**Framework**: Problem Formulation
**From Hypothesis**: Hypothesis 2
**Description**: Create 5 task-oriented query templates covering the most \
common ideation workflows. Each template is inspectable and modifiable, \
serving as an on-ramp to full SPARQL fluency. Deploy with usage tracking \
to validate the training-wheels hypothesis.

## Idea 3: Ambient Contextual Query Suggestions
**Framework**: Experimental Testing
**From Hypothesis**: Hypothesis 3
**Description**: Generate contextual query suggestions for each idea view, \
surfacing unexplored connections and inviting the user to explore. A/B test \
with 10 users to measure whether ambient suggestions increase exploration \
depth and shift the interaction from adversarial to collaborative.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by DeweyPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = DeweyPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = DeweyPhase().build_prompt(ctx)
        assert "ep-dewey-ideas.md" in prompt

    def test_prompt_contains_phase_markers(self, ctx: PhaseContext) -> None:
        prompt = DeweyPhase().build_prompt(ctx)
        # Dewey mode defines 6 phases
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

    def test_prompt_contains_dewey_grounding(self, ctx: PhaseContext) -> None:
        prompt = DeweyPhase().build_prompt(ctx)
        assert "Dewey" in prompt
        assert "felt difficulty" in prompt.lower()

    def test_prompt_contains_anti_collapse_no_five_whys(
        self,
        ctx: PhaseContext,
    ) -> None:
        prompt = DeweyPhase().build_prompt(ctx)
        assert "Do NOT use Five Whys" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by DeweyPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = DeweyPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = DeweyPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = DeweyPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_web_search_tool_present(self, ctx: PhaseContext) -> None:
        tools = DeweyPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "WebSearch" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = DeweyPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify DeweyPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = DeweyPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-dewey-ideas.md", SAMPLE_OUTPUT)
        phase = DeweyPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "dewey"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedDeweyPhase(DeweyPhase):
    """DeweyPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "ep-dewey-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedDeweyPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "dewey"
