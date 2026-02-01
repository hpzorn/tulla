"""ImplementPhase — Claude with acceptEdits to implement a requirement.

Part of the Implementation loop. This phase invokes Claude with
``acceptEdits`` permission mode to generate or modify code for the
current requirement.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ralph.ports.claude import ClaudePort, ClaudeRequest

from .models import FindOutput, ImplementOutput

logger = logging.getLogger(__name__)


class ImplementPhase:
    """Invoke Claude to implement a single requirement.

    Builds a prompt from the requirement's description, files, and
    action, then calls Claude with acceptEdits permission mode.
    """

    phase_id: str = "implement"
    timeout_s: float = 3600.0  # 60 minutes

    def execute(
        self,
        claude: ClaudePort,
        requirement: FindOutput,
        budget_usd: float,
        feedback: str = "",
    ) -> ImplementOutput:
        """Implement the requirement using Claude.

        Parameters:
            claude: Claude invocation port.
            requirement: The requirement to implement (from FindPhase).
            budget_usd: Remaining budget for this invocation.
            feedback: Optional feedback from a failed verification
                attempt, used for retry.

        Returns:
            An :class:`ImplementOutput` with the result.
        """
        req_id = requirement.requirement_id or "unknown"
        prompt = self._build_prompt(requirement, feedback)

        request = ClaudeRequest(
            prompt=prompt,
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
            budget_usd=budget_usd,
            timeout_seconds=self.timeout_s,
            permission_mode="acceptEdits",
        )

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
    ) -> str:
        """Build the implementation prompt for Claude."""
        lines = [
            f"You are Implementation-Ralph, an ontology-driven implementation agent.",
            "",
            "## Your Task",
            f"Implement requirement: {requirement.requirement_id}",
            f"**Title**: {requirement.title}",
            "",
            "## Description",
            requirement.description,
            "",
            "## Files",
            f"Action: {requirement.action}",
        ]

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
