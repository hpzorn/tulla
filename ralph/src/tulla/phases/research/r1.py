"""R1 Phase - Research Question Refinement.

Supports two modes (see idea-58):

- **Groundwork** (no planning_dir): Starts from a raw idea, generates
  research questions from scratch to establish feasibility and novelty.
- **Spike** (planning_dir provided): Refines specific research requests
  from planning P5 into precise, answerable questions.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import R1Output


class R1Phase(Phase[R1Output]):
    """R1: Research Question Refinement phase.

    Constructs a prompt that asks Claude to take the research requests
    from P5 and refine them into precise, answerable research questions
    with methodology notes.  Writes results to
    ``r1-question-refinement.md`` inside the work directory.
    """

    phase_id: str = "r1"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R1 question refinement prompt.

        Supports two modes:
        - **Groundwork** (no planning_dir): Start from the raw idea, generate
          research questions from scratch.  Runs before discovery/planning.
        - **Spike** (planning_dir provided): Refine specific research requests
          from planning P5 into answerable questions.
        """
        output_file = ctx.work_dir / "r1-question-refinement.md"
        research_date = date.today().isoformat()
        planning_dir = ctx.config.get("planning_dir", "")
        discovery_dir = ctx.config.get("discovery_dir", "")

        # --- Three modes (see idea-58) ---
        # 1. Spike: planning_dir provided → refine P5 research requests
        # 2. Discovery-fed: discovery_dir provided → refine D5 research brief
        # 3. Groundwork: neither → generate RQs from the raw idea
        if planning_dir:
            mode_label = "Targeted Spike"
            goal = (
                "Refine the research requests from planning into precise, answerable\n"
                "research questions with methodology notes.\n"
            )
            input_instructions = (
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
            )
            origin_field = "   **Origin**: [Which RR from P5]\n"
        elif discovery_dir:
            mode_label = "Discovery-Fed Research"
            goal = (
                "Refine the research questions from the discovery research brief (D5)\n"
                "into precise, answerable research questions with methodology notes.\n"
                "The discovery phase has already identified gaps, personas, and value;\n"
                "your job is to sharpen the research questions it produced.\n"
            )
            input_instructions = (
                f"2. Read the discovery research brief: {discovery_dir}/d5-research-brief.md\n"
                "   This contains prioritized research questions with business rationale\n"
                "   and success criteria from the discovery phase.\n"
                "\n"
                f"   Also read the supporting discovery artifacts from {discovery_dir}:\n"
                "   - d1-inventory.md — existing tools, MCP servers, related ideas\n"
                "   - d2-personas.md — user personas and their needs\n"
                "   - d3-value-mapping.md — value assessment and priority scoring\n"
                "   - d4-gap-analysis.md — knowledge gaps and technical blockers\n"
                "\n"
                "3. For each research question from D5, refine it into:\n"
                "   - A precise, answerable question (sharpen if D5's version is vague)\n"
                "   - Why it matters (use D5's business rationale, add depth)\n"
                "   - Suggested methodology (literature review, experiment, prototype)\n"
                "   - Acceptance criteria (use D5's success criteria, make measurable)\n"
                "   - Respect D5's priority ordering (High > Medium > Low)\n"
                "\n"
                "   You may split, merge, or reorder D5's questions if it improves\n"
                "   research quality, but preserve their intent and traceability.\n"
            )
            origin_field = "   **Origin**: [Which RQ from D5 research brief]\n"
        else:
            mode_label = "Groundwork Research"
            goal = (
                "Analyze the raw idea and generate precise, answerable research\n"
                "questions that establish feasibility, novelty, and design direction.\n"
            )
            input_instructions = (
                "2. Analyze the idea thoroughly:\n"
                "   - What is the core concept? What problem does it solve?\n"
                "   - What are the key technical challenges?\n"
                "   - What prior art or related work might exist?\n"
                "   - What assumptions need validation?\n"
                "\n"
                "3. Generate 2-6 research questions that would establish whether\n"
                "   this idea is novel, feasible, and worth building. Consider:\n"
                "   - Prior art: Is this already solved? Partially solved?\n"
                "   - Feasibility: Can the key technical challenges be overcome?\n"
                "   - Architecture: What design patterns or approaches apply?\n"
                "   - Integration: How does this fit with existing systems?\n"
                "\n"
                "   For each research question, define:\n"
                "   - A precise, answerable question\n"
                "   - Why it matters (impact on feasibility or design)\n"
                "   - Suggested methodology (literature review, experiment, prototype)\n"
                "   - Acceptance criteria (what counts as an answer)\n"
            )
            origin_field = "   **Origin**: [Which aspect of the idea prompted this question]\n"

        return (
            f"You are conducting Phase R1: Research Question Refinement for idea {ctx.idea_id}.\n"
            f"**Mode**: {mode_label}\n"
            "\n"
            "## Goal\n"
            + goal
            + "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: use mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "\n"
            + input_instructions
            + "\n"
            f"4. Write the refined questions to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R1: Research Question Refinement\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            f"   **Mode**: {mode_label}\n"
            "\n"
            "   ## Refined Research Questions\n"
            "\n"
            "   ### RQ1: [Precise question]\n"
            + origin_field
            + "   **Impact**: [What depends on the answer]\n"
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
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
        ]

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
        """Return the R1 timeout in seconds (20 minutes)."""
        return self.timeout_s
