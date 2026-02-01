"""Epistemology Problem mode — problem-framing review.

Examines whether the problem an idea addresses is correctly framed,
well-scoped, and not a symptom of a deeper issue.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import ProblemOutput


class ProblemPhase(Phase[ProblemOutput]):
    """Epistemology problem mode: review problem framing and scoping."""

    phase_id: str = "ep-problem"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / "ep-problem-framing.md"
        run_date = date.today().isoformat()

        return (
            f"You are conducting Epistemology — Problem Framing for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Examine whether the problem this idea addresses is correctly framed, "
            "well-scoped, and not merely a symptom of a deeper issue.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            "2. Recall related context: mcp__ontology-server__recall_facts\n"
            "3. Assess the problem framing:\n"
            "   - Is the problem statement clear and falsifiable?\n"
            "   - Is the scope appropriate (not too broad, not too narrow)?\n"
            "   - Could this be a symptom of a deeper root cause?\n"
            "   - Are there alternative framings worth considering?\n"
            "\n"
            f"4. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # Epistemology: Problem Framing\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "\n"
            "   ## Problems Reviewed\n"
            "   | # | Problem Statement | Clarity | Scope | Root-Cause Risk |\n"
            "   |---|------------------|---------|-------|----------------|\n"
            "\n"
            "   ## Root-Cause Analysis\n"
            "   [Whether stated problems are symptoms of deeper issues]\n"
            "\n"
            "   ## Alternative Framings\n"
            "   [Other ways to frame the problem that may be more productive]\n"
            "\n"
            "   ## Recommendations\n"
            "   [Suggested reframings or scope adjustments]\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__idea-pool__read_idea"},
            {"name": "mcp__idea-pool__query_ideas"},
            {"name": "mcp__ontology-server__recall_facts"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        raise NotImplementedError(
            "ProblemPhase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> ProblemOutput:
        output_file = ctx.work_dir / "ep-problem-framing.md"

        if not output_file.exists():
            raise ParseError(
                f"ep-problem-framing.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        problems_section = _extract_section(content, "Problems Reviewed")
        problems_reviewed = _count_table_rows(problems_section)

        reframings_suggested = 0
        for heading in ("Alternative Framings", "Recommendations"):
            section = _extract_section(content, heading)
            reframings_suggested += _count_bullet_items(section)

        return ProblemOutput(
            output_file=output_file,
            problems_reviewed=problems_reviewed,
            reframings_suggested=reframings_suggested,
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
