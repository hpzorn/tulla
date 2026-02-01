"""ImplementationLoop — custom orchestrator for Find-Implement-Verify loop.

Unlike the linear :class:`~ralph.core.pipeline.Pipeline` used by
Discovery, Planning, and Research, the Implementation phase uses a
loop-based architecture:

    Find → (no req? → ALL_COMPLETE → exit)
         → Implement → Commit → Verify
         → (fail? → retry with feedback up to max_retries)
         → Status (Complete/Blocked)
         → loop back to Find
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import click

from ralph.config import RalphConfig
from ralph.ports.claude import ClaudePort
from ralph.ports.ontology import OntologyPort

from .commit import CommitPhase
from .find import FindPhase
from .implement import ImplementPhase
from .models import (
    IterationResult,
    LoopOutcome,
    LoopResult,
    RequirementStatus,
)
from .status import StatusPhase
from .verify import VerifyPhase

logger = logging.getLogger(__name__)


class ImplementationLoop:
    """Custom loop orchestrator for the Implementation phase.

    Repeatedly finds the next ready requirement, implements it,
    commits the changes, verifies against spec, and updates status.
    Continues until all requirements are complete or budget is exhausted.

    Parameters:
        claude_port: Claude invocation adapter.
        ontology_port: Ontology-server adapter.
        project_root: Root directory of the project.
        prd_context: Ontology context for PRD facts (e.g. ``"prd-idea-54"``).
        config: Ralph configuration.
        max_retries: Max verification retries per requirement.
        total_budget_usd: Total dollar budget for the loop.
    """

    # Step instances (shared across iterations)
    _find: FindPhase
    _implement: ImplementPhase
    _commit: CommitPhase
    _verify: VerifyPhase
    _status: StatusPhase

    def __init__(
        self,
        claude_port: ClaudePort,
        ontology_port: OntologyPort,
        project_root: Path,
        prd_context: str,
        config: RalphConfig,
        max_retries: int = 2,
        total_budget_usd: float = 10.0,
    ) -> None:
        self._claude = claude_port
        self._ontology = ontology_port
        self._project_root = project_root
        self._prd_context = prd_context
        self._config = config
        self._max_retries = max_retries
        self._total_budget_usd = total_budget_usd

        # Instantiate loop steps
        self._find = FindPhase()
        self._implement = ImplementPhase()
        self._commit = CommitPhase()
        self._verify = VerifyPhase()
        self._status = StatusPhase()

    # ------------------------------------------------------------------
    # Properties (for dry-run introspection)
    # ------------------------------------------------------------------

    @property
    def phases(self) -> list[tuple[str, Any]]:
        """Return the loop steps as (id, phase) pairs for display."""
        return [
            ("find", self._find),
            ("implement", self._implement),
            ("commit", self._commit),
            ("verify", self._verify),
            ("status", self._status),
        ]

    @property
    def total_budget_usd(self) -> float:
        """Total budget for this loop run."""
        return self._total_budget_usd

    @property
    def max_retries(self) -> int:
        """Max verification retries per requirement."""
        return self._max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> LoopResult:
        """Execute the implementation loop until all requirements are done.

        Returns a :class:`LoopResult` summarising all iterations.
        """
        loop_result = LoopResult()
        budget_remaining = self._total_budget_usd

        while True:
            # Budget guard
            if budget_remaining <= 0:
                logger.warning("Budget exhausted, stopping loop")
                iteration = IterationResult(
                    outcome=LoopOutcome.BUDGET_EXHAUSTED,
                    error="Budget exhausted",
                )
                loop_result.iterations.append(iteration)
                break

            # --- FIND ---
            find_output = self._find.execute(
                ontology=self._ontology,
                prd_context=self._prd_context,
            )

            if find_output.all_complete:
                logger.info("All requirements complete")
                iteration = IterationResult(
                    outcome=LoopOutcome.ALL_COMPLETE,
                    find=find_output,
                )
                loop_result.iterations.append(iteration)
                loop_result.all_complete = True
                break

            req_id = find_output.requirement_id or "unknown"
            logger.info("Found requirement: %s — %s", req_id, find_output.title)

            # Mark as in-progress
            self._status.execute(
                ontology=self._ontology,
                requirement_id=req_id,
                new_status=RequirementStatus.IN_PROGRESS,
                prd_context=self._prd_context,
            )

            # --- IMPLEMENT → COMMIT → VERIFY (with retries) ---
            iteration = IterationResult(
                requirement_id=req_id,
                outcome=LoopOutcome.IMPLEMENTED,
                find=find_output,
            )
            feedback = ""

            for attempt in range(1 + self._max_retries):
                # IMPLEMENT
                impl_output = self._implement.execute(
                    claude=self._claude,
                    requirement=find_output,
                    budget_usd=budget_remaining,
                    feedback=feedback,
                )
                budget_remaining -= impl_output.cost_usd
                loop_result.total_cost_usd += impl_output.cost_usd
                iteration.implement = impl_output

                # COMMIT
                commit_output = self._commit.execute(
                    requirement=find_output,
                    project_root=self._project_root,
                )
                iteration.commit = commit_output

                # VERIFY
                verify_output = self._verify.execute(
                    claude=self._claude,
                    requirement=find_output,
                    implementation=impl_output,
                    budget_usd=budget_remaining,
                )
                budget_remaining -= verify_output.cost_usd
                loop_result.total_cost_usd += verify_output.cost_usd
                iteration.verify = verify_output

                if verify_output.passed:
                    iteration.outcome = LoopOutcome.IMPLEMENTED
                    iteration.retries_used = attempt
                    break

                # Verification failed — retry with feedback
                feedback = verify_output.feedback
                logger.warning(
                    "Verification failed for %s (attempt %d/%d): %s",
                    req_id,
                    attempt + 1,
                    1 + self._max_retries,
                    feedback[:200],
                )
                iteration.retries_used = attempt + 1

            else:
                # All retries exhausted
                iteration.outcome = LoopOutcome.VERIFY_FAILED
                logger.error(
                    "Verification failed after %d attempts for %s",
                    1 + self._max_retries,
                    req_id,
                )

            # --- STATUS ---
            if iteration.outcome == LoopOutcome.IMPLEMENTED:
                new_status = RequirementStatus.COMPLETE
                loop_result.requirements_completed += 1
            else:
                new_status = RequirementStatus.BLOCKED
                loop_result.requirements_blocked += 1

            status_output = self._status.execute(
                ontology=self._ontology,
                requirement_id=req_id,
                new_status=new_status,
                prd_context=self._prd_context,
            )
            iteration.status = status_output
            loop_result.iterations.append(iteration)

        return loop_result

    # ------------------------------------------------------------------
    # Dry-run display
    # ------------------------------------------------------------------

    def show_dry_run(
        self,
        idea_id: int,
        work_dir: Path,
    ) -> None:
        """Print the loop execution plan without running anything."""
        click.echo("=== Dry-run plan ===")
        click.echo(f"Agent:      implementation")
        click.echo(f"Idea:       {idea_id}")
        click.echo(f"Work dir:   {work_dir}")
        click.echo(f"PRD context: {self._prd_context}")
        click.echo(f"Budget:     ${self._total_budget_usd:.2f} USD")
        click.echo(f"Max retries: {self._max_retries}")
        click.echo()
        click.echo("Loop steps (repeated per requirement):")
        click.echo("  → find       (FindPhase)       — query ontology for next READY req")
        click.echo("  → implement  (ImplementPhase)  — Claude with acceptEdits")
        click.echo("  → commit     (CommitPhase)     — git commit (no Claude)")
        click.echo("  → verify     (VerifyPhase)     — Claude verifies against spec")
        click.echo("  → status     (StatusPhase)     — update ontology status")
        click.echo()
        click.echo("Flow:")
        click.echo("  Find → no req? → ALL_COMPLETE → exit")
        click.echo("       → Implement → Commit → Verify")
        click.echo(f"       → fail? → retry with feedback (up to {self._max_retries}x)")
        click.echo("       → Status (Complete/Blocked) → loop to Find")
        click.echo()
        click.echo("No steps will be executed (dry-run).")
