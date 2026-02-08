"""Tests for RESEARCH_IDENTITY in research phase prompts."""

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


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.research"),
    )


ALL_PHASES = [
    pytest.param(R1Phase(), id="R1"),
    pytest.param(R2Phase(), id="R2"),
    pytest.param(R3Phase(), id="R3"),
    pytest.param(R4Phase(), id="R4"),
    pytest.param(R5Phase(), id="R5"),
    pytest.param(R6Phase(), id="R6"),
]


class TestResearchIdentity:
    """All research phases include the shared RESEARCH_IDENTITY preamble."""

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_prompt_includes_research_tulla(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Research-Tulla" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_prompt_includes_capabilities(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "**Capabilities**" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_prompt_includes_context_mention(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "A-box" in prompt

    @pytest.mark.parametrize("phase", ALL_PHASES)
    def test_identity_before_goal(self, phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        identity_pos = prompt.index("Research-Tulla")
        goal_pos = prompt.index("## Goal")
        assert identity_pos < goal_pos
