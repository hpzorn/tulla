"""Lightweight pipeline factory.

Provides :func:`lightweight_pipeline`, a convenience factory that assembles
the five lightweight sub-phases (Intake, ContextScan, Plan, Execute, Trace)
into a :class:`~tulla.core.pipeline.Pipeline` ready for execution.

# @pattern:PipesAndFilters -- Five phases chained as filters:
#   each consumes prev_output and produces typed output for the next
# @pattern:PortsAndAdapters -- OntologyMCPAdapter instantiated
#   from config URL; Pipeline receives it via config dict,
#   not direct import
# @pattern:Blackboard -- Pipeline config dict acts as shared data
#   store: phases read ontology_port, shape_registry,
#   change_description
# @principle:LooseCoupling -- Factory wires phases together
#   without phases knowing about each other; Pipeline mediates
#   data flow
# @principle:SingleResponsibility -- Factory's sole job is
#   assembly; phase logic, persistence, and execution live
#   elsewhere

Architecture decisions: arch:adr-53-1
Quality focus: isaqb:Maintainability
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tulla.adapters.ontology_mcp import OntologyMCPAdapter
from tulla.config import TullaConfig
from tulla.core.pipeline import Pipeline
from tulla.ontology.phase_shapes import PHASE_SHAPES

from .context_scan import ContextScanPhase
from .execute import ExecutePhase
from .intake import IntakePhase
from .plan import PlanPhase
from .trace import TracePhase


def lightweight_pipeline(
    claude_port: Any,
    work_dir: Path,
    idea_id: str,
    config: TullaConfig,
    change_description: str = "",
) -> Pipeline:
    """Create a lightweight :class:`Pipeline` with phases Intake through Trace.

    Parameters:
        claude_port: Claude invocation adapter forwarded to each phase.
        work_dir: Scratch directory for this pipeline run.
        idea_id: Identifier of the idea being processed.
        config: Root Tulla configuration; ``config.lightweight.budget_usd``
            is used as the pipeline's total budget.
        change_description: Human-readable description of the change to
            implement (forwarded to phases via config dict).

    Returns:
        A fully configured :class:`Pipeline` instance.
    """
    phases: list[tuple[str, Any]] = [
        ("lw-intake", IntakePhase()),
        ("lw-context", ContextScanPhase()),
        ("lw-plan", PlanPhase()),
        ("lw-execute", ExecutePhase()),
        ("lw-trace", TracePhase()),
    ]

    ontology_port = OntologyMCPAdapter(base_url=config.ontology_server_url)

    return Pipeline(
        phases=phases,
        claude_port=claude_port,
        work_dir=work_dir,
        idea_id=idea_id,
        config={
            "ontology_port": ontology_port,
            "shape_registry": PHASE_SHAPES,
            "permission_mode": config.lightweight.permission_mode,
            "phase_timeouts": config.lightweight.phase_timeouts,
            "change_description": change_description,
        },
        total_budget_usd=config.lightweight.budget_usd,
    )
