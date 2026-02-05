"""VerifyPhase — Claude verifies implementation against spec.

Part of the Implementation loop. This phase invokes Claude to verify
that the implementation satisfies the requirement's verification
criteria.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from tulla.annotations import ANNOTATION_REGEX, APF_TARGET
from tulla.phases.implementation.import_graph import LAYER_RULES
from tulla.ports.claude import ClaudePort, ClaudeRequest

from .models import FindOutput, ImplementOutput, VerifyOutput

logger = logging.getLogger(__name__)


def _extract_verdict(feedback: str) -> str:
    """Extract the VERIFY_FAIL verdict line from verifier feedback."""
    for line in reversed(feedback.splitlines()):
        stripped = line.strip()
        if stripped.startswith("VERIFY_FAIL"):
            return stripped
    return feedback.splitlines()[-1].strip() if feedback.strip() else ""


def _strip_prefix(identifier: str) -> str:
    """Strip a namespace prefix like ``isaqb:`` from an identifier.

    Returns the part after the last ``:`` or the original string if no
    colon is present.  Used to map resolved pattern identifiers (e.g.
    ``isaqb:PortsAndAdapters``) to :data:`import_graph.LAYER_RULES` keys.
    """
    return identifier.rsplit(":", 1)[-1] if ":" in identifier else identifier


class VerifyPhase:
    """Invoke Claude to verify an implementation against its spec.

    Builds a verification prompt from the requirement's verification
    criteria and asks Claude to check the implementation.
    """

    phase_id: str = "verify"
    timeout_s: float = 600.0  # 10 minutes (class-level fallback)

    def __init__(
        self,
        timeout_s: float = 600.0,
        apf_target: tuple[int, int] = (2, 5),
        novel_word_threshold: int = 5,
        verbose_word_limit: int = 50,
    ) -> None:
        self.timeout_s = timeout_s
        self._apf_target = apf_target
        self._novel_word_threshold = novel_word_threshold
        self._verbose_word_limit = verbose_word_limit

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

        logger.debug("Claude prompt", extra={
            "phase_id": self.phase_id,
            "requirement_id": req_id,
            "prompt": prompt,
        })

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

        # --- Annotation Verification ---
        ann_lines = self._build_annotation_verification(
            requirement,
            apf_target=self._apf_target,
            novel_word_threshold=self._novel_word_threshold,
            verbose_word_limit=self._verbose_word_limit,
        )
        if ann_lines:
            lines.extend(ann_lines)

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
    def _build_annotation_verification(
        requirement: FindOutput,
        apf_target: tuple[int, int] = APF_TARGET,
        novel_word_threshold: int = 5,
        verbose_word_limit: int = 50,
    ) -> list[str]:
        """Build the optional Annotation Verification prompt section.

        Generates verification checks for annotations placed during
        implementation:

        - **Coverage check** — pattern checklist ensuring every resolved
          pattern/principle has at least one annotation.
        - **Density check** — APF (annotations-per-file) within the
          target range.
        - **Quality check** — detect hollow (restates identifier) and
          verbose (exceeds word limit) explanations.
        - **Structural import check** — for patterns that have layer
          rules in :data:`import_graph.LAYER_RULES`, verify that inner
          modules do not import outer modules.

        Returns an empty list when there are no resolved patterns or
        principles to verify.

        Architecture decision: arch:adr-65-4 (separate _build_ method)
        Architecture decision: arch:adr-65-5 (import-graph for structural only)
        """
        items = list(requirement.resolved_patterns) + list(requirement.resolved_principles)
        if not items:
            return []

        apf_lo, apf_hi = apf_target

        lines: list[str] = ["## Annotation Verification", ""]

        # --- Coverage check ---
        lines.append("### Coverage Check")
        lines.append("")
        lines.append(
            "Verify that each pattern/principle below has at least one "
            "annotation in the implementation files:"
        )
        lines.append("")
        for item in items:
            lines.append(f"- [ ] {item}")
        lines.append("")
        lines.append(
            "Annotations must match the format: "
            f"`{ANNOTATION_REGEX.pattern}`"
        )
        lines.append("")
        lines.append(
            "**Important**: For pure data-model files (e.g. `models.py`, files "
            "containing only Pydantic BaseModel subclasses or dataclasses), "
            "only require annotations for patterns/principles that are "
            "architecturally applicable to data definitions. Skip behavioral "
            "and orchestration patterns (e.g. PipesAndFilters, Blackboard, "
            "CQRS) that apply to pipeline or service code, not data models. "
            "A data-model file with 0 applicable patterns should pass coverage."
        )
        lines.append("")

        # --- Density check ---
        lines.append("### Density Check")
        lines.append("")
        lines.append(
            f"Verify that each implementation file has {apf_lo}-{apf_hi} "
            f"annotations per file (APF). Flag files outside this range."
        )
        lines.append("")

        # --- Quality check ---
        lines.append("### Quality Check")
        lines.append("")
        lines.append(
            "Check each annotation explanation for quality issues:"
        )
        lines.append("")
        lines.append(
            f"- **Hollow**: explanation restates the identifier without "
            f"adding code-specific detail (fewer than {novel_word_threshold} novel words)"
        )
        lines.append(
            f"- **Verbose**: explanation exceeds {verbose_word_limit} words"
        )
        lines.append("")
        lines.append(
            f"Each explanation should be adequate: concise, code-specific, "
            f"and between {novel_word_threshold} novel words and {verbose_word_limit} total words."
        )
        lines.append("")

        # --- Structural import check (only for applicable patterns) ---
        structural_patterns = [
            item for item in items
            if _strip_prefix(item) in LAYER_RULES
        ]
        if structural_patterns:
            lines.append("### Structural Import Check")
            lines.append("")
            lines.append(
                "For the following structural patterns, verify that inner-layer "
                "modules do not import from outer-layer modules:"
            )
            lines.append("")
            for sp in structural_patterns:
                pattern_key = _strip_prefix(sp)
                rules = LAYER_RULES[pattern_key]
                inner = ", ".join(sorted(rules.get("inner", set())))
                outer = ", ".join(sorted(rules.get("outer", set())))
                lines.append(
                    f"- **{sp}**: inner ({inner}) must NOT import "
                    f"from outer ({outer})"
                )
            lines.append("")

        return lines

    @staticmethod
    def extract_lesson(
        verify_output: "VerifyOutput",
        retries_used: int,
        failure_feedback: str = "",
    ) -> str | None:
        """Extract a lesson string from a verification outcome.

        Parameters:
            verify_output: The final verification output.
            retries_used: How many retries were needed.
            failure_feedback: Feedback from the failed attempts (preserved
                separately since verify_output.feedback is from the final
                successful verification when retries_used > 0).

        Returns:
            A lesson string if there is something to learn, or ``None``
            if the requirement passed on the first try.
        """
        req_id = verify_output.requirement_id

        if verify_output.passed and retries_used > 0:
            # Use preserved failure feedback, not the final (success) feedback
            feedback_verdict = (
                _extract_verdict(failure_feedback)
                if failure_feedback
                else ""
            )
            return (
                f"{req_id}: Fixed after {retries_used} "
                f"{'retry' if retries_used == 1 else 'retries'}. "
                f"Issue: {feedback_verdict}"
            )

        if not verify_output.passed:
            feedback_verdict = (
                _extract_verdict(verify_output.feedback)
                if verify_output.feedback
                else ""
            )
            return (
                f"{req_id}: Failed. Issue: {feedback_verdict}"
            )

        # Passed on first try — no lesson to extract
        return None
