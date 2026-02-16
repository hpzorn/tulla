"""Baseline tests for DomainPhase (pre-rewrite).

These tests capture the current behavior of ``DomainPhase`` so that the
philosopher-grounded rewrite (Popperian falsificationist mode) can be
validated against a known baseline.  No prompt may be modified until these pass.

Requirement: prd:req-83-1-6
"""

from __future__ import annotations

from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.epistemology.models import EpistemologyOutput
from tulla.phases.epistemology.domain import DomainPhase

# ---------------------------------------------------------------------------
# Sample output constant — uses Idea N: headings with Domain mode format
# ---------------------------------------------------------------------------

SAMPLE_OUTPUT = """\
# Generated Ideas — Domain Mode
**Root Idea**: idea-42
**Date**: 2026-02-16
**Frameworks**: Gap Analysis, Analogical Transfer, Assumption Inversion
**Domain**: Knowledge graph construction for software architecture decisions

## Research Log
### Search 1: recent advances in knowledge graph construction 2026
**Key Findings**: Property graph databases (Neo4j 6, Memgraph) now support \
RDF interop natively, eliminating the traditional gap between labeled property \
graphs and triple stores. Graph RAG pipelines are becoming mainstream for \
enterprise knowledge management.
**Surprise**: The convergence happened faster than expected — two years ago \
these were separate ecosystems.

### Search 2: unsolved problems in architectural knowledge management
**Key Findings**: Architectural Decision Records (ADRs) remain disconnected \
from the systems they describe. No major tool links ADR content to runtime \
topology. ISO 42010 compliance is still largely manual.
**Surprise**: Despite widespread ADR adoption, tooling has barely evolved \
since the original Nygard template.

### Search 3: biological taxonomy approaches to classification problems
**Key Findings**: Cladistic methods use shared derived characteristics \
(synapomorphies) rather than overall similarity for classification. Molecular \
phylogenetics revolutionized taxonomy by providing objective, computable \
classification criteria independent of morphological opinion.
**Surprise**: The parallel to ontology alignment problems is striking — both \
fields struggle with lumpers vs splitters.

## Pool Confrontation
| Finding | Pool Status | Implication |
|---------|-------------|-------------|
| Property graph / RDF convergence | Pool is blind | Pool assumes triple-store-only architecture |
| ADR disconnection from runtime | Pool has it | idea-17 addresses this partially |
| Cladistic classification methods | Pool is blind | No idea applies biological classification to software concepts |
| Graph RAG pipelines | Pool is behind | idea-31 mentions RAG but not graph-structured retrieval |

## Idea 1: Convergent Graph Architecture
**Protocol**: Gap Analysis
**External Finding**: Neo4j 6 and Memgraph support RDF interop natively
**Pool Blind Spot**: Pool assumes triple stores and property graphs are separate worlds
**Description**: Redesign the ontology-server storage layer to exploit native \
RDF interop in modern property graph databases. This would allow SPARQL queries \
AND Cypher traversals on the same data, eliminating the current impedance \
mismatch between the idea pool's semantic model and graph analytics.

## Idea 2: Cladistic Idea Classification
**Protocol**: Analogical Transfer
**Source Field**: Biological taxonomy (molecular phylogenetics)
**Source Solution**: Classify organisms by shared derived characteristics rather than overall similarity
**Structural Mapping**: Ideas can be classified by their shared architectural \
implications (the "derived characteristics") rather than surface-level topic \
similarity. An idea about caching and an idea about event sourcing might share \
the derived characteristic of "eventual consistency acceptance."
**Description**: Build a cladistic classifier that groups ideas by their deep \
structural implications rather than keyword similarity. Use the ontology's \
property structure as the equivalent of molecular markers — objective, \
computable, and independent of subjective categorization.

## Idea 3: ADR-Runtime Topology Bridge
**Protocol**: Assumption Inversion
**Conventional Wisdom**: ADRs are documentation artifacts reviewed by humans
**Challenge Found**: No major tool links ADR content to runtime topology despite widespread adoption
**Description**: Invert the assumption that ADRs are static documents. Treat \
each ADR as an executable constraint that can be validated against the actual \
system topology. When the system diverges from its recorded decisions, surface \
the contradiction automatically rather than waiting for a human audit.
"""


# =========================================================================
# TestBuildPrompt
# =========================================================================


class TestBuildPrompt:
    """Verify the prompt produced by DomainPhase.build_prompt."""

    def test_prompt_contains_idea_id(self, ctx: PhaseContext) -> None:
        prompt = DomainPhase().build_prompt(ctx)
        assert "idea-42" in prompt

    def test_prompt_contains_output_filename(self, ctx: PhaseContext) -> None:
        prompt = DomainPhase().build_prompt(ctx)
        assert "ep-domain-ideas.md" in prompt

    def test_prompt_contains_phase_marker(self, ctx: PhaseContext) -> None:
        prompt = DomainPhase().build_prompt(ctx)
        # Domain mode defines 5 phases; at least one must appear
        phase_markers = [
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
            "Phase 5",
        ]
        found = [m for m in phase_markers if m in prompt]
        assert found, "Prompt must contain at least one Phase marker"

    def test_prompt_contains_domain_research_emphasis(self, ctx: PhaseContext) -> None:
        prompt = DomainPhase().build_prompt(ctx)
        # Domain mode is distinctively outward-looking — web research is the core
        assert "Domain Research" in prompt


# =========================================================================
# TestGetTools
# =========================================================================


class TestGetTools:
    """Verify the tool list returned by DomainPhase.get_tools."""

    def test_get_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = DomainPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__get_idea" in names

    def test_query_ideas_tool_present(self, ctx: PhaseContext) -> None:
        tools = DomainPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ideas" in names

    def test_create_idea_tool_present(self, ctx: PhaseContext) -> None:
        tools = DomainPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "mcp__ontology-server__create_idea" in names

    def test_web_search_tool_present(self, ctx: PhaseContext) -> None:
        tools = DomainPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "WebSearch" in names

    def test_write_tool_present(self, ctx: PhaseContext) -> None:
        tools = DomainPhase().get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Write" in names


# =========================================================================
# TestParseOutput
# =========================================================================


class TestParseOutput:
    """Verify DomainPhase.parse_output handles missing and present files."""

    def test_missing_file_raises_parse_error(self, ctx: PhaseContext) -> None:
        phase = DomainPhase()
        with pytest.raises(ParseError):
            phase.parse_output(ctx, raw="ignored")

    def test_present_file_returns_epistemology_output(
        self,
        ctx: PhaseContext,
        write_sample_output,
    ) -> None:
        write_sample_output("ep-domain-ideas.md", SAMPLE_OUTPUT)
        phase = DomainPhase()
        result = phase.parse_output(ctx, raw="ignored")

        assert isinstance(result, EpistemologyOutput)
        assert result.ideas_generated == 3
        assert result.mode == "domain"


# =========================================================================
# TestExecuteWithMock
# =========================================================================


class _MockedDomainPhase(DomainPhase):
    """DomainPhase subclass that writes sample output instead of calling Claude."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "ep-domain-ideas.md"
        output_file.write_text(SAMPLE_OUTPUT, encoding="utf-8")
        return "mock"


class TestExecuteWithMock:
    """End-to-end execute via a mock that writes sample output."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockedDomainPhase()
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert isinstance(result.data, EpistemologyOutput)
        assert result.data.ideas_generated == 3
        assert result.data.mode == "domain"
