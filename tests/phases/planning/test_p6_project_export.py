"""Tests for P6 project export instructions (req-69-5-4)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import PhaseContext
from tulla.phases.planning.p6 import P6Phase


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Standard PhaseContext pointing at a temporary work directory."""
    # P6 build_prompt reads p4-implementation-plan.md — create a stub
    (tmp_path / "p4-implementation-plan.md").write_text("# stub")
    return PhaseContext(
        idea_id="idea-99",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.p6"),
    )


@pytest.fixture()
def phase() -> P6Phase:
    return P6Phase()


SAMPLE_DECISIONS = [
    {
        "id": "arch:adr-project-99-1",
        "title": "Use Python for all new code",
        "decision": "All new modules must be Python 3.11+",
        "quality_attributes": "Maintainability, Testability",
    },
    {
        "id": "arch:adr-project-99-2",
        "title": "Ontology-driven traceability",
        "decision": "Every requirement links to an ADR",
        "quality_attributes": "FunctionalCorrectness",
    },
]


class TestBuildProjectExportInstructions:
    """Tests for _build_project_export_instructions method."""

    def test_with_project_decisions_in_prompt(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """Prompt includes project export section when decisions are present."""
        ctx.config["project_decisions"] = SAMPLE_DECISIONS

        prompt = phase.build_prompt(ctx)

        assert "## Project ADR Linkage" in prompt
        assert "prd:projectADR" in prompt
        assert "arch:adr-project-99-1" in prompt
        assert "Use Python for all new code" in prompt
        assert "arch:adr-project-99-2" in prompt
        assert "Ontology-driven traceability" in prompt
        # Verify it says project instance already exists
        assert "already exists in the A-box" in prompt
        # Verify it says only linkage triples needed
        assert "linkage triples" in prompt

    def test_empty_decisions_no_section(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """Prompt omits project section entirely when decisions are empty."""
        ctx.config["project_decisions"] = []

        prompt = phase.build_prompt(ctx)

        assert "## Project ADR Linkage" not in prompt
        assert "prd:projectADR" not in prompt

    def test_no_decisions_key_no_section(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """Prompt omits project section when key is absent from config."""
        # config has no "project_decisions" key at all
        prompt = phase.build_prompt(ctx)

        assert "## Project ADR Linkage" not in prompt
        assert "prd:projectADR" not in prompt

    def test_template_uses_project_id(
        self, phase: P6Phase, ctx: PhaseContext
    ) -> None:
        """The Turtle example in the instructions uses the correct project ID."""
        ctx.config["project_decisions"] = SAMPLE_DECISIONS

        prompt = phase.build_prompt(ctx)

        # The template example should use idea-99
        assert "prd:req-idea-99-1-1 prd:projectADR" in prompt

    def test_method_directly_returns_empty_for_no_decisions(
        self, phase: P6Phase
    ) -> None:
        """_build_project_export_instructions returns '' for empty list."""
        result = phase._build_project_export_instructions([], "idea-99")
        assert result == ""
