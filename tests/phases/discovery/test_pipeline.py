"""Tests for tulla.phases.discovery.pipeline – discovery_pipeline factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from tulla.config import TullaConfig
from tulla.core.pipeline import Pipeline
from tulla.phases.discovery.d1 import D1Phase
from tulla.phases.discovery.d2 import D2Phase
from tulla.phases.discovery.d3 import D3Phase
from tulla.phases.discovery.d4 import D4Phase
from tulla.phases.discovery.d5 import D5Phase
from tulla.phases.discovery.pipeline import discovery_pipeline

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
    """A discovery pipeline built via the factory."""
    return discovery_pipeline(
        claude_port=StubClaudePort(),
        work_dir=tmp_path,
        idea_id="idea-99",
        config=config,
    )


# ===================================================================
# Pipeline has exactly 5 phases in D1–D5 order
# ===================================================================


class TestDiscoveryPipelinePhases:
    """discovery_pipeline() returns a Pipeline with 5 phases in order."""

    def test_has_five_phases(self, pipeline: Pipeline) -> None:
        assert len(pipeline._phases) == 5

    def test_phase_ids_in_d1_d5_order(self, pipeline: Pipeline) -> None:
        ids = [pid for pid, _ in pipeline._phases]
        assert ids == ["d1", "d2", "d3", "d4", "d5"]

    def test_phase_types(self, pipeline: Pipeline) -> None:
        expected_types = [D1Phase, D2Phase, D3Phase, D4Phase, D5Phase]
        for (_, phase), expected in zip(pipeline._phases, expected_types, strict=False):
            assert isinstance(phase, expected)


# ===================================================================
# Budget comes from config.discovery.budget_usd
# ===================================================================


class TestDiscoveryPipelineBudget:
    """discovery_pipeline() uses config.discovery.budget_usd as total budget."""

    def test_default_budget(self, pipeline: Pipeline) -> None:
        # AgentConfig default budget_usd is 5.0
        assert pipeline._total_budget_usd == 5.0

    def test_custom_budget(self, tmp_path: Path) -> None:
        config = TullaConfig(discovery={"budget_usd": 12.5})
        p = discovery_pipeline(
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-100",
            config=config,
        )
        assert p._total_budget_usd == 12.5


# ===================================================================
# Mode is forwarded in pipeline config
# ===================================================================


class TestDiscoveryPipelineMode:
    """discovery_pipeline() forwards the mode parameter."""

    def test_default_mode_upstream(self, pipeline: Pipeline) -> None:
        assert pipeline._config["mode"] == "upstream"

    def test_downstream_mode(self, tmp_path: Path, config: TullaConfig) -> None:
        p = discovery_pipeline(
            claude_port=StubClaudePort(),
            work_dir=tmp_path,
            idea_id="idea-101",
            config=config,
            mode="downstream",
        )
        assert p._config["mode"] == "downstream"
