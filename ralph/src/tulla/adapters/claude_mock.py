"""Mock Claude adapter for testing.

Provides :class:`MockClaudeAdapter`, a :class:`ClaudePort` implementation that
returns pre-configured responses without calling the real Claude CLI.  Used by
all phase tests to avoid external dependencies.
"""

from __future__ import annotations

from typing import Callable

from tulla.ports.claude import ClaudePort, ClaudeRequest, ClaudeResult


class MockClaudeAdapter(ClaudePort):
    """Test double for :class:`ClaudePort`.

    Supports three response strategies (checked in order):

    1. **responses dict** – keyed by a substring matched against the prompt.
    2. **response_fn** – callable for dynamic / stateful behaviour.
    3. **default_response** – fallback when neither of the above matches.

    Every invocation is recorded in :attr:`calls` so tests can assert on
    what was sent.

    Parameters:
        responses: Mapping of prompt-substring → :class:`ClaudeResult`.
        response_fn: Optional callable ``(ClaudeRequest) -> ClaudeResult``.
        default_response: Fallback result when no other strategy matches.
    """

    def __init__(
        self,
        responses: dict[str, ClaudeResult] | None = None,
        response_fn: Callable[[ClaudeRequest], ClaudeResult] | None = None,
        default_response: ClaudeResult | None = None,
    ) -> None:
        self.responses: dict[str, ClaudeResult] = responses or {}
        self.response_fn = response_fn
        self.default_response = default_response or ClaudeResult(
            exit_code=0,
            output_text="mock response",
        )
        self.calls: list[ClaudeRequest] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        """Return a pre-configured response and record the call."""
        self.calls.append(request)

        # Strategy 1: match prompt substring in responses dict.
        for key, result in self.responses.items():
            if key in request.prompt:
                return result

        # Strategy 2: dynamic callable.
        if self.response_fn is not None:
            return self.response_fn(request)

        # Strategy 3: default fallback.
        return self.default_response
