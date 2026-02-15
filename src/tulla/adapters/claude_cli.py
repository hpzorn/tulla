"""Claude CLI adapter – invokes ``claude`` as a subprocess.

Implements :class:`ClaudePort` by shelling out to the ``claude`` CLI with
``--output-format json``.  Follows Postel's Law: strict in what it sends,
liberal in what it accepts (graceful degradation when JSON is unavailable).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from typing import Any

from tulla.ports.claude import ClaudePort, ClaudeRequest, ClaudeResult

logger = logging.getLogger(__name__)


class ClaudeCLIAdapter(ClaudePort):
    """Concrete :class:`ClaudePort` that invokes the ``claude`` CLI.

    Parameters:
        claude_bin: Path or name of the ``claude`` binary (default ``"claude"``).
    """

    def __init__(self, claude_bin: str = "claude") -> None:
        self._claude_bin = claude_bin

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        """Execute a Claude CLI invocation described by *request*."""
        cmd = self._build_command(request)
        start = time.monotonic()

        timeout = request.timeout_seconds if request.timeout_seconds > 0 else None
        cwd = str(request.cwd) if request.cwd is not None else None

        # Strip CLAUDECODE so the subprocess doesn't think it's nested.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            logger.warning(
                "Claude CLI timed out after %.1f s", elapsed,
            )
            return ClaudeResult(
                exit_code=124,
                output_text="",
                timed_out=True,
                duration_seconds=elapsed,
            )

        elapsed = time.monotonic() - start
        output_json = self._try_parse_json(proc.stdout)
        cost = self._extract_cost(output_json)

        logger.debug(
            "Claude subprocess completed",
            extra={
                "exit_code": proc.returncode,
                "cost_usd": cost,
                "duration_s": round(elapsed, 2),
                "stdout_length": len(proc.stdout),
                "stderr_length": len(proc.stderr),
                "cwd": cwd,
            },
        )
        if proc.stdout:
            logger.debug("Claude stdout", extra={"output": proc.stdout})
        if proc.stderr:
            logger.debug("Claude stderr", extra={"output": proc.stderr})

        return ClaudeResult(
            exit_code=proc.returncode,
            output_text=proc.stdout,
            output_json=output_json,
            cost_usd=cost,
            duration_seconds=elapsed,
            timed_out=False,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_command(self, request: ClaudeRequest) -> list[str]:
        """Construct the CLI argument list from *request*."""
        cmd: list[str] = [
            self._claude_bin,
            "--output-format", "json",
            "-p", request.prompt,
        ]

        if request.budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(request.budget_usd)])

        if request.permission_mode:
            cmd.extend(["--permission-mode", request.permission_mode])

        if request.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(request.allowed_tools)])

        if request.disallowed_tools:
            cmd.extend(["--disallowedTools", ",".join(request.disallowed_tools)])

        return cmd

    @staticmethod
    def _try_parse_json(stdout: str) -> dict[str, Any] | None:
        """Attempt to parse *stdout* as JSON; return ``None`` on failure.

        Follows Postel's Law – never raises on malformed input.
        """
        if not stdout or not stdout.strip():
            return None
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                return parsed
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _extract_cost(output_json: dict[str, Any] | None) -> float:
        """Extract cost from various JSON shapes produced by the CLI.

        Checks the following keys (in order) at multiple nesting levels:
        ``cost_usd``, ``costUsd``, ``total_cost``, ``cost`` — both at the
        top level and nested under ``usage``, ``metadata``, and ``result``
        containers.  Returns ``0.0`` when no cost information is found.
        """
        if output_json is None:
            return 0.0

        cost_keys = ("total_cost_usd", "cost_usd", "costUsd", "total_cost", "cost")
        containers = ("usage", "metadata", "result", "modelUsage")

        # Check top-level keys first.
        for key in cost_keys:
            if key in output_json:
                try:
                    return float(output_json[key])
                except (TypeError, ValueError):
                    continue

        # Check nested containers.
        for container in containers:
            nested = output_json.get(container)
            if isinstance(nested, dict):
                for key in cost_keys:
                    if key in nested:
                        try:
                            return float(nested[key])
                        except (TypeError, ValueError):
                            continue

        return 0.0
