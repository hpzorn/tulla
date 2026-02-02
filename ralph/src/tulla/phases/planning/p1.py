"""P1 Phase – Discovery Context Load.

Implements the first planning sub-phase that loads and synthesises all
discovery documents (and optional research findings) into a unified
planning context.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import P1Output


class P1Phase(Phase[P1Output]):
    """P1: Discovery Context Load phase.

    Constructs a prompt that asks Claude to read and synthesise discovery
    documents (D1-D5) and optional research findings into a consolidated
    planning context, writing results to ``p1-discovery-context.md``
    inside the work directory.
    """

    phase_id: str = "p1"
    timeout_s: float = 600.0  # 10 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P1 discovery context load prompt, ported from planning-tulla.sh."""
        output_file = ctx.work_dir / "p1-discovery-context.md"
        planning_date = date.today().isoformat()
        discovery_dir = ctx.config.get("discovery_dir", "")
        research_dir = ctx.config.get("research_dir", "")

        research_instructions = ""
        research_output_section = ""
        step_after_discovery = "3"

        if research_dir:
            research_instructions = (
                f"\n3. Read downstream research findings from: {research_dir}\n"
                "   These are answers to the research questions identified in discovery (D4/D5).\n"
                "   - r3-research-questions.md (the RQs that were investigated)\n"
                "   - r4-literature-review.md (literature review per RQ)\n"
                "   - r5-research-findings.md (experiments and prototypes)\n"
                "   - r6-research-synthesis.md (conclusions and recommendations)\n"
                "\n"
                "   Use Glob to find files if names vary slightly.\n"
                "   These findings SUPERSEDE the open questions from D5 — the RQs have been answered.\n"
            )
            research_output_section = (
                f"\n   ## Research Findings (answers to discovery RQs)\n"
                f"   **Research Source**: {research_dir}\n"
                "\n"
                "   For each RQ that was investigated:\n"
                "   ### RQ: [question]\n"
                "   **Answer**: [key finding from R4/R5/R6]\n"
                "   **Implication for planning**: [how this constrains or informs the architecture]\n"
                "\n"
                "   ## Resolved Blockers\n"
                "   [List blockers from D4 that are now resolved by research, with the resolution]\n"
            )
            step_after_discovery = "4"

        research_note = ""
        if research_dir:
            research_note = " and downstream research findings"

        return (
            f"You are conducting Phase P1: Load Discovery Context for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            f"Load and synthesize all discovery documents{research_note} into a unified planning context.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the original idea: use mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "\n"
            f"2. Read all discovery documents from: {discovery_dir}\n"
            "   - D1-inventory.md (technical inventory)\n"
            "   - D2-personas.md (user personas)\n"
            "   - D3-value-mapping.md (value proposition)\n"
            "   - D4-gap-analysis.md (gaps identified)\n"
            "   - D5-research-brief.md (research questions if any)\n"
            "   - DISCOVERY-SUMMARY.md (summary)\n"
            "\n"
            "   Use Glob to find files if names vary slightly.\n"
            f"{research_instructions}"
            f"{step_after_discovery}. Write a consolidated context to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # P1: Discovery Context\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {planning_date}\n"
            f"   **Discovery Source**: {discovery_dir}\n"
            "\n"
            "   ## Idea Summary\n"
            "   [One paragraph summary of what we're building]\n"
            "\n"
            "   ## User Persona\n"
            "   [Key persona characteristics from D2]\n"
            "\n"
            "   ## Value Proposition\n"
            "   [Core value from D3]\n"
            "\n"
            "   ## Existing Capabilities (from D1)\n"
            "\n"
            "   ### Available Tools\n"
            "   | Tool/Skill | Type | Relevance |\n"
            "   |------------|------|----------|\n"
            "   | ... | MCP/Skill/Library | High/Medium/Low |\n"
            "\n"
            "   ### Validated Technologies\n"
            "   [What has been tested and works]\n"
            "\n"
            "   ## Gaps to Address (from D4)\n"
            "\n"
            "   | Gap | Priority | Type |\n"
            "   |-----|----------|------|\n"
            "   | ... | P0/P1/P2 | Implementation/Research/Design |\n"
            f"{research_output_section}"
            "   ## Open Research Questions (from D5)\n"
            "   [List any questions that still need research-tulla, "
            "or 'None — all resolved by downstream research' if research answered them]\n"
            "\n"
            "   ## Planning Constraints\n"
            "   - Must use: [existing tools/patterns]\n"
            "   - Should avoid: [anti-patterns identified]\n"
            "   - Success criteria: [from D3]\n"
            "\n"
            "Be thorough but concise. This context drives all subsequent planning."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P1."""
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P1Output:
        """Parse P1 output by reading ``p1-discovery-context.md`` from *work_dir*.

        Extracts triples loaded count and ontologies queried from the content.
        Raises :class:`ParseError` if the context file is missing.
        """
        context_file = ctx.work_dir / "p1-discovery-context.md"

        if not context_file.exists():
            raise ParseError(
                f"p1-discovery-context.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = context_file.read_text(encoding="utf-8")

        # Count triples loaded from "Available Tools" table rows.
        tools_section = _extract_section(content, "Available Tools")
        triples_loaded = _count_table_rows(tools_section)

        # Fallback: count from "Gaps to Address" table if tools table is empty.
        if triples_loaded == 0:
            gaps_section = _extract_section(content, "Gaps to Address")
            triples_loaded = _count_table_rows(gaps_section)

        # Extract ontologies queried from discovery source references.
        ontologies_queried = _extract_ontologies(content)

        return P1Output(
            context_file=context_file,
            triples_loaded=triples_loaded,
            ontologies_queried=ontologies_queried,
        )

    def get_timeout_seconds(self) -> float:
        """Return the P1 timeout in seconds (5 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown ``## heading`` or ``### heading`` until the next heading."""
    pattern = rf"##[#]?\s+{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
    """Count markdown table data rows (excludes header and separator rows)."""
    rows = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip header separator rows like |---|---|---|
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        # Count lines that look like table rows: | content | ... |
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    # Subtract 1 for the header row if we counted any rows
    return max(0, rows - 1) if rows > 0 else 0


def _extract_ontologies(content: str) -> list[str]:
    """Extract ontology references from the content."""
    ontologies: list[str] = []
    # Look for discovery source paths.
    source_match = re.search(r"\*\*Discovery Source\*\*:\s*(.+)", content)
    if source_match:
        ontologies.append(source_match.group(1).strip())
    # Look for research source if present.
    research_match = re.search(r"\*\*Research Source\*\*:\s*(.+)", content)
    if research_match:
        ontologies.append(research_match.group(1).strip())
    return ontologies
