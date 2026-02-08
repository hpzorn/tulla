"""ImplementPhase — Claude with acceptEdits to implement a requirement.

Part of the Implementation loop. This phase invokes Claude with
``acceptEdits`` permission mode to generate or modify code for the
current requirement.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from tulla.annotations import ANNOTATION_REGEX, APF_TARGET
from tulla.ports.claude import ClaudePort, ClaudeRequest

from .models import FindOutput, ImplementOutput

logger = logging.getLogger(__name__)


class ImplementPhase:
    """Invoke Claude to implement a single requirement.

    Builds a prompt from the requirement's description, files, and
    action, then calls Claude with acceptEdits permission mode.
    """

    phase_id: str = "implement"
    timeout_s: float = 3600.0  # 60 minutes (class-level fallback)

    def __init__(
        self,
        timeout_s: float = 3600.0,
        apf_target: tuple[int, int] = (2, 5),
    ) -> None:
        self.timeout_s = timeout_s
        self._apf_target = apf_target

    def execute(
        self,
        claude: ClaudePort,
        requirement: FindOutput,
        budget_usd: float,
        feedback: str = "",
        architecture_context: dict[str, Any] | None = None,
        lessons: list[str] | None = None,
    ) -> ImplementOutput:
        """Implement the requirement using Claude.

        Parameters:
            claude: Claude invocation port.
            requirement: The requirement to implement (from FindPhase).
            budget_usd: Remaining budget for this invocation.
            feedback: Optional feedback from a failed verification
                attempt, used for retry.
            architecture_context: Optional dict with keys
                ``quality_goals``, ``design_principles``, ``adrs``
                loaded from the ontology's ``arch-idea-{N}`` context.
            lessons: Optional list of lesson strings from previous
                requirements in this run.

        Returns:
            An :class:`ImplementOutput` with the result.
        """
        req_id = requirement.requirement_id or "unknown"
        prompt = self._build_prompt(
            requirement, feedback, architecture_context, lessons,
        )

        request = ClaudeRequest(
            prompt=prompt,
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
            budget_usd=budget_usd,
            timeout_seconds=self.timeout_s,
            permission_mode="acceptEdits",
        )

        logger.debug("Claude prompt", extra={
            "phase_id": self.phase_id,
            "requirement_id": req_id,
            "prompt": prompt,
        })

        start = time.monotonic()
        result = claude.run(request)
        elapsed = time.monotonic() - start

        logger.info(
            "ImplementPhase for %s completed (exit=%d, cost=$%.4f, %.1fs)",
            req_id,
            result.exit_code,
            result.cost_usd,
            elapsed,
        )

        files_changed: list[str] = []
        if requirement.files:
            files_changed = list(requirement.files)

        return ImplementOutput(
            requirement_id=req_id,
            files_changed=files_changed,
            output_text=result.output_text,
            cost_usd=result.cost_usd,
            duration_s=elapsed,
        )

    def _build_prompt(
        self,
        requirement: FindOutput,
        feedback: str,
        architecture_context: dict[str, Any] | None = None,
        lessons: list[str] | None = None,
    ) -> str:
        """Build the implementation prompt for Claude."""
        lines = [
            f"You are Implementation-Tulla, an ontology-driven implementation agent.",
            "",
            "## Your Task",
            f"Implement requirement: {requirement.requirement_id}",
            f"**Title**: {requirement.title}",
            "",
            "## Description",
            requirement.description,
            "",
        ]

        # --- Architecture Context (between Description and Files) ---
        arch_lines = self._build_architecture_section(
            requirement, architecture_context,
        )
        if arch_lines:
            lines.extend(arch_lines)

        # --- Pattern Annotations (after Architecture Context) ---
        ann_lines = self._build_annotation_section(requirement, self._apf_target)
        if ann_lines:
            lines.extend(ann_lines)

        lines.extend([
            "## Files",
            f"Action: {requirement.action}",
        ])

        for f in requirement.files:
            lines.append(f"- {f}")

        lines.extend([
            "",
            "## Verification Criteria",
            requirement.verification,
            "",
            "## Rules",
            "- For NEW files, use Python 3.11+ unless specified otherwise",
            "- For EXISTING files, use the file's own language",
            "- Implement EXACTLY what the requirement describes",
            "- Ensure the verification criteria will PASS",
        ])

        # --- Lessons from Previous Requirements ---
        if lessons:
            lines.extend([
                "",
                "## Lessons from Previous Requirements",
                "The following lessons were learned from earlier requirements in this run:",
            ])
            for lesson in lessons:
                lines.append(f"- {lesson}")
            lines.append("")
            lines.append("Avoid repeating these mistakes.")

        if feedback:
            lines.extend([
                "",
                "## Previous Attempt Feedback",
                "The previous implementation attempt failed verification:",
                feedback,
                "",
                "Fix the issues described above.",
            ])

        lines.extend([
            "",
            "## Output",
            "On the FINAL line, output exactly:",
            f"- IMPLEMENTED: {requirement.requirement_id} -- if successful",
            f"- IMPLEMENT_FAIL: {requirement.requirement_id} [reason] -- if failed",
        ])

        return "\n".join(lines)

    @staticmethod
    def _build_architecture_section(
        requirement: FindOutput,
        architecture_context: dict[str, Any] | None,
    ) -> list[str]:
        """Build the optional Architecture Context prompt section.

        Returns an empty list when there is no context to inject.
        """
        if not architecture_context:
            return []

        lines: list[str] = ["## Architecture Context", ""]

        # Northstar (big-picture context, before per-requirement details)
        northstar = architecture_context.get("northstar", "")
        if northstar:
            lines.append(f"**Northstar**: {northstar}")
            lines.append("")

        # Key constraints
        key_constraints = architecture_context.get("key_constraints", "")
        if key_constraints:
            lines.append("**Key Constraints**:")
            if isinstance(key_constraints, list):
                for c in key_constraints:
                    lines.append(f"- {c}")
            else:
                lines.append(f"- {key_constraints}")
            lines.append("")

        # Quality focus for this specific requirement
        if requirement.quality_focus:
            lines.append(
                f"**Quality focus for this requirement**: {requirement.quality_focus}"
            )
            lines.append("")

        # Relevant ADRs (filtered by requirement.related_adrs)
        all_adrs: dict[str, str] = architecture_context.get("adrs", {})
        if requirement.related_adrs and all_adrs:
            lines.append("**Relevant Architecture Decisions**:")
            for adr_id in requirement.related_adrs:
                text = all_adrs.get(adr_id, "")
                if text:
                    lines.append(f"- {adr_id}: {text}")
            lines.append("")

        # Design principles (always included — compact)
        principles: list[str] = architecture_context.get("design_principles", [])
        if principles:
            lines.append("**Design Principles**:")
            for p in principles:
                lines.append(f"- {p}")
            lines.append("")

        lines.append("Respect these architecture decisions in your implementation.")
        lines.append("")
        return lines

    @staticmethod
    def _build_annotation_section(
        requirement: FindOutput,
        apf_target: tuple[int, int] = APF_TARGET,
    ) -> list[str]:
        """Build the optional Pattern Annotations prompt section.

        Generates annotation instructions from *resolved_patterns* and
        *resolved_principles* on the requirement.  Returns an empty list
        when there are no resolved items to annotate.

        Architecture decision: arch:adr-65-4 (separate _build_ method)
        Architecture decision: arch:adr-65-6 (class-level, APF 2-5)
        """
        items = list(requirement.resolved_patterns) + list(requirement.resolved_principles)
        if not items:
            return []

        apf_lo, apf_hi = apf_target
        lines: list[str] = ["## Pattern Annotations", ""]

        # Format specification
        lines.append("**Format** (regex):")
        lines.append(f"`{ANNOTATION_REGEX.pattern}`")
        lines.append("")

        # Pattern checklist
        lines.append("**Checklist** — annotate usage of these patterns/principles:")
        for item in items:
            lines.append(f"- [ ] {item}")
        lines.append("")

        # Good / bad examples
        lines.append("**Examples**:")
        lines.append("")
        lines.append("Good:")
        lines.append("```python")
        lines.append(
            "# @pattern:PortsAndAdapters -- ClaudePort abstracts "
            "subprocess invocation behind an interface"
        )
        lines.append("```")
        lines.append("")
        lines.append("Bad (hollow — restates the identifier without code-specific detail):")
        lines.append("```python")
        lines.append(
            "# @pattern:PortsAndAdapters -- Uses the Ports and Adapters pattern"
        )
        lines.append("```")
        lines.append("")

        # Rules
        lines.append("**Rules**:")
        lines.append(
            f"- Target {apf_lo}-{apf_hi} annotations per file (APF)."
        )
        lines.append(
            "- Place annotations at class/module level, not on every method."
        )
        lines.append(
            "- Each explanation must add code-specific detail beyond the identifier name."
        )
        lines.append("")
        return lines
