"""PlanPhase — Claude-invoked tactical planning for the lightweight pipeline.

# @pattern:PortsAndAdapters -- Delegates Claude invocation to
#   the injected ClaudePort; reads ContextScanOutput from
#   prev_output
# @pattern:EventSourcing -- Produces an immutable PlanOutput
#   consumed by downstream Execute/Trace phases
# @principle:FailSafeRouting -- Provides reasonable defaults for
#   incomplete Claude responses (empty risk_notes, etc.)
# @principle:InformationHiding -- Prompt construction details
#   and conformance-data formatting are hidden behind the
#   build_prompt() template method

Architecture decisions: arch:adr-53-3
Quality focus: isaqb:FunctionalCorrectness
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.phases.lightweight.models import PlanOutput

logger = logging.getLogger(__name__)


class PlanPhase(Phase[PlanOutput]):
    """Produce a compressed tactical plan via Claude.

    Reads ``ContextScanOutput`` from ``ctx.config["prev_output"]`` and
    constructs a prompt instructing Claude to return a JSON plan with
    ordered implementation steps, files to modify, and risk notes informed
    by conformance data.

    This phase is analysis-only — ``get_tools()`` returns an empty list.
    """

    phase_id: str = "plan"
    timeout_s: float = 300.0

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Construct the planning prompt from conformance context."""
        prev_output = ctx.config.get("prev_output")

        # Extract fields from ContextScanOutput (model or dict)
        description = ""
        affected_files: list[str] = []
        violations: list[dict] = []
        violation_report = ""
        patterns: list[str] = []
        conformance_status = ""

        if prev_output is not None:
            if hasattr(prev_output, "violation_report"):
                violation_report = prev_output.violation_report
                violations = prev_output.violations
                patterns = prev_output.patterns
                conformance_status = prev_output.conformance_status
            elif isinstance(prev_output, dict):
                violation_report = prev_output.get("violation_report", "")
                violations = prev_output.get("violations", [])
                patterns = prev_output.get("patterns", [])
                conformance_status = prev_output.get("conformance_status", "")

        # Retrieve change description and affected files from upstream config
        # These may come from the original pipeline config or upstream facts
        change_description = ctx.config.get("change_description", description)
        config_affected = ctx.config.get("affected_files", affected_files)

        # Include upstream ontology facts if available
        upstream_facts = ctx.config.get("upstream_facts", [])
        upstream_section = ""
        if upstream_facts:
            facts_text = json.dumps(upstream_facts, indent=2)
            upstream_section = (
                f"\n## Upstream Ontology Facts\n{facts_text}\n"
            )

        violations_section = ""
        if violations:
            violations_section = (
                f"\n## Conformance Violations\n{violation_report}\n"
            )
        else:
            violations_section = "\n## Conformance Violations\nNo violations detected.\n"

        patterns_section = ""
        if patterns:
            patterns_section = (
                "\n## Detected Patterns\n"
                + "\n".join(f"- {p}" for p in patterns)
                + "\n"
            )

        files_section = ""
        if config_affected:
            files_section = (
                "\n## Affected Files\n"
                + "\n".join(f"- {f}" for f in config_affected)
                + "\n"
            )

        return (
            f"You are a tactical implementation planner for idea {ctx.idea_id}.\n"
            "\n"
            "## Change Description\n"
            f"{change_description}\n"
            f"{files_section}"
            f"\n## Conformance Status\n{conformance_status}\n"
            f"{violations_section}"
            f"{patterns_section}"
            f"{upstream_section}"
            "\n## Task\n"
            "Produce a compressed tactical plan with:\n"
            "1. A concise plan summary\n"
            "2. Ordered implementation steps\n"
            "3. Files to modify\n"
            "4. Risk notes informed by the conformance data above\n"
            "\n"
            "Respond with ONLY a JSON object matching this schema:\n"
            "{\n"
            '  "plan_summary": "<string: summary of the implementation plan>",\n'
            '  "plan_steps": ["<string: step 1>", "<string: step 2>", ...],\n'
            '  "files_to_modify": ["<string: file path>", ...],\n'
            '  "risk_notes": "<string: risk assessment notes>"\n'
            "}\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return empty list — Plan phase is analysis-only, no tool use."""
        return []

    def parse_output(self, ctx: PhaseContext, raw: Any) -> PlanOutput:
        """Extract JSON from Claude's response and construct a PlanOutput.

        Handles both ``ClaudeResult`` objects (with ``output_json`` or
        ``output_text``) and plain dicts/strings for testability.
        Provides reasonable defaults for missing fields.
        """
        data: dict[str, Any] | None = None

        # Try output_json first (structured output from ClaudeResult)
        if hasattr(raw, "output_json") and raw.output_json is not None:
            data = raw.output_json

        # Fall back to parsing output_text
        if data is None and hasattr(raw, "output_text") and raw.output_text:
            data = _extract_json(raw.output_text)

        # Support plain dict input (e.g., from tests overriding run_claude)
        if data is None and isinstance(raw, dict):
            data = raw

        # Support plain string input
        if data is None and isinstance(raw, str):
            data = _extract_json(raw)

        if data is None:
            raise ParseError(
                "Could not extract JSON from Claude response",
                raw_output=raw,
                context={"phase": "plan"},
            )

        # Apply defaults for missing or incomplete fields
        return PlanOutput(
            plan_summary=data.get("plan_summary", ""),
            plan_steps=data.get("plan_steps", []),
            files_to_modify=data.get("files_to_modify", []),
            risk_notes=data.get("risk_notes", ""),
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from text, handling markdown code fences.

    Returns the parsed dict or ``None`` if no valid JSON is found.
    """
    # Strip markdown code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Remove first line (```json or ```) and last line (```)
        inner_lines = []
        started = False
        for line in lines:
            if not started:
                started = True
                continue
            if line.strip() == "```":
                break
            inner_lines.append(line)
        stripped = "\n".join(inner_lines).strip()

    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    return None
