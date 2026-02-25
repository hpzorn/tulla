"""Tests for tulla.phases.planning.p3 – P3Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.planning.p3 import P3Phase, _extract_adrs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext pointing at a temporary work directory."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.p3"),
    )


@pytest.fixture()
def phase() -> P3Phase:
    """A plain P3Phase instance."""
    return P3Phase()


SAMPLE_ARCHITECTURE = """\
# P3: Architecture Design
**Idea**: idea-42
**Date**: 2026-02-01

## Quality Goals (isaqb:QualityGoal)

| Priority | Quality Attribute | Sub-Attributes | Rationale |
|----------|-------------------|----------------|-----------|
| 1 | Maintainability | Modularity, Testability | Core pipeline needs to be extensible |
| 2 | Reliability | FaultTolerance | Pipeline must not lose work |

### Quality Tradeoffs

| Attribute A | conflicts with | Attribute B | Resolution |
|-------------|---------------|-------------|------------|
| PerformanceEfficiency | ↔ | Maintainability | Favour maintainability |

## Design Principles (isaqb:DesignPrinciple)

1. **Separation of Concerns** (Category: Modularization) — Each phase is independent
2. **Template Method** (Category: Abstraction) — Common phase structure

## Architectural Patterns (isaqb:ArchitecturalPattern)

| Pattern | Addresses Quality | Embodies Principle | Relevance |
|---------|------------------|--------------------|-----------|
| Pipes & Filters | Maintainability | Separation of Concerns | R1 |

## System Architecture

### High-Level Flow
[Input] → [P1] → [P2] → [P3] → [P4] → [P5] → [Output]

### Building Blocks
Phase classes inheriting from Phase[T] base.

### Runtime View
Sequential pipeline execution.

## Data Flow
Markdown files passed between phases.

## Integration Plan
MCP tools connected via tool definitions.

## Cross-Cutting Concerns
Error handling via ParseError.

## Architecture Decisions (ADRs)

### ADR-1: Use Template Method Pattern
**Status**: Proposed
**Decision**: Template Method for phases

## Quality Scenarios

| ID | Quality Attribute | Stimulus | Environment | Response | Measure |
|----|-------------------|----------|-------------|----------|---------|
| QS-1 | Reliability | Phase timeout | Production | Graceful degradation | < 1s recovery |

## File Structure
```
tulla/src/tulla/phases/planning/
├── p1.py
├── p2.py
├── p3.py
├── p4.py
└── p5.py
```

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Timeout | Medium | Medium | Phase-level timeouts |

## Unknowns Requiring Research

| Unknown | Why It Matters | Blocking? |
|---------|----------------|-----------|
| iSAQB schema coverage | May miss quality attributes | No |
| MCP rate limits | Could affect pipeline speed | Yes |
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """P3Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: P3Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_architecture_output_path(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p3-architecture-design.md" in prompt

    def test_includes_phase_heading(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase P3: Architecture Design" in prompt

    def test_reads_p1_and_p2(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p1-discovery-context.md" in prompt
        assert "p2-codebase-analysis.md" in prompt

    def test_includes_schema_context_when_provided(
        self, phase: P3Phase, tmp_path: Path
    ) -> None:
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"schema_context": "iSAQB quality attributes here"},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p3"),
        )
        prompt = phase.build_prompt(ctx)
        assert "iSAQB quality attributes here" in prompt
        assert "iSAQB Architecture Schema" in prompt

    def test_no_schema_block_when_absent(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "iSAQB Architecture Schema" not in prompt

    def test_project_adr_section_with_decisions(
        self, phase: P3Phase, tmp_path: Path
    ) -> None:
        decisions = [
            {
                "title": "ADR-P-1: Use Event Sourcing",
                "decision": "All state changes persisted as immutable events.",
                "quality_attributes": "Reliability, Auditability",
            },
            {
                "title": "ADR-P-2: GraphQL Gateway",
                "decision": "Single GraphQL gateway for all client queries.",
                "quality_attributes": "Maintainability",
            },
        ]
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"project_decisions": decisions},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p3"),
        )
        prompt = phase.build_prompt(ctx)

        # Section must be present
        assert "## Project ADRs in Effect" in prompt

        # Both ADR titles present
        assert "ADR-P-1: Use Event Sourcing" in prompt
        assert "ADR-P-2: GraphQL Gateway" in prompt

        # Correct ordering: section appears between upstream area and ## Goal
        adr_pos = prompt.index("## Project ADRs in Effect")
        goal_pos = prompt.index("## Goal")
        assert adr_pos < goal_pos

    def test_project_adr_section_between_upstream_facts_and_goal(
        self, phase: P3Phase, tmp_path: Path
    ) -> None:
        """Project ADR section appears between upstream facts and ## Goal."""
        decisions = [
            {
                "title": "ADR-P-1: Use Event Sourcing",
                "decision": "All state changes persisted as immutable events.",
                "quality_attributes": "Reliability",
            },
        ]
        upstream_facts = [
            {
                "subject": "http://tulla.dev/phase#idea-42-d1",
                "predicate": "http://tulla.dev/phase#preserves-key_capabilities",
                "object": "Graph traversal engine",
            },
        ]
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={
                "project_decisions": decisions,
                "upstream_facts": upstream_facts,
            },
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p3"),
        )
        prompt = phase.build_prompt(ctx)

        upstream_pos = prompt.index("## Upstream Facts")
        adr_pos = prompt.index("## Project ADRs in Effect")
        goal_pos = prompt.index("## Goal")
        assert upstream_pos < adr_pos < goal_pos

    def test_project_adr_section_omitted_when_empty(
        self, phase: P3Phase, tmp_path: Path
    ) -> None:
        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={"project_decisions": []},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p3"),
        )
        prompt = phase.build_prompt(ctx)
        assert "## Project ADRs in Effect" not in prompt

    def test_project_adr_section_omitted_when_key_absent(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        prompt = phase.build_prompt(ctx)
        assert "## Project ADRs in Effect" not in prompt

    def test_collect_project_decisions_called_when_not_present(
        self, phase: P3Phase, tmp_path: Path
    ) -> None:
        """When ontology_port and project_id are set but project_decisions
        is absent, build_prompt populates it via collect_project_decisions."""

        class _MockOntologyPort:
            def sparql_query(self, query: str) -> dict:
                return {
                    "results": [
                        {
                            "adr": "http://example.org#adr-proj-1",
                            "title": "ADR-Mock: Test Decision",
                            "consequences": "Mock consequence text.",
                            "quality_attributes": "Testability",
                            "status": "isaqb:StatusAccepted",
                        },
                    ]
                }

        ctx = PhaseContext(
            idea_id="idea-42",
            work_dir=tmp_path,
            config={
                "ontology_port": _MockOntologyPort(),
                "project_id": "proj",
            },
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.p3"),
        )
        prompt = phase.build_prompt(ctx)

        # Should have auto-collected and inserted
        assert "## Project ADRs in Effect" in prompt
        assert "ADR-Mock: Test Decision" in prompt
        # project_decisions should now be populated in config
        assert "project_decisions" in ctx.config
        assert len(ctx.config["project_decisions"]) == 1


# ===================================================================
# get_tools includes ontology-server tools
# ===================================================================


class TestGetTools:
    """P3Phase.get_tools() tests."""

    def test_includes_ontology_server_tools(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = [t["name"] for t in tools]
        assert "mcp__ontology-server__query_ontology" in tool_names
        assert "mcp__ontology-server__sparql_query" in tool_names

    def test_includes_read_write(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """P3Phase.parse_output() when p3-architecture-design.md is absent."""

    def test_raises_parse_error_on_missing_file(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError, match="p3-architecture-design.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """P3Phase.parse_output() when p3-architecture-design.md is present."""

    def test_returns_p3_output(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        arch_file = ctx.work_dir / "p3-architecture-design.md"
        arch_file.write_text(SAMPLE_ARCHITECTURE, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.dependency_graph_file == arch_file
        assert result.total_dependencies == 2  # 2 unknowns in table
        assert result.circular_dependencies == 1  # 1 with "Yes"

    def test_zero_unknowns_when_table_empty(
        self, phase: P3Phase, ctx: PhaseContext
    ) -> None:
        minimal = (
            "# P3: Architecture Design\n"
            "## Unknowns Requiring Research\n"
            "No unknowns found.\n"
            "## Risk Assessment\n"
        )
        arch_file = ctx.work_dir / "p3-architecture-design.md"
        arch_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        assert result.total_dependencies == 0
        assert result.circular_dependencies == 0


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockP3Phase(P3Phase):
    """P3Phase with a mocked run_claude that writes the architecture file."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        output_file = ctx.work_dir / "p3-architecture-design.md"
        output_file.write_text(self._content, encoding="utf-8")
        return "mock-raw-output"


# ===================================================================
# _build_project_adr_section
# ===================================================================


class TestBuildProjectAdrSection:
    """P3Phase._build_project_adr_section() tests."""

    SAMPLE_DECISIONS: list[dict[str, Any]] = [
        {
            "title": "ADR-P-1: Use Event Sourcing",
            "decision": "All state changes persisted as immutable events.",
            "quality_attributes": "Reliability, Auditability",
        },
        {
            "title": "ADR-P-2: GraphQL Gateway",
            "decision": "Single GraphQL gateway for all client queries.",
            "quality_attributes": "Maintainability",
        },
        {
            "title": "ADR-P-3: SHACL Validation",
            "decision": "SHACL shapes enforce data governance at ingest.",
            "quality_attributes": "FunctionalCorrectness, Interoperability",
        },
    ]

    def test_contains_all_adr_titles(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        for adr in self.SAMPLE_DECISIONS:
            assert adr["title"] in result

    def test_contains_decision_text(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        for adr in self.SAMPLE_DECISIONS:
            assert adr["decision"] in result

    def test_contains_quality_attributes(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        for adr in self.SAMPLE_DECISIONS:
            assert adr["quality_attributes"] in result

    def test_contains_do_not_instruction(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        assert "DO NOT" in result
        assert "restate" in result.lower()

    def test_contains_do_instruction(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        assert "**DO**" in result
        assert "feature-specific" in result

    def test_contains_if_override_instruction(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        assert "**IF**" in result
        assert "isaqb:supersedes" in result
        assert "isaqb:refinesDecision" in result

    def test_contains_align_instruction(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        assert "**ALIGN**" in result
        assert "quality" in result.lower()

    def test_contains_scope_annotation_notice(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        assert "isaqb:decisionScope" in result
        assert "feature" in result

    def test_section_heading(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section(self.SAMPLE_DECISIONS)
        assert "## Project ADRs in Effect" in result

    def test_empty_decisions_returns_empty_string(self, phase: P3Phase) -> None:
        result = phase._build_project_adr_section([])
        assert result == ""


class TestExecuteWithMock:
    """P3Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockP3Phase(SAMPLE_ARCHITECTURE)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.dependency_graph_file == ctx.work_dir / "p3-architecture-design.md"
        assert result.data.total_dependencies == 2
        assert result.data.circular_dependencies == 1
        assert result.error is None
        assert result.duration_s > 0


# ===================================================================
# _extract_adrs scope annotation
# ===================================================================


class TestExtractAdrsScope:
    """_extract_adrs() annotates each ADR with scope='idea'."""

    TWO_ADR_MARKDOWN = (
        "## Architecture Decisions (ADRs)\n\n"
        "### ADR-1: Use Template Method\n"
        "**Status**: Proposed\n"
        "**Decision**: Template Method for phases\n"
        "**Rationale**: Uniform phase structure\n\n"
        "### ADR-2: Event-Driven Pipeline\n"
        "**Status**: Proposed\n"
        "**Decision**: Events for inter-phase communication\n"
        "**Rationale**: Loose coupling\n"
    )

    THREE_ADR_MARKDOWN = (
        "## Architecture Decisions (ADRs)\n\n"
        "### ADR-1: Use Template Method\n"
        "**Status**: Proposed\n"
        "**Decision**: Template Method for phases\n"
        "**Rationale**: Uniform phase structure\n\n"
        "### ADR-2: Event-Driven Pipeline\n"
        "**Status**: Proposed\n"
        "**Decision**: Events for inter-phase communication\n"
        "**Rationale**: Loose coupling\n\n"
        "### ADR-3: SHACL Validation Layer\n"
        "**Status**: Proposed\n"
        "**Decision**: SHACL shapes enforce data governance\n"
        "**Rationale**: Catches structural errors early\n"
    )

    def test_each_adr_has_scope_idea(self) -> None:
        adrs = _extract_adrs(self.TWO_ADR_MARKDOWN)
        assert len(adrs) == 2
        for adr in adrs:
            assert adr["scope"] == "idea"

    def test_three_adrs_all_have_scope_idea(self) -> None:
        adrs = _extract_adrs(self.THREE_ADR_MARKDOWN)
        assert len(adrs) == 3
        for adr in adrs:
            assert isinstance(adr, dict)
            assert "scope" in adr
            assert adr["scope"] == "idea"
