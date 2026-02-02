"""Abstract port for Claude invocations.

Defines the request/result dataclasses and the abstract :class:`ClaudePort`
interface.  Concrete adapters (subprocess, SDK, mock) are provided in
``tulla.adapters`` and belong to Phase 2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Request / Result value objects
# ---------------------------------------------------------------------------


@dataclass
class ClaudeRequest:
    """Parameters for a single Claude invocation.

    Attributes:
        prompt: The prompt string to send to Claude.
        allowed_tools: Tool names Claude is permitted to use.
        budget_usd: Maximum dollar spend for this invocation.
        timeout_seconds: Wall-clock timeout; 0 means no limit.
        permission_mode: Permission / approval mode string
            (e.g. ``"auto"``, ``"manual"``).
    """

    prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    budget_usd: float = 0.0
    timeout_seconds: float = 0.0
    permission_mode: str = "bypassPermissions"


@dataclass
class ClaudeResult:
    """Outcome of a single Claude invocation.

    Attributes:
        exit_code: Process / API exit code (0 = success).
        output_text: Raw text output from Claude.
        output_json: Parsed JSON output, if available.
        cost_usd: Actual dollar cost of the invocation.
        duration_seconds: Wall-clock seconds elapsed.
        timed_out: Whether the invocation was terminated due to timeout.
    """

    exit_code: int = 0
    output_text: str = ""
    output_json: dict[str, Any] | None = None
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Abstract port
# ---------------------------------------------------------------------------


class ClaudePort(ABC):
    """Abstract interface for invoking Claude.

    Concrete implementations (subprocess wrapper, SDK client, test stub)
    live in ``tulla.adapters`` and are wired in at composition time.
    """

    @abstractmethod
    def run(self, request: ClaudeRequest) -> ClaudeResult:
        """Execute a Claude invocation described by *request*.

        Returns a :class:`ClaudeResult` with the outcome.  Implementations
        must populate ``timed_out=True`` when the timeout is exceeded rather
        than raising an exception.
        """
