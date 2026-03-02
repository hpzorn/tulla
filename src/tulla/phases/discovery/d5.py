"""D5 Phase – Integration (mode-dependent).

Implements the fifth discovery sub-phase.  Operates in two modes:

- **upstream**: Pre-research discovery — produces ``d5-research-brief.md``.
- **downstream**: Post-research integration — produces ``d5-product-spec.md``.

The mode is determined by ``ctx.config["mode"]`` (default: ``"upstream"``).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from tulla.core.markdown_extract import (
    extract_bullet_items,
    extract_checklist_items,
    extract_section,
    trim_text,
)
from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts

from .models import D5Output


class D5Phase(Phase[D5Output]):
    """D5: Integration phase (mode-dependent).

    Constructs a mode-specific prompt:
    - **upstream** → research brief (``d5-research-brief.md``)
    - **downstream** → product spec (``d5-product-spec.md``)

    The mode is read from ``ctx.config["mode"]``; defaults to ``"upstream"``.
    """

    phase_id: str = "d5"
    timeout_s: float = 1200.0  # 20 minutes

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def _get_mode(self, ctx: PhaseContext) -> str:
        """Return the discovery mode from context config."""
        return ctx.config.get("mode", "upstream")

    def _get_output_filename(self, ctx: PhaseContext) -> str:
        """Return the output filename based on mode."""
        mode = self._get_mode(ctx)
        if mode == "downstream":
            return "d5-product-spec.md"
        return "d5-research-brief.md"

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the D5 integration prompt, ported from discovery-tulla.sh."""
        mode = self._get_mode(ctx)
        output_filename = self._get_output_filename(ctx)
        output_file = ctx.work_dir / output_filename
        discovery_date = date.today().isoformat()

        d1_file = ctx.work_dir / "d1-inventory.md"
        d2_file = ctx.work_dir / "d2-personas.md"
        d3_file = ctx.work_dir / "d3-value-mapping.md"
        d4_file = ctx.work_dir / "d4-gap-analysis.md"

        raw_facts = ctx.config.get("upstream_facts", [])
        grouped = group_upstream_facts(raw_facts)
        upstream_section = ""
        if grouped:
            upstream_section = (
                "## Upstream Facts\n"
                f"{json.dumps(grouped, indent=2)}\n"
                "\n"
            )

        context_block = (
            "## Context\n"
            "Read all discovery phases:\n"
            f"- {d1_file}\n"
            f"- {d2_file}\n"
            f"- {d3_file}\n"
            f"- {d4_file}\n"
        )

        if mode == "downstream":
            return self._build_downstream_prompt(
                ctx, output_file, discovery_date, context_block,
                upstream_section,
            )
        return self._build_upstream_prompt(
            ctx, output_file, discovery_date, context_block,
            upstream_section,
        )

    def _build_upstream_prompt(
        self,
        ctx: PhaseContext,
        output_file: Any,
        discovery_date: str,
        context_block: str,
        upstream_section: str,
    ) -> str:
        """Build the upstream (pre-research) prompt."""
        return (
            f"You are conducting Phase D5: Integration (UPSTREAM) for idea {ctx.idea_id}.\n"
            "\n"
            f"{upstream_section}"
            "## Goal\n"
            "Create a research brief for research-tulla, informed by product discovery.\n"
            "\n"
            f"{context_block}"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Synthesize discovery findings into a research brief\n"
            "2. Prioritize research questions based on business value\n"
            "3. Create research seeds if needed\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "Structure:\n"
            "\n"
            "# D5: Research Brief\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Date**: {discovery_date}\n"
            "**Mode**: Upstream (Discovery -> Research)\n"
            "\n"
            "## Discovery Summary\n"
            "\n"
            "### What We Learned\n"
            "- **What**: [What the idea delivers — name every distinct capability, "
            "mode, protocol, or workflow. Do NOT summarise; preserve the idea's own "
            "language and structure.]\n"
            "- **Users**: [Primary persona and their core need]\n"
            "- **Value**: [Key value proposition]\n"
            "- **Gaps**: [Critical gaps identified]\n"
            "\n"
            "### Priority Score\n"
            "From D3 value mapping: [X/60] - [P0/P1/P2/P3]\n"
            "\n"
            "## Research Questions (Prioritized by Value)\n"
            "\n"
            "### High Priority (Must answer before implementation)\n"
            "1. **RQ**: [Question from D4]\n"
            "   **Business rationale**: [Why this matters]\n"
            "   **Success criteria**: [What a good answer looks like]\n"
            "\n"
            "### Medium Priority (Would improve implementation)\n"
            "2. **RQ**: [Question]\n"
            "\n"
            "### Low Priority (Nice to know)\n"
            "3. **RQ**: [Question]\n"
            "\n"
            "## Mandatory Features\n"
            "\n"
            "List EVERY distinct feature, capability, mode, phase, or protocol "
            "described in the idea.\n"
            "Use the idea's own names and structure — do NOT merge, summarise, "
            "or reword.\n"
            "This list is the contract that planning must preserve.\n"
            "\n"
            "- [Feature/capability 1 — exactly as described in the idea]\n"
            "- [Feature/capability 2]\n"
            "- ...\n"
            "\n"
            "## Constraints for Research\n"
            "- **User constraints**: [From D2]\n"
            "- **Technical constraints**: [From D1]\n"
            "- **Business constraints**: [From D3]\n"
            "\n"
            "## Success Definition\n"
            "Research is successful if it answers the key questions and enables\n"
            "the outcomes identified in discovery.\n"
            "\n"
            "After writing, append a discovery summary to the idea using "
            "mcp__ontology-server__append_to_idea.\n"
            "\n"
            "Output the word 'research' on the final line to indicate handoff "
            "to research-tulla."
        )

    def _build_downstream_prompt(
        self,
        ctx: PhaseContext,
        output_file: Any,
        discovery_date: str,
        context_block: str,
        upstream_section: str,
    ) -> str:
        """Build the downstream (post-research) prompt."""
        return (
            f"You are conducting Phase D5: Integration (DOWNSTREAM) for idea {ctx.idea_id}.\n"
            "\n"
            f"{upstream_section}"
            "## Goal\n"
            "Integrate research findings with product discovery to create an "
            "actionable product spec.\n"
            "\n"
            f"{context_block}"
            "\n"
            "Also look for research artifacts (r6-research-synthesis.md, prd.md).\n"
            "\n"
            "## Instructions\n"
            "\n"
            "Create a product specification that bridges research findings with "
            "user needs.\n"
            "\n"
            f"Write to: {output_file}\n"
            "\n"
            "Structure:\n"
            "\n"
            "# D5: Product Specification\n"
            f"**Idea**: {ctx.idea_id}\n"
            f"**Date**: {discovery_date}\n"
            "**Mode**: Downstream (Research -> Product)\n"
            "\n"
            "## Executive Summary\n"
            "[2-3 sentences: what, for whom, why now]\n"
            "\n"
            "## User Story\n"
            "As a [persona from D2],\n"
            "I want to [capability],\n"
            "So that [outcome/benefit from D3].\n"
            "\n"
            "## Research Foundation\n"
            "[Summary of key research findings]\n"
            "\n"
            "## Product Requirements\n"
            "\n"
            "### Must Have (P0)\n"
            "- [ ] [Requirement tied to primary persona need]\n"
            "\n"
            "### Should Have (P1)\n"
            "- [ ] [Requirement]\n"
            "\n"
            "### Nice to Have (P2)\n"
            "- [ ] [Requirement]\n"
            "\n"
            "## Success Metrics\n"
            "| Metric | Target | Measurement |\n"
            "|--------|--------|-------------|\n"
            "| ... | ... | ... |\n"
            "\n"
            "## Integration Points\n"
            "| System | Integration | Complexity |\n"
            "|--------|-------------|------------|\n"
            "| ... | ... | ... |\n"
            "\n"
            "After writing, append product spec summary to idea using "
            "mcp__ontology-server__append_to_idea.\n"
            "\n"
            "Output 'implement' on the final line if ready for implementation, "
            "or 'research' if more research needed."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during D5."""
        tools = [
            {"name": "mcp__ontology-server__get_idea"},
            {"name": "mcp__ontology-server__append_to_idea"},
            {"name": "Read"},
            {"name": "Write"},
        ]
        mode = self._get_mode(ctx)
        if mode == "upstream":
            tools.append({"name": "mcp__ontology-server__capture_seed"})
        elif mode == "downstream":
            tools.append({"name": "Glob"})
        return tools

    def parse_output(self, ctx: PhaseContext, raw: Any) -> D5Output:
        """Parse D5 output by reading the mode-specific output file.

        Extracts the recommendation (research/implement/park) from the file.
        Raises :class:`ParseError` if the output file is missing.
        """
        output_filename = self._get_output_filename(ctx)
        output_file = ctx.work_dir / output_filename
        mode = self._get_mode(ctx)

        if not output_file.exists():
            raise ParseError(
                f"{output_filename} not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir), "mode": mode},
            )

        content = output_file.read_text(encoding="utf-8")

        recommendation = _extract_recommendation(content, mode)

        # Extract semantic fields (mode-dependent)
        if mode == "upstream":
            northstar_section = extract_section(content, "What We Learned", level=3)
            if not northstar_section:
                northstar_section = extract_section(content, "Discovery Summary")
            features_section = extract_section(
                content, "Mandatory Features",
            )
            features = (
                extract_bullet_items(features_section)
                if features_section
                else []
            )
            constraints_section = extract_section(
                content, "Constraints for Research",
            )
            constraints = (
                extract_bullet_items(constraints_section)
                if constraints_section
                else []
            )
        else:
            northstar_section = extract_section(content, "Executive Summary")
            p0_section = extract_section(content, "Must Have (P0)", level=3)
            features = (
                extract_checklist_items(p0_section)
                if p0_section
                else extract_bullet_items(p0_section) if p0_section else []
            )
            constraints_section = extract_section(
                content, "Integration Points",
            )
            constraints = (
                extract_bullet_items(constraints_section)
                if constraints_section
                else []
            )

        # Northstar is critical for drift prevention — use higher limit (2000 chars)
        northstar = trim_text(northstar_section, max_chars=2000) if northstar_section else ""
        mandatory_features = json.dumps(features)
        key_constraints = json.dumps(constraints)

        return D5Output(
            output_file=output_file,
            mode=mode,
            recommendation=recommendation,
            northstar=northstar,
            mandatory_features=mandatory_features,
            key_constraints=key_constraints,
        )

    def get_timeout_seconds(self) -> float:
        """Return the D5 timeout in seconds (20 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_recommendation(content: str, mode: str) -> str:
    """Extract the recommendation from the last few lines of the output.

    Looks for 'research', 'implement', or 'park' keywords near the end.
    Falls back to mode-based defaults.
    """
    # Check the last 5 lines for a recommendation keyword.
    last_lines = content.strip().splitlines()[-5:]
    for line in reversed(last_lines):
        lower = line.strip().lower()
        if lower in ("research", "implement", "park"):
            return lower
        # Also check for the keyword anywhere in the line
        for keyword in ("research", "implement", "park"):
            if keyword in lower:
                return keyword

    # Default based on mode.
    return "research" if mode == "upstream" else "implement"
