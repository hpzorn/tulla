"""R6 Phase - Research Synthesis.

Implements the sixth and final research sub-phase that synthesises all
research findings into a coherent conclusion with recommendations for
the implementation phase.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import R6Output


class R6Phase(Phase[R6Output]):
    """R6: Research Synthesis phase.

    Constructs a prompt that asks Claude to synthesise all research
    phases (R1-R5) into a final report with conclusions and
    recommendations.  Writes results to ``r6-research-synthesis.md``
    inside the work directory.
    """

    phase_id: str = "r6"
    timeout_s: float = 600.0  # 10 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R6 research synthesis prompt."""
        output_file = ctx.work_dir / "r6-research-synthesis.md"
        r1_file = ctx.work_dir / "r1-question-refinement.md"
        r3_file = ctx.work_dir / "r3-research-questions.md"
        r4_file = ctx.work_dir / "r4-literature-review.md"
        r5_file = ctx.work_dir / "r5-research-findings.md"
        research_date = date.today().isoformat()

        return (
            f"You are conducting Phase R6: Research Synthesis for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Synthesise all research findings into a coherent conclusion with\n"
            "actionable recommendations for the implementation phase.\n"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Read all prior research outputs:\n"
            f"   - {r1_file} (refined questions)\n"
            f"   - {r3_file} (investigation results)\n"
            f"   - {r4_file} (literature review)\n"
            f"   - {r5_file} (experiment findings)\n"
            "\n"
            "2. For each research question, synthesise:\n"
            "   - The final answer (from literature + experiments)\n"
            "   - Confidence level and evidence quality\n"
            "   - Concrete implications for implementation\n"
            "\n"
            "3. Produce actionable recommendations:\n"
            "   - What approaches to use (and why)\n"
            "   - What to avoid (and why)\n"
            "   - Remaining risks and mitigations\n"
            "\n"
            f"4. Write the synthesis to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R6: Research Synthesis\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            "\n"
            "   ## Executive Summary\n"
            "   [2-3 sentence overview of key findings and recommendation]\n"
            "\n"
            "   ## Findings by Research Question\n"
            "\n"
            "   ### RQ1: [Question]\n"
            "   **Answer**: [Final synthesised answer]\n"
            "   **Confidence**: High / Medium / Low\n"
            "   **Evidence**: Literature: [count] sources, Experiments: [count]\n"
            "   **Implication**: [What this means for implementation]\n"
            "\n"
            "   ### RQ2: ...\n"
            "\n"
            "   ## Recommendations\n"
            "   1. [Recommendation with justification]\n"
            "   2. ...\n"
            "\n"
            "   ## Risks & Mitigations\n"
            "   | Risk | Likelihood | Impact | Mitigation |\n"
            "   |------|-----------|--------|------------|\n"
            "   | ... | ... | ... | ... |\n"
            "\n"
            "   ## Conclusion\n"
            "   [Overall recommendation: proceed / revise plan / more research needed]\n"
            "\n"
            "This is the final research deliverable. Be clear and actionable."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during R6."""
        return [
            {"name": "Read"},
            {"name": "Write"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> R6Output:
        """Parse R6 output by reading ``r6-research-synthesis.md`` from *work_dir*.

        Extracts findings count and the overall recommendation.
        Raises :class:`ParseError` if the output file is missing.
        """
        output_file = ctx.work_dir / "r6-research-synthesis.md"

        if not output_file.exists():
            raise ParseError(
                f"r6-research-synthesis.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Count findings (### RQ headings in findings section).
        findings_count = len(re.findall(r"###\s+RQ\d+:", content))

        # Extract recommendation from Conclusion section.
        recommendation = _extract_recommendation(content)

        return R6Output(
            output_file=output_file,
            findings_count=findings_count,
            recommendation=recommendation,
        )

    def get_timeout_seconds(self) -> float:
        """Return the R6 timeout in seconds (5 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_recommendation(content: str) -> str:
    """Extract the recommendation from the Conclusion section.

    Falls back to 'proceed' if no explicit recommendation is found.
    """
    conclusion_match = re.search(
        r"##\s+Conclusion\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL
    )
    if conclusion_match:
        conclusion = conclusion_match.group(1).strip()
        lower = conclusion.lower()
        if "more research" in lower:
            return "more research needed"
        if "revise" in lower:
            return "revise plan"
        if "proceed" in lower:
            return "proceed"
        # Return first line as summary.
        first_line = conclusion.splitlines()[0].strip() if conclusion else "proceed"
        return first_line
    return "proceed"
