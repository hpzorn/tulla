"""P3 Phase – Architecture Design.

Implements the third planning sub-phase that designs how existing
components will be connected to achieve the goal.  Includes
ontology-server tools for architecture queries (iSAQB schema).
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from tulla.core.markdown_extract import (
    extract_section,
    extract_table_rows,
)
from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import collect_project_decisions, group_upstream_facts
from tulla.phases.planning import PLANNING_IDENTITY, build_northstar_section

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
    # Prompt section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_project_adr_section(decisions: list[dict[str, Any]]) -> str:
        """Build a prompt section listing project ADRs in effect.

        Constructs a ``## Project ADRs in Effect`` section that lists each
        project ADR with its title, decision text, and quality attributes,
        then provides instructions for feature ADR generation using dual
        positive+negative framing.

        Returns an empty string when *decisions* is empty.
        """
        if not decisions:
            return ""

        lines: list[str] = ["## Project ADRs in Effect", ""]
        lines.append(
            "The following project-level ADRs establish architectural authority. "
            "Feature ADRs operate within this governance context."
        )
        lines.append("")

        for adr in decisions:
            title = adr.get("title", "Untitled")
            decision = adr.get("decision", "")
            quality_attributes = adr.get("quality_attributes", "")
            lines.append(f"- **{title}**")
            if decision:
                lines.append(f"  Decision: {decision}")
            if quality_attributes:
                lines.append(f"  Quality Attributes: {quality_attributes}")
        lines.append("")

        # Dual positive+negative instruction blocks
        lines.append(
            "**DO NOT** restate or re-derive the project ADRs above. "
            "They are already accepted and in effect."
        )
        lines.append("")
        lines.append(
            "**DO** generate ONLY feature-specific architectural choices "
            "that operate within the boundaries set by project ADRs."
        )
        lines.append("")
        lines.append(
            "**IF** a feature decision must override a project ADR, use "
            "`isaqb:supersedes` or `isaqb:refinesDecision` to declare the "
            "relationship explicitly and justify the deviation."
        )
        lines.append("")
        lines.append(
            "**ALIGN** each feature ADR with the project quality goals. "
            "Every decision must reference which project quality attribute "
            "it supports or trades off against."
        )
        lines.append("")
        lines.append(
            "**Scope annotation**: Tag each feature ADR with "
            '`isaqb:decisionScope "feature"` to distinguish it from '
            "project-level decisions."
        )
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P3 architecture design prompt, ported from planning-tulla.sh."""
        output_file = ctx.work_dir / "p3-architecture-design.md"
        p1_file = ctx.work_dir / "p1-discovery-context.md"
        p2_file = ctx.work_dir / "p2-codebase-analysis.md"
        planning_date = date.today().isoformat()

        # Populate project decisions from ontology if not already present
        if "project_decisions" not in ctx.config:
            ontology_port = ctx.config.get("ontology_port")
            project_id = ctx.config.get("project_id", "")
            if ontology_port and project_id:
                ctx.config["project_decisions"] = collect_project_decisions(
                    ontology_port, project_id
                )

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

        # Build project ADR section from project decisions
        project_decisions = ctx.config.get("project_decisions", [])
        project_adr_section = self._build_project_adr_section(project_decisions)

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
            PLANNING_IDENTITY
            + f"## Phase P3: Architecture Design\n"
            f"**Idea**: {ctx.idea_id}\n"
            "\n"
            f"{northstar_section}"
            f"{upstream_section}"
            f"{project_adr_section}"
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
            "**CRITICAL**: Read the Feature Scope table in P1. Your architecture MUST cover ALL features listed there.\n"
            "Do not drop features. Do not add features not in the scope. Trace every building block to a feature.\n"
            "\n"
            "Design an architecture that:\n"
            "1. Covers EVERY feature in P1's Feature Scope table (no exceptions)\n"
            "2. Reuses existing tools/skills wherever possible\n"
            "3. Creates minimal new code (glue/orchestration)\n"
            "4. Is concrete enough to implement directly\n"
            "5. Addresses all gaps identified in discovery\n"
            "6. For features involving AI prompts or LLM-driven phases: specifies the\n"
            "   DOMAIN METHODOLOGY the prompt must encode, not just the plumbing\n"
            "\n"
            "### Prompt-Content Features (CRITICAL)\n"
            "\n"
            "When a feature involves designing, creating, or modifying an AI prompt\n"
            "(e.g., research phases, discovery phases, planning phases, agent instructions),\n"
            "the Building Block description MUST specify:\n"
            "- The **intellectual process** the AI should follow (step-by-step methodology)\n"
            "- The **domain knowledge** the prompt must encode (frameworks, taxonomies,\n"
            "  evaluation criteria, decision procedures)\n"
            "- The **quality criteria** for the output (what makes a good vs bad result)\n"
            "- The **failure modes** to guard against (common mistakes, shortcuts, omissions)\n"
            "\n"
            "Example of BAD architecture for a Literature Review phase:\n"
            "  'R4 gets a mode preamble: exploratory for groundwork, focused for spikes'\n"
            "\n"
            "Example of GOOD architecture for a Literature Review phase:\n"
            "  'R4 prompt must instruct: (1) systematic search using constructed keyword\n"
            "   queries, (2) source credibility assessment (recency, peer review, authority),\n"
            "   (3) thematic synthesis across sources (not summarization), (4) evidence\n"
            "   grading (strong/moderate/weak with explicit criteria), (5) contradiction\n"
            "   resolution protocol, (6) comparison matrix: approach × quality attributes'\n"
            "\n"
            "The prompts ARE the product. Enums, CLI flags, and configs are plumbing.\n"
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
            "## Feature Coverage Matrix (REQUIRED)\n"
            "\n"
            "Map EVERY feature from P1's Feature Scope to architectural components:\n"
            "\n"
            "| Feature (from P1) | Building Blocks | Routes/APIs | Data Flow | Notes |\n"
            "|-------------------|-----------------|-------------|-----------|-------|\n"
            "| [Feature 1] | [Components involved] | [Endpoints] | [Data path] | ... |\n"
            "| [Feature 2] | ... | ... | ... | ... |\n"
            "\n"
            "**Coverage check**: All [N] features from P1 are mapped above.\n"
            "If any feature is missing, this architecture is INCOMPLETE.\n"
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
            "\n"
            "For each key decision, use the arc42/Nygard ADR format:\n"
            "\n"
            "### ADR-{idea}-N: [Decision Title]\n"
            "**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-X\n"
            "\n"
            "**Context**: Describe the situation, including technical, political, social,\n"
            "and project aspects. These forces might be in tension. Include alternatives\n"
            "considered if relevant.\n"
            "\n"
            "**Decision**: The actual choice made in response to the circumstances.\n"
            "Be specific about what will be done and why this option was chosen.\n"
            "\n"
            "**Consequences**: What will or can happen as a result of this decision.\n"
            "List ALL consequences — positive, negative, and neutral:\n"
            "- (+) [Positive outcome or quality attribute addressed]\n"
            "- (-) [Negative outcome, tradeoff, or risk introduced]\n"
            "- (~) [Neutral change or side effect]\n"
            "\n"
            "## Quality Scenarios\n"
            "## File Structure\n"
            "## Risk Assessment\n"
            "## Unknowns Requiring Research\n"
            "\n"
            "| Unknown | Why It Matters | Blocking? |\n"
            "|---------|----------------|----------|\n"
            "| ... | ... | Yes/No |\n"
            "\n"
            "## Architecture Fact Storage\n"
            "\n"
            "After writing the architecture design file, store key decisions as facts\n"
            "in the ontology A-box so the Implementation phase can use them.\n"
            f'Use context: "arch-idea-{ctx.idea_id}"\n'
            "\n"
            "### Quality Goals and Principles (use store_fact)\n"
            "\n"
            "1. **Quality Goals** (top 3):\n"
            f'   - subject="arch:idea-{ctx.idea_id}", predicate="arch:qualityGoal",\n'
            '     object="[Attribute]: [rationale in 1 sentence]"\n'
            "\n"
            "2. **Design Principles** (top 3):\n"
            f'   - subject="arch:idea-{ctx.idea_id}", predicate="arch:designPrinciple",\n'
            '     object="[Principle Name]: [how it applies in 1 sentence]"\n'
            "\n"
            "### Architecture Decisions (use add_triple for structured ADRs)\n"
            "\n"
            "For each ADR, create a structured `isaqb:ArchitectureDecision` instance\n"
            "using mcp__ontology-server__add_triple. This enables SHACL validation\n"
            "and rich queries.\n"
            "\n"
            f"For ADR-{ctx.idea_id}-N, store these triples:\n"
            "\n"
            "```\n"
            f'# 1. Type assertion (required for SHACL)\n'
            f'add_triple(subject="arch:adr-{ctx.idea_id}-N",\n'
            '           predicate="rdf:type",\n'
            '           object="isaqb:ArchitectureDecision")\n'
            "\n"
            f'# 2. Title (required)\n'
            f'add_triple(subject="arch:adr-{ctx.idea_id}-N",\n'
            '           predicate="rdfs:label",\n'
            f'           object="ADR-{ctx.idea_id}-N: [Title]",\n'
            '           is_literal=True)\n'
            "\n"
            f'# 3. Context (required) — forces, constraints, alternatives\n'
            f'add_triple(subject="arch:adr-{ctx.idea_id}-N",\n'
            '           predicate="isaqb:context",\n'
            '           object="[Context paragraph]",\n'
            '           is_literal=True)\n'
            "\n"
            f'# 4. Status (required)\n'
            f'add_triple(subject="arch:adr-{ctx.idea_id}-N",\n'
            '           predicate="isaqb:decisionStatus",\n'
            '           object="isaqb:StatusProposed")\n'
            "\n"
            f'# 5. Consequences (required) — use (+), (-), (~) prefixes\n'
            f'add_triple(subject="arch:adr-{ctx.idea_id}-N",\n'
            '           predicate="isaqb:consequences",\n'
            '           object="(+) [positive]. (-) [negative]. (~) [neutral].",\n'
            '           is_literal=True)\n'
            "\n"
            f'# 6. Quality links (optional but recommended)\n'
            f'add_triple(subject="arch:adr-{ctx.idea_id}-N",\n'
            '           predicate="isaqb:addresses",\n'
            '           object="isaqb:[QualityAttribute]")  # e.g., isaqb:Maintainability\n'
            "```\n"
            "\n"
            "Keep total facts under 20. Be concise — no markdown formatting in values.\n"
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
            {"name": "mcp__ontology-server__store_fact"},
        ]

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
        unknowns_section = extract_section(content, "Unknowns Requiring Research")
        unknowns_rows = extract_table_rows(unknowns_section)
        total_dependencies = len(unknowns_rows)

        # Count circular/blocking dependencies (rows with "Yes" in Blocking column).
        circular_dependencies = len(
            re.findall(r"\|\s*Yes\s*\|", unknowns_section, re.IGNORECASE)
        )

        # Extract semantic fields: ADRs
        adrs = _extract_adrs(content)
        architecture_decisions = json.dumps(adrs)

        # Extract semantic fields: quality goals
        qg_section = extract_section(content, "Quality Goals (isaqb:QualityGoal)")
        if not qg_section:
            qg_section = extract_section(content, "Quality Goals")
        qg_rows = extract_table_rows(qg_section) if qg_section else []
        quality_goals_list = [
            {
                "attribute": row.get("Quality Attribute", ""),
                "priority": row.get("Priority", ""),
            }
            for row in qg_rows
        ]
        quality_goals = json.dumps(quality_goals_list)

        return P3Output(
            dependency_graph_file=dependency_graph_file,
            total_dependencies=total_dependencies,
            circular_dependencies=circular_dependencies,
            architecture_decisions=architecture_decisions,
            quality_goals=quality_goals,
        )

    def get_timeout_seconds(self) -> float:
        """Return the P3 timeout in seconds (15 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_adrs(content: str) -> list[dict[str, str]]:
    """Extract Architecture Decision Records from ### ADR headings.

    Looks for ``### ADR-N: Title`` headings and captures the title plus
    the first ``**Decision**:`` line found in that section.
    """
    adrs: list[dict[str, str]] = []
    # Match ### headings that look like ADR entries
    pattern = r"###\s+(ADR[- ]\d+[^#\n]*)\n(.*?)(?=\n###\s|\n##\s|\Z)"
    for match in re.finditer(pattern, content, re.DOTALL):
        title = match.group(1).strip().rstrip(":")
        body = match.group(2)
        decision = ""
        rationale = ""
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("**decision**"):
                decision = re.sub(r"^\*\*[Dd]ecision\*\*:\s*", "", stripped)
            elif stripped.lower().startswith("**rationale**"):
                rationale = re.sub(r"^\*\*[Rr]ationale\*\*:\s*", "", stripped)
        adr = {
            "title": title,
            "decision": decision,
            "rationale": rationale,
        }
        adr["scope"] = "idea"
        adrs.append(adr)
    return adrs
