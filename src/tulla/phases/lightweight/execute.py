"""ExecutePhase -- Claude-invoked execution for the lightweight pipeline.

# @pattern:PortsAndAdapters -- Delegates Claude invocation to the injected ClaudePort; reads PlanOutput from prev_output
# @pattern:EventSourcing -- Produces an immutable ExecuteOutput consumed by downstream Trace phase
# @principle:FailSafeRouting -- Provides reasonable defaults for incomplete Claude responses (empty commit_ref for dry-run)
# @pattern:LayeredArchitecture -- ExecutePhase sits in the execution layer, consuming PlanOutput from the planning layer above

Architecture decisions: arch:adr-53-3
Quality focus: isaqb:FunctionalCorrectness
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.phases.lightweight.models import ExecuteOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Commit type mapping: 6-category taxonomy -> conventional commits
# ---------------------------------------------------------------------------

_COMMIT_TYPE_MAP: dict[str, str] = {
    "bugfix": "fix",
    "feature": "feat",
    "enhancement": "feat",
    "chore": "chore",
    "test": "test",
    "refactor": "refactor",
}


class ExecutePhase(Phase[ExecuteOutput]):
    """Execute planned changes via Claude with file read/write and bash tools.

    Reads ``PlanOutput`` from ``ctx.config["prev_output"]`` and constructs
    a prompt instructing Claude to implement the planned changes, respecting
    architectural guard-rails (only modify listed files, no new dependencies,
    follow existing conventions, create a conventional commit).

    ``get_tools()`` returns file read/write and bash tool specifications
    following the pattern from existing implementation phases.
    """

    phase_id: str = "execute"
    timeout_s: float = 600.0

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Construct the execution prompt from plan context and guard-rails."""
        prev_output = ctx.config.get("prev_output")

        # Extract fields from PlanOutput (model or dict)
        plan_summary = ""
        plan_steps: list[str] = []
        files_to_modify: list[str] = []

        if prev_output is not None:
            if hasattr(prev_output, "plan_steps"):
                plan_summary = prev_output.plan_summary
                plan_steps = prev_output.plan_steps
                files_to_modify = prev_output.files_to_modify
            elif isinstance(prev_output, dict):
                plan_summary = prev_output.get("plan_summary", "")
                plan_steps = prev_output.get("plan_steps", [])
                files_to_modify = prev_output.get("files_to_modify", [])

        # Retrieve change description and change type from upstream config
        change_description = ctx.config.get("change_description", "")
        change_type = ctx.config.get("change_type", "chore")
        commit_type = _COMMIT_TYPE_MAP.get(change_type, "chore")

        # Build plan steps section
        steps_section = ""
        if plan_steps:
            steps_text = "\n".join(f"{i}. {s}" for i, s in enumerate(plan_steps, 1))
            steps_section = f"\n## Plan Steps\n{steps_text}\n"

        # Build files section
        files_section = ""
        if files_to_modify:
            files_text = "\n".join(f"- {f}" for f in files_to_modify)
            files_section = f"\n## Files to Modify\n{files_text}\n"

        return (
            f"You are an implementation executor for idea {ctx.idea_id}.\n"
            "\n"
            "## Change Description\n"
            f"{change_description}\n"
            "\n"
            "## Plan Summary\n"
            f"{plan_summary}\n"
            f"{steps_section}"
            f"{files_section}"
            "\n## Architectural Guard-Rails\n"
            "- Only modify files listed in the plan\n"
            "- Do not introduce new external dependencies\n"
            "- Follow existing code conventions\n"
            f"- Create a git commit using conventional commit format: "
            f"{commit_type}(scope): description\n"
            "\n"
            "## Task\n"
            "Implement the planned changes following the steps above.\n"
            "After making the changes, create a git commit.\n"
            "\n"
            "When complete, respond with ONLY a JSON object matching this schema:\n"
            "{\n"
            '  "changes_summary": "<string: summary of changes made>",\n'
            '  "files_modified": ["<string: file path>", ...],\n'
            '  "commit_ref": "<string: git commit SHA>",\n'
            '  "execution_notes": "<string: any additional notes>"\n'
            "}\n"
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions for file read/write and bash execution."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Edit"},
            {"name": "Glob"},
            {"name": "Grep"},
            {"name": "Bash"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> ExecuteOutput:
        """Extract JSON from Claude's response and construct an ExecuteOutput.

        Handles both ``ClaudeResult`` objects (with ``output_json`` or
        ``output_text``) and plain dicts/strings for testability.
        Provides reasonable defaults for missing fields.  If no commit
        was created (e.g., dry-run mode), ``commit_ref`` defaults to
        empty string.
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
                context={"phase": "execute"},
            )

        # Apply defaults for missing or incomplete fields
        # commit_ref defaults to empty string for dry-run mode
        return ExecuteOutput(
            changes_summary=data.get("changes_summary", ""),
            files_modified=data.get("files_modified", []),
            commit_ref=data.get("commit_ref", ""),
            execution_notes=data.get("execution_notes", ""),
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
