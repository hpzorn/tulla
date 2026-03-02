"""Argument parsing for Tulla script hygiene modes.

Provides --clean, --no-clean, and --check argument parsing
that can be integrated into any Tulla script's CLI interface.

Hygiene modes:
    --clean    : Enable pre-flight hygiene (cleanup stale state before run)
    --no-clean : Disable pre-flight hygiene (preserve existing state)
    --check    : Dry-run hygiene check (report what would be cleaned, don't execute)

Default behavior when no flag is provided: clean is enabled.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class HygieneMode(Enum):
    """Operating modes for the hygiene subsystem."""

    CLEAN = "clean"
    NO_CLEAN = "no-clean"
    CHECK = "check"


@dataclass(frozen=True)
class HygieneConfig:
    """Parsed hygiene configuration from CLI arguments.

    Attributes:
        mode: The selected hygiene mode.
        remaining_args: Arguments not consumed by hygiene parsing,
            passed through for the host script's own argument parser.
    """

    mode: HygieneMode
    remaining_args: list[str]

    @property
    def should_clean(self) -> bool:
        """Whether hygiene cleanup should actually execute."""
        return self.mode == HygieneMode.CLEAN

    @property
    def is_check_only(self) -> bool:
        """Whether we're in dry-run check mode."""
        return self.mode == HygieneMode.CHECK

    @property
    def is_disabled(self) -> bool:
        """Whether hygiene is explicitly disabled."""
        return self.mode == HygieneMode.NO_CLEAN


def build_hygiene_parser() -> argparse.ArgumentParser:
    """Create an argument parser for hygiene-related flags.

    Returns:
        An ArgumentParser configured with --clean, --no-clean, and --check
        as a mutually exclusive group.
    """
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--clean",
        action="store_const",
        const=HygieneMode.CLEAN,
        dest="hygiene_mode",
        help="Enable pre-flight hygiene (default)",
    )
    group.add_argument(
        "--no-clean",
        action="store_const",
        const=HygieneMode.NO_CLEAN,
        dest="hygiene_mode",
        help="Disable pre-flight hygiene",
    )
    group.add_argument(
        "--check",
        action="store_const",
        const=HygieneMode.CHECK,
        dest="hygiene_mode",
        help="Dry-run: report what would be cleaned without executing",
    )
    return parser


def parse_hygiene_args(argv: Sequence[str] | None = None) -> HygieneConfig:
    """Parse hygiene arguments from the command line.

    This uses parse_known_args so that unrecognized arguments are
    preserved and returned in remaining_args for the host script.

    Args:
        argv: Command-line arguments to parse. Defaults to sys.argv[1:].

    Returns:
        A HygieneConfig with the resolved mode and remaining arguments.
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = build_hygiene_parser()
    known, remaining = parser.parse_known_args(list(argv))

    mode = known.hygiene_mode if known.hygiene_mode is not None else HygieneMode.CLEAN

    return HygieneConfig(mode=mode, remaining_args=remaining)
