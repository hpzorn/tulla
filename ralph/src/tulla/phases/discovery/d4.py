"""D4 Phase – Gap Analysis.

Implements the fourth discovery sub-phase that identifies gaps between
the current state and desired state, prioritises opportunities, and
optionally incorporates iSAQB architecture schema context.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from tulla.core.markdown_extract import (
    extract_section,
    trim_text,
)
from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts

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

        raw_facts = ctx.config.get("upstream_facts", [])
        grouped = group_upstream_facts(raw_facts)
        upstream_section = ""
        if grouped:
            upstream_section = (
                "## Upstream Facts\n"
                f"{json.dumps(grouped, indent=2)}\n"
                "\n"
            )

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
            f"{upstream_section}"
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

        Extracts semantic fields: blockers, root_blocker, and
        recommended_next_steps.  Raises :class:`ParseError` if the gap
        analysis file is missing.
        """
        gap_analysis_file = ctx.work_dir / "d4-gap-analysis.md"

        if not gap_analysis_file.exists():
            raise ParseError(
                f"d4-gap-analysis.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = gap_analysis_file.read_text(encoding="utf-8")

        # Extract blockers narrative
        blockers_section = extract_section(content, "Blockers")
        blockers = trim_text(blockers_section) if blockers_section else ""

        # Extract root blocker: first item from Blockers section
        root_blocker = ""
        if blockers_section:
            from tulla.core.markdown_extract import extract_bullet_items
            blocker_items = extract_bullet_items(blockers_section)
            if blocker_items:
                root_blocker = blocker_items[0]

        # Extract recommended next steps
        next_steps_section = extract_section(content, "Recommended Next Steps")
        recommended_next_steps = (
            trim_text(next_steps_section) if next_steps_section else ""
        )

        return D4Output(
            gap_analysis_file=gap_analysis_file,
            blockers=blockers,
            root_blocker=root_blocker,
            recommended_next_steps=recommended_next_steps,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D4 timeout in seconds (15 minutes)."""
        return self.timeout_s


