"""Log pre-flight hygiene decision at script startup.

Emits a structured log record capturing the resolved hygiene mode,
the source of that decision (explicit CLI flag vs. default), and
contextual metadata (script name, work directories) so operators
can reconstruct what a Ralph script decided and why.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from ralph.hygiene.args import HygieneConfig, HygieneMode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreflightDecision:
    """Structured record of the hygiene decision made at startup.

    Attributes:
        script_name: Name of the Ralph script that made the decision.
        mode: The resolved hygiene mode (clean, no-clean, or check).
        source: Whether the mode was set by an explicit CLI flag or by default.
        work_dirs: Directories that will be inspected/cleaned.
        remaining_args: CLI arguments passed through to the host script.
    """

    script_name: str
    mode: str
    source: str
    work_dirs: list[str]
    remaining_args: list[str]

    def as_dict(self) -> dict[str, object]:
        """Return a plain dict suitable for structured logging or serialization."""
        return asdict(self)

    def as_json(self) -> str:
        """Return a compact JSON representation of the decision."""
        return json.dumps(asdict(self), separators=(",", ":"))


# CLI flags that explicitly select a hygiene mode.
_EXPLICIT_FLAGS: frozenset[str] = frozenset({"--clean", "--no-clean", "--check"})


def _detect_source(config: HygieneConfig, argv: Sequence[str] | None) -> str:
    """Determine whether the mode was set by an explicit flag or by default.

    Args:
        config: The resolved hygiene configuration.
        argv: The original CLI arguments before parsing (if available).

    Returns:
        ``"explicit"`` if a hygiene flag was present, ``"default"`` otherwise.
    """
    if argv is not None:
        for arg in argv:
            if arg in _EXPLICIT_FLAGS:
                return "explicit"
        return "default"

    # If argv is not available, infer from the mode.
    if config.mode != HygieneMode.CLEAN:
        return "explicit"
    return "unknown"


def build_preflight_decision(
    script_name: str,
    config: HygieneConfig,
    work_dirs: Sequence[Path],
    argv: Sequence[str] | None = None,
) -> PreflightDecision:
    """Build a structured PreflightDecision record.

    Args:
        script_name: Name of the Ralph script.
        config: The resolved hygiene configuration from argument parsing.
        work_dirs: Directories targeted for hygiene inspection/cleanup.
        argv: The original CLI arguments (used to detect explicit vs default).

    Returns:
        A frozen PreflightDecision capturing the decision and context.
    """
    source = _detect_source(config, argv)
    return PreflightDecision(
        script_name=script_name,
        mode=config.mode.value,
        source=source,
        work_dirs=[str(d) for d in work_dirs],
        remaining_args=list(config.remaining_args),
    )


def log_preflight_decision(
    script_name: str,
    config: HygieneConfig,
    work_dirs: Sequence[Path],
    argv: Sequence[str] | None = None,
) -> PreflightDecision:
    """Log the pre-flight hygiene decision at startup.

    Builds a PreflightDecision and emits a structured INFO log
    message containing all decision metadata.

    Args:
        script_name: Name of the Ralph script.
        config: The resolved hygiene configuration.
        work_dirs: Directories targeted for hygiene.
        argv: The original CLI arguments (for source detection).

    Returns:
        The PreflightDecision record (useful for testing or further processing).
    """
    decision = build_preflight_decision(
        script_name=script_name,
        config=config,
        work_dirs=work_dirs,
        argv=argv,
    )

    logger.info(
        "[%s] Pre-flight decision: mode=%s source=%s dirs=%s",
        decision.script_name,
        decision.mode,
        decision.source,
        decision.work_dirs,
    )

    if decision.remaining_args:
        logger.debug(
            "[%s] Remaining args passed through: %s",
            decision.script_name,
            decision.remaining_args,
        )

    return decision
