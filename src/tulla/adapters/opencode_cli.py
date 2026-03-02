"""OpenCode CLI adapter – invokes ``opencode`` as a subprocess.

Implements :class:`ClaudePort` by shelling out to the ``opencode`` CLI.
OpenCode supports OpenAI plan logins and has MCP integration.

The OpenCode CLI interface:
- Uses -p/--prompt for the prompt
- Supports --model for model selection
- Uses --yes for auto-approval (non-interactive mode)
- JSON output via --output-format json

# @pattern:PortsAndAdapters -- Implements ClaudePort ABC for interchangeable LLM backends
# @principle:PostelsLaw -- Strict output, graceful degradation on malformed input
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import Any

from tulla.ports.claude import ClaudePort, ClaudeRequest, ClaudeResult

logger = logging.getLogger(__name__)


class OpenCodeCLIAdapter(ClaudePort):
    """Concrete :class:`ClaudePort` that invokes the ``opencode`` CLI.

    Parameters:
        opencode_bin: Path or name of the ``opencode`` binary (default ``"opencode"``).
        model: Model to use (default ``"gpt-4.1"``).
        provider: Provider name if using non-default backend.
    """

    def __init__(
        self,
        opencode_bin: str = "opencode",
        model: str = "gpt-4.1",
        provider: str | None = None,
    ) -> None:
        self._opencode_bin = opencode_bin
        self._model = model
        self._provider = provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        """Execute an OpenCode CLI invocation described by *request*."""
        cmd = self._build_command(request)
        start = time.monotonic()

        timeout = request.timeout_seconds if request.timeout_seconds > 0 else None
        cwd = str(request.cwd) if request.cwd is not None else None

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            logger.warning(
                "OpenCode CLI timed out after %.1f s", elapsed,
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
            "OpenCode subprocess completed",
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
            logger.debug("OpenCode stdout", extra={"output": proc.stdout})
        if proc.stderr:
            logger.debug("OpenCode stderr", extra={"output": proc.stderr})

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
        cmd: list[str] = [self._opencode_bin]

        # Model selection
        cmd.extend(["--model", self._model])

        # Provider if specified
        if self._provider:
            cmd.extend(["--provider", self._provider])

        # Auto-approval for non-interactive mode (maps from permission modes)
        if request.permission_mode in ("bypassPermissions", "auto", "full-auto"):
            cmd.append("--yes")

        # Output format
        cmd.extend(["--output-format", "json"])

        # Quiet mode to suppress interactive prompts
        cmd.append("--quiet")

        # Tool filtering (OpenCode style)
        if request.allowed_tools:
            cmd.extend(["--tools", ",".join(request.allowed_tools)])

        if request.disallowed_tools:
            cmd.extend(["--disable-tools", ",".join(request.disallowed_tools)])

        # Prompt via -p flag
        cmd.extend(["-p", request.prompt])

        return cmd

    @staticmethod
    def _try_parse_json(stdout: str) -> dict[str, Any] | None:
        """Attempt to parse *stdout* as JSON; return ``None`` on failure.

        Handles both single JSON object and newline-delimited JSON (NDJSON)
        by taking the last complete JSON object.
        """
        if not stdout or not stdout.strip():
            return None

        # Try parsing as single JSON object first
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Try NDJSON - take the last valid JSON line
        for line in reversed(stdout.strip().split("\n")):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                continue

        return None

    @staticmethod
    def _extract_cost(output_json: dict[str, Any] | None) -> float:
        """Extract cost from OpenCode JSON output.

        Checks various field names used by OpenAI-compatible backends.
        Returns ``0.0`` when no cost information is found.
        """
        if output_json is None:
            return 0.0

        cost_keys = (
            "total_cost",
            "cost",
            "cost_usd",
            "total_cost_usd",
            "costUsd",
        )
        containers = ("usage", "metadata", "result", "stats", "session")

        # Check top-level keys first
        for key in cost_keys:
            if key in output_json:
                try:
                    return float(output_json[key])
                except (TypeError, ValueError):
                    continue

        # Check nested containers
        for container in containers:
            nested = output_json.get(container)
            if isinstance(nested, dict):
                for key in cost_keys:
                    if key in nested:
                        try:
                            return float(nested[key])
                        except (TypeError, ValueError):
                            continue

        # OpenAI-style: calculate from token counts if available
        usage = output_json.get("usage", {})
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            # Rough estimate for GPT-4.1 pricing (adjust as needed)
            if prompt_tokens or completion_tokens:
                return float((prompt_tokens * 0.01 + completion_tokens * 0.03) / 1000)

        return 0.0
