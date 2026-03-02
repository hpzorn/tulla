"""R3 Phase - Research Questions.

Implements the third research sub-phase that conducts the actual research
investigation, reading sources and answering each research question.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts
from tulla.phases.research import RESEARCH_IDENTITY, build_northstar_section

from .models import R3Output


class R3Phase(Phase[R3Output]):
    """R3: Research Questions phase.

    Constructs a prompt that asks Claude to investigate each research
    question using the identified sources, writing answers and evidence
    to ``r3-research-questions.md`` inside the work directory.
    """

    phase_id: str = "r3"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R3 research questions prompt."""
        output_file = ctx.work_dir / "r3-research-questions.md"
        r1_file = ctx.work_dir / "r1-question-refinement.md"
        r2_file = ctx.work_dir / "r2-source-identification.md"
        research_date = date.today().isoformat()

        raw_facts = ctx.config.get("upstream_facts", [])
        grouped = group_upstream_facts(raw_facts)
        northstar_section = build_northstar_section(grouped)
        upstream_section = ""
        if grouped:
            upstream_section = (
                "## Upstream Facts\n"
                f"{json.dumps(grouped, indent=2)}\n"
                "\n"
            )

        return (
            RESEARCH_IDENTITY
            + f"## Phase R3: Research Questions\n"
            f"**Idea**: {ctx.idea_id}\n"
            "\n"
            f"{northstar_section}"
            f"{upstream_section}"
            "## Goal\n"
            "Investigate each research question using identified sources and\n"
            "produce evidence-backed answers.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the refined questions from: {r1_file}\n"
            f"2. Read the source map from: {r2_file}\n"
            "\n"
            "3. For each research question:\n"
            "   - Read the identified sources (documentation, code, etc.)\n"
            "   - Gather evidence that answers the question\n"
            "   - Note any contradictions or caveats\n"
            "   - Assess confidence level in the answer\n"
            "\n"
            f"4. Write the investigation results to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R3: Research Questions\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            "\n"
            "   ## Investigation Results\n"
            "\n"
            "   ### RQ1: [Question]\n"
            "   **Status**: Answered / Partially Answered / Unanswered\n"
            "   **Confidence**: High / Medium / Low\n"
            "   **Answer**: [Concise answer]\n"
            "   **Evidence**:\n"
            "   - [Source 1]: [Key finding]\n"
            "   - [Source 2]: [Key finding]\n"
            "   **Caveats**: [Limitations or conditions]\n"
            "\n"
            "   ### RQ2: ...\n"
            "\n"
            "   ## Summary\n"
            "   | RQ | Status | Confidence |\n"
            "   |----|--------|------------|\n"
            "   | RQ1 | Answered | High |\n"
            "\n"
            "   ## Remaining Unknowns\n"
            "   [Questions that need further investigation via experiment/prototype]\n"
            "\n"
            "Be thorough and evidence-based. Cite specific sources for each finding."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during R3."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
            {"name": "mcp__ontology-server__query_ontology"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> R3Output:
        """Parse R3 output by reading ``r3-research-questions.md`` from *work_dir*.

        Extracts the count and content of investigated research questions.
        Raises :class:`ParseError` if the output file is missing.
        """
        from tulla.core.markdown_extract import (
            extract_field,
            extract_rq_sections,
            extract_section,
            trim_text,
        )

        output_file = ctx.work_dir / "r3-research-questions.md"

        if not output_file.exists():
            raise ParseError(
                f"r3-research-questions.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Extract per-RQ answers.
        rq_sections = extract_rq_sections(content)
        research_questions = len(rq_sections)

        answers = []
        for rq in rq_sections:
            answers.append({
                "id": rq["id"],
                "status": extract_field(rq["body"], "Status"),
                "confidence": extract_field(rq["body"], "Confidence"),
                "answer": extract_field(rq["body"], "Answer"),
            })

        unknowns_section = extract_section(content, "Remaining Unknowns")
        remaining_unknowns = trim_text(unknowns_section) if unknowns_section else ""

        return R3Output(
            output_file=output_file,
            research_questions=research_questions,
            rq_answers=json.dumps(answers),
            remaining_unknowns=remaining_unknowns,
        )

    def get_timeout_seconds(self) -> float:
        """Return the R3 timeout in seconds (20 minutes)."""
        return self.timeout_s
