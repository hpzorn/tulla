"""Research pipeline factory.

Provides :func:`research_pipeline`, a convenience factory that assembles
the six research sub-phases (R1-R6) into a :class:`~ralph.core.pipeline.Pipeline`
ready for execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ralph.config import RalphConfig
from ralph.core.pipeline import Pipeline

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
    config: RalphConfig,
    planning_dir: str = "",
) -> Pipeline:
    """Create a research :class:`Pipeline` with phases R1 through R6.

    Parameters:
        claude_port: Claude invocation adapter forwarded to each phase.
        work_dir: Scratch directory for this pipeline run.
        idea_id: Identifier of the idea being researched.
        config: Root Ralph configuration; ``config.research.budget_usd``
            is used as the pipeline's total budget and
            ``config.research.max_retries`` configures R5's retry loop.
        planning_dir: Path to the planning output directory whose
            research requests (P5) seed the research questions.

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

    return Pipeline(
        phases=phases,
        claude_port=claude_port,
        work_dir=work_dir,
        idea_id=idea_id,
        config={"planning_dir": planning_dir},
        total_budget_usd=config.research.budget_usd,
    )
