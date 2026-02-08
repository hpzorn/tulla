"""D1 Phase – Tool & MCP Inventory.

Implements the first discovery sub-phase that audits existing tools,
MCP servers, related ideas, and prior work relevant to a given idea.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from tulla.core.markdown_extract import (
    extract_section,
    extract_table_rows,
    trim_text,
)
from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import D1Output


class D1Phase(Phase[D1Output]):
    """D1: Tool & Skill Inventory phase.

    Constructs a prompt that asks Claude to audit everything related to the
    target idea—tools, MCP servers, related ideas, and prior work—and write
    the findings to ``d1-inventory.md`` inside the work directory.
    """

    phase_id: str = "d1"
    timeout_s: float = 900.0  # 15 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the D1 inventory prompt, ported from discovery-tulla.sh."""
        output_file = ctx.work_dir / "d1-inventory.md"
        discovery_date = date.today().isoformat()

        return (
            f"You are conducting Phase D1: Inventory for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Audit what currently exists related to this idea - in the codebase, "
            "idea pool, and ecosystem.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "\n"
            "2. Search for related work:\n"
            "   - Use mcp__ontology-server__query_ideas to find connected ideas\n"
            "   - Use Glob/Grep to find related code/files in the codebase\n"
            "\n"
            "3. Catalog existing components:\n"
            "   - What tools/systems already exist that touch this domain?\n"
            "   - What ideas in the pool are related?\n"
            "   - What prior work has been done?\n"
            "\n"
            f"4. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # D1: Inventory\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {discovery_date}\n"
            "   **Time-box**: 15 minutes\n"
            "\n"
            "   ## The Idea\n"
            f"   [Brief summary of idea {ctx.idea_id}]\n"
            "\n"
            "   ## Related Ideas in Pool\n"
            "   | ID | Title | Lifecycle | Relationship |\n"
            "   |----|-------|-----------|---------------|\n"
            "   | ... | ... | ... | builds-on/complements/conflicts |\n"
            "\n"
            "   ## Existing Systems & Tools\n"
            "   | Component | Location | Relevance |\n"
            "   |-----------|----------|----------|\n"
            "   | ... | ... | ... |\n"
            "\n"
            "   ## Prior Work\n"
            "   [What has already been done in this space]\n"
            "\n"
            "   ## Current Gaps\n"
            "   [What's clearly missing that this idea would address]\n"
            "\n"
            "   ## Ecosystem Context\n"
            "   [How this fits into the broader system/project]\n"
            "\n"
            "Be thorough - good discovery starts with knowing what exists."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during D1."""
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__query_ideas"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
            {"name": "Grep"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D1Output:
        """Parse D1 output by reading ``d1-inventory.md`` from *work_dir*.

        Extracts semantic fields: key_capabilities, ecosystem_context,
        and reuse_opportunities from the markdown sections.
        Raises :class:`ParseError` if the inventory file is missing.
        """
        inventory_file = ctx.work_dir / "d1-inventory.md"

        if not inventory_file.exists():
            raise ParseError(
                f"d1-inventory.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = inventory_file.read_text(encoding="utf-8")

        # Extract semantic fields
        tools_section = extract_section(content, "Existing Systems & Tools")
        table_rows = extract_table_rows(tools_section)
        key_capabilities = json.dumps(
            [
                {
                    k.lower().replace(" ", "_"): v
                    for k, v in row.items()
                }
                for row in table_rows
            ],
        )
        ecosystem_text = extract_section(content, "Ecosystem Context")
        ecosystem_context = trim_text(ecosystem_text) if ecosystem_text else ""

        prior_work_text = extract_section(content, "Prior Work")
        reuse_opportunities = trim_text(prior_work_text) if prior_work_text else ""

        return D1Output(
            inventory_file=inventory_file,
            key_capabilities=key_capabilities,
            ecosystem_context=ecosystem_context,
            reuse_opportunities=reuse_opportunities,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D1 timeout in seconds (15 minutes)."""
        return self.timeout_s


