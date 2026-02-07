"""Codex CLI adapter – invokes ``codex`` as a subprocess.

Implements :class:`ClaudePort` by shelling out to OpenAI's ``codex`` CLI.
Follows Postel's Law: strict in what it sends, liberal in what it accepts.

The Codex CLI has a different interface than Claude CLI:
- Uses positional prompt argument or --prompt flag
- Supports --model for model selection (o4-mini, o3, etc.)
- Uses --approval-mode (suggest, auto-edit, full-auto)
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

# Mapping from tulla permission modes to codex approval modes
_PERMISSION_MODE_MAP: dict[str, str] = {
    "bypassPermissions": "full-auto",
    "auto": "auto-edit",
    "manual": "suggest",
    "suggest": "suggest",
    "auto-edit": "auto-edit",
    "full-auto": "full-auto",
}


class CodexCLIAdapter(ClaudePort):
    """Concrete :class:`ClaudePort` that invokes the ``codex`` CLI.

    Parameters:
        codex_bin: Path or name of the ``codex`` binary (default ``"codex"``).
        model: Model to use (default ``"gpt-5.3-codex"``).
        provider: Provider name if using non-OpenAI backend.
    """

    def __init__(
        self,
        codex_bin: str = "codex",
        model: str = "gpt-5.3-codex",
        provider: str | None = None,
    ) -> None:
        self._codex_bin = codex_bin
        self._model = model
        self._provider = provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        """Execute a Codex CLI invocation described by *request*."""
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
                "Codex CLI timed out after %.1f s", elapsed,
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
            "Codex subprocess completed",
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
            logger.debug("Codex stdout", extra={"output": proc.stdout})
        if proc.stderr:
            logger.debug("Codex stderr", extra={"output": proc.stderr})

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
        cmd: list[str] = [self._codex_bin]

        # Model selection
        cmd.extend(["--model", self._model])

        # Provider if specified
        if self._provider:
            cmd.extend(["--provider", self._provider])

        # Approval mode (mapped from permission_mode)
        approval_mode = _PERMISSION_MODE_MAP.get(
            request.permission_mode, "full-auto"
        )
        cmd.extend(["--approval-mode", approval_mode])

        # Output format
        cmd.extend(["--output-format", "json"])

        # Quiet mode to suppress interactive prompts
        cmd.append("--quiet")

        # Allowed/disallowed tools (codex uses different syntax)
        # Codex doesn't have direct tool filtering like Claude,
        # but we can use --no-* flags for specific capabilities
        if request.disallowed_tools:
            for tool in request.disallowed_tools:
                tool_lower = tool.lower()
                if tool_lower in ("bash", "shell", "exec"):
                    cmd.append("--no-shell")
                elif tool_lower in ("write", "edit"):
                    cmd.append("--no-write")
                elif tool_lower in ("read",):
                    cmd.append("--no-read")

        # The prompt goes last as positional argument
        cmd.append(request.prompt)

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
        """Extract cost from Codex JSON output.

        Codex uses different field names than Claude. Checks:
        ``total_cost``, ``cost``, ``usage.total_cost``, etc.
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
        containers = ("usage", "metadata", "result", "stats")

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

        # Codex-specific: calculate from token counts if available
        usage = output_json.get("usage", {})
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            # Rough estimate for o4-mini pricing
            if input_tokens or output_tokens:
                return (input_tokens * 0.00015 + output_tokens * 0.0006) / 1000

        return 0.0
