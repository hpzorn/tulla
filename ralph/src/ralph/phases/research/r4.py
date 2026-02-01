"""R4 Phase - Literature Review.

Implements the fourth research sub-phase that conducts a structured
literature review per research question, synthesising findings from
sources into actionable technical guidance.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import R4Output


class R4Phase(Phase[R4Output]):
    """R4: Literature Review phase.

    Constructs a prompt that asks Claude to perform a structured
    literature review for each research question, writing findings to
    ``r4-literature-review.md`` inside the work directory.
    """

    phase_id: str = "r4"
    timeout_s: float = 600.0  # 10 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R4 literature review prompt."""
        output_file = ctx.work_dir / "r4-literature-review.md"
        r2_file = ctx.work_dir / "r2-source-identification.md"
        r3_file = ctx.work_dir / "r3-research-questions.md"
        research_date = date.today().isoformat()

        return (
            f"You are conducting Phase R4: Literature Review for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Conduct a structured literature review per research question,\n"
            "synthesising findings into actionable technical guidance.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the source map from: {r2_file}\n"
            f"2. Read the investigation results from: {r3_file}\n"
            "\n"
            "3. For each RQ, perform a deeper review:\n"
            "   - Read all identified sources thoroughly\n"
            "   - Compare approaches across sources\n"
            "   - Identify best practices and anti-patterns\n"
            "   - Note trade-offs and recommendations\n"
            "\n"
            f"4. Write the literature review to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R4: Literature Review\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            "\n"
            "   ## Reviews by Research Question\n"
            "\n"
            "   ### RQ1: [Question]\n"
            "   **Sources Reviewed**: [count]\n"
            "\n"
            "   #### Key Findings\n"
            "   1. [Finding with source citation]\n"
            "   2. ...\n"
            "\n"
            "   #### Approaches Compared\n"
            "   | Approach | Pros | Cons | Source |\n"
            "   |----------|------|------|--------|\n"
            "   | ... | ... | ... | ... |\n"
            "\n"
            "   #### Recommendation\n"
            "   [Recommended approach with justification]\n"
            "\n"
            "   ### RQ2: ...\n"
            "\n"
            "   ## Cross-Cutting Themes\n"
            "   [Patterns that emerged across multiple RQs]\n"
            "\n"
            "   ## Open Items for Experimentation\n"
            "   [Questions that cannot be answered by review alone]\n"
            "\n"
            "Synthesise, don't just summarise. Focus on actionable guidance."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during R4."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Invoke Claude.

        The base framework will provide a concrete adapter; this default
        raises NotImplementedError to signal that a real adapter is needed.
        """
        raise NotImplementedError(
            "R4Phase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> R4Output:
        """Parse R4 output by reading ``r4-literature-review.md`` from *work_dir*.

        Extracts the count of papers reviewed and RQs addressed.
        Raises :class:`ParseError` if the output file is missing.
        """
        output_file = ctx.work_dir / "r4-literature-review.md"

        if not output_file.exists():
            raise ParseError(
                f"r4-literature-review.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Count RQs addressed (### RQ headings).
        rqs_addressed = len(re.findall(r"###\s+RQ\d+:", content))

        # Count sources reviewed from "Sources Reviewed" lines.
        papers_reviewed = 0
        for match in re.findall(r"\*\*Sources Reviewed\*\*:\s*(\d+)", content):
            papers_reviewed += int(match)
        # Fallback: count approach table rows if no explicit count.
        if papers_reviewed == 0:
            papers_reviewed = _count_table_rows(content)

        return R4Output(
            output_file=output_file,
            papers_reviewed=papers_reviewed,
            rqs_addressed=rqs_addressed,
        )

    def get_timeout_seconds(self) -> float:
        """Return the R4 timeout in seconds (10 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _count_table_rows(content: str) -> int:
    """Count markdown table data rows across all tables."""
    rows = 0
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    # Subtract header rows (rough estimate: one per table).
    table_count = len(re.findall(r"\n\|[\s-]+\|", content))
    return max(0, rows - table_count)
