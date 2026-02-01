"""Structured logging configuration for Ralph pipeline execution."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    *,
    work_dir: Path | None = None,
    phase_id: str | None = None,
    level: int = logging.DEBUG,
    **initial_context: object,
) -> structlog.stdlib.BoundLogger:
    """Configure structlog with console + optional JSON file output.

    Args:
        work_dir: If provided (together with *phase_id*), a JSON-lines log
            file is written to ``{work_dir}/{phase_id}.log.json``.
        phase_id: Identifier used for the JSON log filename.
        level: Minimum log level for all handlers (default ``DEBUG``).
        **initial_context: Extra key-value pairs bound to the returned
            logger instance.

    Returns:
        A bound structlog logger ready for use.
    """
    # Shared structlog processors (applied before formatting).
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    # -- Root stdlib logger --------------------------------------------------
    root_logger = logging.getLogger()
    # Remove any pre-existing handlers so repeated calls don't duplicate.
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    # -- Console handler (human-readable, stderr) ----------------------------
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # -- Optional JSON file handler ------------------------------------------
    if work_dir is not None and phase_id is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
        file_handler = logging.FileHandler(
            work_dir / f"{phase_id}.log.json",
            mode="a",
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    # Return a bound logger with any initial context.
    logger: structlog.stdlib.BoundLogger = structlog.get_logger()
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger
