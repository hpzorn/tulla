"""Epistemology Idea mode — single-idea epistemic review.

Deep-dives into one idea's epistemic foundations: checks claims,
validates assumptions, and identifies reasoning gaps.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import IdeaOutput


class IdeaPhase(Phase[IdeaOutput]):
    """Epistemology idea mode: review epistemic foundations of a single idea."""

    phase_id: str = "ep-idea"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the single-idea epistemology prompt."""
        output_file = ctx.work_dir / "ep-idea-review.md"
        run_date = date.today().isoformat()

        return (
            f"You are conducting Epistemology — Idea Review for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Deep-dive into this idea's epistemic foundations: check claims, "
            "validate assumptions, and identify reasoning gaps.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            "2. Recall any stored facts: mcp__ontology-server__recall_facts\n"
            "3. For each claim or assumption in the idea:\n"
            "   - Is it supported by evidence?\n"
            "   - Is the reasoning valid (no logical fallacies)?\n"
            "   - Are there hidden assumptions?\n"
            "   - What would falsify this claim?\n"
            "\n"
            f"4. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # Epistemology: Idea Review\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "\n"
            "   ## Claims Inventory\n"
            "   | # | Claim | Evidence | Status |\n"
            "   |---|-------|----------|--------|\n"
            "\n"
            "   ## Assumption Audit\n"
            "   [Hidden or explicit assumptions and their validity]\n"
            "\n"
            "   ## Reasoning Gaps\n"
            "   [Logical gaps, fallacies, or unsupported leaps]\n"
            "\n"
            "   ## Falsifiability\n"
            "   [What evidence would disprove key claims]\n"
            "\n"
            "   ## Recommendations\n"
            "   [Actions to strengthen epistemic foundations]\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__idea-pool__read_idea"},
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
        raise NotImplementedError(
            "IdeaPhase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> IdeaOutput:
        output_file = ctx.work_dir / "ep-idea-review.md"

        if not output_file.exists():
            raise ParseError(
                f"ep-idea-review.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        claims_section = _extract_section(content, "Claims Inventory")
        claims_checked = _count_table_rows(claims_section)

        issues_found = 0
        for heading in ("Assumption Audit", "Reasoning Gaps"):
            section = _extract_section(content, heading)
            issues_found += _count_bullet_items(section)

        return IdeaOutput(
            output_file=output_file,
            claims_checked=claims_checked,
            issues_found=issues_found,
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
