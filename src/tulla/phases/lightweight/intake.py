"""IntakePhase — classifies a change and determines lightweight eligibility.

# @pattern:EventSourcing -- Phase produces an immutable
#   IntakeOutput fact from git state and description, consumed
#   downstream
# @pattern:PortsAndAdapters -- Overrides run_claude() to perform
#   local computation, keeping the Phase[T] port contract intact
# @principle:FailSafeRouting -- Composite heuristic defaults to
#   ineligible for uncertain/refactor cases (0%
#   false-lightweight)

Architecture decisions: arch:adr-53-3, arch:adr-53-1
Quality focus: isaqb:Reliability
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from tulla.core.phase import Phase, PhaseContext
from tulla.phases.lightweight.models import IntakeOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CHANGE_TYPES = frozenset(
    {"bugfix", "feature", "enhancement", "chore", "test", "refactor"}
)

_KEYWORD_MAP: dict[str, list[str]] = {
    "bugfix": ["fix", "bug", "patch", "hotfix", "repair", "correct"],
    "test": ["test", "spec", "coverage", "assert"],
    "refactor": ["refactor", "restructure", "reorganize", "clean up", "cleanup"],
    "chore": ["chore", "ci", "build", "config", "dependency", "deps", "bump"],
    "enhancement": ["enhance", "improve", "update", "upgrade", "optimise", "optimize"],
    "feature": ["feature", "add", "new", "implement", "create", "introduce"],
}


# ---------------------------------------------------------------------------
# IntakePhase
# ---------------------------------------------------------------------------


class IntakePhase(Phase[IntakeOutput]):
    """Classify a change and determine lightweight pipeline eligibility.

    Overrides ``run_claude()`` to perform local computation instead of
    calling Claude.  Reads ``change_description`` from ``ctx.config``,
    classifies the change via keyword matching, extracts affected files
    from ``git diff``, and applies the composite routing heuristic.
    """

    phase_id: str = "intake"
    timeout_s: float = 30.0

    # ------------------------------------------------------------------
    # Template hooks (unused for non-Claude phase)
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Unused — non-Claude phase."""
        return ""

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Unused — non-Claude phase."""
        return []

    # ------------------------------------------------------------------
    # Core logic — overrides run_claude() per arch:adr-53-1
    # ------------------------------------------------------------------

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Perform local intake computation instead of calling Claude.

        Returns a dict consumed by ``parse_output()`` to build an
        ``IntakeOutput``.
        """
        description: str = ctx.config.get("change_description", "")
        change_type = _classify_change(description)
        affected_files = _get_affected_files()
        scope = _compute_scope(affected_files)
        eligible = _is_lightweight_eligible(
            change_type, affected_files, scope, description
        )

        return {
            "change_type": change_type,
            "description": description,
            "affected_files": affected_files,
            "scope": scope,
            "lightweight_eligible": eligible,
        }

    # ------------------------------------------------------------------
    # Parse output — wraps dict into IntakeOutput model
    # ------------------------------------------------------------------

    def parse_output(self, ctx: PhaseContext, raw: Any) -> IntakeOutput:
        """Wrap the dict returned by ``run_claude()`` into an IntakeOutput."""
        return IntakeOutput(**raw)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _classify_change(description: str) -> str:
    """Classify a change description into one of six categories using keyword matching.

    Checks keywords in a priority order that places more specific categories
    first (bugfix, test, refactor, chore, enhancement) and the broadest
    category (feature) last.  Returns ``"feature"`` as the default if no
    keywords match.
    """
    lower = description.lower()
    for category in ("bugfix", "test", "refactor", "chore", "enhancement", "feature"):
        for keyword in _KEYWORD_MAP[category]:
            if keyword in lower:
                return category
    # Default: treat unrecognised descriptions as feature (routed conservatively)
    return "feature"


def _get_affected_files() -> list[str]:
    """Extract affected files via ``git diff --name-only HEAD``.

    Paths returned by git are relative to the repository root, which may
    differ from the current working directory (e.g. when CWD is a
    subdirectory of the repo).  This function strips the repo-root prefix
    so that the returned paths are relative to CWD and can be opened
    directly by downstream phases.

    Falls back to an empty list if git is unavailable or the command fails.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        # Determine the CWD-relative prefix to strip from repo-root paths
        top_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        prefix = ""
        if top_result.returncode == 0:
            repo_root = Path(top_result.stdout.strip())
            cwd = Path.cwd()
            try:
                prefix = str(cwd.relative_to(repo_root))
            except ValueError:
                prefix = ""

        lines = result.stdout.strip().splitlines()
        files: list[str] = []
        for line in lines:
            name = line.strip()
            if not name:
                continue
            if prefix and name.startswith(prefix + "/"):
                name = name[len(prefix) + 1:]
            files.append(name)
        return files
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _compute_scope(affected_files: list[str]) -> str:
    """Determine package scope from affected file paths.

    Returns ``"single-package"`` if all files share a common top-level
    package directory, ``"cross-package"`` otherwise.  An empty file list
    is treated as single-package.
    """
    if not affected_files:
        return "single-package"

    top_dirs: set[str] = set()
    for path in affected_files:
        parts = path.split(os.sep)
        # Also handle forward slashes on all platforms (git output)
        if len(parts) == 1:
            parts = path.split("/")
        top_dirs.add(parts[0])

    return "single-package" if len(top_dirs) == 1 else "cross-package"


def _has_new_public_interfaces(description: str) -> bool:
    """Heuristic check for new public interfaces in the description.

    Scans for keywords suggesting new public API surface.
    """
    indicators = ["public api", "public interface", "new endpoint", "new api",
                   "expose", "export"]
    lower = description.lower()
    return any(indicator in lower for indicator in indicators)


def _is_lightweight_eligible(
    change_type: str,
    affected_files: list[str],
    scope: str,
    description: str,
) -> bool:
    """Apply the composite routing heuristic.

    Rules (arch:adr-53-3):
    - refactor: always ineligible
    - bugfix / chore / test: eligible if files <= 5
    - enhancement: eligible if files <= 3 AND single-package
    - feature: eligible if files <= 3, no new public interfaces, AND single-package
    - uncertain / unrecognised: defaults to ineligible (fail-safe)
    """
    file_count = len(affected_files)

    if change_type == "refactor":
        return False

    if change_type in ("bugfix", "chore", "test"):
        return file_count <= 5

    if change_type == "enhancement":
        return file_count <= 3 and scope == "single-package"

    if change_type == "feature":
        return (
            file_count <= 3
            and not _has_new_public_interfaces(description)
            and scope == "single-package"
        )

    # Unrecognised change type — fail-safe to ineligible
    return False
