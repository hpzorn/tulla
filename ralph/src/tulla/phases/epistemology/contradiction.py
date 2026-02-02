"""Epistemology Contradiction mode — contradiction detection.

Scans for contradictions between an idea and its neighbours in the pool,
between claims within the idea, and between the idea and ontology facts.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import ContradictionOutput


class ContradictionPhase(Phase[ContradictionOutput]):
    """Epistemology contradiction mode: detect contradictions."""

    phase_id: str = "ep-contradiction"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / "ep-contradictions.md"
        run_date = date.today().isoformat()

        return (
            f"You are conducting Epistemology — Contradiction Detection for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Scan for contradictions: between claims within this idea, between this "
            "idea and its neighbours in the pool, and between the idea and ontology facts.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Query neighbours: mcp__ontology-server__query_ideas\n"
            "3. Recall known facts: mcp__ontology-server__recall_facts\n"
            "4. For each pair of claims or facts:\n"
            "   - Do they logically contradict each other?\n"
            "   - Are there implicit contradictions (different assumptions)?\n"
            "   - Can the contradiction be resolved, or is it fundamental?\n"
            "\n"
            f"5. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # Epistemology: Contradictions\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "\n"
            "   ## Pairs Checked\n"
            "   | # | Claim A | Claim B | Source | Contradiction? |\n"
            "   |---|---------|---------|--------|---------------|\n"
            "\n"
            "   ## Internal Contradictions\n"
            "   [Contradictions within the idea itself]\n"
            "\n"
            "   ## External Contradictions\n"
            "   [Contradictions with other ideas or known facts]\n"
            "\n"
            "   ## Resolution Paths\n"
            "   [How each contradiction might be resolved]\n"
            "\n"
            "   ## Recommendations\n"
            "   [Priority actions to address contradictions]\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__query_ideas"},
            {"name": "mcp__ontology-server__recall_facts"},
            {"name": "mcp__ontology-server__query_ontology"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> ContradictionOutput:
        output_file = ctx.work_dir / "ep-contradictions.md"

        if not output_file.exists():
            raise ParseError(
                f"ep-contradictions.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        pairs_section = _extract_section(content, "Pairs Checked")
        pairs_checked = _count_table_rows(pairs_section)

        contradictions_found = 0
        for heading in ("Internal Contradictions", "External Contradictions"):
            section = _extract_section(content, heading)
            contradictions_found += _count_bullet_items(section)

        return ContradictionOutput(
            output_file=output_file,
            pairs_checked=pairs_checked,
            contradictions_found=contradictions_found,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
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
    count = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            count += 1
    return count
