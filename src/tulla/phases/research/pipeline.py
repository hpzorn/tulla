"""Research pipeline factory.

Provides :func:`research_pipeline`, a convenience factory that assembles
the six research sub-phases (R1-R6) into a :class:`~tulla.core.pipeline.Pipeline`
ready for execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tulla.adapters.ontology_mcp import OntologyMCPAdapter
from tulla.config import TullaConfig
from tulla.core.pipeline import Pipeline
from tulla.ontology.phase_shapes import PHASE_SHAPES

from .r1 import R1Phase
from .r2 import R2Phase
from .r3 import R3Phase
from .r4 import R4Phase
from .r5 import R5Phase
from .r6 import R6Phase


def research_pipeline(
    claude_port: Any,
    work_dir: Path,
    idea_id: str,
    config: TullaConfig,
    planning_dir: str = "",
    discovery_dir: str = "",
) -> Pipeline:
    """Create a research :class:`Pipeline` with phases R1 through R6.

    Supports three modes, selected by the combination of *planning_dir*
    and *discovery_dir* (see idea-58):

    - **Groundwork** (neither ``planning_dir`` nor ``discovery_dir`` set):
      Full R1-R6 on a raw seed with novelty assessment and possible early
      termination.
    - **Discovery-Fed** (``discovery_dir`` set, no ``planning_dir``):
      Full R1-R6 driven by the D5 research brief questions produced
      during discovery.
    - **Spike** (``planning_dir`` set): Targeted R1-R6 answering P5
      research requests from the planning phase.

    .. note:: **Spike Re-entry Workflow**

       After a spike completes, R6 facts are persisted to the A-box.
       The user then re-runs ``tulla run planning --idea N --from p5``
       to resume planning with spike results available as upstream facts.
       No automatic re-entry is implemented — the user reviews spike
       results before continuing.

    Mode precedence: ``planning_dir`` > ``discovery_dir`` > groundwork.
    When both are supplied, *planning_dir* wins and the pipeline runs
    in Spike mode.

    Parameters:
        claude_port: Claude invocation adapter forwarded to each phase.
        work_dir: Scratch directory for this pipeline run.
        idea_id: Identifier of the idea being researched.
        config: Root Tulla configuration; ``config.research.budget_usd``
            is used as the pipeline's total budget and
            ``config.research.max_retries`` configures R5's retry loop.
        planning_dir: Path to the planning output directory whose
            research requests (P5) seed the research questions (spike mode).
        discovery_dir: Path to the discovery output directory whose
            artifacts (D1-D5) ground the research (discovery-fed mode).

    Returns:
        A fully configured :class:`Pipeline` instance.
    """
    phases: list[tuple[str, Any]] = [
        ("r1", R1Phase()),
        ("r2", R2Phase()),
        ("r3", R3Phase()),
        ("r4", R4Phase()),
        ("r5", R5Phase(max_retries=config.research.max_retries)),
        ("r6", R6Phase()),
    ]

    ontology_port = OntologyMCPAdapter(base_url=config.ontology_server_url)

    # Include discovery phases (d1-d5) as prior phases for upstream fact
    # collection. This enables cross-agent fact flow (northstar, etc.).
    prior_phases = ["d1", "d2", "d3", "d4", "d5"]

    return Pipeline(
        phases=phases,
        claude_port=claude_port,
        work_dir=work_dir,
        idea_id=idea_id,
        config={
            "planning_dir": planning_dir,
            "discovery_dir": discovery_dir,
            "permission_mode": config.research.permission_mode,
            "phase_timeouts": config.research.phase_timeouts,
            "ontology_port": ontology_port,
            # shape_registry disabled: ontology-server validate_instance
            # cannot see triples stored via add_triple (A-Box/SHACL gap).
            # Re-enable when validate_instance queries the A-Box graph.
            # "shape_registry": PHASE_SHAPES,
        },
        total_budget_usd=config.research.budget_usd,
        prior_phases=prior_phases,
    )
