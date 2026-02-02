"""R2 Phase - Source Identification.

Implements the second research sub-phase that identifies relevant sources
(documentation, APIs, repositories, papers) for each research question.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import R2Output


class R2Phase(Phase[R2Output]):
    """R2: Source Identification phase.

    Constructs a prompt that asks Claude to identify relevant sources
    for each research question from R1.  Writes results to
    ``r2-source-identification.md`` inside the work directory.
    """

    phase_id: str = "r2"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R2 source identification prompt."""
        output_file = ctx.work_dir / "r2-source-identification.md"
        r1_file = ctx.work_dir / "r1-question-refinement.md"
        research_date = date.today().isoformat()

        return (
            f"You are conducting Phase R2: Source Identification for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Identify relevant sources (documentation, APIs, repositories, papers)\n"
            "for each research question.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the refined research questions from: {r1_file}\n"
            "\n"
            "2. For each RQ, identify:\n"
            "   - Official documentation and API references\n"
            "   - Relevant code repositories or examples\n"
            "   - Academic papers or technical blog posts\n"
            "   - Existing implementations to study\n"
            "\n"
            "3. Search the codebase for existing patterns that might inform answers.\n"
            "   Use Glob and Grep to find relevant code.\n"
            "\n"
            f"4. Write the source map to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R2: Source Identification\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            "\n"
            "   ## Sources by Research Question\n"
            "\n"
            "   ### RQ1: [Question text]\n"
            "   | Source | Type | Relevance | URL/Path |\n"
            "   |--------|------|-----------|----------|\n"
            "   | ... | Doc/Code/Paper | High/Medium | ... |\n"
            "\n"
            "   ### RQ2: ...\n"
            "\n"
            "   ## Codebase Patterns Found\n"
            "   [Relevant existing patterns discovered in the codebase]\n"
            "\n"
            "   ## Source Gaps\n"
            "   [RQs where sources are scarce - may need experimentation]\n"
            "\n"
            "Prioritize primary sources over secondary ones."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during R2."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> R2Output:
        """Parse R2 output by reading ``r2-source-identification.md`` from *work_dir*.

        Extracts the count of sources identified.
        Raises :class:`ParseError` if the output file is missing.
        """
        output_file = ctx.work_dir / "r2-source-identification.md"

        if not output_file.exists():
            raise ParseError(
                f"r2-source-identification.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Count source rows across all tables.
        sources_identified = _count_source_rows(content)

        return R2Output(
            output_file=output_file,
            sources_identified=sources_identified,
        )

    def get_timeout_seconds(self) -> float:
        """Return the R2 timeout in seconds (20 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _count_source_rows(content: str) -> int:
    """Count markdown table data rows across all source tables."""
    rows = 0
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            # Check it's a data row (has content, not just a header)
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) >= 3 and any(c and c != "..." for c in cells):
                rows += 1
    # Subtract header rows (one per table section).
    rq_sections = len(re.findall(r"###\s+RQ\d+:", content))
    return max(0, rows - rq_sections)
