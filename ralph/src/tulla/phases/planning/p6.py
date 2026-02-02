"""P6 Phase -- Export PRD to RDF.

Implements the sixth planning sub-phase that converts the implementation
plan (P4) into RDF triples and stores them in the ontology A-box via
``mcp__ontology-server__store_fact``.  This creates the ``prd-idea-{N}``
context that the dashboard displays under "Product Requirements" and
that Implementation-Ralph reads to find work items.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ralph.core.phase import ParseError, Phase, PhaseContext

from .models import P6Output

# PRD ontology namespaces (matches planning-ralph.sh)
PRD_NS = "http://impl-ralph.io/prd#"
TRACE_NS = "http://impl-ralph.io/trace#"


class P6Phase(Phase[P6Output]):
    """P6: Export PRD to RDF.

    Reads the P4 implementation plan and asks Claude to:
    1. Generate a Turtle RDF file with ``prd:Requirement`` instances
    2. Call ``mcp__ontology-server__store_fact`` for each triple
    3. Write a summary file

    This is the bridge between planning and implementation — without it,
    the ontology dashboard shows no PRD and Implementation-Ralph has
    no requirements to process.
    """

    phase_id: str = "p6"
    timeout_s: float = 600.0  # 10 minutes — needs to store many facts

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P6 PRD export prompt, ported from planning-ralph.sh."""
        p4_file = ctx.work_dir / "p4-implementation-plan.md"
        output_file = ctx.work_dir / "p6-prd-export.ttl"
        summary_file = ctx.work_dir / "p6-prd-summary.md"
        planning_date = date.today().isoformat()
        idea_id = ctx.idea_id

        return (
            f"You are conducting Phase P6: Export PRD to RDF for idea {idea_id}.\n"
            "\n"
            "## Goal\n"
            "Convert the implementation plan into RDF requirements that "
            "Implementation-Ralph can consume.\n"
            "This creates the semantic graph of requirements with dependencies "
            "for the ontology-driven implementation loop.\n"
            "\n"
            "## Context\n"
            f"Read the implementation plan: {p4_file}\n"
            "\n"
            "## PRD Ontology Schema\n"
            "\n"
            "Use these namespaces:\n"
            "```turtle\n"
            f"@prefix prd: <{PRD_NS}> .\n"
            f"@prefix trace: <{TRACE_NS}> .\n"
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "```\n"
            "\n"
            "### Classes\n"
            "- `prd:Requirement` - A single implementable requirement/task\n"
            "- `prd:AcceptanceCriteria` - Success condition for verification\n"
            "\n"
            "### Properties\n"
            "- `prd:title` (string) - Short name for the requirement\n"
            "- `prd:description` (string) - Full requirement text\n"
            "- `prd:status` - One of: `prd:Pending`, `prd:InProgress`, `prd:Complete`\n"
            "- `prd:dependsOn` - Requirement → Requirement (dependency link)\n"
            "- `prd:priority` - One of: `prd:P0`, `prd:P1`, `prd:P2`\n"
            "- `prd:phase` (integer) - Implementation phase number\n"
            "- `prd:taskId` (string) - Original task ID from P4 (e.g., '1.1', '2.3')\n"
            "- `prd:files` (string) - Files to create/modify\n"
            "- `prd:action` (string) - Either 'create' (new file) or 'modify' (edit existing)\n"
            "- `prd:verification` (string) - How to verify completion\n"
            "- `prd:relatedADR` (string, multi-valued) - Links requirement to an architecture decision (e.g. \"arch:adr-{idea_id}-1\")\n"
            "- `prd:qualityFocus` (string) - Quality attribute this requirement primarily addresses (e.g. \"Testability\")\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the implementation plan from {p4_file}\n"
            "\n"
            "2. Extract each task from the 'Implementation Phases' section\n"
            "   - Each 'Task X.Y' becomes a `prd:Requirement` instance\n"
            "   - Use task dependencies to set `prd:dependsOn` relationships\n"
            "   - Phase 1 tasks are P0, Phase 2 are P1, Phase 3 are P2\n"
            "\n"
            f"3. Write Turtle RDF to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "   ```turtle\n"
            f"   @prefix prd: <{PRD_NS}> .\n"
            "   @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "   @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "   @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "\n"
            "   # Requirement 1.1\n"
            f"   prd:req-{idea_id}-1-1 a prd:Requirement ;\n"
            '       prd:taskId "1.1" ;\n'
            '       prd:title "[Task title]" ;\n'
            '       prd:description """[Full task description]""" ;\n'
            "       prd:status prd:Pending ;\n"
            "       prd:priority prd:P0 ;\n"
            "       prd:phase 1 ;\n"
            '       prd:files "path/to/file.py" ;\n'
            '       prd:action "create" ;\n'
            '       prd:verification "[How to verify]" .\n'
            "   ```\n"
            "\n"
            "3.5. **Link requirements to architecture**\n"
            f'   - Use mcp__ontology-server__recall_facts with context="arch-idea-{idea_id}" '
            "to see what ADRs exist\n"
            "   - For each requirement clearly related to an ADR, store a "
            "prd:relatedADR fact:\n"
            f'     subject="prd:req-{idea_id}-X-Y", predicate="prd:relatedADR", '
            f'object="arch:adr-{idea_id}-N", context="prd-idea-{idea_id}"\n'
            "   - For requirements focused on a specific quality attribute, store:\n"
            f'     subject="prd:req-{idea_id}-X-Y", predicate="prd:qualityFocus", '
            f'object="[Attribute]", context="prd-idea-{idea_id}"\n'
            "   - Only link when the relationship is clear — don't force links\n"
            "\n"
            "4. After writing the Turtle file, use mcp__ontology-server__store_fact "
            "to add each requirement to the A-box fact store.\n"
            f'   - Context: "prd-idea-{idea_id}"\n'
            "   - For each triple (subject, predicate, object) in the Turtle file, "
            "call store_fact with:\n"
            f'     subject=the requirement URI (e.g. "prd:req-{idea_id}-1-1")\n'
            '     predicate=the property (e.g. "rdf:type", "prd:title", "prd:status", etc.)\n'
            "     object=the value\n"
            f'     context="prd-idea-{idea_id}"\n'
            "   - Do NOT use add_triple — that writes to the T-box (ontology schema), "
            "not the A-box (fact store).\n"
            "     Implementation-Ralph reads requirements via recall_facts, "
            "which only sees the A-box.\n"
            "\n"
            f"5. Write a summary to: {summary_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            f"   # P6: RDF Export Summary\n"
            f"   **Idea**: {idea_id}\n"
            f"   **Date**: {planning_date}\n"
            "\n"
            "   ## Export Status: SUCCESS\n"
            "\n"
            "   ## Requirements Created\n"
            "\n"
            "   | Requirement ID | Title | Priority | Dependencies |\n"
            "   |----------------|-------|----------|-------------|\n"
            f"   | req-{idea_id}-1-1 | ... | P0 | None |\n"
            f"   | req-{idea_id}-1-2 | ... | P0 | 1.1 |\n"
            "   | ... | ... | ... | ... |\n"
            "\n"
            "   ## Dependency Graph\n"
            "\n"
            "   ```\n"
            "   [ASCII representation of dependency graph]\n"
            "   ```\n"
            "\n"
            "   ## Ontology Location\n"
            "\n"
            f"   - Turtle file: {output_file}\n"
            f'   - Graph context: prd-idea-{idea_id}\n'
            "\n"
            "   ## Next Step\n"
            "\n"
            f"   Run Implementation-Ralph: `ralph run implementation --idea {idea_id}`\n"
            "\n"
            "Be precise with RDF syntax. Each task from P4 becomes exactly one "
            "prd:Requirement."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P6."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "mcp__ontology-server__store_fact"},
            {"name": "mcp__ontology-server__recall_facts"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P6Output:
        """Parse P6 output by checking for the Turtle and summary files.

        Counts requirements from the Turtle file (``prd:Requirement`` instances).
        Raises :class:`ParseError` if the Turtle file is missing.
        """
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        summary_file = ctx.work_dir / "p6-prd-summary.md"
        idea_id = ctx.idea_id

        if not turtle_file.exists():
            raise ParseError(
                f"p6-prd-export.ttl not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = turtle_file.read_text(encoding="utf-8")

        # Count prd:Requirement instances
        req_count = len(re.findall(r"a\s+prd:Requirement", content))

        return P6Output(
            turtle_file=turtle_file,
            summary_file=summary_file,
            requirements_exported=req_count,
            prd_context=f"prd-idea-{idea_id}",
        )

    def get_timeout_seconds(self) -> float:
        """Return the P6 timeout in seconds (10 minutes)."""
        return self.timeout_s
