"""R1 Phase - Research Question Refinement.

Implements the first research sub-phase that refines the research questions
from the planning phase (P5) into precise, answerable questions with
methodology notes.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import R1Output


class R1Phase(Phase[R1Output]):
    """R1: Research Question Refinement phase.

    Constructs a prompt that asks Claude to take the research requests
    from P5 and refine them into precise, answerable research questions
    with methodology notes.  Writes results to
    ``r1-question-refinement.md`` inside the work directory.
    """

    phase_id: str = "r1"
    timeout_s: float = 300.0  # 5 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R1 question refinement prompt."""
        output_file = ctx.work_dir / "r1-question-refinement.md"
        research_date = date.today().isoformat()
        planning_dir = ctx.config.get("planning_dir", "")

        return (
            f"You are conducting Phase R1: Research Question Refinement for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Refine the research requests from planning into precise, answerable\n"
            "research questions with methodology notes.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: use mcp__idea-pool__read_idea with identifier {ctx.idea_id}\n"
            "\n"
            f"2. Read the planning research requests from: {planning_dir}\n"
            "   Look for p5-research-requests.md which contains the blocked research questions.\n"
            "   Also read p4-implementation-plan.md for context on what is blocked.\n"
            "\n"
            "   Use Glob to find files if names vary slightly.\n"
            "\n"
            "3. For each research request, refine it into:\n"
            "   - A precise, answerable question\n"
            "   - Why it matters (impact on implementation)\n"
            "   - Suggested methodology (literature review, experiment, prototype)\n"
            "   - Acceptance criteria (what counts as an answer)\n"
            "\n"
            f"4. Write the refined questions to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R1: Research Question Refinement\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            "\n"
            "   ## Refined Research Questions\n"
            "\n"
            "   ### RQ1: [Precise question]\n"
            "   **Origin**: [Which RR from P5]\n"
            "   **Impact**: [What implementation is blocked]\n"
            "   **Methodology**: Literature Review / Experiment / Prototype\n"
            "   **Acceptance Criteria**: [What counts as an answer]\n"
            "\n"
            "   ### RQ2: ...\n"
            "\n"
            "   ## Research Plan\n"
            "   [Recommended order of investigation and dependencies between RQs]\n"
            "\n"
            "Be precise - vague questions lead to vague answers."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during R1."""
        return [
            {"name": "mcp__idea-pool__read_idea"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
        ]

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Invoke Claude.

        The base framework will provide a concrete adapter; this default
        raises NotImplementedError to signal that a real adapter is needed.
        """
        raise NotImplementedError(
            "R1Phase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> R1Output:
        """Parse R1 output by reading ``r1-question-refinement.md`` from *work_dir*.

        Extracts the count of refined research questions.
        Raises :class:`ParseError` if the output file is missing.
        """
        output_file = ctx.work_dir / "r1-question-refinement.md"

        if not output_file.exists():
            raise ParseError(
                f"r1-question-refinement.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Count refined research questions (### RQ headings).
        questions_refined = len(re.findall(r"###\s+RQ\d+:", content))

        return R1Output(
            output_file=output_file,
            questions_refined=questions_refined,
        )

    def get_timeout_seconds(self) -> float:
        """Return the R1 timeout in seconds (5 minutes)."""
        return self.timeout_s
