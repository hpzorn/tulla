"""VerifyPhase — Claude verifies implementation against spec.

Part of the Implementation loop. This phase invokes Claude to verify
that the implementation satisfies the requirement's verification
criteria.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from tulla.ports.claude import ClaudePort, ClaudeRequest

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
        architecture_context: dict[str, Any] | None = None,
    ) -> VerifyOutput:
        """Verify the implementation against the requirement spec.

        Parameters:
            claude: Claude invocation port.
            requirement: The requirement that was implemented.
            implementation: The implementation output to verify.
            budget_usd: Remaining budget for this invocation.
            architecture_context: Optional dict with keys
                ``quality_goals``, ``design_principles``, ``adrs``
                loaded from the ontology's ``arch-idea-{N}`` context.

        Returns:
            A :class:`VerifyOutput` with pass/fail and feedback.
        """
        req_id = requirement.requirement_id or "unknown"
        prompt = self._build_prompt(requirement, implementation, architecture_context)

        request = ClaudeRequest(
            prompt=prompt,
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            budget_usd=budget_usd,
            timeout_seconds=self.timeout_s,
            permission_mode="bypassPermissions",
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
        architecture_context: dict[str, Any] | None = None,
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
        ]

        # --- Architecture Compliance ---
        arch_lines = self._build_architecture_compliance(
            requirement, architecture_context,
        )
        if arch_lines:
            lines.extend(arch_lines)

        lines.append("## Files to Check")

        for f in implementation.files_changed:
            lines.append(f"- {f}")

        lines.extend([
            "",
            "## Instructions",
            "1. Read each file listed above",
            "2. Check that the implementation matches the description",
            "3. Check that the verification criteria are satisfied",
            "4. Run any verification commands if specified",
        ])
        if architecture_context:
            lines.append(
                "5. Check that the implementation respects the architecture "
                "decisions and design principles listed above"
            )

        lines.extend([
            "",
            "## Output",
            "On the FINAL line, output exactly ONE of:",
            "- VERIFY_PASS — if all criteria are satisfied",
            "- VERIFY_FAIL: [specific issues] — if criteria are NOT satisfied",
        ])

        return "\n".join(lines)

    @staticmethod
    def _build_architecture_compliance(
        requirement: FindOutput,
        architecture_context: dict[str, Any] | None,
    ) -> list[str]:
        """Build the optional Architecture Compliance prompt section."""
        if not architecture_context:
            return []

        lines: list[str] = ["## Architecture Compliance", ""]
        lines.append(
            "In addition to functional correctness, verify that the "
            "implementation conforms to these architecture decisions:"
        )
        lines.append("")

        # Relevant ADRs
        all_adrs: dict[str, str] = architecture_context.get("adrs", {})
        if requirement.related_adrs and all_adrs:
            for adr_id in requirement.related_adrs:
                text = all_adrs.get(adr_id, "")
                if text:
                    lines.append(f"- {adr_id}: {text}")

        # Design principles
        principles: list[str] = architecture_context.get("design_principles", [])
        if principles:
            lines.append("")
            lines.append("**Design Principles**:")
            for p in principles:
                lines.append(f"- {p}")

        lines.append("")
        return lines

    @staticmethod
    def extract_lesson(
        verify_output: "VerifyOutput",
        retries_used: int,
    ) -> str | None:
        """Extract a lesson string from a verification outcome.

        Returns:
            A lesson string if there is something to learn, or ``None``
            if the requirement passed on the first try.
        """
        req_id = verify_output.requirement_id
        feedback_first_line = (
            verify_output.feedback.split("\n", 1)[0].strip()
            if verify_output.feedback
            else ""
        )

        if verify_output.passed and retries_used > 0:
            return (
                f"{req_id}: Fixed after {retries_used} "
                f"{'retry' if retries_used == 1 else 'retries'}. "
                f"Issue: {feedback_first_line}"
            )

        if not verify_output.passed:
            return (
                f"{req_id}: Failed. Issue: {feedback_first_line}"
            )

        # Passed on first try — no lesson to extract
        return None
