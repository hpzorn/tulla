"""Epistemology Pool mode — idea-pool health assessment.

Analyses the entire idea pool for epistemic hygiene: stale assumptions,
missing evidence, circular reasoning, and knowledge gaps.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import PoolOutput


class PoolPhase(Phase[PoolOutput]):
    """Epistemology pool mode: assess epistemic health of the idea pool."""

    phase_id: str = "ep-pool"
    timeout_s: float = 900.0  # 15 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the pool-level epistemology prompt."""
        output_file = ctx.work_dir / "ep-pool-health.md"
        run_date = date.today().isoformat()

        return (
            f"You are conducting Epistemology — Pool Health Assessment for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Assess the epistemic health of the idea pool: identify stale assumptions, "
            "missing evidence, circular reasoning, and knowledge gaps across ideas.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the target idea: mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            "2. Query related ideas: mcp__idea-pool__query_ideas\n"
            "3. For each idea in the neighbourhood, assess:\n"
            "   - Are assumptions still valid?\n"
            "   - Is there evidence backing key claims?\n"
            "   - Are there circular dependencies between ideas?\n"
            "   - What knowledge gaps exist?\n"
            "\n"
            f"4. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # Epistemology: Pool Health\n"
            f"   **Idea context**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "\n"
            "   ## Ideas Analysed\n"
            "   | ID | Title | Epistemic Status | Issues |\n"
            "   |----|-------|-----------------|--------|\n"
            "\n"
            "   ## Stale Assumptions\n"
            "   [Assumptions that may no longer hold]\n"
            "\n"
            "   ## Missing Evidence\n"
            "   [Claims lacking supporting evidence]\n"
            "\n"
            "   ## Circular Dependencies\n"
            "   [Ideas that circularly depend on each other's assumptions]\n"
            "\n"
            "   ## Knowledge Gaps\n"
            "   [Areas where the pool lacks coverage]\n"
            "\n"
            "   ## Recommendations\n"
            "   [Prioritised actions to improve pool health]\n"
            "\n"
            "Be thorough and evidence-based in your assessment."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during pool mode."""
        return [
            {"name": "mcp__idea-pool__read_idea"},
            {"name": "mcp__idea-pool__query_ideas"},
            {"name": "mcp__ontology-server__recall_facts"},
            {"name": "mcp__ontology-server__query_ontology"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Invoke Claude via injected adapter."""
        raise NotImplementedError(
            "PoolPhase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> PoolOutput:
        """Parse pool mode output from ``ep-pool-health.md``."""
        output_file = ctx.work_dir / "ep-pool-health.md"

        if not output_file.exists():
            raise ParseError(
                f"ep-pool-health.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Count ideas analysed from the table
        ideas_section = _extract_section(content, "Ideas Analysed")
        ideas_analysed = _count_table_rows(ideas_section)

        # Count issues across all issue sections
        issues_found = 0
        for heading in ("Stale Assumptions", "Missing Evidence",
                        "Circular Dependencies", "Knowledge Gaps"):
            section = _extract_section(content, heading)
            issues_found += _count_bullet_items(section)

        return PoolOutput(
            output_file=output_file,
            ideas_analysed=ideas_analysed,
            issues_found=issues_found,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown heading until the next heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
    """Count markdown table data rows (excludes header and separator)."""
    rows = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    return max(0, rows - 1) if rows > 0 else 0


def _count_bullet_items(section: str) -> int:
    """Count markdown bullet items (lines starting with - or *)."""
    count = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            count += 1
    return count
