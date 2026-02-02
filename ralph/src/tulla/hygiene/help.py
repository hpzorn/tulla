"""Help text utilities for Ralph script hygiene modes.

Provides formatted help/usage text that documents the --clean,
--no-clean, and --check flags available in any Ralph script
with hygiene support.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from ralph.hygiene.args import build_hygiene_parser

if TYPE_CHECKING:
    import argparse

# Compact one-line summary for embedding in other help output.
HYGIENE_USAGE_LINE = "  [--clean | --no-clean | --check]"

# Section header used when appending hygiene help to a script's own help.
HYGIENE_HELP_HEADER = "Hygiene Options:"

# Detailed description block for hygiene modes.
HYGIENE_HELP_BODY = """\
  --clean       Enable pre-flight hygiene before execution (default).
                Cleans stale state, expired locks, and orphaned temp files.
  --no-clean    Skip pre-flight hygiene entirely. Preserves all existing
                state -- useful for resuming interrupted runs.
  --check       Dry-run mode. Reports what pre-flight hygiene would clean
                without executing any changes. Exit code 0 = clean,
                1 = issues found."""


def get_hygiene_help_text() -> str:
    """Return the full hygiene help section as a formatted string.

    Returns:
        A multi-line string containing the header and all flag
        descriptions, ready to be printed or appended to help output.
    """
    return f"{HYGIENE_HELP_HEADER}\n{HYGIENE_HELP_BODY}"


def get_hygiene_usage_line() -> str:
    """Return the compact usage line fragment for hygiene flags.

    This is meant to be embedded in a script's usage synopsis, e.g.:
        ``usage: research-ralph.sh [options] [--clean | --no-clean | --check]``

    Returns:
        A short usage fragment string.
    """
    return HYGIENE_USAGE_LINE


def format_hygiene_parser_help() -> str:
    """Format the argparse-generated help from the hygiene parser.

    Uses the parser built by build_hygiene_parser() to produce
    help text that stays in sync with the actual argument definitions.

    Returns:
        The argparse-formatted help string for hygiene arguments.
    """
    parser: argparse.ArgumentParser = build_hygiene_parser()
    buf = io.StringIO()
    parser.print_help(buf)
    return buf.getvalue()


def inject_hygiene_help(script_name: str, script_description: str) -> str:
    """Build a complete help message for a Ralph script with hygiene support.

    Args:
        script_name: Name of the script (e.g., "research-ralph.sh").
        script_description: One-line description of what the script does.

    Returns:
        A formatted help string combining script info and hygiene options.
    """
    lines = [
        f"Usage: {script_name} [options]{HYGIENE_USAGE_LINE}",
        "",
        f"  {script_description}",
        "",
        get_hygiene_help_text(),
    ]
    return "\n".join(lines)
