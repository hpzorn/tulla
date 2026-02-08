"""Tests for tulla.phases.planning.pipeline – planning_pipeline factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from tulla.config import TullaConfig
from tulla.core.pipeline import Pipeline
from tulla.phases.planning.p1 import P1Phase
from tulla.phases.planning.p2 import P2Phase
from tulla.phases.planning.p3 import P3Phase
from tulla.phases.planning.p4 import P4Phase
from tulla.phases.planning.p5 import P5Phase
from tulla.phases.planning.p6 import P6Phase
from tulla.phases.planning.pipeline import planning_pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class StubClaudePort:
    """Placeholder claude port for pipeline factory tests."""


@pytest.fixture()
def config() -> TullaConfig:
    """A default TullaConfig instance."""
    return TullaConfig()


@pytest.fixture()
def pipeline(tmp_path: Path, config: TullaConfig) -> Pipeline:
    """A planning pipeline built via the factory."""
    return planning_pipeline(
        claude_port=StubClaudePort(),
        work_dir=tmp_path,
        idea_id="idea-99",
        config=config,
    )


# ===================================================================
# Pipeline has exactly 6 phases in P1–P6 order
# ===================================================================


class TestPlanningPipelinePhases:
    """planning_pipeline() returns a Pipeline with 6 phases in order."""

    def test_has_six_phases(self, pipeline: Pipeline) -> None:
        assert len(pipeline._phases) == 6

    def test_phase_ids_in_p1_p6_order(self, pipeline: Pipeline) -> None:
        ids = [pid for pid, _ in pipeline._phases]
        assert ids == ["p1", "p2", "p3", "p4", "p5", "p6"]

    def test_phase_types(self, pipeline: Pipeline) -> None:
        expected_types = [P1Phase, P2Phase, P3Phase, P4Phase, P5Phase, P6Phase]
        for (_, phase), expected in zip(pipeline._phases, expected_types):
            assert isinstance(phase, expected)


# ===================================================================
# Budget comes from config.planning.budget_usd
# ===================================================================


class TestPlanningPipelineBudget:
    """planning_pipeline() uses config.planning.budget_usd as total budget."""

    def test_default_budget(self, pipeline: Pipeline) -> None:
        # AgentConfig default budget_usd is 5.0
        assert pipeline._total_budget_usd == 5.0

    def test_custom_budget(self, tmp_path: Path) -> None:
        config = TullaConfig(planning={"budget_usd": 12.5})
        p = planning_pipeline(
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-100",
            config=config,
        )
        assert p._total_budget_usd == 12.5


# ===================================================================
# discovery_dir is forwarded in pipeline config
# ===================================================================


class TestPlanningPipelineConfig:
    """planning_pipeline() forwards config parameters."""

    def test_project_id_forwarded(self, pipeline: Pipeline) -> None:
        assert pipeline._config["project_id"] == "ralph"

    def test_custom_project_id(self, tmp_path: Path) -> None:
        config = TullaConfig(project_id="my-project")
        p = planning_pipeline(
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-102",
            config=config,
        )
        assert p._config["project_id"] == "my-project"

    def test_default_discovery_dir_empty(self, pipeline: Pipeline) -> None:
        assert pipeline._config["discovery_dir"] == ""

    def test_custom_discovery_dir(self, tmp_path: Path, config: TullaConfig) -> None:
        p = planning_pipeline(
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-101",
            config=config,
            discovery_dir="/some/discovery/output",
        )
        assert p._config["discovery_dir"] == "/some/discovery/output"


# ===================================================================
# Granularity thresholds forwarded from config
# ===================================================================


class TestPlanningPipelineGranularityThresholds:
    """planning_pipeline() forwards granularity threshold fields to config."""

    def test_config_contains_max_files_per_requirement(self, pipeline: Pipeline) -> None:
        assert pipeline._config["max_files_per_requirement"] == 3

    def test_config_contains_min_wpf_blocking(self, pipeline: Pipeline) -> None:
        assert pipeline._config["min_wpf_blocking"] == 12.0

    def test_config_contains_min_wpf_advisory(self, pipeline: Pipeline) -> None:
        assert pipeline._config["min_wpf_advisory"] == 15.0

    def test_config_contains_max_granularity_retries(self, pipeline: Pipeline) -> None:
        assert pipeline._config["max_granularity_retries"] == 1
