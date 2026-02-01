"""P2 Phase – Codebase Analysis.

Implements the second planning sub-phase that deeply analyses internal
implementations to understand how existing tools work, enabling accurate
planning.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import P2Output


class P2Phase(Phase[P2Output]):
    """P2: Codebase Analysis phase.

    Constructs a prompt that asks Claude to deeply analyse existing skills,
    MCP servers, and integration patterns, writing findings to
    ``p2-codebase-analysis.md`` inside the work directory.  Reads
    ``p1-discovery-context.md`` from the previous phase.
    """

    phase_id: str = "p2"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P2 codebase analysis prompt, ported from planning-ralph.sh."""
        output_file = ctx.work_dir / "p2-codebase-analysis.md"
        p1_file = ctx.work_dir / "p1-discovery-context.md"
        planning_date = date.today().isoformat()

        skills_dir = ctx.config.get("skills_dir", "~/.claude/skills")
        visual_tools_dir = ctx.config.get("visual_tools_dir", "~/visual-tools")
        mcp_servers_dir = ctx.config.get("mcp_servers_dir", "~/.claude/mcp-servers")

        return (
            f"You are conducting Phase P2: Codebase Analysis for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Deeply analyze internal implementations to understand HOW existing tools work,\n"
            "not just WHAT they do. This enables accurate planning.\n"
            "\n"
            "## Context\n"
            f"Read the discovery context: {p1_file}\n"
            "\n"
            "## Internal Paths to Analyze\n"
            "\n"
            f"1. **Skills Directory**: {skills_dir}\n"
            "   - Look for presentation skills (beamer-inovex, typst-presentation)\n"
            "   - Understand skill structure, how they work\n"
            "\n"
            f"2. **Visual Tools**: {visual_tools_dir}\n"
            "   - MCP servers for rendering (kpi-cards, process-flow, compose-scene)\n"
            "   - nano-banana for image generation\n"
            "\n"
            f"3. **MCP Servers Config**: {mcp_servers_dir}\n"
            "   - How are MCP tools configured and called?\n"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Use Glob to find relevant files:\n"
            f"   - `{skills_dir}/**/*.md` for skill definitions\n"
            f"   - `{visual_tools_dir}/**/server.py` for MCP servers\n"
            f"   - `{visual_tools_dir}/**/pyproject.toml` for dependencies\n"
            "\n"
            "2. Read key implementation files to understand:\n"
            "   - How are skills structured? What's the interface?\n"
            "   - How do MCP tools receive and return data?\n"
            "   - What patterns are used for composition?\n"
            "   - What are the actual function signatures?\n"
            "\n"
            f"3. Write analysis to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # P2: Codebase Analysis\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {planning_date}\n"
            "\n"
            "   ## Skill Architecture\n"
            "\n"
            "   ### Skill Structure\n"
            "   [How skills are defined and invoked]\n"
            "\n"
            "   ### Key Skills for This Project\n"
            "   [Details per skill]\n"
            "\n"
            "   ## MCP Server Architecture\n"
            "\n"
            "   ### Key Servers for This Project\n"
            "   [Details per server]\n"
            "\n"
            "   ## Integration Patterns\n"
            "   [How tools are currently composed together]\n"
            "\n"
            "   ## Reusable Components\n"
            "\n"
            "   | Component | Location | Can Reuse For |\n"
            "   |-----------|----------|---------------|\n"
            "   | ... | ... | ... |\n"
            "\n"
            "   ## Extension Points\n"
            "   [Where can we add new functionality without rewriting?]\n"
            "\n"
            "   ## Code Quality Observations\n"
            "   [Patterns to follow, anti-patterns to avoid]\n"
            "\n"
            "Focus on UNDERSTANDING the code deeply enough to write a precise implementation plan."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P2."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P2Output:
        """Parse P2 output by reading ``p2-codebase-analysis.md`` from *work_dir*.

        Extracts requirement count and P0 count from the reusable components
        table.  Raises :class:`ParseError` if the analysis file is missing.
        """
        requirements_file = ctx.work_dir / "p2-codebase-analysis.md"

        if not requirements_file.exists():
            raise ParseError(
                f"p2-codebase-analysis.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = requirements_file.read_text(encoding="utf-8")

        # Count reusable components from the table.
        reusable_section = _extract_section(content, "Reusable Components")
        requirement_count = _count_table_rows(reusable_section)

        # Count extension points (## headings under Extension Points or bullet items).
        extension_section = _extract_section(content, "Extension Points")
        p0_count = len(re.findall(r"^\s*[-*]\s+", extension_section, re.MULTILINE))

        return P2Output(
            requirements_file=requirements_file,
            requirement_count=requirement_count,
            p0_count=p0_count,
        )

    def get_timeout_seconds(self) -> float:
        """Return the P2 timeout in seconds (20 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown ``## heading`` until the next heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
    """Count markdown table data rows (excludes header and separator rows)."""
    rows = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip header separator rows like |---|---|---|
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        # Count lines that look like table rows: | content | ... |
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    # Subtract 1 for the header row if we counted any rows
    return max(0, rows - 1) if rows > 0 else 0
