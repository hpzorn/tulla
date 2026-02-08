"""Check mode function for Tulla script hygiene.

Provides a standalone entry point for running hygiene in check (dry-run)
mode. Inspects work directories and reports stale files without removing
them, returning structured results suitable for programmatic use or
direct CLI invocation with exit codes.

Exit code semantics:
    0 -- workspace is clean (no stale files found)
    1 -- issues found (stale files detected)

Integrates with:
    - tulla.hygiene.args for HygieneConfig / HygieneMode
    - tulla.hygiene.preflight for inspection and reporting
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Sequence

from tulla.hygiene.args import HygieneConfig, HygieneMode
from tulla.hygiene.preflight import (
    DEFAULT_STALE_THRESHOLD_SECS,
    HygieneReport,
    run_preflight_hygiene,
)

logger = logging.getLogger(__name__)


def run_check_mode(
    directories: Sequence[Path],
    stale_threshold_secs: int = DEFAULT_STALE_THRESHOLD_SECS,
) -> HygieneReport:
    """Run hygiene in check (dry-run) mode over the given directories.

    This is a convenience function that constructs a CHECK-mode
    HygieneConfig and delegates to run_preflight_hygiene. It
    guarantees no files are modified or removed.

    Args:
        directories: Work directories to inspect for stale files.
        stale_threshold_secs: Age threshold in seconds for considering
            lock/temp files stale. Defaults to 1 hour.

    Returns:
        A HygieneReport with inspection results (cleaned_files will
        always be empty in check mode).
    """
    config = HygieneConfig(
        mode=HygieneMode.CHECK,
        remaining_args=[],
    )
    return run_preflight_hygiene(
        config=config,
        directories=directories,
        stale_threshold_secs=stale_threshold_secs,
    )


def check_mode_exit_code(report: HygieneReport) -> int:
    """Determine the exit code for a check-mode report.

    Args:
        report: A HygieneReport from a check-mode run.

    Returns:
        0 if the workspace is clean, 1 if stale files were found.
    """
    return 0 if report.is_clean else 1


def run_check_mode_cli(
    directories: Sequence[Path],
    stale_threshold_secs: int = DEFAULT_STALE_THRESHOLD_SECS,
    *,
    output_stream: object | None = None,
) -> int:
    """Run check mode and print results, returning an exit code.

    This is the CLI-oriented entry point that combines inspection,
    reporting, and exit-code determination. Suitable for use as the
    main logic behind ``--check`` in a Tulla script.

    Args:
        directories: Work directories to inspect.
        stale_threshold_secs: Age threshold for stale detection.
        output_stream: A file-like object for output. Defaults to
            sys.stdout. Accepts any object with a ``write`` method.

    Returns:
        Exit code: 0 if clean, 1 if issues found.
    """
    if output_stream is None:
        output_stream = sys.stdout

    report = run_check_mode(
        directories=directories,
        stale_threshold_secs=stale_threshold_secs,
    )

    # Print the summary.
    output_stream.write(report.summary() + "\n")  # type: ignore[union-attr]

    # Print details for each stale file found.
    for sf in report.stale_files:
        output_stream.write(  # type: ignore[union-attr]
            f"  [{sf.category}] {sf.path} -- {sf.reason}\n"
        )

    exit_code = check_mode_exit_code(report)
    logger.debug(
        "Check mode complete: %d issue(s), exit code %d",
        report.issues_found,
        exit_code,
    )
    return exit_code
