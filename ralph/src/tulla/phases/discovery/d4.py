"""D4 Phase – Gap Analysis.

Implements the fourth discovery sub-phase that identifies gaps between
the current state and desired state, prioritises opportunities, and
optionally incorporates iSAQB architecture schema context.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import D4Output


class D4Phase(Phase[D4Output]):
    """D4: Gap Analysis phase.

    Constructs a prompt that asks Claude to identify gaps, categorise them,
    and prioritise based on value mapping.  Adds ontology-server query tools
    for architecture-aware gap analysis.  Writes findings to
    ``d4-gap-analysis.md`` inside the work directory.

    Accepts an optional ``schema_context`` parameter via
    ``ctx.config["schema_context"]`` for iSAQB architecture schema content.
    """

    phase_id: str = "d4"
    timeout_s: float = 900.0  # 15 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the D4 gap analysis prompt, ported from discovery-tulla.sh."""
        output_file = ctx.work_dir / "d4-gap-analysis.md"
        d1_file = ctx.work_dir / "d1-inventory.md"
        d2_file = ctx.work_dir / "d2-personas.md"
        d3_file = ctx.work_dir / "d3-value-mapping.md"
        discovery_date = date.today().isoformat()

        schema_context = ctx.config.get("schema_context", "")
        schema_block = ""
        if schema_context:
            schema_block = (
                "\n## iSAQB Architecture Schema\n\n"
                f"{schema_context}\n\n"
                "Use the iSAQB schema above to inform your gap analysis. You can query\n"
                "the ontology-server via SPARQL (mcp__ontology-server__query_ontology or\n"
                "mcp__ontology-server__sparql_query) to look up quality attributes, "
                "architectural\npatterns, risks, and design principles relevant to "
                "identifying gaps.\n"
            )

        return (
            f"You are conducting Phase D4: Gap Analysis for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Identify what's missing to move this idea forward and prioritize "
            "opportunities.\n"
            "\n"
            "## Context\n"
            "Read all previous discovery phases:\n"
            f"- {d1_file}\n"
            f"- {d2_file}\n"
            f"- {d3_file}\n"
            f"{schema_block}"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Identify all gaps between current state and desired state\n"
            "2. Categorize gaps by type, including quality-attribute gaps\n"
            "3. Prioritize based on value mapping and quality goal impact\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "Structure:\n"
            "\n"
            "# D4: Gap Analysis\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Date**: {discovery_date}\n"
            "**Time-box**: 15 minutes\n"
            "\n"
            "## Gap Categories\n"
            "\n"
            "### Knowledge Gaps\n"
            "| Gap | Impact | Research Question |\n"
            "|-----|--------|-------------------|\n"
            '| ... | High/Med/Low | "How does X work?" |\n'
            "\n"
            "### Technical Gaps\n"
            "| Gap | Blocks | Solution Approach |\n"
            "|-----|--------|-------------------|\n"
            "| ... | [what it blocks] | Build/Buy/Integrate |\n"
            "\n"
            "### Quality-Attribute Gaps\n"
            "| Quality Attribute | Current State | Desired State | Gap Severity |\n"
            "|-------------------|---------------|---------------|-------------|\n"
            "| [e.g. Maintainability] | [What exists] | [What's needed] | High/Med/Low |\n"
            "\n"
            "### Resource Gaps\n"
            "| Gap | Type | Mitigation |\n"
            "|-----|------|------------|\n"
            "| ... | Skills/Time/Tools/Budget | ... |\n"
            "\n"
            "### Integration Gaps\n"
            "| Gap | Systems Involved | Complexity |\n"
            "|-----|------------------|------------|\n"
            "| ... | ... | High/Med/Low |\n"
            "\n"
            "## Priority Matrix\n"
            "\n"
            "| Gap | Value Impact | Effort to Close | Priority |\n"
            "|-----|--------------|-----------------|----------|\n"
            "| ... | High/Med/Low | High/Med/Low | P0/P1/P2/P3 |\n"
            "\n"
            "## Blockers\n"
            "[Critical gaps that must be resolved first]\n"
            "\n"
            "## Opportunities\n"
            "[Gaps that, if closed, would create outsized value]\n"
            "\n"
            "## Recommended Next Steps\n"
            "\n"
            "### If proceeding to research (upstream):\n"
            "1. [Step 1]\n"
            "\n"
            "### If integrating research (downstream):\n"
            "1. [Step 1]\n"
            "\n"
            "Be specific about gaps - vague gaps can't be closed."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during D4."""
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "mcp__ontology-server__query_ontology"},
            {"name": "mcp__ontology-server__sparql_query"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D4Output:
        """Parse D4 output by reading ``d4-gap-analysis.md`` from *work_dir*.

        Extracts total gap count and P0 gap count from the Priority Matrix
        table.  Raises :class:`ParseError` if the gap analysis file is missing.
        """
        gap_analysis_file = ctx.work_dir / "d4-gap-analysis.md"

        if not gap_analysis_file.exists():
            raise ParseError(
                f"d4-gap-analysis.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = gap_analysis_file.read_text(encoding="utf-8")

        # Count gaps from "Priority Matrix" table rows.
        priority_section = _extract_section(content, "Priority Matrix")
        gaps_found = _count_table_rows(priority_section)

        # Count P0 gaps in the Priority Matrix.
        p0_gaps = len(re.findall(r"\|\s*P0\s*\|", priority_section))

        return D4Output(
            gap_analysis_file=gap_analysis_file,
            gaps_found=gaps_found,
            p0_gaps=p0_gaps,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D4 timeout in seconds (15 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    """Extract content under a markdown ``## heading`` until the next heading."""
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
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
