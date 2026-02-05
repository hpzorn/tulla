"""ImplementationLoop — custom orchestrator for Find-Implement-Verify loop.

Unlike the linear :class:`~tulla.core.pipeline.Pipeline` used by
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
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from tulla.config import TullaConfig
from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import PhaseFactPersister
from tulla.ports.claude import ClaudePort
from tulla.ports.ontology import OntologyPort

from .commit import CommitPhase
from .find import FindPhase
from .implement import ImplementPhase
from .models import (
    IterationFactRecord,
    IterationResult,
    LoopOutcome,
    LoopResult,
    RequirementStatus,
)
from .status import StatusPhase
from .verify import VerifyPhase

logger = logging.getLogger(__name__)


def _extract_verdict(feedback: str) -> str:
    """Extract the VERIFY_FAIL verdict line from verifier feedback."""
    for line in reversed(feedback.splitlines()):
        stripped = line.strip()
        if stripped.startswith("VERIFY_FAIL"):
            return stripped
    return feedback.splitlines()[-1].strip() if feedback.strip() else ""


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
        config: Tulla configuration.
        max_retries: Max verification retries per requirement.
        total_budget_usd: Total dollar budget for the loop.
        persister: Optional :class:`PhaseFactPersister` for writing
            iteration facts to the A-Box after each Status step.
        bootstrap_predecessor: Phase id used as the predecessor for
            the first iteration (default ``"p6"``).
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
        config: TullaConfig,
        max_retries: int = 2,
        total_budget_usd: float = 10.0,
        persister: PhaseFactPersister | None = None,
        bootstrap_predecessor: str = "p6",
    ) -> None:
        self._claude = claude_port
        self._ontology = ontology_port
        self._project_root = project_root
        self._prd_context = prd_context
        self._config = config
        self._max_retries = max_retries
        self._total_budget_usd = total_budget_usd
        self._persister = persister
        self._bootstrap_predecessor = bootstrap_predecessor

        # Instantiate loop steps with config-driven thresholds
        impl_cfg = config.implementation
        self._find = FindPhase(
            max_files_per_requirement=impl_cfg.max_files_per_requirement,
            min_wpf_advisory=impl_cfg.min_wpf_advisory,
            ontology_query_limit=impl_cfg.ontology_query_limit,
        )
        self._implement = ImplementPhase(
            timeout_s=impl_cfg.phase_timeouts.get("implement", 3600.0),
            apf_target=(impl_cfg.apf_min, impl_cfg.apf_max),
        )
        self._commit = CommitPhase()
        self._verify = VerifyPhase(
            timeout_s=impl_cfg.phase_timeouts.get("verify", 600.0),
            apf_target=(impl_cfg.apf_min, impl_cfg.apf_max),
            novel_word_threshold=impl_cfg.novel_word_threshold,
            verbose_word_limit=impl_cfg.verbose_word_limit,
        )
        self._status = StatusPhase()

        # Architecture context and lessons (loaded once at loop start)
        self._architecture_context: dict[str, Any] | None = None
        self._lessons: list[str] = []

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
    # Console logging helpers (bash-style timestamped output to stderr)
    # ------------------------------------------------------------------

    @staticmethod
    def _log(msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"[{ts}] {msg}", err=True)
        logger.info(msg)

    @staticmethod
    def _separator() -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"[{ts}] {'=' * 46}", err=True)

    # ------------------------------------------------------------------
    # Architecture & Lessons loading
    # ------------------------------------------------------------------

    def _load_architecture_and_lessons(self) -> None:
        """Load architecture context and lessons from the ontology once.

        Populates ``self._architecture_context`` and ``self._lessons``.
        Tolerates missing data gracefully (empty dicts/lists).
        """
        # Derive idea id from prd_context ("prd-idea-54" → "54")
        idea_id = self._prd_context.removeprefix("prd-idea-")
        arch_context = f"arch-idea-{idea_id}"
        lesson_context = f"lesson-idea-{idea_id}"

        # --- Quality goals ---
        qg_facts = self._ontology.recall_facts(
            predicate="arch:qualityGoal",
            context=arch_context,
        )
        quality_goals = [
            f.get("object", "")
            for f in qg_facts.get("result", [])
            if f.get("object")
        ]

        # --- Design principles ---
        dp_facts = self._ontology.recall_facts(
            predicate="arch:designPrinciple",
            context=arch_context,
        )
        design_principles = [
            f.get("object", "")
            for f in dp_facts.get("result", [])
            if f.get("object")
        ]

        # --- ADRs ---
        adr_facts = self._ontology.recall_facts(
            predicate="arch:decision",
            context=arch_context,
        )
        adrs: dict[str, str] = {}
        for f in adr_facts.get("result", []):
            subj = f.get("subject", "")
            obj = f.get("object", "")
            if subj and obj:
                adrs[subj] = obj

        if quality_goals or design_principles or adrs:
            self._architecture_context = {
                "quality_goals": quality_goals,
                "design_principles": design_principles,
                "adrs": adrs,
            }
            logger.info(
                "Loaded architecture context: %d goals, %d principles, %d ADRs",
                len(quality_goals),
                len(design_principles),
                len(adrs),
            )
        else:
            logger.info("No architecture context found in %s", arch_context)

        # --- Lessons ---
        self._lessons = self._find.load_lessons(self._ontology, lesson_context)
        if self._lessons:
            logger.info("Loaded %d lessons from %s", len(self._lessons), lesson_context)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> LoopResult:
        """Execute the implementation loop until all requirements are done.

        Returns a :class:`LoopResult` summarising all iterations.
        """
        # --- Startup banner ---
        self._separator()
        self._log("Implementation-Tulla starting")
        self._log(f"PRD Context: {self._prd_context}")
        self._log(f"Budget: ${self._total_budget_usd:.2f} USD")
        self._log(f"Max retries: {self._max_retries}")

        # Load architecture context and lessons once before the loop
        self._load_architecture_and_lessons()

        arch = self._architecture_context
        if arch:
            self._log(
                f"Architecture: {len(arch['quality_goals'])} goals, "
                f"{len(arch['design_principles'])} principles, "
                f"{len(arch['adrs'])} ADRs"
            )
        if self._lessons:
            self._log(f"Lessons loaded: {len(self._lessons)}")
        self._separator()

        loop_result = LoopResult()
        budget_remaining = self._total_budget_usd
        req_counter = 0

        while True:
            # Budget guard
            if budget_remaining <= 0:
                self._log("BUDGET EXHAUSTED — stopping loop")
                logger.warning("Budget exhausted, stopping loop")
                iteration = IterationResult(
                    outcome=LoopOutcome.BUDGET_EXHAUSTED,
                    error="Budget exhausted",
                )
                loop_result.iterations.append(iteration)
                break

            req_counter += 1
            self._separator()
            self._log(f"=== Requirement {req_counter} ===")
            self._separator()

            # --- FIND ---
            self._log("--- Phase 1: Finding next ready requirement ---")
            find_output = self._find.execute(
                ontology=self._ontology,
                prd_context=self._prd_context,
            )

            if find_output.all_complete:
                self._log("All requirements complete")
                logger.info("All requirements complete")
                iteration = IterationResult(
                    outcome=LoopOutcome.ALL_COMPLETE,
                    find=find_output,
                )
                loop_result.iterations.append(iteration)
                loop_result.all_complete = True
                break

            req_id = find_output.requirement_id or "unknown"
            self._log(f"Found: {req_id} — {find_output.title}")
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
            last_failure_feedback = ""  # Track failure feedback for lessons

            for attempt in range(1 + self._max_retries):
                self._log(
                    f"--- Attempt {attempt + 1} of {1 + self._max_retries}"
                    f" for {req_id} ---"
                )

                # IMPLEMENT
                self._log(f"--- Phase 2: Implementing {req_id} ---")
                impl_output = self._implement.execute(
                    claude=self._claude,
                    requirement=find_output,
                    budget_usd=budget_remaining,
                    feedback=feedback,
                    architecture_context=self._architecture_context,
                    lessons=self._lessons or None,
                )
                budget_remaining -= impl_output.cost_usd
                loop_result.total_cost_usd += impl_output.cost_usd
                iteration.implement = impl_output

                # COMMIT
                self._log(f"--- Phase 3: Committing {req_id} ---")
                commit_output = self._commit.execute(
                    requirement=find_output,
                    project_root=self._project_root,
                )
                iteration.commit = commit_output

                # VERIFY
                self._log(f"--- Phase 4: Verifying {req_id} ---")
                verify_output = self._verify.execute(
                    claude=self._claude,
                    requirement=find_output,
                    implementation=impl_output,
                    budget_usd=budget_remaining,
                    architecture_context=self._architecture_context,
                )
                budget_remaining -= verify_output.cost_usd
                loop_result.total_cost_usd += verify_output.cost_usd
                iteration.verify = verify_output

                if verify_output.passed:
                    self._log(f"VERIFY_PASS: {req_id}")
                    iteration.outcome = LoopOutcome.IMPLEMENTED
                    iteration.retries_used = attempt
                    break

                # Verification failed — retry with feedback
                feedback = verify_output.feedback
                last_failure_feedback = feedback  # Preserve for lesson
                verdict = _extract_verdict(feedback)
                self._log(
                    f"VERIFY_FAIL: {req_id} (attempt {attempt + 1}"
                    f"/{1 + self._max_retries})"
                )
                self._log(f"Verdict: {verdict}")
                logger.warning(
                    "Verification failed for %s (attempt %d/%d): %s",
                    req_id,
                    attempt + 1,
                    1 + self._max_retries,
                    verdict,
                )
                iteration.retries_used = attempt + 1

            else:
                # All retries exhausted
                iteration.outcome = LoopOutcome.VERIFY_FAILED
                self._log(
                    f"BLOCKED: {req_id} — verification failed after"
                    f" {1 + self._max_retries} attempts"
                )
                logger.error(
                    "Verification failed after %d attempts for %s",
                    1 + self._max_retries,
                    req_id,
                )

            # --- Store lesson after verify ---
            if iteration.verify is not None:
                lesson = VerifyPhase.extract_lesson(
                    iteration.verify,
                    iteration.retries_used,
                    failure_feedback=last_failure_feedback,
                )
                if lesson:
                    self._store_lesson(lesson)

            # --- STATUS ---
            self._log(f"--- Phase 5: Marking {req_id} status ---")
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

            # --- PERSIST iteration facts ---
            if self._persister is not None:
                self._persist_iteration_facts(iteration, req_counter)

            loop_result.iterations.append(iteration)

            spent = self._total_budget_usd - budget_remaining
            status_label = "Completed" if new_status == RequirementStatus.COMPLETE else "BLOCKED"
            self._log(
                f"{status_label}: {req_id}"
                f" (${spent:.2f} spent, ${budget_remaining:.2f} remaining)"
            )

        # --- Final summary ---
        self._separator()
        self._log("Implementation-Tulla finished")
        self._log(
            f"Requirements completed: {loop_result.requirements_completed},"
            f" blocked: {loop_result.requirements_blocked}"
        )
        self._log(f"Total cost: ${loop_result.total_cost_usd:.2f}")
        self._log(f"Budget remaining: ${budget_remaining:.2f}")
        self._separator()

        return loop_result

    def _persist_iteration_facts(
        self, iteration: IterationResult, iteration_number: int,
    ) -> None:
        """Persist an IterationFactRecord after the Status step."""
        phase_id = f"p6-iter-{iteration_number}"
        if iteration_number == 1:
            predecessor = self._bootstrap_predecessor
        else:
            predecessor = f"p6-iter-{iteration_number - 1}"

        record = IterationFactRecord(
            requirement_id=iteration.requirement_id or "",
            quality_focus=(
                iteration.find.quality_focus
                if iteration.find is not None
                else ""
            ),
            passed=(
                iteration.verify.passed
                if iteration.verify is not None
                else False
            ),
            feedback=(
                iteration.verify.feedback
                if iteration.verify is not None
                else ""
            ),
            commit_hash=(
                iteration.commit.commit_hash
                if iteration.commit is not None
                else ""
            ),
        )

        idea_id = self._prd_context.removeprefix("prd-idea-")
        phase_result: PhaseResult[IterationFactRecord] = PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=record,
        )

        try:
            self._persister.persist(  # type: ignore[union-attr]
                idea_id=idea_id,
                phase_id=phase_id,
                phase_result=phase_result,
                predecessor_phase_id=predecessor,
                shacl_shape_id=None,
            )
            logger.info("Persisted iteration facts for %s", phase_id)
        except Exception:
            logger.warning(
                "Failed to persist iteration facts for %s",
                phase_id,
                exc_info=True,
            )

    def _store_lesson(self, lesson: str) -> None:
        """Store a lesson fact in the ontology and append to the local cache."""
        idea_id = self._prd_context.removeprefix("prd-idea-")
        lesson_context = f"lesson-idea-{idea_id}"
        try:
            self._ontology.store_fact(
                subject=f"lesson:{idea_id}",
                predicate="lesson:text",
                object=lesson,
                context=lesson_context,
            )
            self._lessons.append(lesson)
            logger.info("Stored lesson: %s", lesson)
        except Exception:
            logger.warning("Failed to store lesson: %s", lesson, exc_info=True)

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
