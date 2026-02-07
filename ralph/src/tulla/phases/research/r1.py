"""R1 Phase - Research Question Refinement.

Supports two modes (see idea-58):

- **Groundwork** (no planning_dir): Starts from a raw idea, generates
  research questions from scratch to establish feasibility and novelty.
- **Spike** (planning_dir provided): Refines specific research requests
  from planning P5 into precise, answerable questions.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts
from tulla.phases.research import RESEARCH_IDENTITY, build_northstar_section

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
                "Perform a structured prior-art triage of the raw idea to assess\n"
                "novelty and generate precise, answerable research questions\n"
                "targeting only the novel and partially-novel capabilities.\n"
            )
            input_instructions = (
                "2. **Capability Decomposition**: Break the idea into 3-5 constituent\n"
                "   capabilities. Each capability is a distinct functional building block\n"
                "   that the idea requires. Name each capability concisely and describe\n"
                "   what it does in one sentence.\n"
                "\n"
                "3. **Per-Capability Novelty Assessment**: For EACH capability, assess\n"
                "   its novelty level using exactly one of the following labels:\n"
                "   - **Novel**: No known prior art; this capability would need to be\n"
                "     invented or fundamentally researched.\n"
                "   - **Partial**: Prior art exists but does not fully address the\n"
                "     capability as required; adaptation or extension is needed.\n"
                "   - **Derivative**: Well-known solutions exist; the capability can be\n"
                "     assembled from existing tools/libraries with minor glue code.\n"
                "   - **Commoditized**: Off-the-shelf solutions exist; no research needed.\n"
                "\n"
                "   For each capability, cite at least one source (library, paper, tool,\n"
                "   or project) that justifies the novelty label. Format:\n"
                "\n"
                "   | # | Capability | Novelty | Source / Evidence |\n"
                "   |---|------------|---------|-------------------|\n"
                "   | 1 | [name]     | Novel / Partial / Derivative / Commoditized | [citation] |\n"
                "\n"
                "4. **Derivative Idea Detection**: If ALL capabilities are rated\n"
                "   Derivative or Commoditized, the idea as a whole is Derivative.\n"
                "   In this case:\n"
                "   - State clearly that no novel research questions are warranted.\n"
                "   - Recommend proceeding directly to implementation or dropping the idea.\n"
                "   - Do NOT generate research questions for commoditized capabilities.\n"
                "\n"
                "5. **Research Question Generation**: Generate research questions ONLY\n"
                "   for capabilities rated Novel or Partial. Do NOT generate research\n"
                "   questions for Derivative or Commoditized capabilities.\n"
                "\n"
                "   For each research question, define:\n"
                "   - A precise, answerable question (not vague or open-ended)\n"
                "   - **Capability**: Which capability this question targets\n"
                "   - **Methodology**: One of: Literature Review, Experiment, Prototype\n"
                "   - **Acceptance Criteria**: Measurable criteria — what specific\n"
                "     evidence or result would answer this question\n"
                "\n"
                "   FAILURE MODE GUARDS:\n"
                "   - Do NOT generate questions about Derivative or Commoditized\n"
                "     capabilities. If you catch yourself doing this, delete the question.\n"
                "   - Do NOT skip the Novelty Assessment. Every idea must be triaged.\n"
                "   - Do NOT leave acceptance criteria vague (e.g. 'works well').\n"
                "     Each criterion must be measurable or verifiable.\n"
            )
            origin_field = "   **Origin**: [Which capability prompted this question]\n"

        # Groundwork mode uses steps 2-5 for triage, so write step is 6.
        # Other modes use steps 2-3, so write step is 4.
        is_groundwork = not planning_dir and not discovery_dir
        write_step = "6" if is_groundwork else "4"

        # Build the output structure template — groundwork gets extra sections.
        if is_groundwork:
            output_structure = (
                "   # R1: Research Question Refinement\n"
                f"   **Idea**: {ctx.idea_id}\n"
                f"   **Date**: {research_date}\n"
                f"   **Mode**: {mode_label}\n"
                "\n"
                "   ## Capability Decomposition\n"
                "\n"
                "   | # | Capability | Description |\n"
                "   |---|------------|-------------|\n"
                "   | 1 | [name]     | [one-sentence description] |\n"
                "   | ... | ... | ... |\n"
                "\n"
                "   ## Per-Capability Novelty Assessment\n"
                "\n"
                "   | # | Capability | Novelty | Source / Evidence |\n"
                "   |---|------------|---------|-------------------|\n"
                "   | 1 | [name]     | Novel / Partial / Derivative / Commoditized | [citation] |\n"
                "   | ... | ... | ... | ... |\n"
                "\n"
                "   ## Novelty Assessment\n"
                "\n"
                "   **Verdict**: Novel | Partially Novel | Derivative\n"
                "\n"
                "   [Brief justification referencing the per-capability table above.\n"
                "    - Novel: at least one capability is Novel.\n"
                "    - Partially Novel: no Novel capabilities, but at least one is Partial.\n"
                "    - Derivative: ALL capabilities are Derivative or Commoditized.]\n"
                "\n"
                "   ## Refined Research Questions\n"
                "   (Only for Novel / Partial capabilities. Omit this section entirely\n"
                "   if the verdict is Derivative.)\n"
                "\n"
                "   ### RQ1: [Precise question]\n"
                + origin_field
                + "   **Methodology**: Literature Review / Experiment / Prototype\n"
                "   **Acceptance Criteria**: [Measurable criteria]\n"
                "\n"
                "   ### RQ2: ...\n"
                "\n"
                "   ## Research Plan\n"
                "   [Recommended order of investigation and dependencies between RQs]\n"
            )
        else:
            output_structure = (
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
            )

        return (
            RESEARCH_IDENTITY
            + f"## Phase R1: Research Question Refinement\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Mode**: {mode_label}\n"
            "\n"
            f"{northstar_section}"
            f"{upstream_section}"
            "## Goal\n"
            + goal
            + "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: use mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "\n"
            + input_instructions
            + "\n"
            f"{write_step}. Write the refined questions to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            + output_structure
            + "\n"
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

        Extracts the count and content of refined research questions.
        Raises :class:`ParseError` if the output file is missing.
        """
        from tulla.core.markdown_extract import extract_field, extract_rq_sections

        output_file = ctx.work_dir / "r1-question-refinement.md"

        if not output_file.exists():
            raise ParseError(
                f"r1-question-refinement.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Count refined research questions (### RQ headings).
        rq_sections = extract_rq_sections(content)
        questions_refined = len(rq_sections)

        # Extract content-bearing facts.
        rq_list = []
        for rq in rq_sections:
            rq_list.append({
                "id": rq["id"],
                "question": rq["title"],
                "methodology": extract_field(rq["body"], "Methodology"),
                "acceptance_criteria": extract_field(rq["body"], "Acceptance Criteria"),
            })

        return R1Output(
            output_file=output_file,
            questions_refined=questions_refined,
            research_questions=json.dumps(rq_list),
        )

    def get_timeout_seconds(self) -> float:
        """Return the R1 timeout in seconds (20 minutes)."""
        return self.timeout_s
