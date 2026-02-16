"""Shared test fixtures for epistemology phase tests.

Provides:

- ``ctx`` – a :class:`PhaseContext` with sensible defaults for epistemology
  tests (idea_id="idea-42", budget=5.0, test logger).
- ``write_sample_output`` – helper that writes markdown content into the
  work dir and returns the resulting path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tulla.core.phase import PhaseContext


@pytest.fixture()
def ctx(tmp_path: Path) -> PhaseContext:
    """Return a :class:`PhaseContext` configured for epistemology tests."""
    return PhaseContext(
        idea_id="idea-42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.epistemology"),
    )


@pytest.fixture()
def write_sample_output(tmp_path: Path):
    """Factory fixture: write markdown to the work dir and return the path.

    Usage::

        def test_something(write_sample_output):
            path = write_sample_output("output.md", "# Hello\\nWorld")
            assert path.exists()
    """

    def _write(filename: str, content: str) -> Path:
        p = tmp_path / filename
        p.write_text(content, encoding="utf-8")
        return p

    return _write
