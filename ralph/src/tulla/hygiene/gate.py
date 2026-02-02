"""Control flow gate for Ralph script hygiene.

Provides a single entry-point function that Ralph scripts call at
startup to handle all hygiene control flow before main logic executes.

The gate:
  1. Parses --clean / --no-clean / --check from CLI arguments.
  2. Dispatches to the correct hygiene path based on the resolved mode:
     - CHECK  -> run dry-run inspection, print report, exit with status code.
     - CLEAN  -> run pre-flight cleanup, log results, proceed.
     - NO_CLEAN -> skip hygiene entirely, proceed.
  3. Returns remaining (non-hygiene) arguments and the hygiene report
     so the calling script can continue with its own argument parsing.

Usage in a Ralph script::

    from ralph.hygiene import hygiene_gate

    def main() -> None:
        result = hygiene_gate(
            script_name="research-ralph",
            work_dirs=[Path("./work")],
        )
        remaining_args = result.remaining_args
        ...
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from ralph.hygiene.args import HygieneConfig, HygieneMode, parse_hygiene_args
from ralph.hygiene.check import run_check_mode_cli
from ralph.hygiene.preflight import (
    DEFAULT_STALE_THRESHOLD_SECS,
    HygieneReport,
    run_preflight_hygiene,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GateResult:
    """Result returned when the hygiene gate allows the script to proceed.

    Attributes:
        config: The resolved hygiene configuration.
        report: The hygiene report from pre-flight (None if hygiene was skipped).
        remaining_args: CLI arguments not consumed by hygiene parsing,
            available for the host script's own argument parser.
    """

    config: HygieneConfig
    report: HygieneReport | None
    remaining_args: list[str] = field(default_factory=list)


def hygiene_gate(
    script_name: str,
    work_dirs: Sequence[Path],
    argv: Sequence[str] | None = None,
    stale_threshold_secs: int = DEFAULT_STALE_THRESHOLD_SECS,
    *,
    exit_func: object | None = None,
    output_stream: object | None = None,
) -> GateResult:
    """Run the hygiene control flow gate at script startup.

    This is the main entry point that every Ralph script should call
    before executing its core logic. It handles argument parsing,
    mode dispatch, and (in check mode) process termination.

    Args:
        script_name: Name of the calling script (used in log messages).
        work_dirs: Directories to inspect/clean during pre-flight hygiene.
        argv: CLI arguments to parse. Defaults to sys.argv[1:].
        stale_threshold_secs: Age threshold for stale file detection.
        exit_func: Callable to terminate the process in check mode.
            Defaults to sys.exit. Accepts an int exit code.
        output_stream: File-like object for check-mode output.
            Defaults to sys.stdout.

    Returns:
        A GateResult if the script should proceed (CLEAN or NO_CLEAN mode).
        Does not return in CHECK mode (calls exit_func instead).

    Raises:
        SystemExit: In CHECK mode, exits with code 0 (clean) or 1 (issues).
    """
    if exit_func is None:
        exit_func = sys.exit
    if output_stream is None:
        output_stream = sys.stdout

    # Step 1: Parse hygiene arguments.
    config = parse_hygiene_args(argv)
    logger.info(
        "[%s] Hygiene gate: mode=%s", script_name, config.mode.value,
    )

    # Step 2: Dispatch based on mode.
    if config.is_check_only:
        # CHECK mode: run inspection, print report, and exit.
        logger.info("[%s] Entering check mode -- will exit after report.", script_name)
        exit_code = run_check_mode_cli(
            directories=list(work_dirs),
            stale_threshold_secs=stale_threshold_secs,
            output_stream=output_stream,
        )
        exit_func(exit_code)  # type: ignore[operator]
        # Unreachable in production, but allows tests with non-exiting exit_func.
        return GateResult(
            config=config,
            report=None,
            remaining_args=list(config.remaining_args),
        )

    if config.is_disabled:
        # NO_CLEAN mode: skip hygiene entirely.
        logger.info("[%s] Hygiene disabled (--no-clean), skipping.", script_name)
        return GateResult(
            config=config,
            report=None,
            remaining_args=list(config.remaining_args),
        )

    # CLEAN mode: run pre-flight hygiene, log results, proceed.
    logger.info("[%s] Running pre-flight hygiene cleanup.", script_name)
    report = run_preflight_hygiene(
        config=config,
        directories=list(work_dirs),
        stale_threshold_secs=stale_threshold_secs,
    )
    logger.info("[%s] %s", script_name, report.summary())

    return GateResult(
        config=config,
        report=report,
        remaining_args=list(config.remaining_args),
    )
