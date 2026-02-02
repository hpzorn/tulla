"""Entry point for ``python3 -m ralph.phases.discovery``.

Provides a lightweight bash-calls-Python bridge so that shell scripts
can invoke the discovery pipeline directly without going through the
top-level ``ralph run discovery`` command.

Exit codes:
    0  — pipeline completed successfully
    1  — pipeline failed (phase error, bad input, etc.)
    124 — pipeline timed out
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ralph.adapters.claude_cli import ClaudeCLIAdapter
from ralph.config import RalphConfig
from ralph.core.phase import PhaseStatus

from .pipeline import discovery_pipeline

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_TIMEOUT = 124


@click.command("discovery")
@click.option(
    "--idea",
    required=True,
    type=int,
    help="Idea ID to process (required).",
)
@click.option(
    "--work-dir",
    required=True,
    type=click.Path(path_type=Path),
    help="Working directory for pipeline artifacts.",
)
@click.option(
    "--from",
    "resume_from",
    type=str,
    default=None,
    help="Resume from a specific phase (e.g. 'd3').",
)
@click.option(
    "--mode",
    type=str,
    default="upstream",
    help="Discovery mode: 'upstream' (default) or 'downstream'.",
)
def main(
    idea: int,
    work_dir: Path,
    resume_from: str | None,
    mode: str,
) -> None:
    """Run the discovery pipeline for a given idea.

    This entry point is designed for bash-calls-Python bridges:

        python3 -m ralph.phases.discovery --idea 54 --work-dir /tmp/test
    """
    config = RalphConfig()

    work_dir.mkdir(parents=True, exist_ok=True)

    claude_port = ClaudeCLIAdapter()
    pipeline = discovery_pipeline(
        claude_port=claude_port,
        work_dir=work_dir,
        idea_id=str(idea),
        config=config,
        mode=mode,
    )

    result = pipeline.run(start_from=resume_from)

    if result.final_status == PhaseStatus.SUCCESS:
        sys.exit(EXIT_SUCCESS)
    elif result.final_status == PhaseStatus.TIMEOUT:
        sys.exit(EXIT_TIMEOUT)
    else:
        sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
    main()
