"""P3 Phase – Architecture Design.

Implements the third planning sub-phase that designs how existing
components will be connected to achieve the goal.  Includes
ontology-server tools for architecture queries (iSAQB schema).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import P3Output


class P3Phase(Phase[P3Output]):
    """P3: Architecture Design phase.

    Constructs a prompt that asks Claude to design architecture using
    existing components, writing findings to ``p3-architecture-design.md``
    inside the work directory.  Reads ``p1-discovery-context.md`` and
    ``p2-codebase-analysis.md`` from previous phases.

    Includes ontology-server tools for querying iSAQB architecture schema.
    Accepts an optional ``schema_context`` parameter via
    ``ctx.config["schema_context"]``.
    """

    phase_id: str = "p3"
    timeout_s: float = 900.0  # 15 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P3 architecture design prompt, ported from planning-ralph.sh."""
        output_file = ctx.work_dir / "p3-architecture-design.md"
        p1_file = ctx.work_dir / "p1-discovery-context.md"
        p2_file = ctx.work_dir / "p2-codebase-analysis.md"
        planning_date = date.today().isoformat()

        schema_context = ctx.config.get("schema_context", "")
        schema_block = ""
        if schema_context:
            schema_block = (
                "\n## iSAQB Architecture Schema\n\n"
                f"{schema_context}\n\n"
                "Use the iSAQB schema above to inform your architecture design. You can query\n"
                "the ontology-server via SPARQL (mcp__ontology-server__query_ontology or\n"
                "mcp__ontology-server__sparql_query) to look up patterns, quality attributes,\n"
                "tradeoffs, and design principles relevant to this idea.\n"
            )

        return (
            f"You are conducting Phase P3: Architecture Design for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Design how existing components will be connected to achieve the goal.\n"
            "Minimize new code; maximize reuse of existing capabilities.\n"
            "\n"
            "## Context\n"
            f"- Discovery context: {p1_file}\n"
            f"- Codebase analysis: {p2_file}\n"
            "\n"
            "Read both files thoroughly before designing.\n"
            f"{schema_block}"
            "\n"
            "## Instructions\n"
            "\n"
            "Design an architecture that:\n"
            "1. Reuses existing tools/skills wherever possible\n"
            "2. Creates minimal new code (glue/orchestration)\n"
            "3. Is concrete enough to implement directly\n"
            "4. Addresses all gaps identified in discovery\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "Structure:\n"
            "\n"
            "# P3: Architecture Design\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Date**: {planning_date}\n"
            "\n"
            "## Quality Goals (isaqb:QualityGoal)\n"
            "| Priority | Quality Attribute | Sub-Attributes | Rationale |\n"
            "|----------|-------------------|----------------|-----------|\n"
            "| ... | ... | ... | ... |\n"
            "\n"
            "### Quality Tradeoffs\n"
            "| Attribute A | conflicts with | Attribute B | Resolution |\n"
            "|-------------|---------------|-------------|------------|\n"
            "| ... | ... | ... | ... |\n"
            "\n"
            "## Design Principles (isaqb:DesignPrinciple)\n"
            "1. **[Principle Name]** (Category: [...]) — [How it applies here]\n"
            "\n"
            "## Architectural Patterns (isaqb:ArchitecturalPattern)\n"
            "| Pattern | Addresses Quality | Embodies Principle | Relevance |\n"
            "|---------|------------------|--------------------|----------|\n"
            "| ... | ... | ... | ... |\n"
            "\n"
            "## System Architecture\n"
            "### High-Level Flow\n"
            "### Building Blocks\n"
            "### Runtime View\n"
            "\n"
            "## Data Flow\n"
            "## Integration Plan\n"
            "## Cross-Cutting Concerns\n"
            "## Architecture Decisions (ADRs)\n"
            "## Quality Scenarios\n"
            "## File Structure\n"
            "## Risk Assessment\n"
            "## Unknowns Requiring Research\n"
            "\n"
            "| Unknown | Why It Matters | Blocking? |\n"
            "|---------|----------------|----------|\n"
            "| ... | ... | Yes/No |\n"
            "\n"
            "Be concrete and specific. This design will be translated directly into implementation tasks."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P3.

        Includes ontology-server query tools for architecture queries.
        """
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "mcp__ontology-server__query_ontology"},
            {"name": "mcp__ontology-server__sparql_query"},
        ]

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Invoke Claude.

        The base framework will provide a concrete adapter; this default
        raises NotImplementedError to signal that a real adapter is needed.
        """
        raise NotImplementedError(
            "P3Phase.run_claude requires a Claude adapter to be injected"
        )

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P3Output:
        """Parse P3 output by reading ``p3-architecture-design.md`` from *work_dir*.

        Extracts dependency count and circular dependency count.
        Raises :class:`ParseError` if the architecture design file is missing.
        """
        dependency_graph_file = ctx.work_dir / "p3-architecture-design.md"

        if not dependency_graph_file.exists():
            raise ParseError(
                f"p3-architecture-design.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = dependency_graph_file.read_text(encoding="utf-8")

        # Count dependencies from "Unknowns Requiring Research" table rows.
        unknowns_section = _extract_section(content, "Unknowns Requiring Research")
        total_dependencies = _count_table_rows(unknowns_section)

        # Count circular/blocking dependencies (rows with "Yes" in Blocking column).
        circular_dependencies = len(
            re.findall(r"\|\s*Yes\s*\|", unknowns_section, re.IGNORECASE)
        )

        return P3Output(
            dependency_graph_file=dependency_graph_file,
            total_dependencies=total_dependencies,
            circular_dependencies=circular_dependencies,
        )

    def get_timeout_seconds(self) -> float:
        """Return the P3 timeout in seconds (15 minutes)."""
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
