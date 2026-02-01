"""Tests for ralph.adapters.claude_cli module."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from ralph.adapters.claude_cli import ClaudeCLIAdapter
from ralph.ports.claude import ClaudeRequest, ClaudeResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter() -> ClaudeCLIAdapter:
    """Default adapter with standard binary name."""
    return ClaudeCLIAdapter()


@pytest.fixture()
def basic_request() -> ClaudeRequest:
    """Minimal ClaudeRequest for testing."""
    return ClaudeRequest(prompt="Hello")


# ===================================================================
# _build_command() tests
# ===================================================================


class TestBuildCommand:
    """Tests for ClaudeCLIAdapter._build_command()."""

    def test_minimal_request(self, adapter: ClaudeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="Say hello")
        cmd = adapter._build_command(req)

        assert cmd[0] == "claude"
        assert "--output-format" in cmd
        assert cmd[cmd.index("--output-format") + 1] == "json"
        assert "-p" in cmd
        assert cmd[cmd.index("-p") + 1] == "Say hello"

    def test_budget_flag(self, adapter: ClaudeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", budget_usd=2.5)
        cmd = adapter._build_command(req)

        assert "--max-budget-usd" in cmd
        assert cmd[cmd.index("--max-budget-usd") + 1] == "2.5"

    def test_no_budget_flag_when_zero(self, adapter: ClaudeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", budget_usd=0.0)
        cmd = adapter._build_command(req)

        assert "--max-budget-usd" not in cmd

    def test_permission_mode_flag(self, adapter: ClaudeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", permission_mode="manual")
        cmd = adapter._build_command(req)

        assert "--permission-mode" in cmd
        assert cmd[cmd.index("--permission-mode") + 1] == "manual"

    def test_allowed_tools_flag(self, adapter: ClaudeCLIAdapter) -> None:
        req = ClaudeRequest(
            prompt="test",
            allowed_tools=["Read", "Write", "Bash"],
        )
        cmd = adapter._build_command(req)

        assert "--allowedTools" in cmd
        assert cmd[cmd.index("--allowedTools") + 1] == "Read,Write,Bash"

    def test_no_allowed_tools_when_empty(
        self, adapter: ClaudeCLIAdapter
    ) -> None:
        req = ClaudeRequest(prompt="test", allowed_tools=[])
        cmd = adapter._build_command(req)

        assert "--allowedTools" not in cmd

    def test_custom_binary(self) -> None:
        adapter = ClaudeCLIAdapter(claude_bin="/usr/local/bin/claude")
        req = ClaudeRequest(prompt="test")
        cmd = adapter._build_command(req)

        assert cmd[0] == "/usr/local/bin/claude"

    def test_all_flags_together(self, adapter: ClaudeCLIAdapter) -> None:
        req = ClaudeRequest(
            prompt="Do something",
            budget_usd=5.0,
            permission_mode="acceptEdits",
            allowed_tools=["Read", "Bash"],
        )
        cmd = adapter._build_command(req)

        assert "--output-format" in cmd
        assert "-p" in cmd
        assert "--max-budget-usd" in cmd
        assert "--permission-mode" in cmd
        assert "--allowedTools" in cmd


# ===================================================================
# _try_parse_json() tests
# ===================================================================


class TestTryParseJson:
    """Tests for ClaudeCLIAdapter._try_parse_json()."""

    def test_valid_json_object(self) -> None:
        result = ClaudeCLIAdapter._try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_empty_string(self) -> None:
        assert ClaudeCLIAdapter._try_parse_json("") is None

    def test_whitespace_only(self) -> None:
        assert ClaudeCLIAdapter._try_parse_json("   \n  ") is None

    def test_invalid_json(self) -> None:
        assert ClaudeCLIAdapter._try_parse_json("not json at all") is None

    def test_json_array_returns_none(self) -> None:
        """Only dict objects are accepted, not arrays."""
        assert ClaudeCLIAdapter._try_parse_json("[1, 2, 3]") is None

    def test_json_scalar_returns_none(self) -> None:
        assert ClaudeCLIAdapter._try_parse_json("42") is None

    def test_nested_json(self) -> None:
        data = {"result": {"text": "hello"}, "cost_usd": 0.01}
        result = ClaudeCLIAdapter._try_parse_json(json.dumps(data))
        assert result == data

    def test_truncated_json(self) -> None:
        """Graceful degradation on truncated JSON (Postel's Law)."""
        assert ClaudeCLIAdapter._try_parse_json('{"key": "val') is None


# ===================================================================
# _extract_cost() tests
# ===================================================================


class TestExtractCost:
    """Tests for ClaudeCLIAdapter._extract_cost()."""

    def test_none_input(self) -> None:
        assert ClaudeCLIAdapter._extract_cost(None) == 0.0

    def test_empty_dict(self) -> None:
        assert ClaudeCLIAdapter._extract_cost({}) == 0.0

    def test_top_level_cost_usd(self) -> None:
        assert ClaudeCLIAdapter._extract_cost({"cost_usd": 1.23}) == 1.23

    def test_top_level_costUsd(self) -> None:
        assert ClaudeCLIAdapter._extract_cost({"costUsd": 0.5}) == 0.5

    def test_top_level_total_cost(self) -> None:
        assert ClaudeCLIAdapter._extract_cost({"total_cost": 2.0}) == 2.0

    def test_top_level_cost(self) -> None:
        assert ClaudeCLIAdapter._extract_cost({"cost": 0.99}) == 0.99

    def test_nested_under_usage(self) -> None:
        data = {"usage": {"cost_usd": 0.42}}
        assert ClaudeCLIAdapter._extract_cost(data) == 0.42

    def test_nested_under_metadata(self) -> None:
        data = {"metadata": {"costUsd": 0.15}}
        assert ClaudeCLIAdapter._extract_cost(data) == 0.15

    def test_nested_under_result(self) -> None:
        data = {"result": {"total_cost": 3.0}}
        assert ClaudeCLIAdapter._extract_cost(data) == 3.0

    def test_top_level_takes_priority_over_nested(self) -> None:
        data = {"cost_usd": 1.0, "usage": {"cost_usd": 2.0}}
        assert ClaudeCLIAdapter._extract_cost(data) == 1.0

    def test_non_numeric_cost_skipped(self) -> None:
        data = {"cost_usd": "not-a-number", "costUsd": 0.5}
        assert ClaudeCLIAdapter._extract_cost(data) == 0.5

    def test_none_cost_value_skipped(self) -> None:
        data = {"cost_usd": None, "usage": {"cost_usd": 0.3}}
        assert ClaudeCLIAdapter._extract_cost(data) == 0.3

    def test_string_numeric_cost(self) -> None:
        """String that is parseable as float should work."""
        assert ClaudeCLIAdapter._extract_cost({"cost_usd": "0.75"}) == 0.75

    def test_no_cost_keys_returns_zero(self) -> None:
        data = {"text": "hello", "exit_code": 0}
        assert ClaudeCLIAdapter._extract_cost(data) == 0.0


# ===================================================================
# Timeout handling tests
# ===================================================================


class TestTimeoutHandling:
    """Tests for subprocess timeout handling in run()."""

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_timeout_returns_timed_out_result(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["claude"], timeout=10
        )
        req = ClaudeRequest(prompt="test", timeout_seconds=10)

        result = adapter.run(req)

        assert result.timed_out is True
        assert result.exit_code == 124
        assert result.duration_seconds > 0

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_no_timeout_when_zero(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout="{}",
            stderr="",
        )
        req = ClaudeRequest(prompt="test", timeout_seconds=0)

        adapter.run(req)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] is None

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_timeout_passed_to_subprocess(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout="{}",
            stderr="",
        )
        req = ClaudeRequest(prompt="test", timeout_seconds=30)

        adapter.run(req)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30


# ===================================================================
# Full run() integration (mocked subprocess)
# ===================================================================


class TestRun:
    """Tests for the full run() method with mocked subprocess."""

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_successful_run_parses_json(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        output = json.dumps({"text": "hi", "cost_usd": 0.01})
        mock_run.return_value = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout=output,
            stderr="",
        )

        result = adapter.run(ClaudeRequest(prompt="hello"))

        assert result.exit_code == 0
        assert result.timed_out is False
        assert result.output_json == {"text": "hi", "cost_usd": 0.01}
        assert result.cost_usd == pytest.approx(0.01)
        assert result.duration_seconds > 0

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_non_json_output_degrades_gracefully(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout="plain text output",
            stderr="",
        )

        result = adapter.run(ClaudeRequest(prompt="hello"))

        assert result.exit_code == 0
        assert result.output_text == "plain text output"
        assert result.output_json is None
        assert result.cost_usd == 0.0

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_nonzero_exit_code(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["claude"],
            returncode=1,
            stdout="",
            stderr="error occurred",
        )

        result = adapter.run(ClaudeRequest(prompt="fail"))

        assert result.exit_code == 1
        assert result.timed_out is False

    @patch("ralph.adapters.claude_cli.subprocess.run")
    def test_result_is_claude_result_instance(
        self, mock_run: MagicMock, adapter: ClaudeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout="{}",
            stderr="",
        )

        result = adapter.run(ClaudeRequest(prompt="test"))

        assert isinstance(result, ClaudeResult)
