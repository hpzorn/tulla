"""Click-based CLI for the Ralph agent system.

Provides the ``ralph`` command group with a ``run`` subcommand that
dispatches to agent-specific pipeline factories.

Exit codes:
    0  — pipeline completed successfully
    1  — pipeline failed (phase error, bad input, etc.)
    124 — pipeline timed out
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from ralph.adapters.claude_cli import ClaudeCLIAdapter
from ralph.adapters.ontology_mcp import OntologyMCPAdapter
from ralph.config import RalphConfig
from ralph.core.phase import PhaseStatus
from ralph.core.pipeline import Pipeline, PipelineResult

# ---------------------------------------------------------------------------
# Valid agent names and their default modes
# ---------------------------------------------------------------------------

AGENTS = ("discovery", "planning", "research", "implementation", "epistemology")

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_TIMEOUT = 124


# ---------------------------------------------------------------------------
# Pipeline factory
# ---------------------------------------------------------------------------


def _build_pipeline(
    agent: str,
    idea_id: int,
    config: RalphConfig,
    work_dir: Path,
    mode: str | None,
) -> Pipeline:
    """Create the appropriate pipeline for *agent*.

    Currently only the discovery agent has a full pipeline factory.
    Other agents raise :class:`click.ClickException` until implemented.
    """
    claude_port = ClaudeCLIAdapter()
    idea_str = str(idea_id)

    if agent == "discovery":
        from ralph.phases.discovery.pipeline import discovery_pipeline

        effective_mode = mode if mode else "upstream"
        return discovery_pipeline(
            claude_port=claude_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            mode=effective_mode,
        )

    if agent == "planning":
        from ralph.phases.planning.pipeline import planning_pipeline

        effective_discovery_dir = mode if mode else ""
        return planning_pipeline(
            claude_port=claude_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            discovery_dir=effective_discovery_dir,
        )

    if agent == "research":
        from ralph.phases.research.pipeline import research_pipeline

        effective_planning_dir = mode if mode else ""
        return research_pipeline(
            claude_port=claude_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            planning_dir=effective_planning_dir,
        )

    # Placeholder for future agents
    raise click.ClickException(
        f"Agent '{agent}' pipeline is not yet implemented. "
        f"Available: discovery, planning, research"
    )


# ---------------------------------------------------------------------------
# Dry-run display
# ---------------------------------------------------------------------------


def _show_dry_run(
    agent: str,
    idea_id: int,
    pipeline: Pipeline,
    work_dir: Path,
    resume_from: str | None,
    mode: str | None,
) -> None:
    """Print the execution plan without running anything."""
    click.echo("=== Dry-run plan ===")
    click.echo(f"Agent:      {agent}")
    click.echo(f"Idea:       {idea_id}")
    click.echo(f"Work dir:   {work_dir}")
    if mode:
        click.echo(f"Mode:       {mode}")
    if resume_from:
        click.echo(f"Resume from: {resume_from}")
    click.echo(f"Budget:     ${pipeline._total_budget_usd:.2f} USD")
    click.echo()
    click.echo("Phases:")

    skipping = resume_from is not None
    for phase_id, phase in pipeline._phases:
        if skipping:
            if phase_id == resume_from:
                skipping = False
                marker = "→"
            else:
                marker = "⏭"
        else:
            marker = "→"

        phase_cls = type(phase).__name__
        click.echo(f"  {marker} {phase_id:8s}  ({phase_cls})")

    click.echo()
    click.echo("No phases will be executed (dry-run).")


# ---------------------------------------------------------------------------
# Result reporting
# ---------------------------------------------------------------------------


def _report_result(result: PipelineResult) -> int:
    """Print an execution summary and return the appropriate exit code."""
    click.echo()
    click.echo("=== Execution Summary ===")
    click.echo(f"Status:     {result.final_status}")
    click.echo(f"Total cost: ${result.total_cost_usd:.4f} USD")
    click.echo()

    if result.phase_results:
        click.echo("Phase results:")
        for phase_id, phase_result in result.phase_results:
            status_str = str(phase_result.status)
            duration = f"{phase_result.duration_s:.1f}s"
            cost = phase_result.metadata.get("cost_usd", 0.0)
            line = f"  {phase_id:8s}  {status_str:8s}  {duration:>8s}  ${cost:.4f}"
            if phase_result.error:
                line += f"  ⚠ {phase_result.error}"
            click.echo(line)

    click.echo()

    if result.final_status == PhaseStatus.SUCCESS:
        click.echo("Pipeline completed successfully.")
        return EXIT_SUCCESS
    elif result.final_status == PhaseStatus.TIMEOUT:
        click.echo("Pipeline timed out.")
        return EXIT_TIMEOUT
    else:
        click.echo("Pipeline failed.")
        return EXIT_FAILURE


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to a YAML configuration file.",
)
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """Ralph — ontology-driven idea hygiene and lifecycle agent."""
    ctx.ensure_object(dict)

    if config_path:
        ctx.obj["config"] = RalphConfig.from_yaml(config_path)
    else:
        ctx.obj["config"] = RalphConfig()


@main.command()
@click.argument(
    "agent",
    type=click.Choice(AGENTS, case_sensitive=False),
)
@click.option(
    "--idea",
    required=True,
    type=int,
    help="Idea ID to process (required).",
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
    default=None,
    help="Agent-specific mode (e.g. 'upstream'/'downstream' for discovery).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show execution plan without running.",
)
@click.option(
    "--work-dir",
    type=click.Path(),
    default=None,
    help="Override the work directory for this run.",
)
@click.pass_context
def run(
    ctx: click.Context,
    agent: str,
    idea: int,
    resume_from: str | None,
    mode: str | None,
    dry_run: bool,
    work_dir: str | None,
) -> None:
    """Run an agent pipeline for a given idea.

    AGENT is one of: discovery, planning, research, implementation, epistemology.
    """
    config: RalphConfig = ctx.obj["config"]

    # Resolve work directory
    if work_dir:
        resolved_work_dir = Path(work_dir)
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        resolved_work_dir = (
            config.work_base_dir / f"idea-{idea}-{agent}-{timestamp}"
        )

    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    # Build the pipeline
    pipeline = _build_pipeline(
        agent=agent,
        idea_id=idea,
        config=config,
        work_dir=resolved_work_dir,
        mode=mode,
    )

    # Dry-run: show plan and exit
    if dry_run:
        _show_dry_run(
            agent=agent,
            idea_id=idea,
            pipeline=pipeline,
            work_dir=resolved_work_dir,
            resume_from=resume_from,
            mode=mode,
        )
        return

    # Execute the pipeline
    result = pipeline.run(start_from=resume_from)

    # Report results and exit with appropriate code
    exit_code = _report_result(result)
    if exit_code != EXIT_SUCCESS:
        sys.exit(exit_code)
