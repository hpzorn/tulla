"""Tests for tulla.config — TullaConfig and AgentConfig."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tulla.config import AgentConfig, TullaConfig


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestAgentConfigDefaults:
    """AgentConfig ships sensible defaults."""

    def test_default_budget(self) -> None:
        cfg = AgentConfig()
        assert cfg.budget_usd == 5.0

    def test_default_max_retries(self) -> None:
        cfg = AgentConfig()
        assert cfg.max_retries == 2

    def test_default_permission_mode(self) -> None:
        cfg = AgentConfig()
        assert cfg.permission_mode == "bypassPermissions"

    def test_default_phase_timeout(self) -> None:
        cfg = AgentConfig()
        assert cfg.phase_timeout_minutes == 15


class TestGranularityThresholds:
    """AgentConfig granularity thresholds have correct defaults and accept custom values."""

    def test_default_max_files_per_requirement(self) -> None:
        cfg = AgentConfig()
        assert cfg.max_files_per_requirement == 3

    def test_default_min_wpf_blocking(self) -> None:
        cfg = AgentConfig()
        assert cfg.min_wpf_blocking == 12.0

    def test_default_min_wpf_advisory(self) -> None:
        cfg = AgentConfig()
        assert cfg.min_wpf_advisory == 15.0

    def test_default_max_granularity_retries(self) -> None:
        cfg = AgentConfig()
        assert cfg.max_granularity_retries == 1

    def test_custom_max_files_per_requirement(self) -> None:
        cfg = AgentConfig(max_files_per_requirement=5)
        assert cfg.max_files_per_requirement == 5

    def test_custom_min_wpf_blocking(self) -> None:
        cfg = AgentConfig(min_wpf_blocking=8.0)
        assert cfg.min_wpf_blocking == 8.0

    def test_custom_min_wpf_advisory(self) -> None:
        cfg = AgentConfig(min_wpf_advisory=20.0)
        assert cfg.min_wpf_advisory == 20.0

    def test_custom_max_granularity_retries(self) -> None:
        cfg = AgentConfig(max_granularity_retries=3)
        assert cfg.max_granularity_retries == 3


class TestTullaConfigDefaults:
    """TullaConfig has correct defaults including per-agent overrides."""

    def test_default_work_base_dir(self) -> None:
        cfg = TullaConfig()
        # Relative default is resolved to absolute at creation time
        assert cfg.work_base_dir == Path("./work").resolve()
        assert cfg.work_base_dir.is_absolute()

    def test_default_ideas_dir(self) -> None:
        cfg = TullaConfig()
        assert cfg.ideas_dir == Path.home() / ".claude" / "ideas"

    def test_default_ontology_server_url(self) -> None:
        cfg = TullaConfig()
        assert cfg.ontology_server_url == "http://localhost:8100"

    def test_discovery_defaults(self) -> None:
        cfg = TullaConfig()
        assert cfg.discovery.budget_usd == 5.0
        assert cfg.discovery.permission_mode == "bypassPermissions"

    def test_planning_defaults(self) -> None:
        cfg = TullaConfig()
        assert cfg.planning.budget_usd == 5.0

    def test_research_extended_budget(self) -> None:
        cfg = TullaConfig()
        assert cfg.research.budget_usd == 8.0

    def test_research_extended_timeout(self) -> None:
        cfg = TullaConfig()
        assert cfg.research.phase_timeout_minutes == 30

    def test_implementation_budget(self) -> None:
        cfg = TullaConfig()
        assert cfg.implementation.budget_usd == 10.0

    def test_implementation_permission_mode(self) -> None:
        cfg = TullaConfig()
        assert cfg.implementation.permission_mode == "acceptEdits"

    def test_epistemology_defaults(self) -> None:
        cfg = TullaConfig()
        assert cfg.epistemology.budget_usd == 5.0


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------


class TestEnvVarOverride:
    """Environment variables with RALPH_ prefix override defaults."""

    def test_work_base_dir_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TULLA_WORK_BASE_DIR", "/tmp/tulla-work")
        cfg = TullaConfig()
        assert cfg.work_base_dir == Path("/tmp/tulla-work")

    def test_ontology_server_url_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TULLA_ONTOLOGY_SERVER_URL", "http://remote:9999")
        cfg = TullaConfig()
        assert cfg.ontology_server_url == "http://remote:9999"

    def test_nested_agent_override_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TULLA_DISCOVERY__BUDGET_USD", "12.5")
        cfg = TullaConfig()
        assert cfg.discovery.budget_usd == 12.5


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestYamlLoading:
    """from_yaml() reads YAML files correctly."""

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "tulla.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "work_base_dir": "/custom/work",
                    "ontology_server_url": "http://yaml-host:8080",
                }
            )
        )
        cfg = TullaConfig.from_yaml(yaml_file)
        assert cfg.work_base_dir == Path("/custom/work")
        assert cfg.ontology_server_url == "http://yaml-host:8080"

    def test_yaml_with_agent_config(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "tulla.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "discovery": {
                        "budget_usd": 20.0,
                        "max_retries": 5,
                    },
                }
            )
        )
        cfg = TullaConfig.from_yaml(yaml_file)
        assert cfg.discovery.budget_usd == 20.0
        assert cfg.discovery.max_retries == 5

    def test_missing_yaml_file_uses_defaults(self, tmp_path: Path) -> None:
        cfg = TullaConfig.from_yaml(tmp_path / "nonexistent.yaml")
        assert cfg.work_base_dir == Path("./work").resolve()

    def test_empty_yaml_uses_defaults(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        cfg = TullaConfig.from_yaml(yaml_file)
        assert cfg.work_base_dir == Path("./work").resolve()


# ---------------------------------------------------------------------------
# Per-agent overrides
# ---------------------------------------------------------------------------


class TestPerAgentOverrides:
    """Per-agent configs can be overridden independently."""

    def test_override_single_agent(self) -> None:
        cfg = TullaConfig(
            discovery=AgentConfig(budget_usd=99.0),
        )
        assert cfg.discovery.budget_usd == 99.0
        # Others unchanged
        assert cfg.research.budget_usd == 8.0
        assert cfg.implementation.budget_usd == 10.0

    def test_override_preserves_other_defaults(self) -> None:
        cfg = TullaConfig(
            planning=AgentConfig(max_retries=10),
        )
        assert cfg.planning.max_retries == 10
        assert cfg.planning.budget_usd == 5.0  # default preserved


# ---------------------------------------------------------------------------
# CLI / keyword precedence (overrides > env > YAML > defaults)
# ---------------------------------------------------------------------------


class TestCLIPrecedence:
    """Explicit keyword overrides beat env vars and YAML values."""

    def test_override_beats_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "tulla.yaml"
        yaml_file.write_text(
            yaml.dump({"ontology_server_url": "http://from-yaml:1111"})
        )
        cfg = TullaConfig.from_yaml(
            yaml_file,
            ontology_server_url="http://from-override:2222",
        )
        assert cfg.ontology_server_url == "http://from-override:2222"

    def test_override_beats_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TULLA_ONTOLOGY_SERVER_URL", "http://from-env:3333")
        cfg = TullaConfig(ontology_server_url="http://from-kwarg:4444")
        assert cfg.ontology_server_url == "http://from-kwarg:4444"

    def test_override_beats_yaml_and_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TULLA_ONTOLOGY_SERVER_URL", "http://from-env:5555")
        yaml_file = tmp_path / "tulla.yaml"
        yaml_file.write_text(
            yaml.dump({"ontology_server_url": "http://from-yaml:6666"})
        )
        cfg = TullaConfig.from_yaml(
            yaml_file,
            ontology_server_url="http://from-override:7777",
        )
        assert cfg.ontology_server_url == "http://from-override:7777"
