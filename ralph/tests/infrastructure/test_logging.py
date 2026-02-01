"""Tests for ralph.infrastructure.logging module."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import structlog

from ralph.infrastructure.logging import configure_logging


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Reset stdlib root logger and structlog between tests."""
    yield
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)
    structlog.reset_defaults()


# ===================================================================
# Console output on stderr
# ===================================================================


class TestConsoleOutput:
    """configure_logging() must attach a stderr console handler."""

    def test_console_handler_attached(self) -> None:
        configure_logging()
        root = logging.getLogger()
        assert any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            for h in root.handlers
        ), "Expected a StreamHandler (non-FileHandler) on the root logger"

    def test_console_writes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = configure_logging()
        logger.info("hello from test")
        captured = capsys.readouterr()
        assert "hello from test" in captured.err
        assert captured.out == ""


# ===================================================================
# JSON file creation
# ===================================================================


class TestJsonFileOutput:
    """When work_dir and phase_id are given, a JSON log file is created."""

    def test_json_file_created(self, tmp_path: Path) -> None:
        logger = configure_logging(work_dir=tmp_path, phase_id="discovery")
        logger.info("json test")
        # Flush handlers so the file is written.
        for h in logging.getLogger().handlers:
            h.flush()
        log_file = tmp_path / "discovery.log.json"
        assert log_file.exists(), f"Expected {log_file} to be created"

    def test_no_json_file_without_work_dir(self, tmp_path: Path) -> None:
        configure_logging()
        root = logging.getLogger()
        assert not any(
            isinstance(h, logging.FileHandler) for h in root.handlers
        ), "FileHandler should not be present when work_dir is not given"


# ===================================================================
# Valid JSON lines
# ===================================================================


class TestJsonLinesValidity:
    """Each line in the JSON log file must be valid JSON."""

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        logger = configure_logging(work_dir=tmp_path, phase_id="phase-1")
        logger.info("line one")
        logger.warning("line two")
        # Flush all handlers.
        for h in logging.getLogger().handlers:
            h.flush()
        log_file = tmp_path / "phase-1.log.json"
        lines = [
            ln for ln in log_file.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        assert len(lines) >= 2, f"Expected at least 2 log lines, got {len(lines)}"
        for i, line in enumerate(lines):
            parsed = json.loads(line)  # raises on invalid JSON
            assert isinstance(parsed, dict), f"Line {i} is not a JSON object"


# ===================================================================
# Bound context in output
# ===================================================================


class TestBoundContext:
    """Initial context passed to configure_logging() appears in output."""

    def test_bound_context_in_json_output(self, tmp_path: Path) -> None:
        logger = configure_logging(
            work_dir=tmp_path,
            phase_id="ctx-test",
            idea_id="idea-42",
            run="run-7",
        )
        logger.info("context check")
        for h in logging.getLogger().handlers:
            h.flush()
        log_file = tmp_path / "ctx-test.log.json"
        lines = [
            ln for ln in log_file.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry.get("idea_id") == "idea-42", f"idea_id missing: {entry}"
        assert entry.get("run") == "run-7", f"run missing: {entry}"

    def test_bound_context_in_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logger = configure_logging(idea_id="idea-99")
        logger.info("stderr context check")
        captured = capsys.readouterr()
        assert "idea-99" in captured.err
