"""Tests for upstream facts injection in research phases R1-R6."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tulla.core.phase import PhaseContext
from tulla.phases.research.r1 import R1Phase
from tulla.phases.research.r2 import R2Phase
from tulla.phases.research.r3 import R3Phase
from tulla.phases.research.r4 import R4Phase
from tulla.phases.research.r5 import R5Phase
from tulla.phases.research.r6 import R6Phase


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_TRIPLES = [
    {
        "subject": "http://impl-ralph.io/phase#idea-42-r1",
        "predicate": "http://impl-ralph.io/phase#preserves-questions_refined",
        "object": "5",
    },
    {
        "subject": "http://impl-ralph.io/phase#idea-42-r1",
        "predicate": "http://impl-ralph.io/phase#preserves-output_file",
        "object": "/tmp/work/r1-question-refinement.md",
    },
]


def _ctx_with_facts(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={"upstream_facts": SAMPLE_TRIPLES},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.research"),
    )


def _ctx_no_facts(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.research"),
    )


# ---------------------------------------------------------------------------
# Parametrised tests across all six phases
# ---------------------------------------------------------------------------

PHASES = [
    pytest.param(R1Phase(), id="R1"),
    pytest.param(R2Phase(), id="R2"),
    pytest.param(R3Phase(), id="R3"),
    pytest.param(R4Phase(), id="R4"),
    pytest.param(R5Phase(), id="R5"),
    pytest.param(R6Phase(), id="R6"),
]


class TestUpstreamFactsIncluded:
    """Upstream facts from A-box are rendered in the prompt."""

    @pytest.mark.parametrize("phase", PHASES)
    def test_upstream_facts_section_present(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_facts(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "## Upstream Facts" in prompt

    @pytest.mark.parametrize("phase", PHASES)
    def test_upstream_facts_contain_field_names(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_facts(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "questions_refined" in prompt

    @pytest.mark.parametrize("phase", PHASES)
    def test_upstream_facts_before_goal(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_with_facts(tmp_path)
        prompt = phase.build_prompt(ctx)
        facts_pos = prompt.index("## Upstream Facts")
        goal_pos = prompt.index("## Goal")
        assert facts_pos < goal_pos


class TestUpstreamFactsOmitted:
    """No upstream facts section when none are provided."""

    @pytest.mark.parametrize("phase", PHASES)
    def test_no_upstream_facts_section(self, phase, tmp_path: Path) -> None:
        ctx = _ctx_no_facts(tmp_path)
        prompt = phase.build_prompt(ctx)
        assert "## Upstream Facts" not in prompt
