"""P6 Phase -- Hygiene & Pre-flight.

Implements the sixth planning sub-phase that runs the hygiene gate
before implementation begins.  Refactored from the standalone
``run_p6_phase()`` function into a ``P6Phase(Phase[P6Output])``
subclass that integrates the promoted hygiene framework from
``ralph.hygiene``.

The hygiene gate is called in ``validate_input()`` as a pre-step
before the (no-op) ``build_prompt()`` / ``run_claude()`` path,
since P6 does not require LLM interaction -- it is purely
mechanical cleanup.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Sequence

from ralph.core.phase import Phase, PhaseContext
from ralph.hygiene import (
    HygieneMode,
    hygiene_gate,
    install_trap_handler,
    log_preflight_decision,
)
from ralph.hygiene.gate import GateResult

from .models import P6Output


logger = logging.getLogger(__name__)

# Script identity constant (preserved from the original run_p6_phase).
SCRIPT_NAME: str = "planning-ralph"


class P6Phase(Phase[P6Output]):
    """P6: Hygiene & Pre-flight phase.

    Runs the hygiene gate as a pre-step (via :meth:`validate_input`),
    storing the result so that :meth:`parse_output` can wrap it into a
    :class:`P6Output`.  The ``build_prompt`` / ``run_claude`` path
    is a no-op because P6 does not require LLM interaction.

    Constructor Args:
        work_dirs: Directories to inspect/clean.  Falls back to
            ``[ctx.work_dir]`` if not provided.
        argv: CLI arguments to parse for hygiene flags
            (``--clean``, ``--no-clean``, ``--check``).
        stale_threshold_secs: Age threshold (seconds) for stale file
            detection.  Defaults to 3600 (1 hour).
    """

    phase_id: str = "p6"
    timeout_s: float = 60.0  # 1 minute -- hygiene is fast

    def __init__(
        self,
        work_dirs: Sequence[Path] | None = None,
        argv: Sequence[str] | None = None,
        stale_threshold_secs: int = 3600,
    ) -> None:
        super().__init__()
        self._work_dirs: list[Path] = list(work_dirs) if work_dirs else []
        self._argv: list[str] = list(argv) if argv else []
        self._stale_threshold_secs = stale_threshold_secs
        # Populated during validate_input, consumed by parse_output.
        self._gate_result: GateResult | None = None
        self._cleanup: Any = None

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def validate_input(self, ctx: PhaseContext) -> None:
        """Run the hygiene gate as a pre-step before the main phase body.

        The gate parses ``--clean`` / ``--no-clean`` / ``--check`` from
        the configured argv, dispatches to the appropriate hygiene path,
        and stores the result for later consumption by ``parse_output``.

        A signal trap handler is also installed for clean exit logging.
        """
        work_dirs = self._work_dirs if self._work_dirs else [ctx.work_dir]

        logger.info("[P6] Running hygiene gate with work_dirs=%s", work_dirs)

        # Install trap handler for clean exit logging.
        captured_exit_code: list[int] = []

        def _capture_exit(code: int) -> None:
            captured_exit_code.append(code)

        self._cleanup = install_trap_handler(
            script_name=SCRIPT_NAME,
            exit_func=_capture_exit,
        )

        # Run the hygiene gate.  We provide a non-exiting exit_func so
        # that the phase framework stays in control during CHECK mode.
        self._gate_result = hygiene_gate(
            script_name=SCRIPT_NAME,
            work_dirs=list(work_dirs),
            argv=self._argv,
            stale_threshold_secs=self._stale_threshold_secs,
            exit_func=_capture_exit,
        )

        # Log the pre-flight decision.
        log_preflight_decision(
            script_name=SCRIPT_NAME,
            config=self._gate_result.config,
            work_dirs=list(work_dirs),
            argv=self._argv,
        )

        if captured_exit_code:
            logger.info(
                "[P6] Check mode completed with exit code %d",
                captured_exit_code[0],
            )

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Return an empty prompt -- P6 does not invoke Claude."""
        return ""

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return an empty tool list -- P6 does not invoke Claude."""
        return []

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """No-op -- P6 does not require LLM interaction.

        Returns the gate result captured during ``validate_input``.
        """
        return self._gate_result

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P6Output:
        """Convert the hygiene gate result into a :class:`P6Output`.

        Args:
            ctx: The phase context.
            raw: The gate result stored during ``validate_input``.

        Returns:
            A P6Output summarising the hygiene run.
        """
        gate: GateResult | None = raw

        if gate is None:
            return P6Output(
                hygiene_report=None,
                mode="unknown",
                was_cleaned=False,
                was_skipped=True,
                remaining_args=[],
            )

        mode = gate.config.mode.value
        report = gate.report
        was_cleaned = report is not None and report.cleaned_count > 0
        was_skipped = gate.config.mode == HygieneMode.NO_CLEAN

        return P6Output(
            hygiene_report=report,
            mode=mode,
            was_cleaned=was_cleaned,
            was_skipped=was_skipped,
            remaining_args=list(gate.remaining_args),
        )

    def get_timeout_seconds(self) -> float:
        """Return the P6 timeout in seconds (1 minute)."""
        return self.timeout_s
