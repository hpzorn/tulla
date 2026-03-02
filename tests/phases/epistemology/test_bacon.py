"""Tests for BaconPhase (Baconian Inductivism mode).

These tests verify the philosopher-grounded ``BaconPhase`` which replaces
the original ``PoolPhase``.  The mode's distinctive process is *eliminative*:
it compiles systematic evidence tables (Presence, Absence, Degrees) then
eliminates non-essential factors to induce the Form — the essential nature.

Requirement: prd:req-83-3-8
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.pool import BaconPhase

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Bacon mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Bacon Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Table of Presence, Table of Absence, Table of Degrees

## The Phenomenon
**Observable Phenomenon**: Structured ontology management produces higher \
query accuracy than ad-hoc knowledge organization
**Source**: idea 42

## Table of Presence
| # | Instance | Phenomenon Manifestation | Surrounding Conditions |
|---|----------|--------------------------|------------------------|
| 1 | Wikidata | High query accuracy via SPARQL | Community curation, strict schema |
| 2 | Gene Ontology | Precise gene function queries | Domain-expert curation, axioms |
| 3 | Schema.org | Reliable structured data extraction | Consortium backing, flat hierarchy |
| 4 | Dublin Core | Consistent metadata retrieval | Minimal vocabulary, wide adoption |
| 5 | SNOMED CT | Accurate clinical concept queries | Terminology management, definitions |

## Table of Absence
| # | Similar Case | Why Expected | Why Absent | Differs From |
|---|-------------|-------------|------------|---------------|
| 1 | Wikipedia infoboxes | Ontology-adjacent format | Schemas vary wildly | Presence #1 |
| 2 | Biomedical preprints | Like Gene Ontology | Free text defeats querying | Presence #2 |
| 3 | Microformats | Like Schema.org | Fragmented adoption | Presence #3 |
| 4 | Folksonomy tags | Like Dublin Core | No controlled vocabulary | Presence #4 |
| 5 | ICD-9 legacy codes | Like SNOMED CT | No formal relationships | Presence #5 |

## Table of Degrees
| # | Instance | Intensity | Co-varying Factor |
|---|----------|-----------|-------------------|
| 1 | Personal Zettelkasten | Low | Minimal formal structure, single-user vocabulary |
| 2 | Corporate taxonomy (SharePoint) | Low-Medium | Some hierarchy but no formal axioms |
| 3 | DBpedia | Medium | Auto-extracted structure, partial ontology coverage |
| 4 | FIBO (Financial Industry) | Medium-High | Formal ontology but narrow domain adoption |
| 5 | Wikidata | High | Full ontology with community curation and SPARQL endpoint |

## Elimination
**Eliminated factors**:
- Domain specificity: eliminated because present in both Presence (Gene Ontology, \
SNOMED CT) and Absence (Biomedical preprints, ICD-9) — domain expertise alone \
does not produce the phenomenon
- Community size: eliminated because Wikipedia infoboxes have massive community \
yet lack the phenomenon, while Dublin Core has small community yet exhibits it
- Digital format: eliminated because all cases are digital — does not discriminate

## The Form
**Induced Form**: The essential nature is *controlled vocabulary with formal \
relationships* — not structure alone, not curation alone, but the combination \
of a bounded term set with explicitly defined inter-term relations.
**Why Surprising**: The naive expectation is that "more structure = better queries." \
The Form reveals that structure without controlled vocabulary (Wikipedia infoboxes) \
and vocabulary without formal relations (folksonomy tags) both fail. It is the \
conjunction that is essential.
**Surviving Evidence**: Explains all three tables — Presence cases have both \
controlled vocabulary and formal relations; Absence cases lack one or both; \
Degrees cases vary in the tightness of vocabulary control and relation formality.

## Idea 1: Vocabulary-First Ontology Bootstrap
**Framework**: Table of Presence
**Form Applied**: If controlled vocabulary + formal relationships is the Form, \
then new ontology projects should start by establishing the controlled vocabulary \
BEFORE defining structural relationships — not the reverse.
**Description**: Build an ontology bootstrap tool that enforces vocabulary \
stabilization before relationship definition. Users define and lock terms first, \
then progressively add formal relations. This inverts the common pattern of \
starting with a schema and hoping vocabulary standardizes later.

## Idea 2: Vocabulary Gap Detector
**Framework**: Table of Absence
**Form Applied**: The Form predicts that any knowledge system lacking controlled \
vocabulary will exhibit low query accuracy regardless of structural sophistication. \
Systems in the Absence table are candidates for vocabulary injection.
**Description**: Build a diagnostic tool that analyzes existing knowledge systems \
(wikis, tag systems, document stores) and identifies where vocabulary control is \
missing. For each gap, suggest the minimal controlled vocabulary that would bring \
the system across the threshold from Absence to Presence.

## Idea 3: Vocabulary-Relation Coupling Meter
**Framework**: Table of Degrees
**Form Applied**: The Degrees table shows that query accuracy co-varies with the \
tightness of vocabulary-relation coupling. This suggests a measurable metric.
**Description**: Define a quantitative coupling coefficient that measures how \
tightly a system's vocabulary is bound to its formal relations. Systems with \
low coupling (like DBpedia's auto-extracted structure) would score low; systems \
with high coupling (like SNOMED CT) would score high. Use the metric to guide \
ontology improvement efforts toward the highest-leverage interventions.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by BaconPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = BaconPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = BaconPhase().build_prompt(ctx)
        assert "ep-bacon-ideas.md" in prompt

    def test_prompt_contains_phase_markers(self, ctx: PhaseContext) -> None:
        prompt = BaconPhase().build_prompt(ctx)
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
            "Phase 6",
            "Phase 7",
            "Phase 8",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert len(found) == 8, f"Prompt must contain all 8 Phase markers, found: {found}"

    def test_prompt_contains_bacon_grounding(self, ctx: PhaseContext) -> None:
        prompt = BaconPhase().build_prompt(ctx)
        assert "Francis Bacon" in prompt
        assert "Novum Organum" in prompt

    def test_prompt_contains_anti_collapse_table_of_absence(
        self,
        ctx: PhaseContext,
    ) -> None:
        prompt = BaconPhase().build_prompt(ctx)
        assert "Table of Absence" in prompt
        assert "Do NOT skip the Absence table" in prompt

    def test_prompt_contains_elimination_emphasis(self, ctx: PhaseContext) -> None:
        prompt = BaconPhase().build_prompt(ctx)
        assert "ELIMINATION" in prompt
        assert "SURPRISING" in prompt

    def test_phase_id_is_ep_bacon(self) -> None:
        phase = BaconPhase()
        assert phase.phase_id == "ep-bacon"


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by BaconPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = BaconPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = BaconPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = BaconPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = BaconPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify BaconPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = BaconPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-bacon-ideas.md", SAMPLE_OUTPUT)
        phase = BaconPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "bacon"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedBaconPhase(BaconPhase):
    """BaconPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "ep-bacon-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedBaconPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "bacon"
