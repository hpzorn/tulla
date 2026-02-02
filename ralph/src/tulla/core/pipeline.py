"""Pipeline executor for sequential phase execution with checkpoint/resume."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tulla.core.checkpoint import CheckpointStore
from tulla.core.phase import Phase, PhaseContext, PhaseResult, PhaseStatus


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Aggregate result of a full pipeline run.

    Attributes:
        phase_results: Ordered list of (phase_id, PhaseResult) pairs.
        total_cost_usd: Sum of cost_usd across all executed phases.
        final_status: Overall pipeline outcome.
    """

    phase_results: list[tuple[str, PhaseResult[Any]]] = field(
        default_factory=list,
    )
    total_cost_usd: float = 0.0
    final_status: PhaseStatus = PhaseStatus.SUCCESS


# ---------------------------------------------------------------------------
# Pipeline executor
# ---------------------------------------------------------------------------


class Pipeline:
    """Sequential phase executor with checkpoint/resume and budget tracking.

    Parameters:
        phases: Ordered list of ``(phase_id, Phase)`` pairs.
        claude_port: Claude invocation port (unused directly by pipeline
            but threaded into config for phases).
        work_dir: Scratch directory for this run; also used by
            :class:`CheckpointStore`.
        idea_id: Identifier of the idea being processed.
        config: Arbitrary configuration dict forwarded to phases.
        total_budget_usd: Dollar budget for the entire pipeline run.
    """

    def __init__(
        self,
        phases: list[tuple[str, Phase[Any]]],
        claude_port: Any,
        work_dir: Path,
        idea_id: str,
        config: dict[str, Any] | None = None,
        total_budget_usd: float = 0.0,
    ) -> None:
        self._phases = phases
        self._claude_port = claude_port
        self._work_dir = work_dir
        self._idea_id = idea_id
        self._config = config or {}
        self._total_budget_usd = total_budget_usd
        self._checkpoint = CheckpointStore(work_dir)
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, start_from: str | None = None) -> PipelineResult:
        """Execute the pipeline, optionally resuming from *start_from*.

        Phases before *start_from* are skipped (their checkpoint results
        are loaded instead).  Execution stops immediately when a phase
        returns a non-SUCCESS status.

        Returns a :class:`PipelineResult` summarising the run.
        """
        result = PipelineResult()
        budget_remaining = self._total_budget_usd
        skipping = start_from is not None
        prev_output: Any = None

        for phase_id, phase in self._phases:
            # --- Skip phases before start_from --------------------------
            if skipping:
                if phase_id == start_from:
                    skipping = False
                else:
                    # Load checkpoint for skipped phase so we can chain
                    # outputs forward.
                    saved = self._checkpoint.load(phase_id)
                    if saved is not None:
                        prev_output = saved.get("data")
                    continue

            # --- Budget guard -------------------------------------------
            if budget_remaining <= 0:
                self._logger.warning(
                    "Budget exhausted before phase %s", phase_id,
                )
                result.final_status = PhaseStatus.FAILURE
                break

            # --- Build context ------------------------------------------
            ctx = PhaseContext(
                idea_id=self._idea_id,
                work_dir=self._work_dir,
                config={
                    **self._config,
                    "claude_port": self._claude_port,
                    "prev_output": prev_output,
                },
                budget_remaining_usd=budget_remaining,
                logger=self._logger,
            )

            # --- Execute phase ------------------------------------------
            phase_result = phase.execute(ctx)
            result.phase_results.append((phase_id, phase_result))

            # --- Record cost --------------------------------------------
            cost = phase_result.metadata.get("cost_usd", 0.0)
            result.total_cost_usd += cost
            budget_remaining -= cost

            # --- Save checkpoint ----------------------------------------
            self._checkpoint.save(phase_id, phase_result.to_dict())

            # --- Stop on failure ----------------------------------------
            if phase_result.status != PhaseStatus.SUCCESS:
                result.final_status = phase_result.status
                break

            # --- Chain output forward -----------------------------------
            prev_output = phase_result.data

        return result
