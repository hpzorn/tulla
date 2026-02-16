"""Click-based CLI for the Tulla agent system.

Provides the ``tulla`` command group with a ``run`` subcommand that
dispatches to agent-specific pipeline factories.

Exit codes:
    0  — pipeline completed successfully
    1  — pipeline failed (phase error, bad input, etc.)
    2  — pipeline incomplete (Terraform -detailed-exitcode convention)
    124 — pipeline timed out
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from tulla.adapters.ontology_mcp import OntologyMCPAdapter
from tulla.config import TullaConfig
from tulla.core.phase import PhaseStatus
from tulla.core.pipeline import Pipeline, PipelineResult
from tulla.infrastructure.logging import configure_logging

# ---------------------------------------------------------------------------
# Valid agent names and their default modes
# ---------------------------------------------------------------------------

AGENTS = ("discovery", "planning", "research", "implementation", "epistemology", "lightweight")

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_INCOMPLETE = 2
EXIT_TIMEOUT = 124


def ep_modes() -> dict[str, tuple[str, Any]]:
    """Build and return the epistemology mode registry.

    Imports are deferred so the epistemology package is only loaded when
    this function is actually called.
    """
    from tulla.phases.epistemology.abduction import AbductionPhase
    from tulla.phases.epistemology.auto import AutoPhase
    from tulla.phases.epistemology.catuskoti import CatuskotiPhase
    from tulla.phases.epistemology.contradiction import ContradictionPhase
    from tulla.phases.epistemology.domain import PopperPhase
    from tulla.phases.epistemology.idea import AristotlePhase
    from tulla.phases.epistemology.pool import BaconPhase
    from tulla.phases.epistemology.problem import DeweyPhase
    from tulla.phases.epistemology.signal import PyrrhonPhase

    return {
        "auto": ("ep-auto", AutoPhase()),
        "pyrrhon": ("ep-pyrrhon", PyrrhonPhase()),
        "aristotle": ("ep-aristotle", AristotlePhase()),
        "hegel": ("ep-contradiction", ContradictionPhase()),
        "abduction": ("ep-abduction", AbductionPhase()),
        "dewey": ("ep-dewey", DeweyPhase()),
        "popper": ("ep-popper", PopperPhase()),
        "bacon": ("ep-bacon", BaconPhase()),
        "catuskoti": ("ep-catuskoti", CatuskotiPhase()),
    }


# Lifecycle transitions: agent -> (on_start, on_success)
# Agents not listed here don't trigger lifecycle changes.
_LIFECYCLE_TRANSITIONS: dict[str, tuple[str, str]] = {
    "discovery": ("researching", "researching"),   # stays researching; research agent finishes it
    "research": ("researching", "researched"),
    "planning": ("decomposing", "scoped"),
    "implementation": ("implementing", "completed"),
}

# Prerequisite chains: target_state -> list of states to walk through in order.
# Used when the idea is in an early state and needs to reach the agent's start
# state.  Mirrors LIFECYCLE_TRANSITIONS in the ontology-server.
_LIFECYCLE_PREREQUISITES: dict[str, list[str]] = {
    "researching":  ["backlog", "researching"],
    "decomposing":  ["backlog", "researching", "researched", "decomposing"],
    "implementing": ["backlog", "researching", "researched", "scoped", "implementing"],
}


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


def _push_lifecycle(
    config: TullaConfig,
    idea_id: int,
    agent: str,
    phase: str,
) -> None:
    """Push an idea's lifecycle forward if the agent has a transition.

    *phase* is ``"start"`` or ``"success"``.  Silently does nothing for
    agents without lifecycle mappings or on communication errors (the
    pipeline run is more important than the lifecycle bookkeeping).

    On *start*, if the idea is in an early state (e.g. ``seed``) the
    helper walks through prerequisite states so that the ontology-server's
    transition validation is satisfied.
    """
    log = logging.getLogger(__name__)
    transitions = _LIFECYCLE_TRANSITIONS.get(agent)
    if not transitions:
        return

    new_state = transitions[0] if phase == "start" else transitions[1]
    reason = f"tulla {agent} agent {phase}"

    try:
        ontology = OntologyMCPAdapter(base_url=config.ontology_server_url)

        if phase == "start":
            # Walk prerequisite chain so early-state ideas reach the target.
            chain = _LIFECYCLE_PREREQUISITES.get(new_state, [new_state])
            for step in chain:
                resp = ontology.set_lifecycle(str(idea_id), step, reason=reason)
                if resp.get("error"):
                    # Transition not valid from current state — skip ahead.
                    continue
                log.info("Lifecycle idea-%d → %s (%s %s)", idea_id, step, agent, phase)
        else:
            resp = ontology.set_lifecycle(str(idea_id), new_state, reason=reason)
            if resp.get("error"):
                log.warning(
                    "Lifecycle idea-%d: cannot reach '%s': %s",
                    idea_id, new_state, resp["error"],
                )
            else:
                log.info("Lifecycle idea-%d → %s (%s %s)", idea_id, new_state, agent, phase)

    except Exception as exc:
        log.warning("Could not update lifecycle for idea-%d: %s", idea_id, exc)


# ---------------------------------------------------------------------------
# Work-dir resolution helpers
# ---------------------------------------------------------------------------


def _find_latest_work_dir(
    work_base: Path, idea: int, agent: str,
) -> Path | None:
    """Find the most recent work directory with checkpoint files.

    Scans *work_base* for directories matching ``idea-{idea}-{agent}-*``
    and returns the most recent one (by lexicographic sort on the
    timestamp suffix) that contains at least one ``*-result.json``
    checkpoint file.

    Returns ``None`` if no suitable directory is found.
    """
    prefix = f"idea-{idea}-{agent}-"
    if not work_base.exists():
        return None

    candidates = sorted(
        (d for d in work_base.iterdir() if d.is_dir() and d.name.startswith(prefix)),
        key=lambda d: d.name,
        reverse=True,
    )

    for candidate in candidates:
        if list(candidate.glob("*-result.json")):
            return candidate

    return None


# ---------------------------------------------------------------------------
# Pipeline factory
# ---------------------------------------------------------------------------


def _build_pipeline(
    agent: str,
    idea_id: int,
    config: TullaConfig,
    work_dir: Path,
    mode: str | None,
    discovery_dir: str | None = None,
    research_dir: str | None = None,
    research_mode: str | None = None,
    description: str = "",
) -> Pipeline:
    """Create the appropriate pipeline for *agent*.

    Currently only the discovery agent has a full pipeline factory.
    Other agents raise :class:`click.ClickException` until implemented.
    """
    llm_port = config.create_llm_adapter()
    idea_str = str(idea_id)

    if agent == "discovery":
        from tulla.phases.discovery.pipeline import discovery_pipeline

        effective_mode = mode if mode else "upstream"
        return discovery_pipeline(
            claude_port=llm_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            mode=effective_mode,
        )

    if agent == "planning":
        from tulla.phases.planning.pipeline import planning_pipeline

        effective_discovery_dir = discovery_dir if discovery_dir else ""
        effective_research_dir = research_dir if research_dir else ""
        return planning_pipeline(
            claude_port=llm_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            discovery_dir=effective_discovery_dir,
            research_dir=effective_research_dir,
        )

    if agent == "research":
        from tulla.phases.research.pipeline import research_pipeline
        from tulla.phases.research.routing import RoutingError, infer_research_mode

        logger = logging.getLogger(__name__)

        try:
            routing = infer_research_mode(
                idea_str,
                explicit_mode=research_mode,
                explicit_planning_dir=mode,
                explicit_discovery_dir=discovery_dir,
                work_base=config.work_base_dir,
            )
        except RoutingError as exc:
            raise click.ClickException(str(exc)) from exc

        logger.info(
            "Research auto-routing: mode=%s, planning_dir=%r, discovery_dir=%r",
            routing.mode.value,
            routing.planning_dir,
            routing.discovery_dir,
        )

        return research_pipeline(
            claude_port=llm_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            planning_dir=routing.planning_dir,
            discovery_dir=routing.discovery_dir,
        )

    if agent == "epistemology":
        modes = ep_modes()

        effective_mode = mode if mode else "auto"
        if effective_mode not in modes:
            raise click.ClickException(
                f"Unknown epistemology mode '{effective_mode}'. "
                f"Available: {', '.join(modes)}"
            )

        phase_id, phase = modes[effective_mode]
        return Pipeline(
            phases=[(phase_id, phase)],
            claude_port=llm_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config={
                "mode": effective_mode,
                "permission_mode": config.epistemology.permission_mode,
            },
            total_budget_usd=config.epistemology.budget_usd,
        )

    # @pattern:Plugin -- Lightweight agent registered via elif branch; same factory contract as other agents
    # @principle:DependencyInversion -- CLI depends on Pipeline abstraction returned by factory, not on concrete phase classes
    # @principle:HighCohesion -- All pipeline dispatch, dry-run display, and result reporting grouped in one CLI module
    if agent == "lightweight":
        from tulla.phases.lightweight.pipeline import lightweight_pipeline

        return lightweight_pipeline(
            claude_port=llm_port,
            work_dir=work_dir,
            idea_id=idea_str,
            config=config,
            change_description=description,
        )

    # @principle:OpenClosedPrinciple -- _build_pipeline() is open for new agents via elif branches without modifying existing wiring
    raise click.ClickException(
        f"Agent '{agent}' pipeline is not yet implemented. "
        f"Available: discovery, planning, research, implementation, epistemology, lightweight"
    )


# ---------------------------------------------------------------------------
# Implementation loop runner
# ---------------------------------------------------------------------------


def _run_implementation(
    idea_id: int,
    config: TullaConfig,
    work_dir: Path,
    dry_run: bool,
) -> None:
    """Build and run the implementation loop for an idea.

    Unlike other agents, implementation uses a loop-based architecture
    (Find→Implement→Commit→Verify→Status) rather than a linear pipeline.
    """
    from tulla.phases.implementation.loop import ImplementationLoop

    llm_port = config.create_llm_adapter()
    ontology_port = OntologyMCPAdapter()
    prd_context = f"prd-idea-{idea_id}"
    project_root = Path.cwd()

    loop = ImplementationLoop(
        claude_port=llm_port,
        ontology_port=ontology_port,
        project_root=project_root,
        prd_context=prd_context,
        config=config,
        max_retries=config.implementation.max_retries,
        total_budget_usd=config.implementation.budget_usd,
        project_id=config.project_id,
    )

    if dry_run:
        loop.show_dry_run(idea_id=idea_id, work_dir=work_dir)
        return

    result = loop.run()

    # Report loop results
    click.echo()
    click.echo("=== Implementation Loop Summary ===")
    click.echo(f"Total cost:   ${result.total_cost_usd:.4f} USD")
    click.echo(f"Completed:    {result.requirements_completed}")
    click.echo(f"Blocked:      {result.requirements_blocked}")
    click.echo(f"All complete: {result.all_complete}")
    click.echo(f"Iterations:   {len(result.iterations)}")
    click.echo()

    for i, iteration in enumerate(result.iterations, 1):
        req = iteration.requirement_id or "(none)"
        click.echo(f"  [{i}] {req}: {iteration.outcome.value}")
        if iteration.error:
            click.echo(f"      Error: {iteration.error}")

    click.echo()

    if result.all_complete:
        _push_lifecycle(config, idea_id, "implementation", "success")
        click.echo("All requirements implemented successfully.")
    elif result.requirements_blocked > 0:
        click.echo("Some requirements are blocked.")
        sys.exit(EXIT_FAILURE)
    else:
        click.echo("Implementation loop ended.")
        sys.exit(EXIT_FAILURE)


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


_DEFAULT_CONFIG_PATH = Path.home() / ".tulla" / "config.yaml"


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to a YAML configuration file (default: ~/.tulla/config.yaml).",
)
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """Tulla — ontology-driven idea hygiene and lifecycle agent."""
    ctx.ensure_object(dict)

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    ctx.obj["config"] = TullaConfig.from_yaml(path)


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
@click.option(
    "--discovery-dir",
    type=click.Path(exists=True),
    default=None,
    help="Discovery output directory (D1-D5 artifacts).",
)
@click.option(
    "--research-dir",
    type=click.Path(exists=True),
    default=None,
    help="Research output directory (R1-R6 artifacts).",
)
@click.option(
    "--research-mode",
    "research_mode",
    type=click.Choice(["groundwork", "spike", "discovery-fed"], case_sensitive=False),
    default=None,
    help="Research pipeline mode (auto-detected if omitted).",
)
@click.option(
    "--description",
    type=str,
    default="",
    help="Change description (used by the lightweight agent).",
)
@click.option(
    "--directive",
    type=str,
    default=None,
    help="High-priority instruction injected into every phase prompt.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable DEBUG-level console logging (default: INFO).",
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
    discovery_dir: str | None,
    research_dir: str | None,
    research_mode: str | None,
    description: str,
    directive: str | None,
    verbose: bool,
) -> None:
    """Run an agent pipeline for a given idea.

    AGENT is one of: discovery, planning, research, implementation, epistemology, lightweight.
    """
    config: TullaConfig = ctx.obj["config"]

    # Resolve work directory to absolute path — Claude CLI may have a
    # different cwd than the Python process, so relative paths break.
    if work_dir:
        resolved_work_dir = Path(work_dir).resolve()
    elif resume_from:
        # --from specified without --work-dir: reuse the latest matching dir
        found = _find_latest_work_dir(config.work_base_dir, idea, agent)
        if found is None:
            raise click.ClickException(
                f"--from {resume_from} requires a previous work directory for "
                f"idea-{idea}-{agent}, but none found in {config.work_base_dir}. "
                f"Use --work-dir to specify one explicitly."
            )
        resolved_work_dir = found.resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        resolved_work_dir = (
            config.work_base_dir / f"idea-{idea}-{agent}-{timestamp}"
        ).resolve()

    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    # Configure structured logging — console (INFO/DEBUG) + JSON file (DEBUG)
    console_level = logging.DEBUG if verbose else logging.INFO
    configure_logging(
        work_dir=resolved_work_dir,
        console_level=console_level,
        agent=agent,
        idea_id=idea,
    )

    # Push lifecycle forward on start (skip for dry-run)
    if not dry_run:
        _push_lifecycle(config, idea, agent, "start")

    # Implementation uses a loop-based orchestrator, not a linear pipeline
    if agent == "implementation":
        _run_implementation(
            idea_id=idea,
            config=config,
            work_dir=resolved_work_dir,
            dry_run=dry_run,
        )
        return

    # Build the pipeline
    pipeline = _build_pipeline(
        agent=agent,
        idea_id=idea,
        config=config,
        work_dir=resolved_work_dir,
        mode=mode,
        discovery_dir=discovery_dir,
        research_dir=research_dir,
        research_mode=research_mode,
        description=description,
    )

    # Inject user directive into pipeline config so Phase.execute() can see it
    if directive:
        pipeline._config["directive"] = directive

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

    # Check for early termination signal from phase metadata
    for _phase_id, phase_result in result.phase_results:
        early = phase_result.metadata.get("early_terminate")
        if early:
            reason = early if isinstance(early, str) else "phase requested early stop"
            click.echo(f"\nEarly termination: {reason}")
            sys.exit(EXIT_SUCCESS)

    # Push lifecycle forward on success
    if result.final_status == PhaseStatus.SUCCESS:
        _push_lifecycle(config, idea, agent, "success")

    # Report results and exit with appropriate code
    exit_code = _report_result(result)
    if exit_code != EXIT_SUCCESS:
        sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Phase ID mappings for reset
# ---------------------------------------------------------------------------

_AGENT_PHASES: dict[str, list[str]] = {
    "discovery": ["d1", "d2", "d3", "d4", "d5"],
    "research": ["r1", "r2", "r3", "r4", "r5", "r6"],
    "planning": ["p1", "p2", "p3", "p4", "p5", "p6"],
}


@main.command()
@click.argument("idea", type=int)
@click.option(
    "--agent",
    type=click.Choice(["discovery", "research", "planning", "all"]),
    default="all",
    help="Scope the reset to a specific agent's phases (default: all).",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def reset(ctx: click.Context, idea: int, agent: str, yes: bool) -> None:
    """Clear A-Box phase facts for an idea so re-runs start clean."""
    from tulla.namespaces import PHASE_NS

    config: TullaConfig = ctx.obj["config"]

    if agent == "all":
        phase_ids = [pid for ids in _AGENT_PHASES.values() for pid in ids]
    else:
        phase_ids = _AGENT_PHASES[agent]

    if not yes:
        phases_str = ", ".join(phase_ids)
        click.confirm(
            f"Clear phase facts for idea {idea} ({agent}): {phases_str}?",
            abort=True,
        )

    ontology_port = OntologyMCPAdapter(base_url=config.ontology_server_url)
    total_cleared = 0

    for pid in phase_ids:
        subject = f"{PHASE_NS}{idea}-{pid}"
        cleared = ontology_port.remove_triples_by_subject(subject)
        if cleared:
            click.echo(f"  {pid}: {cleared} triples removed")
        total_cleared += cleared

    click.echo(f"Cleared {total_cleared} triples for idea {idea} ({agent}).")


@main.command("project-init")
@click.option(
    "--project-id",
    type=str,
    default=None,
    help="Project identifier (default: from config).",
)
@click.option(
    "--claude-md",
    type=click.Path(exists=True),
    default="./CLAUDE.md",
    help="Path to the CLAUDE.md file (default: ./CLAUDE.md).",
)
@click.pass_context
def project_init(ctx: click.Context, project_id: str | None, claude_md: str) -> None:
    """Bootstrap a project from a CLAUDE.md file.

    Creates a project entity in the ontology and extracts architectural
    decisions (ADRs) from the CLAUDE.md instructions using an LLM.
    """
    from tulla.workflows.project_init import init_project

    config: TullaConfig = ctx.obj["config"]
    effective_project_id = project_id if project_id else config.project_id

    ontology_port = OntologyMCPAdapter()
    claude_port = config.create_llm_adapter()

    result = init_project(
        ontology_port=ontology_port,
        claude_port=claude_port,
        project_id=effective_project_id,
        claude_md_path=Path(claude_md).resolve(),
    )

    if not result.project_uri:
        click.echo("Project initialisation failed.", err=True)
        sys.exit(EXIT_FAILURE)

    click.echo(f"Project:  {result.project_uri}")
    click.echo(f"ADRs:     {result.adr_count}")
    for candidate in result.candidates:
        marker = "+" if candidate.confirmed else "-"
        click.echo(f"  [{marker}] {candidate.title}")


@main.command("promote-adr")
@click.argument("adr_id", required=False, default=None)
@click.option(
    "--project-id",
    type=str,
    default=None,
    help="Project identifier (default: from config).",
)
@click.pass_context
def promote_adr_cmd(
    ctx: click.Context,
    adr_id: str | None,
    project_id: str | None,
) -> None:
    """Promote an idea-scope ADR to project scope.

    Accepts an ADR identifier as a full URI or short form (e.g. adr-58-1).
    If no identifier is given, lists available idea-scope ADRs for selection.
    """
    from tulla.namespaces import ARCH_NS, PRD_NS
    from tulla.workflows.project_init import promote_adr

    config: TullaConfig = ctx.obj["config"]
    ontology_port = OntologyMCPAdapter()
    effective_project_id = project_id if project_id else config.project_id
    project_uri = f"{PRD_NS}project-{effective_project_id}"

    if adr_id is None:
        # List idea-scope ADRs via SPARQL
        query = f"""\
SELECT ?adr ?label WHERE {{
  ?adr a isaqb:ArchitectureDecision .
  ?adr isaqb:scope "idea" .
  OPTIONAL {{ ?adr rdfs:label ?label }}
}}
ORDER BY ?adr"""

        try:
            result = ontology_port.sparql_query(query)
        except Exception as exc:
            click.echo(f"Error querying ADRs: {exc}", err=True)
            sys.exit(EXIT_FAILURE)

        bindings = result.get("results", [])
        if not bindings:
            click.echo("No idea-scope ADRs found.")
            sys.exit(EXIT_SUCCESS)

        click.echo("Idea-scope ADRs available for promotion:\n")
        for idx, binding in enumerate(bindings, start=1):
            uri = binding.get("adr", "")
            label = binding.get("label", uri)
            click.echo(f"  [{idx}] {label}  ({uri})")

        click.echo()
        choice = click.prompt(
            "Select ADR number to promote",
            type=click.IntRange(1, len(bindings)),
        )
        adr_uri = bindings[choice - 1].get("adr", "")
    else:
        # Resolve short form (e.g. "adr-58-1") to full URI
        if adr_id.startswith("http://") or adr_id.startswith("https://"):
            adr_uri = adr_id
        else:
            adr_uri = f"{ARCH_NS}{adr_id}"

    if not adr_uri:
        click.echo("Could not resolve ADR identifier.", err=True)
        sys.exit(EXIT_FAILURE)

    try:
        promote_adr(
            ontology_port=ontology_port,
            adr_uri=adr_uri,
            project_uri=project_uri,
        )
    except Exception as exc:
        click.echo(f"Promotion failed: {exc}", err=True)
        sys.exit(EXIT_FAILURE)

    click.echo(f"Promoted {adr_uri}")
    click.echo(f"  isaqb:scope  -> \"project\"")
    click.echo(f"  prd:hasADR   -> {project_uri}")


@main.command()
@click.option(
    "--idea",
    required=True,
    type=int,
    help="Idea ID to query status for (required).",
)
def status(idea: int) -> None:
    """Show PRD requirement status for a given idea."""
    from tulla.commands.status import format_status_table, query_prd_status

    ontology = OntologyMCPAdapter()
    prd_context = f"prd-idea-{idea}"

    try:
        summary = query_prd_status(ontology, prd_context)
    except Exception as exc:
        click.echo(f"Error querying status: {exc}", err=True)
        sys.exit(EXIT_FAILURE)

    table = format_status_table(summary, idea_number=idea)
    click.echo(table)

    # Exit 0 if all complete or no requirements; 2 if work remains
    if summary.total == 0 or summary.complete == summary.total:
        sys.exit(EXIT_SUCCESS)
    else:
        sys.exit(EXIT_INCOMPLETE)
