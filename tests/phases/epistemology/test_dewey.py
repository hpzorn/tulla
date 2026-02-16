"""Baseline tests for ProblemPhase (pre-rewrite).

These tests capture the current behavior of ``ProblemPhase`` so that the
philosopher-grounded rewrite (Deweyan pragmatist inquiry mode) can be
validated against a known baseline.  No prompt may be modified until these pass.

Requirement: prd:req-83-1-5
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.problem import ProblemPhase

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Problem mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Problem Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Direct Approach, Analogical Transfer, Assumption Inversion

## Stated Problem
The current ontology-server query interface requires users to know SPARQL \
syntax, creating a steep learning curve that discourages adoption among \
non-technical ideators.

## Five Whys
- Why 1: Users don't query the idea pool → because SPARQL is too complex
- Why 2: SPARQL is too complex → because it requires knowledge of the schema
- Why 3: Schema knowledge is required → because there is no abstraction layer
- Why 4: No abstraction layer exists → because the system was built for power users
- Why 5: Built for power users → because the initial user base was technical
**Root Cause**: The system's query interface was designed for its builders, \
not its intended audience.

## Constraint Map
| Constraint | Type | Notes |
|-----------|------|-------|
| SPARQL endpoint must remain available | hard | Existing integrations depend on it |
| Must support full ontology expressiveness | soft | 80% of queries use simple patterns |
| Single-user deployment | hard | Architecture assumption |
| Python runtime | hard | Infrastructure choice |

## Prior Art
| Who/What | Approach | Outcome |
|----------|----------|---------|
| Wikidata Query Helper | Natural-language-to-SPARQL | Works for simple queries, fails on complex joins |
| Notion databases | Structured filters with GUI | High adoption but limited expressiveness |
| GraphQL wrappers | Schema-derived query language | Good developer experience, moderate learning curve |

## Real Problem
The real problem is not SPARQL complexity per se, but the absence of a \
progressive disclosure interface — users cannot start simple and graduate \
to complex queries as their needs grow.

## Idea 1: Progressive Query Builder
**Protocol**: Direct Approach
**Driven By**: Root cause (designed for builders, not users)
**Description**: Build a query interface with three tiers: natural language \
for simple lookups, structured filters for common patterns, and raw SPARQL \
for power users. Each tier is a gateway to the next, with examples showing \
how the same query looks at each level.

## Idea 2: Domain-Mapped Query Templates
**Protocol**: Analogical Transfer
**Driven By**: Notion's structured filters achieving high adoption
**Description**: Pre-build query templates mapped to common ideation tasks \
(find related ideas, surface contradictions, trace idea lineage). Users \
select a task and fill in parameters rather than constructing queries. \
Inspired by Notion's approach but preserving full ontology richness.

## Idea 3: Schema-Optional Queries
**Protocol**: Assumption Inversion
**Driven By**: Soft constraint that full ontology expressiveness is required
**Description**: Remove the assumption that every query must traverse the \
full ontology. Provide a simplified view where ideas are flat documents \
with tags, and only expose relational depth when the user explicitly asks \
for it. Most queries never need joins.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by ProblemPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = ProblemPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = ProblemPhase().build_prompt(ctx)
        assert "ep-problem-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = ProblemPhase().build_prompt(ctx)
        # Problem mode defines 5 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_diagnostic_emphasis(self, ctx: PhaseContext) -> None:
        prompt = ProblemPhase().build_prompt(ctx)
        # Problem mode is distinctively diagnostic — archaeology before solutions
        assert "Problem Archaeology" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by ProblemPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = ProblemPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = ProblemPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = ProblemPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_web_search_tool_present(self, ctx: PhaseContext) -> None:
        tools = ProblemPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "WebSearch" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = ProblemPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify ProblemPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = ProblemPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-problem-ideas.md", SAMPLE_OUTPUT)
        phase = ProblemPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "problem"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedProblemPhase(ProblemPhase):
    """ProblemPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-problem-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedProblemPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "problem"
