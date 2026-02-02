"""Tests for tulla.phases.planning.p6 -- P6Phase (Export PRD to RDF)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext
from tulla.phases.planning.models import P6Output
from tulla.phases.planning.p6 import P6Phase, PRD_NS, TRACE_NS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext pointing at a temporary work directory."""
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.p6"),
    )


@pytest.fixture()
def phase() -> P6Phase:
    """A plain P6Phase instance."""
    return P6Phase()


# ===================================================================
# Construction and defaults
# ===================================================================


class TestConstruction:
    """P6Phase construction and attribute defaults."""

    def test_default_phase_id(self) -> None:
        p = P6Phase()
        assert p.phase_id == "p6"

    def test_default_timeout(self) -> None:
        p = P6Phase()
        assert p.timeout_s == 1200.0


# ===================================================================
# build_prompt
# ===================================================================


class TestBuildPrompt:
    """P6Phase.build_prompt() generates the PRD export prompt."""

    def test_contains_idea_id(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "idea 42" in prompt

    def test_references_p4_file(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p4-implementation-plan.md" in prompt

    def test_references_turtle_output(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p6-prd-export.ttl" in prompt

    def test_references_summary_output(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "p6-prd-summary.md" in prompt

    def test_references_prd_namespace(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert PRD_NS in prompt

    def test_references_store_fact(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "mcp__ontology-server__store_fact" in prompt

    def test_references_prd_context(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "prd-idea-42" in prompt

    def test_warns_against_add_triple(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Do NOT use add_triple" in prompt

    def test_adr_linking_is_mandatory(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "MANDATORY" in prompt
        assert "prd:relatedADR" in prompt
        assert "prd:qualityFocus" in prompt

    def test_turtle_template_includes_adr(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert 'prd:relatedADR "arch:adr-42' in prompt
        assert 'prd:qualityFocus "[Quality attribute]"' in prompt


# ===================================================================
# get_tools
# ===================================================================


class TestGetTools:
    """P6Phase.get_tools() returns Read, Write, and store_fact."""

    def test_returns_expected_tools(self, phase: P6Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Read" in names
        assert "Write" in names
        assert "mcp__ontology-server__store_fact" in names


# ===================================================================
# get_timeout_seconds
# ===================================================================


class TestGetTimeoutSeconds:
    """P6Phase.get_timeout_seconds() returns the configured timeout."""

    def test_returns_timeout(self, phase: P6Phase) -> None:
        assert phase.get_timeout_seconds() == 1200.0


# ===================================================================
# parse_output -- success
# ===================================================================


SAMPLE_TURTLE = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "First task" ;
    prd:status prd:Pending ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Maintainability" .

prd:req-42-1-2 a prd:Requirement ;
    prd:taskId "1.2" ;
    prd:title "Second task" ;
    prd:status prd:Pending ;
    prd:dependsOn prd:req-42-1-1 ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Correctness" .

prd:req-42-2-1 a prd:Requirement ;
    prd:taskId "2.1" ;
    prd:title "Third task" ;
    prd:status prd:Pending ;
    prd:relatedADR "arch:adr-42-2" ;
    prd:qualityFocus "Testability" .
"""

SAMPLE_TURTLE_NO_ADR = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "First task" ;
    prd:status prd:Pending .
"""


class TestParseOutputSuccess:
    """P6Phase.parse_output() when turtle file exists."""

    def test_returns_p6_output(self, phase: P6Phase, ctx: PhaseContext) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)
        (ctx.work_dir / "p6-prd-summary.md").write_text("# Summary\n")

        result = phase.parse_output(ctx, None)

        assert isinstance(result, P6Output)
        assert result.requirements_exported == 3
        assert result.prd_context == "prd-idea-42"
        assert result.turtle_file == ctx.work_dir / "p6-prd-export.ttl"

    def test_default_granularity_fields(self, phase: P6Phase, ctx: PhaseContext) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)
        (ctx.work_dir / "p6-prd-summary.md").write_text("# Summary\n")

        result = phase.parse_output(ctx, None)

        assert result.coarse_requirements == []
        assert result.granularity_passed is True

    def test_counts_requirements(self, phase: P6Phase, ctx: PhaseContext) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)
        result = phase.parse_output(ctx, None)
        assert result.requirements_exported == 3


# ===================================================================
# parse_output -- missing file
# ===================================================================


class TestParseOutputADRLinks:
    """P6Phase.parse_output() counts architecture traceability links."""

    def test_counts_adr_links(self, phase: P6Phase, ctx: PhaseContext) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)
        result = phase.parse_output(ctx, None)
        assert result.adr_links == 3

    def test_counts_quality_links(self, phase: P6Phase, ctx: PhaseContext) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)
        result = phase.parse_output(ctx, None)
        assert result.quality_links == 3

    def test_zero_adr_links_warns(
        self, phase: P6Phase, ctx: PhaseContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE_NO_ADR)
        with caplog.at_level(logging.WARNING):
            result = phase.parse_output(ctx, None)
        assert result.adr_links == 0
        assert result.quality_links == 0
        assert "zero prd:relatedADR" in caplog.text

    def test_defaults_to_zero(self, phase: P6Phase, ctx: PhaseContext) -> None:
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE_NO_ADR)
        result = phase.parse_output(ctx, None)
        assert result.adr_links == 0
        assert result.quality_links == 0


# ===================================================================
# parse_output -- missing file
# ===================================================================


class TestParseOutputMissing:
    """P6Phase.parse_output() when turtle file is missing."""

    def test_raises_parse_error(self, phase: P6Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError, match="p6-prd-export.ttl not found"):
            phase.parse_output(ctx, None)


# ===================================================================
# Sample Turtle constants for granularity tests (prd:req-64-3-3)
# ===================================================================

SAMPLE_TURTLE_COARSE = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "Bootstrap Everything" ;
    prd:description "Create files" ;
    prd:status prd:Pending ;
    prd:files "src/a.py, src/b.ts, src/c.go, src/d.rs, src/e.rb, src/f.java, src/g.cpp" ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Maintainability" .
"""

SAMPLE_TURTLE_CROSS_CUTTING = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "Linting Setup @cross-cutting" ;
    prd:description "Set up linting" ;
    prd:status prd:Pending ;
    prd:files "src/a.py, src/b.ts, src/c.go, src/d.rs" ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Consistency" .
"""

SAMPLE_TURTLE_HOMOGENEOUS = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "Create Package Inits" ;
    prd:description "Init" ;
    prd:status prd:Pending ;
    prd:files "src/a/__init__.py, src/b/__init__.py, src/c/__init__.py, src/d/__init__.py" ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Structure" .
"""


# ===================================================================
# TestGranularityMetrics (prd:req-64-3-3)
# ===================================================================


class TestGranularityMetrics:
    """Granularity metrics: fine Turtle passes, coarse detected, cross-cutting exempt, homogeneous exempt."""

    def test_fine_turtle_passes(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """SAMPLE_TURTLE (all ≤3 files) has no coarse requirements."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)

        result = phase.parse_output(ctx, None)

        assert result.coarse_requirements == []
        assert result.granularity_passed is True

    def test_coarse_detected(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """SAMPLE_TURTLE_COARSE triggers coarse detection (7 heterogeneous files, low wpf)."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE_COARSE)

        result = phase.parse_output(ctx, None)

        assert len(result.coarse_requirements) >= 1
        assert result.coarse_requirements[0]["requirement"] == "prd:req-42-1-1"
        assert result.coarse_requirements[0]["file_count"] == 7
        assert result.coarse_requirements[0]["homogeneous"] is False
        assert result.granularity_passed is False

    def test_cross_cutting_exempt(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """SAMPLE_TURTLE_CROSS_CUTTING is exempt from coarse detection via @cross-cutting."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE_CROSS_CUTTING)

        result = phase.parse_output(ctx, None)

        assert result.coarse_requirements == []
        assert result.granularity_passed is True

    def test_homogeneous_exempt(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """SAMPLE_TURTLE_HOMOGENEOUS is exempt because all files share the same basename."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE_HOMOGENEOUS)

        result = phase.parse_output(ctx, None)

        assert result.coarse_requirements == []
        assert result.granularity_passed is True


# ===================================================================
# TestValidateOutputBlocking (prd:req-64-3-3)
# ===================================================================


class TestValidateOutputBlocking:
    """P6Phase.validate_output() is a blocking gate: passes fine, blocks coarse with ValueError."""

    def test_passes_fine(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """validate_output() returns None when granularity_passed is True."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE)
        (ctx.work_dir / "p6-prd-summary.md").write_text("# Summary\n")

        parsed = phase.parse_output(ctx, None)
        # Should not raise
        assert phase.validate_output(ctx, parsed) is None

    def test_blocks_coarse_with_value_error(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """validate_output() raises ValueError when coarse requirements exist."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(SAMPLE_TURTLE_COARSE)

        parsed = phase.parse_output(ctx, None)

        with pytest.raises(ValueError, match="P6 granularity gate failed"):
            phase.validate_output(ctx, parsed)
