"""Pre-flight hygiene function for Tulla scripts.

Performs cleanup of stale state before a Tulla script run.
Inspects and optionally removes:
  - Stale lock files (older than a configurable threshold)
  - Orphaned temp files in work directories
  - Expired .pid files for dead processes

Integrates with HygieneConfig from args to respect
--clean, --no-clean, and --check modes.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from tulla.hygiene.args import HygieneConfig

logger = logging.getLogger(__name__)

# Default threshold in seconds (1 hour) for considering a lock/temp file stale.
DEFAULT_STALE_THRESHOLD_SECS: int = 3600

# File patterns considered temporary / cleanable artifacts.
LOCK_SUFFIXES: frozenset[str] = frozenset({".lock", ".lck"})
TEMP_SUFFIXES: frozenset[str] = frozenset({".tmp", ".temp", ".partial"})
PID_SUFFIXES: frozenset[str] = frozenset({".pid"})

ALL_CLEANABLE_SUFFIXES: frozenset[str] = LOCK_SUFFIXES | TEMP_SUFFIXES | PID_SUFFIXES


@dataclass(frozen=True)
class StaleFile:
    """Represents a stale file discovered during pre-flight inspection.

    Attributes:
        path: Absolute path to the stale file.
        category: Classification of the file (lock, temp, or pid).
        age_secs: How old the file is in seconds.
        reason: Human-readable explanation of why it is considered stale.
    """

    path: Path
    category: str
    age_secs: float
    reason: str


@dataclass(frozen=True)
class HygieneReport:
    """Result of a pre-flight hygiene inspection or cleanup.

    Attributes:
        stale_files: Files identified as stale during inspection.
        cleaned_files: Files that were actually removed (empty in check mode).
        errors: Paths that could not be cleaned, with error descriptions.
        mode_used: String label of the hygiene mode that was applied.
    """

    stale_files: list[StaleFile] = field(default_factory=list)
    cleaned_files: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    mode_used: str = "clean"

    @property
    def is_clean(self) -> bool:
        """Whether the workspace has no stale files."""
        return len(self.stale_files) == 0

    @property
    def issues_found(self) -> int:
        """Number of stale files discovered."""
        return len(self.stale_files)

    @property
    def cleaned_count(self) -> int:
        """Number of files actually removed."""
        return len(self.cleaned_files)

    def summary(self) -> str:
        """Return a human-readable one-line summary of the report."""
        if self.is_clean:
            return "Pre-flight hygiene: workspace is clean."
        if self.mode_used == "check":
            return (
                f"Pre-flight hygiene (check): {self.issues_found} "
                f"stale file(s) found."
            )
        return (
            f"Pre-flight hygiene: cleaned {self.cleaned_count} of "
            f"{self.issues_found} stale file(s)"
            + (f", {len(self.errors)} error(s)." if self.errors else ".")
        )


def _file_age_secs(path: Path) -> float:
    """Return the age of a file in seconds based on its mtime."""
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0.0


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is still running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't signal it -- still alive.
        return True
    except OSError:
        return False


def _classify_file(path: Path) -> str | None:
    """Return the stale-file category for a path, or None if not cleanable."""
    suffix = path.suffix.lower()
    if suffix in LOCK_SUFFIXES:
        return "lock"
    if suffix in TEMP_SUFFIXES:
        return "temp"
    if suffix in PID_SUFFIXES:
        return "pid"
    return None


def _inspect_pid_file(path: Path) -> str | None:
    """Inspect a .pid file. Return a stale reason if the process is dead, else None."""
    try:
        content = path.read_text().strip()
        pid = int(content)
    except (OSError, ValueError):
        return "unreadable or invalid PID file"
    if not _is_pid_alive(pid):
        return f"PID {pid} is no longer running"
    return None


def inspect_directory(
    directory: Path,
    stale_threshold_secs: int = DEFAULT_STALE_THRESHOLD_SECS,
) -> list[StaleFile]:
    """Scan a directory for stale lock, temp, and PID files.

    Args:
        directory: The directory to inspect.
        stale_threshold_secs: Age in seconds after which a lock/temp
            file is considered stale.

    Returns:
        A list of StaleFile entries for files deemed stale.
    """
    stale: list[StaleFile] = []

    if not directory.is_dir():
        return stale

    for item in sorted(directory.rglob("*")):
        if not item.is_file():
            continue

        category = _classify_file(item)
        if category is None:
            continue

        age = _file_age_secs(item)

        if category == "pid":
            reason = _inspect_pid_file(item)
            if reason is None:
                continue  # PID is still alive -- not stale.
            stale.append(StaleFile(
                path=item, category=category, age_secs=age, reason=reason,
            ))
        elif age >= stale_threshold_secs:
            reason = (
                f"{category} file is {age / 3600:.1f}h old "
                f"(threshold: {stale_threshold_secs / 3600:.1f}h)"
            )
            stale.append(StaleFile(
                path=item, category=category, age_secs=age, reason=reason,
            ))

    return stale


def run_preflight_hygiene(
    config: HygieneConfig,
    directories: Sequence[Path],
    stale_threshold_secs: int = DEFAULT_STALE_THRESHOLD_SECS,
) -> HygieneReport:
    """Execute pre-flight hygiene according to the resolved configuration.

    In CLEAN mode, stale files are identified and removed.
    In CHECK mode, stale files are identified but not removed.
    In NO_CLEAN mode, inspection is skipped entirely.

    Args:
        config: The parsed HygieneConfig (from args).
        directories: Work directories to inspect.
        stale_threshold_secs: Age threshold for lock/temp files.

    Returns:
        A HygieneReport summarizing what was found and done.
    """
    if config.is_disabled:
        logger.debug("Pre-flight hygiene disabled (--no-clean).")
        return HygieneReport(mode_used="no-clean")

    # Inspect all directories.
    all_stale: list[StaleFile] = []
    for d in directories:
        all_stale.extend(inspect_directory(d, stale_threshold_secs))

    if config.is_check_only:
        for sf in all_stale:
            logger.info("CHECK: %s -- %s", sf.path, sf.reason)
        return HygieneReport(stale_files=all_stale, mode_used="check")

    # CLEAN mode -- actually remove stale files.
    cleaned: list[Path] = []
    errors: list[tuple[Path, str]] = []

    for sf in all_stale:
        try:
            sf.path.unlink()
            cleaned.append(sf.path)
            logger.info("Cleaned: %s -- %s", sf.path, sf.reason)
        except OSError as exc:
            errors.append((sf.path, str(exc)))
            logger.warning("Failed to clean %s: %s", sf.path, exc)

    return HygieneReport(
        stale_files=all_stale,
        cleaned_files=cleaned,
        errors=errors,
        mode_used="clean",
    )
