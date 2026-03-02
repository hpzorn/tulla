"""Auto-routing for research pipeline mode selection.

Determines the research mode (groundwork, discovery-fed, spike) based on
explicit flags, legacy flag mapping, or automatic scanning of prior work
directories.

Routing rules (precedence order):

1. **Explicit** ``--research-mode`` flag maps directly to a
   :class:`ResearchMode` value.  Spike scans for the latest P5 output,
   discovery-fed scans for the latest D5 brief, groundwork returns empty
   dirs.
2. **Legacy flags** — ``--mode`` (planning dir path) maps to spike,
   ``--discovery-dir`` maps to discovery-fed.
3. **Auto-routing** — scan work_base for P5 output (spike), then D5
   brief (discovery-fed), then default to groundwork.

Precedence: spike > discovery-fed > groundwork.
"""

from __future__ import annotations

import enum
import warnings
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class ResearchMode(enum.Enum):
    """Research pipeline operating mode."""

    GROUNDWORK = "groundwork"
    DISCOVERY_FED = "discovery-fed"
    SPIKE = "spike"


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class RoutingError(Exception):
    """Raised when research mode cannot be determined or is invalid."""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingResult:
    """Resolved research routing decision.

    Attributes:
        mode: The selected research mode.
        planning_dir: Path to the planning output directory (spike mode),
            or empty string when not applicable.
        discovery_dir: Path to the discovery output directory
            (discovery-fed mode), or empty string when not applicable.
    """

    mode: ResearchMode
    planning_dir: str = ""
    discovery_dir: str = ""


# ---------------------------------------------------------------------------
# Directory scanning helpers
# ---------------------------------------------------------------------------


def _find_latest_dir(work_base: Path, idea_id: str, agent: str) -> Path | None:
    """Find the most recent work directory for *agent* containing output files.

    Scans *work_base* for directories matching ``idea-{idea_id}-{agent}-*``
    and returns the most recent one (by lexicographic sort on the timestamp
    suffix) that contains at least one markdown artifact.
    """
    prefix = f"idea-{idea_id}-{agent}-"
    if not work_base.exists():
        return None

    candidates = sorted(
        (
            d
            for d in work_base.iterdir()
            if d.is_dir() and d.name.startswith(prefix)
        ),
        key=lambda d: d.name,
        reverse=True,
    )

    for candidate in candidates:
        if list(candidate.glob("*.md")):
            return candidate

    return None


def _scan_for_p5(work_base: Path, idea_id: str) -> str:
    """Return the planning directory path if it contains a P5 output file."""
    planning_dir = _find_latest_dir(work_base, idea_id, "planning")
    if planning_dir is None:
        return ""
    p5_file = planning_dir / "p5-research-requests.md"
    if p5_file.exists():
        return str(planning_dir)
    return ""


def _scan_for_d5(work_base: Path, idea_id: str) -> str:
    """Return the discovery directory path if it contains a D5 brief."""
    discovery_dir = _find_latest_dir(work_base, idea_id, "discovery")
    if discovery_dir is None:
        return ""
    d5_file = discovery_dir / "d5-research-brief.md"
    if d5_file.exists():
        return str(discovery_dir)
    return ""


# ---------------------------------------------------------------------------
# Main routing function
# ---------------------------------------------------------------------------


def infer_research_mode(
    idea_id: str,
    *,
    explicit_mode: str | None = None,
    explicit_planning_dir: str | None = None,
    explicit_discovery_dir: str | None = None,
    work_base: Path | None = None,
) -> RoutingResult:
    """Determine the research mode and associated directories.

    Parameters:
        idea_id: Identifier of the idea being researched.
        explicit_mode: Value of ``--research-mode`` flag (``"groundwork"``,
            ``"discovery-fed"``, ``"spike"``).  Takes highest precedence.
        explicit_planning_dir: Value of the legacy ``--mode`` flag (path to
            planning output directory).  Maps to spike mode.
        explicit_discovery_dir: Value of ``--discovery-dir`` flag.  Maps to
            discovery-fed mode when no higher-precedence input is provided.
        work_base: Base directory to scan when auto-routing.  Required only
            when no explicit flags resolve the mode.

    Returns:
        A :class:`RoutingResult` with the resolved mode and directories.

    Raises:
        RoutingError: If *explicit_mode* is not a valid :class:`ResearchMode`
            value, or if spike/discovery-fed mode is explicitly requested but
            the required upstream output cannot be found.
    """
    # -----------------------------------------------------------------
    # 1. Explicit --research-mode flag (highest precedence)
    # -----------------------------------------------------------------
    if explicit_mode is not None:
        try:
            mode = ResearchMode(explicit_mode)
        except ValueError:
            valid = ", ".join(m.value for m in ResearchMode)
            raise RoutingError(
                f"Invalid research mode {explicit_mode!r}. "
                f"Valid modes: {valid}"
            ) from None

        if mode is ResearchMode.SPIKE:
            # Explicit spike: use explicit planning dir or scan
            planning_dir = explicit_planning_dir or ""
            if not planning_dir and work_base:
                planning_dir = _scan_for_p5(work_base, idea_id)
            if not planning_dir:
                raise RoutingError(
                    "Spike mode requested but no planning directory with "
                    "P5 output found. Provide --mode <planning-dir> or "
                    "ensure a planning run exists in work_base."
                )
            return RoutingResult(
                mode=ResearchMode.SPIKE,
                planning_dir=planning_dir,
            )

        if mode is ResearchMode.DISCOVERY_FED:
            # Explicit discovery-fed: use explicit discovery dir or scan
            discovery_dir = explicit_discovery_dir or ""
            if not discovery_dir and work_base:
                discovery_dir = _scan_for_d5(work_base, idea_id)
            if not discovery_dir:
                raise RoutingError(
                    "Discovery-fed mode requested but no discovery directory "
                    "with D5 brief found. Provide --discovery-dir or "
                    "ensure a discovery run exists in work_base."
                )
            return RoutingResult(
                mode=ResearchMode.DISCOVERY_FED,
                discovery_dir=discovery_dir,
            )

        # Groundwork
        return RoutingResult(mode=ResearchMode.GROUNDWORK)

    # -----------------------------------------------------------------
    # 2. Legacy flags (--mode maps to spike, --discovery-dir maps to
    #    discovery-fed)
    # -----------------------------------------------------------------
    if explicit_planning_dir:
        warnings.warn(
            "Passing a planning directory via --mode is deprecated. "
            "Use --research-mode spike instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return RoutingResult(
            mode=ResearchMode.SPIKE,
            planning_dir=explicit_planning_dir,
        )

    if explicit_discovery_dir:
        warnings.warn(
            "Passing --discovery-dir without --research-mode is deprecated. "
            "Use --research-mode discovery-fed instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return RoutingResult(
            mode=ResearchMode.DISCOVERY_FED,
            discovery_dir=explicit_discovery_dir,
        )

    # -----------------------------------------------------------------
    # 3. Auto-routing: scan work_base for prior outputs
    # -----------------------------------------------------------------
    if work_base is not None:
        # Spike > discovery-fed > groundwork
        planning_dir = _scan_for_p5(work_base, idea_id)
        if planning_dir:
            return RoutingResult(
                mode=ResearchMode.SPIKE,
                planning_dir=planning_dir,
            )

        discovery_dir = _scan_for_d5(work_base, idea_id)
        if discovery_dir:
            return RoutingResult(
                mode=ResearchMode.DISCOVERY_FED,
                discovery_dir=discovery_dir,
            )

    # Default: groundwork
    return RoutingResult(mode=ResearchMode.GROUNDWORK)
