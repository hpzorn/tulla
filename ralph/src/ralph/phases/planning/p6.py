"""Apply hygiene to planning-ralph P6 phase.

Integrates the ralph.hygiene shared library into the planning-ralph
script's P6 (pre-flight / post-flight) phase. This module provides:

- A ``run_p6_phase`` entry point that wires together the full hygiene
  subsystem: argument parsing, trap handler installation, pre-flight
  gate, startup decision logging, and cleanup.
- A ``P6PhaseResult`` dataclass capturing the outcome for downstream
  phases to inspect.

The P6 phase is the first phase of planning-ralph to execute and
ensures the workspace is in a clean, known-good state before any
planning logic runs.

Usage::

    from ralph.phases.planning.p6 import run_p6_phase
    from pathlib import Path

    result = run_p6_phase(
        work_dirs=[Path("./work")],
        argv=["--clean", "--rounds", "3"],
    )
    # result.remaining_args == ["--rounds", "3"]
    # result.gate_result contains the GateResult from hygiene_gate
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from ralph.hygiene import (
    GateResult,
    HygieneReport,
    PreflightDecision,
    hygiene_gate,
    inject_hygiene_help,
    install_trap_handler,
    log_preflight_decision,
)

logger = logging.getLogger(__name__)

# Script identity constants.
SCRIPT_NAME: str = "planning-ralph"
SCRIPT_DESCRIPTION: str = (
    "Planning-Ralph: ontology-driven planning agent with hygiene support."
)

# Default work directories for planning-ralph relative to CWD.
DEFAULT_WORK_DIRS: list[Path] = [Path("./work")]


@dataclass(frozen=True)
class P6PhaseResult:
    """Outcome of the P6 (hygiene) phase for planning-ralph.

    Attributes:
        gate_result: The control flow gate result from the hygiene subsystem.
            Contains the resolved config, optional report, and remaining args.
        decision: The structured pre-flight decision record that was logged.
        remaining_args: CLI arguments not consumed by hygiene, passed through
            to subsequent planning-ralph phases.
        cleanup: Callable to invoke at script exit. Restores signal handlers
            and logs clean shutdown. Should be called in a ``finally`` block.
    """

    gate_result: GateResult
    decision: PreflightDecision
    remaining_args: list[str] = field(default_factory=list)
    cleanup: Callable[[], None] = field(default=lambda: None)

    @property
    def report(self) -> HygieneReport | None:
        """Shortcut to the hygiene report from the gate result."""
        return self.gate_result.report

    @property
    def was_cleaned(self) -> bool:
        """Whether pre-flight hygiene actually ran a cleanup."""
        return (
            self.gate_result.report is not None
            and self.gate_result.report.mode_used == "clean"
        )

    @property
    def was_skipped(self) -> bool:
        """Whether hygiene was explicitly disabled via --no-clean."""
        return self.gate_result.config.is_disabled

    def summary(self) -> str:
        """Return a human-readable summary of the P6 phase outcome."""
        mode = self.gate_result.config.mode.value
        if self.report is not None:
            return f"P6 phase complete: mode={mode}, {self.report.summary()}"
        return f"P6 phase complete: mode={mode}, hygiene skipped."


def _show_help_and_exit(
    exit_func: Callable[[int], object] | None = None,
) -> None:
    """Print the planning-ralph help text including hygiene options and exit.

    Args:
        exit_func: Callable to terminate the process. Defaults to sys.exit.
    """
    if exit_func is None:
        exit_func = sys.exit
    help_text = inject_hygiene_help(SCRIPT_NAME, SCRIPT_DESCRIPTION)
    print(help_text)
    exit_func(0)


def run_p6_phase(
    work_dirs: Sequence[Path] | None = None,
    argv: Sequence[str] | None = None,
    *,
    stale_threshold_secs: int = 3600,
    exit_func: Callable[[int], object] | None = None,
    output_stream: object | None = None,
) -> P6PhaseResult:
    """Execute the P6 (hygiene) phase of planning-ralph.

    This is the primary entry point that planning-ralph calls before
    any planning logic. It performs the following steps in order:

    1. Install a signal trap handler for clean exit logging.
    2. Run the hygiene gate (parses args, dispatches cleanup/check/skip).
    3. Log the pre-flight decision with structured metadata.
    4. Return the result for downstream phases.

    In ``--check`` mode, this function does NOT return -- the gate
    calls ``exit_func`` after printing the check report.

    Args:
        work_dirs: Directories to inspect/clean. Defaults to ``["./work"]``.
        argv: CLI arguments to parse. Defaults to ``sys.argv[1:]``.
        stale_threshold_secs: Age threshold (seconds) for stale file detection.
            Defaults to 3600 (1 hour).
        exit_func: Callable to terminate the process (used in check mode
            and help display). Defaults to ``sys.exit``.
        output_stream: File-like object for check-mode output.
            Defaults to ``sys.stdout``.

    Returns:
        A P6PhaseResult containing the gate result, decision log, remaining
        arguments, and a cleanup callable.
    """
    if work_dirs is None:
        work_dirs = DEFAULT_WORK_DIRS
    if exit_func is None:
        exit_func = sys.exit
    if output_stream is None:
        output_stream = sys.stdout

    resolved_argv = list(argv) if argv is not None else sys.argv[1:]

    # Check for --help before entering the gate.
    if "--help" in resolved_argv or "-h" in resolved_argv:
        _show_help_and_exit(exit_func=exit_func)

    logger.info("[%s] Starting P6 phase (hygiene).", SCRIPT_NAME)

    # Step 1: Install trap handler for clean exit logging.
    cleanup = install_trap_handler(
        script_name=SCRIPT_NAME,
        exit_func=exit_func,
    )
    logger.debug("[%s] Trap handler installed.", SCRIPT_NAME)

    # Step 2: Run the hygiene gate.
    gate_result = hygiene_gate(
        script_name=SCRIPT_NAME,
        work_dirs=list(work_dirs),
        argv=resolved_argv,
        stale_threshold_secs=stale_threshold_secs,
        exit_func=exit_func,
        output_stream=output_stream,
    )

    # Step 3: Log the pre-flight decision.
    decision = log_preflight_decision(
        script_name=SCRIPT_NAME,
        config=gate_result.config,
        work_dirs=list(work_dirs),
        argv=resolved_argv,
    )

    remaining = list(gate_result.remaining_args)
    logger.info(
        "[%s] P6 phase complete. Remaining args: %s",
        SCRIPT_NAME,
        remaining,
    )

    return P6PhaseResult(
        gate_result=gate_result,
        decision=decision,
        remaining_args=remaining,
        cleanup=cleanup,
    )
