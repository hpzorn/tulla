"""Phase base class and supporting types for Tulla's pipeline execution."""

from __future__ import annotations

import enum
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PhaseStatus(enum.Enum):
    """Outcome status of a phase execution."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ParseError(Exception):
    """Raised when phase output cannot be parsed.

    Captures the raw output and an optional context dict so callers can
    inspect what went wrong.
    """

    def __init__(
        self,
        message: str,
        raw_output: Any = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.context = context or {}


class EarlyTermination(Exception):
    """Signals an intentional early pipeline stop.

    The phase succeeded, but further phases would be wasteful.
    Caught by :meth:`Phase.execute` and converted into a
    :class:`PhaseResult` with ``status=FAILURE`` and
    ``early_terminate`` metadata so the existing pipeline
    break-on-FAILURE logic stops the run.
    """

    def __init__(self, reason: str, r1_output: Any = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.r1_output = r1_output


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult(Generic[T]):
    """Result envelope returned by every phase execution.

    Attributes:
        status: Overall outcome.
        data: Parsed output (generic).
        error: Optional error message when status != SUCCESS.
        duration_s: Wall-clock seconds the phase took.
        metadata: Extra key-value pairs for debugging / telemetry.
    """

    status: PhaseStatus
    data: T | None = None
    error: str | None = None
    duration_s: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON encoding."""
        data = self.data
        if data is not None and hasattr(data, "model_dump"):
            # Pydantic BaseModel — use mode="json" to handle Path etc.
            data = data.model_dump(mode="json")
        return {
            "status": self.status.value,
            "data": data,
            "error": self.error,
            "duration_s": self.duration_s,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PhaseResult[Any]:
        """Reconstruct a PhaseResult from a dict produced by *to_dict()*."""
        return cls(
            status=PhaseStatus(d["status"]),
            data=d.get("data"),
            error=d.get("error"),
            duration_s=d.get("duration_s", 0.0),
            metadata=d.get("metadata", {}),
        )


@dataclass
class PhaseContext:
    """Immutable bag of state threaded through every phase.

    Attributes:
        idea_id: Identifier of the idea being processed.
        work_dir: Scratch directory for this run.
        config: Arbitrary configuration dict.
        budget_remaining_usd: Remaining dollar budget for Claude calls.
        logger: Logger instance (defaults to module-level logger).
    """

    idea_id: str
    work_dir: Path
    config: dict[str, Any] = field(default_factory=dict)
    budget_remaining_usd: float = 0.0
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger(__name__)
    )


# ---------------------------------------------------------------------------
# Abstract base class – Template Method
# ---------------------------------------------------------------------------


class Phase(ABC, Generic[T]):
    """Abstract base for every pipeline phase.

    Subclasses implement the four hook methods; the public *execute()*
    method orchestrates them using the Template Method pattern and
    provides uniform error handling.
    """

    # Subclasses may set a per-phase timeout (seconds); 0 means no limit.
    timeout_s: float = 0.0

    # ------------------------------------------------------------------
    # Template hooks – override in subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def build_prompt(self, ctx: PhaseContext) -> str:
        """Return the prompt string to send to Claude."""

    @abstractmethod
    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during this phase."""

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Invoke Claude via the adapter in ``ctx.config["claude_port"]``.

        Builds a :class:`~tulla.ports.claude.ClaudeRequest` from the prompt,
        tools, and budget, then delegates to the injected
        :class:`~tulla.ports.claude.ClaudePort`.  Subclasses may override
        for custom invocation behaviour.

        Raises :class:`TimeoutError` if the Claude invocation times out.
        """
        from tulla.ports.claude import ClaudeRequest

        claude_port = ctx.config.get("claude_port")
        if claude_port is None:
            raise RuntimeError(
                "No claude_port in context config. "
                "Ensure the pipeline injects a ClaudePort adapter."
            )

        tool_names = [t["name"] for t in tools if "name" in t]
        disallowed = self.get_disallowed_tools(ctx)
        phase_timeouts = ctx.config.get("phase_timeouts", {})
        timeout = phase_timeouts.get(
            getattr(self, "phase_id", ""),
            getattr(self, "timeout_s", 0.0),
        )
        permission_mode = ctx.config.get("permission_mode", "bypassPermissions")

        request = ClaudeRequest(
            prompt=prompt,
            allowed_tools=tool_names,
            disallowed_tools=disallowed,
            budget_usd=ctx.budget_remaining_usd,
            timeout_seconds=timeout,
            permission_mode=permission_mode,
            cwd=ctx.work_dir,
        )

        result = claude_port.run(request)

        if result.timed_out:
            raise TimeoutError(
                f"Claude invocation timed out after {result.duration_seconds:.1f}s"
            )

        return result

    def get_disallowed_tools(self, ctx: PhaseContext) -> list[str]:
        """Return tool names Claude must NOT use during this phase.

        Default is empty.  Override to block specific MCP tools that
        the server exposes but that this phase should not use.
        """
        return []

    @abstractmethod
    def parse_output(self, ctx: PhaseContext, raw: Any) -> T:
        """Parse *raw* Claude output into the phase's result type *T*.

        Must raise :class:`ParseError` if the output cannot be parsed.
        """

    # ------------------------------------------------------------------
    # Optional hooks
    # ------------------------------------------------------------------

    def validate_input(self, ctx: PhaseContext) -> None:
        """Validate preconditions before execution.

        Raise :class:`ValueError` (or a subclass) if preconditions are
        not met.  The default implementation is a no-op.
        """

    def validate_output(self, ctx: PhaseContext, parsed: T) -> None:
        """Validate the parsed result before returning.

        Raise :class:`ValueError` if the output is unacceptable.
        The default implementation is a no-op.
        """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, ctx: PhaseContext) -> PhaseResult[T]:
        """Run the phase end-to-end, returning a :class:`PhaseResult`.

        Steps:
            1. Input validation
            2. Build prompt
            3. Get tools
            4. Run Claude (with optional timeout)
            5. Parse output
            6. Validate output
        """
        start = time.monotonic()
        log = ctx.logger

        # 1 — input validation
        try:
            self.validate_input(ctx)
        except Exception as exc:
            log.warning("Phase input validation failed: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Input validation failed: {exc}",
                duration_s=time.monotonic() - start,
            )

        # 2 — build prompt
        try:
            prompt = self.build_prompt(ctx)
            prompt += (
                "\n\n## IMPORTANT: File Write Constraint\n"
                "You MUST only create or modify files inside the work "
                f"directory: {ctx.work_dir}\n"
                "Do NOT write files anywhere else on the filesystem."
            )
        except Exception as exc:
            log.error("Phase build_prompt failed: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Prompt build failed: {exc}",
                duration_s=time.monotonic() - start,
            )

        # 3 — get tools
        try:
            tools = self.get_tools(ctx)
        except Exception as exc:
            log.error("Phase get_tools failed: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Get tools failed: {exc}",
                duration_s=time.monotonic() - start,
            )

        # 3b — log prompt for post-mortem debugging
        log.debug("Claude prompt", extra={
            "phase_id": getattr(self, "phase_id", "unknown"),
            "idea_id": ctx.idea_id,
            "prompt": prompt,
            "tool_names": [t.get("name", "") for t in tools],
        })

        # 4 — run Claude
        cost_usd = 0.0
        try:
            raw = self.run_claude(ctx, prompt, tools)
            # Extract cost from ClaudeResult if available
            if hasattr(raw, "cost_usd"):
                cost_usd = raw.cost_usd
            if hasattr(raw, "output_text") and raw.output_text:
                log.debug(
                    "Claude output for phase",
                    extra={"output": raw.output_text},
                )
        except TimeoutError:
            log.warning("Phase timed out")
            return PhaseResult(
                status=PhaseStatus.TIMEOUT,
                error="Claude invocation timed out",
                duration_s=time.monotonic() - start,
            )
        except Exception as exc:
            log.error("Phase run_claude failed: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Claude invocation failed: {exc}",
                duration_s=time.monotonic() - start,
            )

        # 5 — parse output
        try:
            parsed = self.parse_output(ctx, raw)
        except EarlyTermination as et:
            log.info("Early termination: %s", et.reason)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                data=et.r1_output,
                duration_s=time.monotonic() - start,
                metadata={"early_terminate": True, "reason": et.reason},
            )
        except ParseError as exc:
            log.warning("Phase parse_output failed: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Output parsing failed: {exc}",
                duration_s=time.monotonic() - start,
                metadata={"parse_context": exc.context},
            )
        except Exception as exc:
            log.error("Unexpected parse error: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Output parsing failed: {exc}",
                duration_s=time.monotonic() - start,
            )

        # 6 — validate output
        try:
            self.validate_output(ctx, parsed)
        except Exception as exc:
            log.warning("Phase output validation failed: %s", exc)
            return PhaseResult(
                status=PhaseStatus.FAILURE,
                error=f"Output validation failed: {exc}",
                duration_s=time.monotonic() - start,
            )

        elapsed = time.monotonic() - start
        log.info("Phase completed successfully in %.2fs", elapsed)
        return PhaseResult(
            status=PhaseStatus.SUCCESS,
            data=parsed,
            duration_s=elapsed,
            metadata={"cost_usd": cost_usd},
        )
