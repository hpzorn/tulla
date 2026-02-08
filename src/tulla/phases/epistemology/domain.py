"""Epistemology Domain mode — domain coherence check.

Examines whether an idea's domain model is internally consistent,
properly bounded, and ontologically sound.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext

from .models import DomainOutput


class DomainPhase(Phase[DomainOutput]):
    """Epistemology domain mode: check domain coherence and ontological soundness."""

    phase_id: str = "ep-domain"
    timeout_s: float = 900.0

    def build_prompt(self, ctx: PhaseContext) -> str:
        output_file = ctx.work_dir / "ep-domain-coherence.md"
        run_date = date.today().isoformat()

        return (
            f"You are conducting Epistemology — Domain Coherence for idea {ctx.idea_id}.\n"
            "\n"
            "## Goal\n"
            "Check whether the idea's domain model is internally consistent, "
            "properly bounded, and ontologically sound.\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the idea: mcp__ontology-server__get_idea with identifier {ctx.idea_id}\n"
            "2. Query relevant ontologies: mcp__ontology-server__query_ontology\n"
            "3. For each domain concept:\n"
            "   - Is it well-defined?\n"
            "   - Are boundaries clear (what's in vs. out of scope)?\n"
            "   - Do concepts overlap or conflict?\n"
            "   - Is the domain model consistent with established ontologies?\n"
            "\n"
            f"4. Write findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # Epistemology: Domain Coherence\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {run_date}\n"
            "\n"
            "   ## Domains Analysed\n"
            "   | Domain | Scope | Consistency | Issues |\n"
            "   |--------|-------|-------------|--------|\n"
            "\n"
            "   ## Boundary Issues\n"
            "   [Where domain boundaries are unclear or overlapping]\n"
            "\n"
            "   ## Ontological Mismatches\n"
            "   [Where the domain model conflicts with established ontologies]\n"
            "\n"
            "   ## Recommendations\n"
            "   [Actions to improve domain coherence]\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        return [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__recall_facts"},
            {"name": "mcp__ontology-server__query_ontology"},
            {"name": "mcp__ontology-server__list_ontologies"},
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Glob"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> DomainOutput:
        output_file = ctx.work_dir / "ep-domain-coherence.md"

        if not output_file.exists():
            raise ParseError(
                f"ep-domain-coherence.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        domains_section = _extract_section(content, "Domains Analysed")
        domains_analysed = _count_table_rows(domains_section)

        incoherences_found = 0
        for heading in ("Boundary Issues", "Ontological Mismatches"):
            section = _extract_section(content, heading)
            incoherences_found += _count_bullet_items(section)

        return DomainOutput(
            output_file=output_file,
            domains_analysed=domains_analysed,
            incoherences_found=incoherences_found,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1) if match else ""


def _count_table_rows(section: str) -> int:
    rows = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\|[\s-]+\|", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            rows += 1
    return max(0, rows - 1) if rows > 0 else 0


def _count_bullet_items(section: str) -> int:
    count = 0
    for line in section.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            count += 1
    return count
