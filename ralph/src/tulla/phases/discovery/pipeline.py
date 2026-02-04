"""Discovery pipeline factory.

Provides :func:`discovery_pipeline`, a convenience factory that assembles
the five discovery sub-phases (D1–D5) into a :class:`~tulla.core.pipeline.Pipeline`
ready for execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tulla.adapters.ontology_mcp import OntologyMCPAdapter
from tulla.config import TullaConfig
from tulla.core.pipeline import Pipeline

from .d1 import D1Phase
from .d2 import D2Phase
from .d3 import D3Phase
from .d4 import D4Phase
from .d5 import D5Phase


def discovery_pipeline(
    claude_port: Any,
    work_dir: Path,
    idea_id: str,
    config: TullaConfig,
    mode: str = "upstream",
) -> Pipeline:
    """Create a discovery :class:`Pipeline` with phases D1 through D5.

    Parameters:
        claude_port: Claude invocation adapter forwarded to each phase.
        work_dir: Scratch directory for this pipeline run.
        idea_id: Identifier of the idea being discovered.
        config: Root Tulla configuration; ``config.discovery.budget_usd``
            is used as the pipeline's total budget.
        mode: Discovery mode passed to D5 (``"upstream"`` or ``"downstream"``).

    Returns:
        A fully configured :class:`Pipeline` instance.
    """
    phases: list[tuple[str, Any]] = [
        ("d1", D1Phase()),
        ("d2", D2Phase()),
        ("d3", D3Phase()),
        ("d4", D4Phase()),
        ("d5", D5Phase()),
    ]

    ontology_port = OntologyMCPAdapter(base_url=config.ontology_server_url)

    return Pipeline(
        phases=phases,
        claude_port=claude_port,
        work_dir=work_dir,
        idea_id=idea_id,
        config={
            "mode": mode,
            "permission_mode": config.discovery.permission_mode,
            "phase_timeouts": config.discovery.phase_timeouts,
            "ontology_port": ontology_port,
        },
        total_budget_usd=config.discovery.budget_usd,
    )
