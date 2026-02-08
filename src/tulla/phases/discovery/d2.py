"""D2 Phase – Persona Discovery.

Implements the second discovery sub-phase that identifies user personas,
their jobs-to-be-done, pain points, and desired outcomes for a given idea.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from tulla.core.markdown_extract import (
    extract_bullet_items,
    extract_section,
    extract_table_rows,
)
from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts

from .models import D2Output


class D2Phase(Phase[D2Output]):
    """D2: Persona Discovery phase.

    Constructs a prompt that asks Claude to identify user personas and
    their jobs-to-be-done, writing findings to ``d2-personas.md`` inside
    the work directory.  Reads ``d1-inventory.md`` from the previous phase.
    """

    phase_id: str = "d2"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the D2 persona discovery prompt, ported from discovery-tulla.sh."""
        output_file = ctx.work_dir / "d2-personas.md"
        d1_file = ctx.work_dir / "d1-inventory.md"
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

        return (
            f"You are conducting Phase D2: Persona Discovery for idea {ctx.idea_id}.\n"
            "\n"
            f"{upstream_section}"
            "## Goal\n"
            "Identify who would use this, their jobs-to-be-done, and their pain points.\n"
            "\n"
            "## Context\n"
            f"- Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            f"- Read inventory: {d1_file}\n"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Identify 2-4 distinct user personas who would benefit from this idea\n"
            "2. For each persona, map their:\n"
            "   - Jobs-to-be-done (JTBD framework)\n"
            "   - Current pain points\n"
            "   - Desired outcomes\n"
            "   - Context of use\n"
            "\n"
            f"3. Write to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # D2: Persona Discovery\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {discovery_date}\n"
            "   **Time-box**: 20 minutes\n"
            "\n"
            "   ## Persona Overview\n"
            "   | Persona | Role | Primary JTBD | Frequency |\n"
            "   |---------|------|--------------|----------|\n"
            "   | ... | ... | ... | Daily/Weekly/Occasional |\n"
            "\n"
            "   ## Detailed Personas\n"
            "\n"
            '   ### Persona 1: [Name - e.g., "Data-Driven Developer"]\n'
            "\n"
            "   **Who they are**:\n"
            "   [Brief description - role, experience level, context]\n"
            "\n"
            "   **Jobs-to-be-done**:\n"
            "   - **Functional**: [What task are they trying to accomplish?]\n"
            "   - **Emotional**: [How do they want to feel?]\n"
            "   - **Social**: [How do they want to be perceived?]\n"
            "\n"
            "   **Current workflow**:\n"
            "   [How do they accomplish this today?]\n"
            "\n"
            "   **Pain points**:\n"
            "   1. [Pain point 1]\n"
            "   2. [Pain point 2]\n"
            "   3. [Pain point 3]\n"
            "\n"
            "   **Desired outcomes**:\n"
            "   - [Outcome 1]\n"
            "   - [Outcome 2]\n"
            "\n"
            "   **Success metrics** (how they'd measure value):\n"
            "   - [Metric 1]\n"
            "   - [Metric 2]\n"
            "\n"
            "   ## Cross-Persona Insights\n"
            "\n"
            "   **Common pain points**:\n"
            "   - [Shared pain]\n"
            "\n"
            "   **Conflicting needs**:\n"
            "   - [Where personas disagree]\n"
            "\n"
            "   **Priority ranking**:\n"
            "   1. [Primary persona] - [why they're primary]\n"
            "   2. [Secondary persona] - [why]\n"
            "\n"
            "   ## JTBD Summary\n"
            "   When I am [situation], I want to [motivation], so I can [outcome].\n"
            "\n"
            "Think like a product manager. Focus on real user needs, not features."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during D2."""
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "WebSearch"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D2Output:
        """Parse D2 output by reading ``d2-personas.md`` from *work_dir*.

        Extracts semantic fields: personas, non_negotiable_needs,
        and primary_persona_jtbd from the markdown sections.
        Raises :class:`ParseError` if the personas file is missing.
        """
        personas_file = ctx.work_dir / "d2-personas.md"

        if not personas_file.exists():
            raise ParseError(
                f"d2-personas.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = personas_file.read_text(encoding="utf-8")

        # Extract personas from overview table
        overview_section = extract_section(content, "Persona Overview")
        table_rows = extract_table_rows(overview_section)

        personas_list: list[dict[str, str]] = []
        for row in table_rows:
            # Table headers: Persona | Role | Primary JTBD | Frequency
            personas_list.append({
                "name": row.get("Persona", ""),
                "role": row.get("Role", ""),
                "primary_jtbd": row.get("Primary JTBD", ""),
            })
        personas = json.dumps(personas_list)

        # Extract non-negotiable needs from cross-persona insights
        insights_section = extract_section(content, "Cross-Persona Insights")
        pain_section = extract_section(
            "## Cross-Persona Insights\n" + insights_section,
            "Common pain points",
            level=3,
        ) if insights_section else ""
        needs = extract_bullet_items(pain_section) if pain_section else []
        non_negotiable_needs = json.dumps(needs)

        # Extract JTBD summary statement
        jtbd_section = extract_section(content, "JTBD Summary")
        primary_persona_jtbd = jtbd_section.strip() if jtbd_section else ""

        return D2Output(
            personas_file=personas_file,
            personas=personas,
            non_negotiable_needs=non_negotiable_needs,
            primary_persona_jtbd=primary_persona_jtbd,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D2 timeout in seconds (20 minutes)."""
        return self.timeout_s


