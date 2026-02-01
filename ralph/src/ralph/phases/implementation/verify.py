"""VerifyPhase — Claude verifies implementation against spec.

Part of the Implementation loop. This phase invokes Claude to verify
that the implementation satisfies the requirement's verification
criteria.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ralph.ports.claude import ClaudePort, ClaudeRequest

from .models import FindOutput, ImplementOutput, VerifyOutput

logger = logging.getLogger(__name__)


class VerifyPhase:
    """Invoke Claude to verify an implementation against its spec.

    Builds a verification prompt from the requirement's verification
    criteria and asks Claude to check the implementation.
    """

    phase_id: str = "verify"
    timeout_s: float = 600.0  # 10 minutes

    def execute(
        self,
        claude: ClaudePort,
        requirement: FindOutput,
        implementation: ImplementOutput,
        budget_usd: float,
    ) -> VerifyOutput:
        """Verify the implementation against the requirement spec.

        Parameters:
            claude: Claude invocation port.
            requirement: The requirement that was implemented.
            implementation: The implementation output to verify.
            budget_usd: Remaining budget for this invocation.

        Returns:
            A :class:`VerifyOutput` with pass/fail and feedback.
        """
        req_id = requirement.requirement_id or "unknown"
        prompt = self._build_prompt(requirement, implementation)

        request = ClaudeRequest(
            prompt=prompt,
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            budget_usd=budget_usd,
            timeout_seconds=self.timeout_s,
            permission_mode="auto",
        )

        start = time.monotonic()
        result = claude.run(request)
        elapsed = time.monotonic() - start

        # Parse verification result from output
        output_text = result.output_text.strip()
        passed = "VERIFY_PASS" in output_text
        feedback = output_text if not passed else ""

        logger.info(
            "VerifyPhase for %s: %s (cost=$%.4f, %.1fs)",
            req_id,
            "PASS" if passed else "FAIL",
            result.cost_usd,
            elapsed,
        )

        return VerifyOutput(
            requirement_id=req_id,
            passed=passed,
            feedback=feedback,
            cost_usd=result.cost_usd,
            duration_s=elapsed,
        )

    def _build_prompt(
        self,
        requirement: FindOutput,
        implementation: ImplementOutput,
    ) -> str:
        """Build the verification prompt for Claude."""
        lines = [
            "You are a verification agent. Your job is to verify that an",
            "implementation satisfies its requirement specification.",
            "",
            f"## Requirement: {requirement.requirement_id}",
            f"**Title**: {requirement.title}",
            "",
            "## Description",
            requirement.description,
            "",
            "## Verification Criteria",
            requirement.verification,
            "",
            "## Files to Check",
        ]

        for f in implementation.files_changed:
            lines.append(f"- {f}")

        lines.extend([
            "",
            "## Instructions",
            "1. Read each file listed above",
            "2. Check that the implementation matches the description",
            "3. Check that the verification criteria are satisfied",
            "4. Run any verification commands if specified",
            "",
            "## Output",
            "On the FINAL line, output exactly ONE of:",
            "- VERIFY_PASS — if all criteria are satisfied",
            "- VERIFY_FAIL: [specific issues] — if criteria are NOT satisfied",
        ])

        return "\n".join(lines)
