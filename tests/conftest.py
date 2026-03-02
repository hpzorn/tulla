"""Shared test fixtures for the tulla test suite.

Provides reusable fixtures that multiple test modules depend on:

- ``tmp_work_dir`` – a fresh temporary directory suitable for checkpoint
  stores, log files, and other filesystem-backed operations.
- ``mock_claude`` – a :class:`MockClaudeAdapter` instance with sensible
  defaults, recording all calls.
- ``mock_claude_with_output`` – factory fixture that creates a
  :class:`MockClaudeAdapter` pre-configured to return a specific output
  text (or ``ClaudeResult``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tulla.adapters.claude_mock import MockClaudeAdapter
from tulla.ports.claude import ClaudeResult

# ---------------------------------------------------------------------------
# Filesystem fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_work_dir(tmp_path: Path) -> Path:
    """Return a temporary working directory for tests.

    This is a thin wrapper around pytest's built-in ``tmp_path`` that
    makes intent explicit when used as a work directory for pipelines,
    checkpoint stores, or log output.
    """
    work = tmp_path / "work"
    work.mkdir()
    return work


# ---------------------------------------------------------------------------
# Mock Claude fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_claude() -> MockClaudeAdapter:
    """Return a default :class:`MockClaudeAdapter` that records calls.

    The adapter returns a successful response with ``"mock response"`` as
    the output text.  Inspect ``mock_claude.calls`` to assert on the
    requests that were sent.
    """
    return MockClaudeAdapter()


@pytest.fixture()
def mock_claude_with_output():
    """Factory fixture: create a :class:`MockClaudeAdapter` with a given output.

    Usage::

        def test_something(mock_claude_with_output):
            adapter = mock_claude_with_output("hello world")
            result = adapter.run(some_request)
            assert result.output_text == "hello world"

        def test_with_result(mock_claude_with_output):
            custom = ClaudeResult(exit_code=0, output_text="custom", cost_usd=0.5)
            adapter = mock_claude_with_output(custom)
            result = adapter.run(some_request)
            assert result.cost_usd == 0.5

    Parameters:
        output: Either a plain string (used as ``output_text`` in a
            successful :class:`ClaudeResult`) or a :class:`ClaudeResult`
            instance used directly.
    """

    def _factory(output: str | ClaudeResult = "mock output") -> MockClaudeAdapter:
        if isinstance(output, ClaudeResult):
            default = output
        else:
            default = ClaudeResult(exit_code=0, output_text=output)
        return MockClaudeAdapter(default_response=default)

    return _factory
