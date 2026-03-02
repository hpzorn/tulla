"""Tests for tulla.adapters.opencode_cli module."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tulla.adapters.opencode_cli import OpenCodeCLIAdapter
from tulla.ports.claude import ClaudeRequest, ClaudeResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def adapter() -> OpenCodeCLIAdapter:
    """Default adapter with standard binary name."""
    return OpenCodeCLIAdapter()


@pytest.fixture()
def basic_request() -> ClaudeRequest:
    """Minimal ClaudeRequest for testing."""
    return ClaudeRequest(prompt="Hello")


# ===================================================================
# _build_command() tests
# ===================================================================


class TestBuildCommand:
    """Tests for OpenCodeCLIAdapter._build_command()."""

    def test_minimal_request(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="Say hello")
        cmd = adapter._build_command(req)

        assert cmd[0] == "opencode"
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "gpt-4.1"
        assert "--output-format" in cmd
        assert cmd[cmd.index("--output-format") + 1] == "json"
        assert "-p" in cmd
        assert cmd[cmd.index("-p") + 1] == "Say hello"

    def test_custom_model(self) -> None:
        adapter = OpenCodeCLIAdapter(model="gpt-4-turbo")
        req = ClaudeRequest(prompt="test")
        cmd = adapter._build_command(req)

        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "gpt-4-turbo"

    def test_custom_binary(self) -> None:
        adapter = OpenCodeCLIAdapter(opencode_bin="/usr/local/bin/opencode")
        req = ClaudeRequest(prompt="test")
        cmd = adapter._build_command(req)

        assert cmd[0] == "/usr/local/bin/opencode"

    def test_provider_flag(self) -> None:
        adapter = OpenCodeCLIAdapter(provider="azure")
        req = ClaudeRequest(prompt="test")
        cmd = adapter._build_command(req)

        assert "--provider" in cmd
        assert cmd[cmd.index("--provider") + 1] == "azure"

    def test_no_provider_when_none(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test")
        cmd = adapter._build_command(req)

        assert "--provider" not in cmd

    def test_yes_flag_for_bypass_permissions(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", permission_mode="bypassPermissions")
        cmd = adapter._build_command(req)

        assert "--yes" in cmd

    def test_yes_flag_for_auto(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", permission_mode="auto")
        cmd = adapter._build_command(req)

        assert "--yes" in cmd

    def test_no_yes_flag_for_manual(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", permission_mode="manual")
        cmd = adapter._build_command(req)

        assert "--yes" not in cmd

    def test_allowed_tools_flag(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", allowed_tools=["Read", "Write", "Bash"])
        cmd = adapter._build_command(req)

        assert "--tools" in cmd
        assert cmd[cmd.index("--tools") + 1] == "Read,Write,Bash"

    def test_disallowed_tools_flag(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test", disallowed_tools=["Bash", "Edit"])
        cmd = adapter._build_command(req)

        assert "--disable-tools" in cmd
        assert cmd[cmd.index("--disable-tools") + 1] == "Bash,Edit"

    def test_quiet_flag_present(self, adapter: OpenCodeCLIAdapter) -> None:
        req = ClaudeRequest(prompt="test")
        cmd = adapter._build_command(req)

        assert "--quiet" in cmd


# ===================================================================
# _try_parse_json() tests
# ===================================================================


class TestTryParseJson:
    """Tests for OpenCodeCLIAdapter._try_parse_json()."""

    def test_valid_json_object(self) -> None:
        result = OpenCodeCLIAdapter._try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_empty_string(self) -> None:
        assert OpenCodeCLIAdapter._try_parse_json("") is None

    def test_whitespace_only(self) -> None:
        assert OpenCodeCLIAdapter._try_parse_json("   \n  ") is None

    def test_invalid_json(self) -> None:
        assert OpenCodeCLIAdapter._try_parse_json("not json at all") is None

    def test_json_array_returns_none(self) -> None:
        """Only dict objects are accepted, not arrays."""
        assert OpenCodeCLIAdapter._try_parse_json("[1, 2, 3]") is None

    def test_ndjson_takes_last_object(self) -> None:
        """NDJSON support: takes last valid JSON object."""
        ndjson = '{"first": 1}\n{"second": 2}\n{"third": 3}'
        result = OpenCodeCLIAdapter._try_parse_json(ndjson)
        assert result == {"third": 3}

    def test_ndjson_with_trailing_newlines(self) -> None:
        ndjson = '{"first": 1}\n{"second": 2}\n\n\n'
        result = OpenCodeCLIAdapter._try_parse_json(ndjson)
        assert result == {"second": 2}


# ===================================================================
# _extract_cost() tests
# ===================================================================


class TestExtractCost:
    """Tests for OpenCodeCLIAdapter._extract_cost()."""

    def test_none_input(self) -> None:
        assert OpenCodeCLIAdapter._extract_cost(None) == 0.0

    def test_empty_dict(self) -> None:
        assert OpenCodeCLIAdapter._extract_cost({}) == 0.0

    def test_top_level_total_cost(self) -> None:
        assert OpenCodeCLIAdapter._extract_cost({"total_cost": 1.23}) == 1.23

    def test_top_level_cost(self) -> None:
        assert OpenCodeCLIAdapter._extract_cost({"cost": 0.5}) == 0.5

    def test_nested_under_usage(self) -> None:
        data = {"usage": {"total_cost": 0.42}}
        assert OpenCodeCLIAdapter._extract_cost(data) == 0.42

    def test_nested_under_session(self) -> None:
        data = {"session": {"cost": 0.15}}
        assert OpenCodeCLIAdapter._extract_cost(data) == 0.15

    def test_token_based_estimation(self) -> None:
        """Cost estimated from OpenAI-style token counts."""
        data = {"usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
        result = OpenCodeCLIAdapter._extract_cost(data)
        # Should return a non-zero estimate
        assert result > 0

    def test_no_cost_keys_returns_zero(self) -> None:
        data = {"text": "hello", "exit_code": 0}
        assert OpenCodeCLIAdapter._extract_cost(data) == 0.0


# ===================================================================
# Timeout handling tests
# ===================================================================


class TestTimeoutHandling:
    """Tests for subprocess timeout handling in run()."""

    @patch("tulla.adapters.opencode_cli.subprocess.run")
    def test_timeout_returns_timed_out_result(
        self, mock_run: MagicMock, adapter: OpenCodeCLIAdapter
    ) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["opencode"], timeout=10)
        req = ClaudeRequest(prompt="test", timeout_seconds=10)

        result = adapter.run(req)

        assert result.timed_out is True
        assert result.exit_code == 124
        assert result.duration_seconds > 0

    @patch("tulla.adapters.opencode_cli.subprocess.run")
    def test_no_timeout_when_zero(self, mock_run: MagicMock, adapter: OpenCodeCLIAdapter) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout="{}",
            stderr="",
        )
        req = ClaudeRequest(prompt="test", timeout_seconds=0)

        adapter.run(req)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] is None


# ===================================================================
# Full run() integration (mocked subprocess)
# ===================================================================


class TestCwd:
    """Tests for cwd passthrough to subprocess."""

    @patch("tulla.adapters.opencode_cli.subprocess.run")
    def test_cwd_passed_to_subprocess(
        self, mock_run: MagicMock, adapter: OpenCodeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout="{}",
            stderr="",
        )
        req = ClaudeRequest(prompt="test", cwd=Path("/tmp/work"))

        adapter.run(req)

        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == "/tmp/work"


class TestRun:
    """Tests for the full run() method with mocked subprocess."""

    @patch("tulla.adapters.opencode_cli.subprocess.run")
    def test_successful_run_parses_json(
        self, mock_run: MagicMock, adapter: OpenCodeCLIAdapter
    ) -> None:
        output = json.dumps({"text": "hi", "cost": 0.01})
        mock_run.return_value = subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout=output,
            stderr="",
        )

        result = adapter.run(ClaudeRequest(prompt="hello"))

        assert result.exit_code == 0
        assert result.timed_out is False
        assert result.output_json == {"text": "hi", "cost": 0.01}
        assert result.cost_usd == pytest.approx(0.01)
        assert result.duration_seconds > 0

    @patch("tulla.adapters.opencode_cli.subprocess.run")
    def test_non_json_output_degrades_gracefully(
        self, mock_run: MagicMock, adapter: OpenCodeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout="plain text output",
            stderr="",
        )

        result = adapter.run(ClaudeRequest(prompt="hello"))

        assert result.exit_code == 0
        assert result.output_text == "plain text output"
        assert result.output_json is None
        assert result.cost_usd == 0.0

    @patch("tulla.adapters.opencode_cli.subprocess.run")
    def test_result_is_claude_result_instance(
        self, mock_run: MagicMock, adapter: OpenCodeCLIAdapter
    ) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["opencode"],
            returncode=0,
            stdout="{}",
            stderr="",
        )

        result = adapter.run(ClaudeRequest(prompt="test"))

        assert isinstance(result, ClaudeResult)


# ===================================================================
# Config factory tests
# ===================================================================


class TestConfigFactory:
    """Tests for TullaConfig.create_llm_adapter() with opencode backend."""

    def test_create_opencode_adapter(self) -> None:
        from tulla.config import TullaConfig

        config = TullaConfig(llm_backend="opencode", llm_model="gpt-4-turbo")
        adapter = config.create_llm_adapter()

        assert isinstance(adapter, OpenCodeCLIAdapter)
        assert adapter._model == "gpt-4-turbo"

    def test_create_opencode_adapter_default_model(self) -> None:
        from tulla.config import TullaConfig

        config = TullaConfig(llm_backend="opencode")
        adapter = config.create_llm_adapter()

        assert isinstance(adapter, OpenCodeCLIAdapter)
        assert adapter._model == "gpt-4.1"

    def test_create_opencode_adapter_custom_bin(self) -> None:
        from tulla.config import TullaConfig

        config = TullaConfig(llm_backend="opencode", llm_bin="/opt/opencode")
        adapter = config.create_llm_adapter()

        assert adapter._opencode_bin == "/opt/opencode"
