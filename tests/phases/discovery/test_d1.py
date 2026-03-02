"""Tests for tulla.phases.discovery.d1 – D1Phase."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import ParseError, PhaseContext, PhaseStatus
from tulla.phases.discovery.d1 import D1Phase

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
        logger=logging.getLogger("test.d1"),
    )


@pytest.fixture()
def phase() -> D1Phase:
    """A plain D1Phase instance."""
    return D1Phase()


SAMPLE_INVENTORY = """\
# D1: Inventory
**Idea**: idea-42
**Date**: 2026-02-01
**Time-box**: 15 minutes

## The Idea
A sample idea for testing.

## Related Ideas in Pool
| ID | Title | Lifecycle | Relationship |
|----|-------|-----------|--------------|
| idea-10 | Related A | active | builds-on |
| idea-11 | Related B | draft | complements |

## Existing Systems & Tools
| Component | Location | Relevance |
|-----------|----------|-----------|
| mcp__ontology-server__get_idea | MCP | high |
| mcp__ontology-server__query | MCP | medium |
| Glob | built-in | high |

## Prior Work
Some prior work was done.

## Current Gaps
Missing integration tests.

## Ecosystem Context
Fits into the Tulla pipeline.
"""


# ===================================================================
# build_prompt includes idea_id
# ===================================================================


class TestBuildPrompt:
    """D1Phase.build_prompt() tests."""

    def test_includes_idea_id(self, phase: D1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert ctx.idea_id in prompt

    def test_includes_inventory_output_path(self, phase: D1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "d1-inventory.md" in prompt

    def test_includes_phase_heading(self, phase: D1Phase, ctx: PhaseContext) -> None:
        prompt = phase.build_prompt(ctx)
        assert "Phase D1: Inventory" in prompt


# ===================================================================
# get_tools includes idea_pool
# ===================================================================


class TestGetTools:
    """D1Phase.get_tools() tests."""

    def test_includes_idea_pool(self, phase: D1Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        tool_names = [t["name"] for t in tools]
        assert any("ontology-server" in name for name in tool_names)

    def test_includes_read_write_glob_grep(self, phase: D1Phase, ctx: PhaseContext) -> None:
        tools = phase.get_tools(ctx)
        tool_names = {t["name"] for t in tools}
        assert "Read" in tool_names
        assert "Write" in tool_names
        assert "Glob" in tool_names
        assert "Grep" in tool_names


# ===================================================================
# parse_output raises on missing file
# ===================================================================


class TestParseOutputMissing:
    """D1Phase.parse_output() when d1-inventory.md is absent."""

    def test_raises_parse_error_on_missing_file(self, phase: D1Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError, match="d1-inventory.md not found"):
            phase.parse_output(ctx, raw="anything")

    def test_parse_error_includes_context(self, phase: D1Phase, ctx: PhaseContext) -> None:
        with pytest.raises(ParseError) as exc_info:
            phase.parse_output(ctx, raw="raw-data")
        assert "work_dir" in exc_info.value.context


# ===================================================================
# parse_output succeeds with file
# ===================================================================


class TestParseOutputSuccess:
    """D1Phase.parse_output() when d1-inventory.md is present."""

    def test_returns_d1_output(self, phase: D1Phase, ctx: PhaseContext) -> None:
        inventory_file = ctx.work_dir / "d1-inventory.md"
        inventory_file.write_text(SAMPLE_INVENTORY, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")

        assert result.inventory_file == inventory_file
        import json

        capabilities = json.loads(result.key_capabilities)
        assert len(capabilities) == 3
        assert result.ecosystem_context == "Fits into the Tulla pipeline."
        assert result.reuse_opportunities == "Some prior work was done."

    def test_empty_capabilities_when_table_empty(self, phase: D1Phase, ctx: PhaseContext) -> None:
        minimal = "# D1: Inventory\n## Existing Systems & Tools\nNo tools found.\n## Prior Work\n"
        inventory_file = ctx.work_dir / "d1-inventory.md"
        inventory_file.write_text(minimal, encoding="utf-8")

        result = phase.parse_output(ctx, raw="raw")
        import json

        assert json.loads(result.key_capabilities) == []


# ===================================================================
# execute SUCCESS with mock
# ===================================================================


class _MockD1Phase(D1Phase):
    """D1Phase with a mocked run_claude that writes the inventory file."""

    def __init__(self, inventory_content: str) -> None:
        super().__init__()
        self._inventory_content = inventory_content

    def run_claude(self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]) -> Any:
        output_file = ctx.work_dir / "d1-inventory.md"
        output_file.write_text(self._inventory_content, encoding="utf-8")
        return "mock-raw-output"


class TestExecuteWithMock:
    """D1Phase.execute() end-to-end with a mocked Claude adapter."""

    def test_execute_returns_success(self, ctx: PhaseContext) -> None:
        phase = _MockD1Phase(SAMPLE_INVENTORY)
        result = phase.execute(ctx)

        assert result.status is PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.inventory_file == ctx.work_dir / "d1-inventory.md"
        import json

        assert len(json.loads(result.data.key_capabilities)) == 3
        assert result.data.ecosystem_context == "Fits into the Tulla pipeline."
        assert result.error is None
        assert result.duration_s > 0
