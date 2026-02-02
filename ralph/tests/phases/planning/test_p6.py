"""Tests for tulla.phases.planning.p6 -- P6Phase (Export PRD to RDF)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tulla.adapters.claude_mock import MockClaudeAdapter
from tulla.core.phase import ParseError, PhaseContext, PhaseResult, PhaseStatus
from tulla.phases.planning.models import P6Output
from tulla.phases.planning.p6 import P6Phase, PRD_NS, TRACE_NS, _compact_uri, _group_files_by_directory
from tulla.ports.claude import ClaudeResult
from tulla.ports.ontology import OntologyPort


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
        assert p.timeout_s == 600.0


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

    def test_does_not_instruct_store_fact(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Do NOT call store_fact" in prompt

    def test_references_prd_context(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "prd-idea-42" in prompt

    def test_adr_linking_is_mandatory(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "MANDATORY" in prompt
        assert "prd:relatedADR" in prompt
        assert "prd:qualityFocus" in prompt

    def test_turtle_template_includes_adr(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert 'prd:relatedADR "arch:adr-42' in prompt
        assert "prd:qualityFocus isaqb:Maintainability" in prompt

    def test_references_isaqb_namespace(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "isaqb:" in prompt
        assert "isaqb:Maintainability" in prompt

    def test_references_granularity_metrics(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "prd:filesCount" in prompt
        assert "prd:descriptionWordCount" in prompt
        assert "prd:wordsPerFile" in prompt

    def test_no_feedback_by_default(self, phase: P6Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Granularity Feedback" not in prompt

    def test_appends_granularity_feedback(self, phase: P6Phase, ctx: PhaseContext) -> None:
        ctx.config["granularity_feedback"] = "Split prd:req-42-1-1 into smaller parts."
        prompt = phase.build_prompt(ctx)
        assert prompt.endswith(
            "## Granularity Feedback (MUST address)\n"
            "Split prd:req-42-1-1 into smaller parts."
        )

    def test_feedback_empty_string_not_appended(self, phase: P6Phase, ctx: PhaseContext) -> None:
        ctx.config["granularity_feedback"] = ""
        prompt = phase.build_prompt(ctx)
        assert "Granularity Feedback" not in prompt


# ===================================================================
# get_tools
# ===================================================================


class TestGetTools:
    """P6Phase.get_tools() returns Read, Write, and recall_facts (no store_fact)."""

    def test_returns_expected_tools(self, phase: P6Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        names = [t["name"] for t in tools]
        assert "Read" in names
        assert "Write" in names
        assert "mcp__ontology-server__recall_facts" in names
        assert "mcp__ontology-server__store_fact" not in names

    def test_disallows_store_fact(self, phase: P6Phase, ctx: PhaseContext) -> None:
        disallowed = phase.get_disallowed_tools(ctx)
        assert "mcp__ontology-server__store_fact" in disallowed
        assert "mcp__ontology-server__add_triple" in disallowed


# ===================================================================
# get_timeout_seconds
# ===================================================================


class TestGetTimeoutSeconds:
    """P6Phase.get_timeout_seconds() returns the configured timeout."""

    def test_returns_timeout(self, phase: P6Phase) -> None:
        assert phase.get_timeout_seconds() == 600.0


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


# ===================================================================
# _MockP6Phase helper (prd:req-64-4-4)
# ===================================================================


class _MockP6Phase(P6Phase):
    """P6Phase subclass with controllable Turtle output per attempt.

    Accepts a list of Turtle strings.  On each ``run_claude`` call the
    next entry is written to the work directory, allowing tests to
    simulate a sequence of coarse → fine outputs across retries without
    ``unittest.mock.patch``.
    """

    def __init__(
        self,
        turtle_per_attempt: list[str],
        summary: str = "# Summary\n",
    ) -> None:
        super().__init__()
        self._turtle_per_attempt = list(turtle_per_attempt)
        self._summary = summary
        self._call_count = 0
        self.captured_prompts: list[str] = []

    @property
    def call_count(self) -> int:
        return self._call_count

    def run_claude(
        self,
        ctx: PhaseContext,
        prompt: str,
        tools: list[dict[str, Any]],
    ) -> ClaudeResult:
        self.captured_prompts.append(prompt)
        idx = min(self._call_count, len(self._turtle_per_attempt) - 1)
        turtle_text = self._turtle_per_attempt[idx]
        self._call_count += 1

        (ctx.work_dir / "p6-prd-export.ttl").write_text(turtle_text)
        (ctx.work_dir / "p6-prd-summary.md").write_text(self._summary)
        return ClaudeResult(exit_code=0, output_text="done", cost_usd=0.1)


# ===================================================================
# TestExecuteRetryLoop (prd:req-64-4-1)
# ===================================================================


FINE_TURTLE = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "First task" ;
    prd:description "Implement the first component" ;
    prd:status prd:Pending ;
    prd:files "src/a.py" ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Maintainability" .

prd:req-42-1-2 a prd:Requirement ;
    prd:taskId "1.2" ;
    prd:title "Second task" ;
    prd:description "Implement the second component" ;
    prd:status prd:Pending ;
    prd:files "src/b.py" ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Correctness" .
"""


class TestExecuteRetryLoop:
    """P6Phase.execute() retries on validation failure with granularity feedback."""

    def test_success_after_one_retry(self, ctx: PhaseContext) -> None:
        """First run_claude produces coarse Turtle, second produces fine: SUCCESS after 1 retry."""
        call_count = 0

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            nonlocal call_count
            call_count += 1
            turtle_file = ctx_.work_dir / "p6-prd-export.ttl"
            summary_file = ctx_.work_dir / "p6-prd-summary.md"
            if call_count == 1:
                turtle_file.write_text(SAMPLE_TURTLE_COARSE)
            else:
                turtle_file.write_text(FINE_TURTLE)
            summary_file.write_text("# Summary\n")
            return ClaudeResult(exit_code=0, output_text="done", cost_usd=0.1)

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.granularity_passed is True
        assert call_count == 2
        assert result.metadata.get("attempts") == 2

    def test_fails_after_retries_exhausted(self, ctx: PhaseContext) -> None:
        """All attempts produce coarse Turtle: FAILURE after retries exhausted."""
        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            turtle_file = ctx_.work_dir / "p6-prd-export.ttl"
            summary_file = ctx_.work_dir / "p6-prd-summary.md"
            turtle_file.write_text(SAMPLE_TURTLE_COARSE)
            summary_file.write_text("# Summary\n")
            return ClaudeResult(exit_code=0, output_text="done")

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.FAILURE
        assert "granularity gate failed" in (result.error or "")

    def test_no_retry_on_parse_error(self, ctx: PhaseContext) -> None:
        """ParseError is not retried — immediate FAILURE."""
        call_count = 0

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            nonlocal call_count
            call_count += 1
            # Do NOT write the turtle file — triggers ParseError
            return ClaudeResult(exit_code=0, output_text="done")

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 2

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.FAILURE
        assert "parsing failed" in (result.error or "").lower()
        assert call_count == 1  # No retry

    def test_no_retry_on_timeout(self, ctx: PhaseContext) -> None:
        """TimeoutError is not retried — immediate TIMEOUT."""
        call_count = 0

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timed out")

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 2

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.TIMEOUT
        assert call_count == 1  # No retry

    def test_default_max_retries_is_one(self, ctx: PhaseContext) -> None:
        """Default max_granularity_retries is 1 when not in config."""
        call_count = 0

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            nonlocal call_count
            call_count += 1
            turtle_file = ctx_.work_dir / "p6-prd-export.ttl"
            summary_file = ctx_.work_dir / "p6-prd-summary.md"
            turtle_file.write_text(SAMPLE_TURTLE_COARSE)
            summary_file.write_text("# Summary\n")
            return ClaudeResult(exit_code=0, output_text="done")

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        # Do NOT set max_granularity_retries — should default to 1

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.FAILURE
        assert call_count == 2  # 1 initial + 1 retry

    def test_feedback_injected_on_retry(self, ctx: PhaseContext) -> None:
        """On retry, granularity feedback is injected into the prompt."""
        prompts: list[str] = []

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            prompts.append(prompt)
            turtle_file = ctx_.work_dir / "p6-prd-export.ttl"
            summary_file = ctx_.work_dir / "p6-prd-summary.md"
            if len(prompts) == 1:
                turtle_file.write_text(SAMPLE_TURTLE_COARSE)
            else:
                turtle_file.write_text(FINE_TURTLE)
            summary_file.write_text("# Summary\n")
            return ClaudeResult(exit_code=0, output_text="done")

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert len(prompts) == 2
        # First prompt should NOT have feedback
        assert "Granularity Feedback" not in prompts[0]
        # Second prompt SHOULD have feedback
        assert "Granularity Feedback" in prompts[1]
        assert "too coarse" in prompts[1]

    def test_first_attempt_succeeds_no_retry(self, ctx: PhaseContext) -> None:
        """Fine Turtle on first attempt — SUCCESS without retry."""
        call_count = 0

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            nonlocal call_count
            call_count += 1
            turtle_file = ctx_.work_dir / "p6-prd-export.ttl"
            summary_file = ctx_.work_dir / "p6-prd-summary.md"
            turtle_file.write_text(FINE_TURTLE)
            summary_file.write_text("# Summary\n")
            return ClaudeResult(exit_code=0, output_text="done")

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert call_count == 1
        assert result.metadata.get("attempts") == 1


# ===================================================================
# TestGroupFilesByDirectory (helper, prd:req-64-4-2)
# ===================================================================


class TestGroupFilesByDirectory:
    """_group_files_by_directory() groups file paths by parent directory."""

    def test_groups_by_dir(self) -> None:
        files = ["src/a.py", "src/b.py", "lib/c.py"]
        result = _group_files_by_directory(files)
        assert result == {"src": ["a.py", "b.py"], "lib": ["c.py"]}

    def test_bare_files_use_dot(self) -> None:
        files = ["a.py", "b.py"]
        result = _group_files_by_directory(files)
        assert result == {".": ["a.py", "b.py"]}

    def test_empty_list(self) -> None:
        assert _group_files_by_directory([]) == {}

    def test_nested_dirs(self) -> None:
        files = ["src/core/a.py", "src/core/b.py", "src/cli/c.py"]
        result = _group_files_by_directory(files)
        assert result == {"src/core": ["a.py", "b.py"], "src/cli": ["c.py"]}


# ===================================================================
# TestBuildGranularityFeedback (prd:req-64-4-2)
# ===================================================================


COARSE_MULTI_DIR_TURTLE = """\
@prefix prd: <http://impl-ralph.io/prd#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

prd:req-42-1-1 a prd:Requirement ;
    prd:taskId "1.1" ;
    prd:title "Bootstrap Everything" ;
    prd:description "Create files" ;
    prd:status prd:Pending ;
    prd:files "src/core/a.py, src/core/b.ts, src/cli/c.go, lib/d.rs" ;
    prd:relatedADR "arch:adr-42-1" ;
    prd:qualityFocus "Maintainability" .
"""


class TestBuildGranularityFeedback:
    """P6Phase._build_granularity_feedback() returns Template A markdown with metrics and split plans."""

    def test_returns_empty_for_no_coarse(self, phase: P6Phase, ctx: PhaseContext) -> None:
        """When there are no coarse requirements, returns empty string."""
        parsed = P6Output(
            turtle_file=ctx.work_dir / "p6-prd-export.ttl",
            summary_file=ctx.work_dir / "p6-prd-summary.md",
            requirements_exported=1,
            prd_context="prd-idea-42",
            coarse_requirements=[],
            granularity_passed=True,
        )
        result = PhaseResult(status=PhaseStatus.SUCCESS, data=parsed)
        assert phase._build_granularity_feedback(result) == ""

    def test_returns_empty_for_none_data(self, phase: P6Phase) -> None:
        """When result.data is None, returns empty string."""
        result = PhaseResult(status=PhaseStatus.FAILURE, data=None)
        assert phase._build_granularity_feedback(result) == ""

    def test_contains_specific_metrics(self, phase: P6Phase, ctx: PhaseContext) -> None:
        """Feedback includes file count, wpf, and word count for each coarse requirement."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(COARSE_MULTI_DIR_TURTLE)
        parsed = P6Output(
            turtle_file=ctx.work_dir / "p6-prd-export.ttl",
            summary_file=ctx.work_dir / "p6-prd-summary.md",
            requirements_exported=1,
            prd_context="prd-idea-42",
            coarse_requirements=[{
                "requirement": "prd:req-42-1-1",
                "file_count": 4,
                "word_count": 2,
                "wpf": 0.5,
                "homogeneous": False,
            }],
            granularity_passed=False,
        )
        result = PhaseResult(status=PhaseStatus.SUCCESS, data=parsed)
        feedback = phase._build_granularity_feedback(result)

        assert "prd:req-42-1-1" in feedback
        assert "**Files**: 4" in feedback
        assert "**Words-per-file (wpf)**: 0.5" in feedback
        assert "**Total description words**: 2" in feedback

    def test_contains_directory_split_suggestions(self, phase: P6Phase, ctx: PhaseContext) -> None:
        """Feedback groups files by directory and suggests split boundaries."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(COARSE_MULTI_DIR_TURTLE)
        parsed = P6Output(
            turtle_file=ctx.work_dir / "p6-prd-export.ttl",
            summary_file=ctx.work_dir / "p6-prd-summary.md",
            requirements_exported=1,
            prd_context="prd-idea-42",
            coarse_requirements=[{
                "requirement": "prd:req-42-1-1",
                "file_count": 4,
                "word_count": 2,
                "wpf": 0.5,
                "homogeneous": False,
            }],
            granularity_passed=False,
        )
        result = PhaseResult(status=PhaseStatus.SUCCESS, data=parsed)
        feedback = phase._build_granularity_feedback(result)

        assert "Suggested splits by directory" in feedback
        assert "`lib/`" in feedback
        assert "`src/cli/`" in feedback
        assert "`src/core/`" in feedback

    def test_contains_critic_instructions(self, phase: P6Phase, ctx: PhaseContext) -> None:
        """Feedback includes CRITIC framework splitting instructions."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(COARSE_MULTI_DIR_TURTLE)
        parsed = P6Output(
            turtle_file=ctx.work_dir / "p6-prd-export.ttl",
            summary_file=ctx.work_dir / "p6-prd-summary.md",
            requirements_exported=1,
            prd_context="prd-idea-42",
            coarse_requirements=[{
                "requirement": "prd:req-42-1-1",
                "file_count": 4,
                "word_count": 2,
                "wpf": 0.5,
                "homogeneous": False,
            }],
            granularity_passed=False,
        )
        result = PhaseResult(status=PhaseStatus.SUCCESS, data=parsed)
        feedback = phase._build_granularity_feedback(result)

        assert "Action required" in feedback
        assert "at most **3 files**" in feedback
        assert "12 words per file" in feedback
        assert "single directory" in feedback
        assert "prd:dependsOn" in feedback

    def test_header_present(self, phase: P6Phase, ctx: PhaseContext) -> None:
        """Feedback starts with a header about coarse requirements."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(COARSE_MULTI_DIR_TURTLE)
        parsed = P6Output(
            turtle_file=ctx.work_dir / "p6-prd-export.ttl",
            summary_file=ctx.work_dir / "p6-prd-summary.md",
            requirements_exported=1,
            prd_context="prd-idea-42",
            coarse_requirements=[{
                "requirement": "prd:req-42-1-1",
                "file_count": 4,
                "word_count": 2,
                "wpf": 0.5,
                "homogeneous": False,
            }],
            granularity_passed=False,
        )
        result = PhaseResult(status=PhaseStatus.SUCCESS, data=parsed)
        feedback = phase._build_granularity_feedback(result)

        assert feedback.startswith("The following requirements are **too coarse**")

    def test_well_formed_markdown(self, phase: P6Phase, ctx: PhaseContext) -> None:
        """Feedback is well-formed markdown with headers and bullet points."""
        (ctx.work_dir / "p6-prd-export.ttl").write_text(COARSE_MULTI_DIR_TURTLE)
        parsed = P6Output(
            turtle_file=ctx.work_dir / "p6-prd-export.ttl",
            summary_file=ctx.work_dir / "p6-prd-summary.md",
            requirements_exported=1,
            prd_context="prd-idea-42",
            coarse_requirements=[{
                "requirement": "prd:req-42-1-1",
                "file_count": 4,
                "word_count": 2,
                "wpf": 0.5,
                "homogeneous": False,
            }],
            granularity_passed=False,
        )
        result = PhaseResult(status=PhaseStatus.SUCCESS, data=parsed)
        feedback = phase._build_granularity_feedback(result)

        # Should have markdown headers
        assert "### prd:req-42-1-1" in feedback
        # Should have bullet points
        assert "- **Files**:" in feedback
        assert "- **Suggested splits" in feedback
        assert "- **Action required**:" in feedback

    def test_execute_uses_template_a_feedback(self, ctx: PhaseContext) -> None:
        """On retry, execute() injects Template A feedback (not raw exception text)."""
        prompts: list[str] = []

        def _side_effect(ctx_: PhaseContext, prompt: str, tools: list) -> ClaudeResult:
            prompts.append(prompt)
            turtle_file = ctx_.work_dir / "p6-prd-export.ttl"
            summary_file = ctx_.work_dir / "p6-prd-summary.md"
            if len(prompts) == 1:
                turtle_file.write_text(COARSE_MULTI_DIR_TURTLE)
            else:
                turtle_file.write_text(FINE_TURTLE)
            summary_file.write_text("# Summary\n")
            return ClaudeResult(exit_code=0, output_text="done", cost_usd=0.1)

        phase = P6Phase()
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        with patch.object(phase, "run_claude", side_effect=_side_effect):
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert len(prompts) == 2
        # Second prompt should contain Template A feedback elements
        assert "Suggested splits by directory" in prompts[1]
        assert "Action required" in prompts[1]
        assert "Words-per-file" in prompts[1]


# ===================================================================
# TestRetryMechanism — _MockP6Phase-based (prd:req-64-4-4)
# ===================================================================


class TestRetryMechanism:
    """End-to-end retry tests using _MockP6Phase (controllable Turtle per attempt)."""

    def test_succeeds_without_retry(self, ctx: PhaseContext) -> None:
        """Fine Turtle on the first attempt — succeeds with no retry."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 2

        phase = _MockP6Phase(turtle_per_attempt=[FINE_TURTLE])
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.granularity_passed is True
        assert phase.call_count == 1
        assert result.metadata.get("attempts") == 1

    def test_retries_on_coarse_then_succeeds(self, ctx: PhaseContext) -> None:
        """First attempt coarse, second fine — succeeds after 1 retry."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        phase = _MockP6Phase(turtle_per_attempt=[SAMPLE_TURTLE_COARSE, FINE_TURTLE])
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.granularity_passed is True
        assert phase.call_count == 2
        assert result.metadata.get("attempts") == 2

    def test_fails_after_exhaustion(self, ctx: PhaseContext) -> None:
        """All attempts produce coarse Turtle — failure after retries exhausted."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        phase = _MockP6Phase(
            turtle_per_attempt=[SAMPLE_TURTLE_COARSE, SAMPLE_TURTLE_COARSE]
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.FAILURE
        assert "granularity gate failed" in (result.error or "")
        assert phase.call_count == 2

    def test_feedback_appended_to_prompt(self, ctx: PhaseContext) -> None:
        """On retry, granularity feedback is appended to the rebuilt prompt."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        phase = _MockP6Phase(turtle_per_attempt=[SAMPLE_TURTLE_COARSE, FINE_TURTLE])
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert len(phase.captured_prompts) == 2
        # First prompt has no feedback
        assert "Granularity Feedback" not in phase.captured_prompts[0]
        # Second prompt carries the feedback section
        assert "Granularity Feedback" in phase.captured_prompts[1]
        assert "too coarse" in phase.captured_prompts[1]
        assert "prd:req-42-1-1" in phase.captured_prompts[1]

    def test_multiple_retries_before_success(self, ctx: PhaseContext) -> None:
        """With max_retries=2, two coarse then fine — succeeds on third attempt."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 2

        phase = _MockP6Phase(
            turtle_per_attempt=[
                SAMPLE_TURTLE_COARSE,
                SAMPLE_TURTLE_COARSE,
                FINE_TURTLE,
            ]
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert phase.call_count == 3
        assert result.metadata.get("attempts") == 3
        # Feedback present in 2nd and 3rd prompts
        assert "Granularity Feedback" not in phase.captured_prompts[0]
        assert "Granularity Feedback" in phase.captured_prompts[1]
        assert "Granularity Feedback" in phase.captured_prompts[2]


# ===================================================================
# TestBuildGranularityFeedbackViaMock (prd:req-64-4-4)
# ===================================================================


class TestBuildGranularityFeedbackViaMock:
    """Verify feedback content via _MockP6Phase retry: flagged reqs, metrics, split plan."""

    def test_feedback_includes_flagged_requirements(self, ctx: PhaseContext) -> None:
        """Retry feedback names the specific coarse requirement IDs."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        phase = _MockP6Phase(
            turtle_per_attempt=[COARSE_MULTI_DIR_TURTLE, FINE_TURTLE]
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        retry_prompt = phase.captured_prompts[1]
        assert "prd:req-42-1-1" in retry_prompt

    def test_feedback_includes_metrics(self, ctx: PhaseContext) -> None:
        """Retry feedback includes file count, wpf, and word count metrics."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        phase = _MockP6Phase(
            turtle_per_attempt=[COARSE_MULTI_DIR_TURTLE, FINE_TURTLE]
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        retry_prompt = phase.captured_prompts[1]
        assert "**Files**:" in retry_prompt
        assert "**Words-per-file (wpf)**:" in retry_prompt
        assert "**Total description words**:" in retry_prompt

    def test_feedback_includes_split_plan(self, ctx: PhaseContext) -> None:
        """Retry feedback includes directory-based split suggestions."""
        ctx.config["claude_port"] = MockClaudeAdapter()
        ctx.config["max_granularity_retries"] = 1

        phase = _MockP6Phase(
            turtle_per_attempt=[COARSE_MULTI_DIR_TURTLE, FINE_TURTLE]
        )
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        retry_prompt = phase.captured_prompts[1]
        assert "Suggested splits by directory" in retry_prompt
        assert "Action required" in retry_prompt
        assert "prd:dependsOn" in retry_prompt


# ===================================================================
# TestCompactUri
# ===================================================================


class TestCompactUri:
    """_compact_uri() compacts full URIs into prefixed form."""

    def test_prd_namespace(self) -> None:
        assert _compact_uri("http://impl-ralph.io/prd#Requirement") == "prd:Requirement"

    def test_rdf_namespace(self) -> None:
        assert _compact_uri("http://www.w3.org/1999/02/22-rdf-syntax-ns#type") == "rdf:type"

    def test_rdfs_namespace(self) -> None:
        assert _compact_uri("http://www.w3.org/2000/01/rdf-schema#label") == "rdfs:label"

    def test_xsd_namespace(self) -> None:
        assert _compact_uri("http://www.w3.org/2001/XMLSchema#integer") == "xsd:integer"

    def test_trace_namespace(self) -> None:
        assert _compact_uri("http://impl-ralph.io/trace#foo") == "trace:foo"

    def test_already_compact(self) -> None:
        assert _compact_uri("prd:Requirement") == "prd:Requirement"

    def test_unknown_namespace(self) -> None:
        uri = "http://example.org/unknown#Thing"
        assert _compact_uri(uri) == uri


# ===================================================================
# _MockOntologyPort for hydration tests
# ===================================================================


class _MockOntologyPort(OntologyPort):
    """In-memory OntologyPort for testing _hydrate_abox."""

    def __init__(self, *, store_fail_count: int = 0) -> None:
        self.stored: list[tuple[str, str, str, str | None]] = []
        self.forgotten_contexts: list[str] = []
        self.forgotten_fact_ids: list[str] = []
        self._store_fail_count = store_fail_count
        self._store_calls = 0

    def forget_by_context(self, context: str) -> int:
        self.forgotten_contexts.append(context)
        return 0

    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        self._store_calls += 1
        if self._store_calls <= self._store_fail_count:
            raise RuntimeError("simulated store failure")
        self.stored.append((subject, predicate, object, context))
        return {"fact_id": f"f-{self._store_calls}"}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        self.forgotten_fact_ids.append(fact_id)
        return {"ok": True}

    def recall_facts(self, *, subject=None, predicate=None, context=None, limit=100):
        return {"result": []}

    def query_ideas(self, *, sparql=None, lifecycle=None, author=None, tag=None, search=None, limit=50):
        return {"ideas": []}

    def get_idea(self, idea_id):
        return {}

    def sparql_query(self, query, *, validate=True):
        return {"bindings": []}

    def update_idea(self, idea_id, *, title=None, description=None, content=None, lifecycle=None, tags=None):
        return {}

    def set_lifecycle(self, idea_id, new_state, *, reason=""):
        return {}


# ===================================================================
# TestHydrateAbox
# ===================================================================


class TestHydrateAbox:
    """P6Phase._hydrate_abox() programmatic A-box hydration."""

    def test_happy_path(self, ctx: PhaseContext) -> None:
        """All triples from Turtle are stored via store_fact."""
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        turtle_file.write_text(SAMPLE_TURTLE)
        mock_port = _MockOntologyPort()
        ctx.config["ontology_port"] = mock_port

        phase = P6Phase()
        count = phase._hydrate_abox(ctx, turtle_file)

        assert count > 0
        assert count == len(mock_port.stored)
        # All stored with correct context
        for _, _, _, stored_ctx in mock_port.stored:
            assert stored_ctx == "prd-idea-42"

    def test_clears_context_first(self, ctx: PhaseContext) -> None:
        """forget_by_context is called before storing new triples."""
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        turtle_file.write_text(SAMPLE_TURTLE)
        mock_port = _MockOntologyPort()
        ctx.config["ontology_port"] = mock_port

        phase = P6Phase()
        phase._hydrate_abox(ctx, turtle_file)

        assert mock_port.forgotten_contexts == ["prd-idea-42"]

    def test_missing_port_returns_zero(self, ctx: PhaseContext) -> None:
        """When ontology_port is missing from config, returns 0 gracefully."""
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        turtle_file.write_text(SAMPLE_TURTLE)
        # No ontology_port in config

        phase = P6Phase()
        count = phase._hydrate_abox(ctx, turtle_file)

        assert count == 0

    def test_error_threshold_raises(self, ctx: PhaseContext) -> None:
        """RuntimeError raised when >10% of triples fail."""
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        turtle_file.write_text(SAMPLE_TURTLE)
        # SAMPLE_TURTLE has ~15 triples; fail all of them to exceed 10%
        mock_port = _MockOntologyPort(store_fail_count=9999)
        ctx.config["ontology_port"] = mock_port

        phase = P6Phase()
        with pytest.raises(RuntimeError, match="error rate too high"):
            phase._hydrate_abox(ctx, turtle_file)

    def test_compacts_uris(self, ctx: PhaseContext) -> None:
        """Stored triples use compacted URI prefixes."""
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        turtle_file.write_text(SAMPLE_TURTLE)
        mock_port = _MockOntologyPort()
        ctx.config["ontology_port"] = mock_port

        phase = P6Phase()
        phase._hydrate_abox(ctx, turtle_file)

        subjects = {s for s, _, _, _ in mock_port.stored}
        predicates = {p for _, p, _, _ in mock_port.stored}
        # Should have compacted prd: and rdf: prefixes
        assert any(s.startswith("prd:") for s in subjects)
        assert any(p.startswith("prd:") or p.startswith("rdf:") for p in predicates)
