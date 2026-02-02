"""Planning pipeline factory.

Provides :func:`planning_pipeline`, a convenience factory that assembles
the six planning sub-phases (P1–P6) into a :class:`~tulla.core.pipeline.Pipeline`
ready for execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tulla.config import TullaConfig
from tulla.core.pipeline import Pipeline

from .p1 import P1Phase
from .p2 import P2Phase
from .p3 import P3Phase
from .p4 import P4Phase
from .p5 import P5Phase
from .p6 import P6Phase


def planning_pipeline(
    claude_port: Any,
    work_dir: Path,
    idea_id: str,
    config: TullaConfig,
    discovery_dir: str = "",
    research_dir: str = "",
) -> Pipeline:
    """Create a planning :class:`Pipeline` with phases P1 through P6.

    Assembles P1–P6 phases.  P4b and P6 are conditionally relevant at
    runtime based on P5 output, but the factory always includes the full
    phase set — the pipeline executor and individual phase logic handle
    conditional skipping.

    Parameters:
        claude_port: Claude invocation adapter forwarded to each phase.
        work_dir: Scratch directory for this pipeline run.
        idea_id: Identifier of the idea being planned.
        config: Root Tulla configuration; ``config.planning.budget_usd``
            is used as the pipeline's total budget.
        discovery_dir: Path to the discovery output directory whose
            artefacts (D1–D5) seed the planning context.
        research_dir: Path to the research output directory whose
            artefacts (R1–R6) provide research grounding for planning.

    Returns:
        A fully configured :class:`Pipeline` instance.
    """
    phases: list[tuple[str, Any]] = [
        ("p1", P1Phase()),
        ("p2", P2Phase()),
        ("p3", P3Phase()),
        ("p4", P4Phase()),
        ("p5", P5Phase()),
        ("p6", P6Phase()),
    ]

    return Pipeline(
        phases=phases,
        claude_port=claude_port,
        work_dir=work_dir,
        idea_id=idea_id,
        config={
            "discovery_dir": discovery_dir,
            "research_dir": research_dir,
            "permission_mode": config.planning.permission_mode,
            "max_files_per_requirement": config.planning.max_files_per_requirement,
            "min_wpf_blocking": config.planning.min_wpf_blocking,
            "min_wpf_advisory": config.planning.min_wpf_advisory,
            "max_granularity_retries": config.planning.max_granularity_retries,
        },
        total_budget_usd=config.planning.budget_usd,
    )
