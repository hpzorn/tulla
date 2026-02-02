"""D2 Phase – Persona Discovery.

Implements the second discovery sub-phase that identifies user personas,
their jobs-to-be-done, pain points, and desired outcomes for a given idea.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import D2Output


class D2Phase(Phase[D2Output]):
    """D2: Persona Discovery phase.

    Constructs a prompt that asks Claude to identify user personas and
    their jobs-to-be-done, writing findings to ``d2-personas.md`` inside
    the work directory.  Reads ``d1-inventory.md`` from the previous phase.
    """

    phase_id: str = "d2"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the D2 persona discovery prompt, ported from discovery-ralph.sh."""
        output_file = ctx.work_dir / "d2-personas.md"
        d1_file = ctx.work_dir / "d1-inventory.md"
        discovery_date = date.today().isoformat()

        return (
            f"You are conducting Phase D2: Persona Discovery for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Identify who would use this, their jobs-to-be-done, and their pain points.\n"
            "\n"
            "## Context\n"
            f"- Read the idea: mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            f"- Read inventory: {d1_file}\n"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Identify 2-4 distinct user personas who would benefit from this idea\n"
            "2. For each persona, map their:\n"
            "   - Jobs-to-be-done (JTBD framework)\n"
            "   - Current pain points\n"
            "   - Desired outcomes\n"
            "   - Context of use\n"
            "\n"
            f"3. Write to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # D2: Persona Discovery\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {discovery_date}\n"
            "   **Time-box**: 20 minutes\n"
            "\n"
            "   ## Persona Overview\n"
            "   | Persona | Role | Primary JTBD | Frequency |\n"
            "   |---------|------|--------------|----------|\n"
            "   | ... | ... | ... | Daily/Weekly/Occasional |\n"
            "\n"
            "   ## Detailed Personas\n"
            "\n"
            '   ### Persona 1: [Name - e.g., "Data-Driven Developer"]\n'
            "\n"
            "   **Who they are**:\n"
            "   [Brief description - role, experience level, context]\n"
            "\n"
            "   **Jobs-to-be-done**:\n"
            "   - **Functional**: [What task are they trying to accomplish?]\n"
            "   - **Emotional**: [How do they want to feel?]\n"
            "   - **Social**: [How do they want to be perceived?]\n"
            "\n"
            "   **Current workflow**:\n"
            "   [How do they accomplish this today?]\n"
            "\n"
            "   **Pain points**:\n"
            "   1. [Pain point 1]\n"
            "   2. [Pain point 2]\n"
            "   3. [Pain point 3]\n"
            "\n"
            "   **Desired outcomes**:\n"
            "   - [Outcome 1]\n"
            "   - [Outcome 2]\n"
            "\n"
            "   **Success metrics** (how they'd measure value):\n"
            "   - [Metric 1]\n"
            "   - [Metric 2]\n"
            "\n"
            "   ## Cross-Persona Insights\n"
            "\n"
            "   **Common pain points**:\n"
            "   - [Shared pain]\n"
            "\n"
            "   **Conflicting needs**:\n"
            "   - [Where personas disagree]\n"
            "\n"
            "   **Priority ranking**:\n"
            "   1. [Primary persona] - [why they're primary]\n"
            "   2. [Secondary persona] - [why]\n"
            "\n"
            "   ## JTBD Summary\n"
            "   When I am [situation], I want to [motivation], so I can [outcome].\n"
            "\n"
            "Think like a product manager. Focus on real user needs, not features."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during D2."""
        return [
            {"name": "mcp__idea-pool__read_idea"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "WebSearch"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D2Output:
        """Parse D2 output by reading ``d2-personas.md`` from *work_dir*.

        Extracts persona count from the Persona Overview table.
        Raises :class:`ParseError` if the personas file is missing.
        """
        personas_file = ctx.work_dir / "d2-personas.md"

        if not personas_file.exists():
            raise ParseError(
                f"d2-personas.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = personas_file.read_text(encoding="utf-8")

        # Count personas from "Persona Overview" table rows.
        overview_section = _extract_section(content, "Persona Overview")
        persona_count = _count_table_rows(overview_section)

        # Fallback: count ### Persona N headings if table is empty.
        if persona_count == 0:
            persona_count = len(re.findall(r"###\s+Persona\s+\d+", content))

        return D2Output(
            personas_file=personas_file,
            persona_count=persona_count,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D2 timeout in seconds (20 minutes)."""
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
