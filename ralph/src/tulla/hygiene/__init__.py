"""tulla.hygiene -- Shared hygiene library for Tulla scripts.

This package consolidates all hygiene functions into a single importable
library that any Tulla script can use. It provides:

- **Argument parsing**: ``parse_hygiene_args``, ``HygieneConfig``, ``HygieneMode``
- **Pre-flight cleanup**: ``run_preflight_hygiene``, ``inspect_directory``
- **Check mode**: ``run_check_mode``, ``run_check_mode_cli``
- **Control flow gate**: ``hygiene_gate``, ``GateResult``
- **Help text**: ``get_hygiene_help_text``, ``inject_hygiene_help``
- **Trap handler**: ``install_trap_handler``, ``TrapContext``
- **Startup logging**: ``log_preflight_decision``, ``PreflightDecision``
- **Fact updates**: ``apply_fact_update``, ``FactUpdate``, ``FactUpdateError``

Usage::

    from tulla.hygiene import hygiene_gate, install_trap_handler
    from pathlib import Path

    def main() -> None:
        cleanup = install_trap_handler("my-script")
        try:
            result = hygiene_gate(
                script_name="my-script",
                work_dirs=[Path("./work")],
            )
            # ... main logic using result.remaining_args ...
        finally:
            cleanup()
"""

# Args module -- core types and parsing
from tulla.hygiene.args import (
    HygieneConfig,
    HygieneMode,
    build_hygiene_parser,
    parse_hygiene_args,
)

# Pre-flight hygiene
from tulla.hygiene.preflight import (
    ALL_CLEANABLE_SUFFIXES,
    DEFAULT_STALE_THRESHOLD_SECS,
    HygieneReport,
    StaleFile,
    inspect_directory,
    run_preflight_hygiene,
)

# Check mode
from tulla.hygiene.check import (
    check_mode_exit_code,
    run_check_mode,
    run_check_mode_cli,
)

# Control flow gate
from tulla.hygiene.gate import (
    GateResult,
    hygiene_gate,
)

# Help text
from tulla.hygiene.help import (
    HYGIENE_HELP_BODY,
    HYGIENE_HELP_HEADER,
    HYGIENE_USAGE_LINE,
    format_hygiene_parser_help,
    get_hygiene_help_text,
    get_hygiene_usage_line,
    inject_hygiene_help,
)

# Trap handler
from tulla.hygiene.trap import (
    TRAPPED_SIGNALS,
    TrapContext,
    install_trap_handler,
)

# Startup logging
from tulla.hygiene.startup_log import (
    PreflightDecision,
    build_preflight_decision,
    log_preflight_decision,
)

# Fact update utilities
from tulla.hygiene.fact_update import (
    FactStore,
    FactUpdate,
    FactUpdateError,
    apply_fact_update,
    apply_fact_updates,
    validate_fact_update,
)

__all__ = [
    # Args
    "HygieneConfig",
    "HygieneMode",
    "build_hygiene_parser",
    "parse_hygiene_args",
    # Preflight
    "ALL_CLEANABLE_SUFFIXES",
    "DEFAULT_STALE_THRESHOLD_SECS",
    "HygieneReport",
    "StaleFile",
    "inspect_directory",
    "run_preflight_hygiene",
    # Check
    "check_mode_exit_code",
    "run_check_mode",
    "run_check_mode_cli",
    # Gate
    "GateResult",
    "hygiene_gate",
    # Help
    "HYGIENE_HELP_BODY",
    "HYGIENE_HELP_HEADER",
    "HYGIENE_USAGE_LINE",
    "format_hygiene_parser_help",
    "get_hygiene_help_text",
    "get_hygiene_usage_line",
    "inject_hygiene_help",
    # Trap
    "TRAPPED_SIGNALS",
    "TrapContext",
    "install_trap_handler",
    # Startup log
    "PreflightDecision",
    "build_preflight_decision",
    "log_preflight_decision",
    # Fact update
    "FactStore",
    "FactUpdate",
    "FactUpdateError",
    "apply_fact_update",
    "apply_fact_updates",
    "validate_fact_update",
]
