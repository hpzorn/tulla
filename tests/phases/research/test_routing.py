"""Unit tests for research mode auto-routing.

Covers infer_research_mode() with tmp_path fixtures to create mock work
directory structures.  Scenarios:

1. No artifacts -> groundwork
2. D5 brief exists -> discovery-fed
3. P5 requests exist -> spike
4. Both D5 and P5 exist -> spike wins
5. --research-mode groundwork overrides even when P5 exists
6. --research-mode spike errors when no P5 output found
7. --research-mode discovery-fed errors when no D5 brief found
8. Legacy --mode flag still works as planning_dir
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from tulla.phases.research.routing import (
    ResearchMode,
    RoutingError,
    infer_research_mode,
)

IDEA_ID = "42"


# ---------------------------------------------------------------------------
# Helpers – create mock work directory structures
# ---------------------------------------------------------------------------


def _make_planning_dir(work_base: Path, *, with_p5: bool = True) -> Path:
    """Create a mock planning work directory with optional P5 output."""
    d = work_base / f"idea-{IDEA_ID}-planning-20260201-120000"
    d.mkdir(parents=True, exist_ok=True)
    # _find_latest_dir requires at least one .md file
    (d / "p1-output.md").write_text("planning artifact")
    if with_p5:
        (d / "p5-research-requests.md").write_text("spike requests")
    return d


def _make_discovery_dir(work_base: Path, *, with_d5: bool = True) -> Path:
    """Create a mock discovery work directory with optional D5 brief."""
    d = work_base / f"idea-{IDEA_ID}-discovery-20260201-110000"
    d.mkdir(parents=True, exist_ok=True)
    (d / "d1-output.md").write_text("discovery artifact")
    if with_d5:
        (d / "d5-research-brief.md").write_text("research brief")
    return d


# ---------------------------------------------------------------------------
# 1. No artifacts -> groundwork
# ---------------------------------------------------------------------------


class TestAutoRouteNoArtifacts:
    """When no prior outputs exist, default to groundwork."""

    def test_empty_work_base(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()

        result = infer_research_mode(IDEA_ID, work_base=work_base)

        assert result.mode is ResearchMode.GROUNDWORK
        assert result.planning_dir == ""
        assert result.discovery_dir == ""

    def test_no_work_base(self) -> None:
        result = infer_research_mode(IDEA_ID)

        assert result.mode is ResearchMode.GROUNDWORK


# ---------------------------------------------------------------------------
# 2. D5 brief exists -> discovery-fed
# ---------------------------------------------------------------------------


class TestAutoRouteDiscoveryFed:
    """When only a D5 brief is present, auto-route to discovery-fed."""

    def test_d5_brief_triggers_discovery_fed(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()
        discovery_dir = _make_discovery_dir(work_base)

        result = infer_research_mode(IDEA_ID, work_base=work_base)

        assert result.mode is ResearchMode.DISCOVERY_FED
        assert result.discovery_dir == str(discovery_dir)
        assert result.planning_dir == ""


# ---------------------------------------------------------------------------
# 3. P5 requests exist -> spike
# ---------------------------------------------------------------------------


class TestAutoRouteSpike:
    """When P5 output is present, auto-route to spike."""

    def test_p5_requests_trigger_spike(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()
        planning_dir = _make_planning_dir(work_base)

        result = infer_research_mode(IDEA_ID, work_base=work_base)

        assert result.mode is ResearchMode.SPIKE
        assert result.planning_dir == str(planning_dir)
        assert result.discovery_dir == ""


# ---------------------------------------------------------------------------
# 4. Both D5 and P5 exist -> spike wins
# ---------------------------------------------------------------------------


class TestAutoRouteSpikeWins:
    """When both P5 and D5 exist, spike takes precedence."""

    def test_spike_beats_discovery_fed(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()
        planning_dir = _make_planning_dir(work_base)
        _make_discovery_dir(work_base)

        result = infer_research_mode(IDEA_ID, work_base=work_base)

        assert result.mode is ResearchMode.SPIKE
        assert result.planning_dir == str(planning_dir)
        assert result.discovery_dir == ""


# ---------------------------------------------------------------------------
# 5. --research-mode groundwork overrides even when P5 exists
# ---------------------------------------------------------------------------


class TestExplicitGroundworkOverride:
    """Explicit groundwork mode ignores existing P5/D5 artifacts."""

    def test_groundwork_overrides_p5(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()
        _make_planning_dir(work_base)

        result = infer_research_mode(
            IDEA_ID,
            explicit_mode="groundwork",
            work_base=work_base,
        )

        assert result.mode is ResearchMode.GROUNDWORK
        assert result.planning_dir == ""
        assert result.discovery_dir == ""

    def test_groundwork_overrides_d5(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()
        _make_discovery_dir(work_base)

        result = infer_research_mode(
            IDEA_ID,
            explicit_mode="groundwork",
            work_base=work_base,
        )

        assert result.mode is ResearchMode.GROUNDWORK


# ---------------------------------------------------------------------------
# 6. --research-mode spike errors when no P5 output found
# ---------------------------------------------------------------------------


class TestExplicitSpikeErrors:
    """Explicit spike mode raises RoutingError when P5 is missing."""

    def test_spike_no_p5_raises(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()

        with pytest.raises(RoutingError, match="Spike mode requested"):
            infer_research_mode(
                IDEA_ID,
                explicit_mode="spike",
                work_base=work_base,
            )

    def test_spike_no_work_base_raises(self) -> None:
        with pytest.raises(RoutingError, match="Spike mode requested"):
            infer_research_mode(IDEA_ID, explicit_mode="spike")

    def test_spike_planning_dir_without_p5_raises(self, tmp_path: Path) -> None:
        """Planning dir exists but has no p5-research-requests.md."""
        work_base = tmp_path / "work"
        work_base.mkdir()
        _make_planning_dir(work_base, with_p5=False)

        with pytest.raises(RoutingError, match="Spike mode requested"):
            infer_research_mode(
                IDEA_ID,
                explicit_mode="spike",
                work_base=work_base,
            )


# ---------------------------------------------------------------------------
# 7. --research-mode discovery-fed errors when no D5 brief found
# ---------------------------------------------------------------------------


class TestExplicitDiscoveryFedErrors:
    """Explicit discovery-fed mode raises RoutingError when D5 is missing."""

    def test_discovery_fed_no_d5_raises(self, tmp_path: Path) -> None:
        work_base = tmp_path / "work"
        work_base.mkdir()

        with pytest.raises(RoutingError, match="Discovery-fed mode requested"):
            infer_research_mode(
                IDEA_ID,
                explicit_mode="discovery-fed",
                work_base=work_base,
            )

    def test_discovery_fed_no_work_base_raises(self) -> None:
        with pytest.raises(RoutingError, match="Discovery-fed mode requested"):
            infer_research_mode(IDEA_ID, explicit_mode="discovery-fed")

    def test_discovery_dir_without_d5_raises(self, tmp_path: Path) -> None:
        """Discovery dir exists but has no d5-research-brief.md."""
        work_base = tmp_path / "work"
        work_base.mkdir()
        _make_discovery_dir(work_base, with_d5=False)

        with pytest.raises(RoutingError, match="Discovery-fed mode requested"):
            infer_research_mode(
                IDEA_ID,
                explicit_mode="discovery-fed",
                work_base=work_base,
            )


# ---------------------------------------------------------------------------
# 8. Legacy --mode flag still works as planning_dir
# ---------------------------------------------------------------------------


class TestLegacyModeFlag:
    """Legacy --mode flag maps to spike with a deprecation warning."""

    def test_legacy_mode_maps_to_spike(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = infer_research_mode(
                IDEA_ID,
                explicit_planning_dir="/some/planning/dir",
            )

        assert result.mode is ResearchMode.SPIKE
        assert result.planning_dir == "/some/planning/dir"
        assert result.discovery_dir == ""
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "--mode is deprecated" in str(w[0].message)

    def test_legacy_discovery_dir_maps_to_discovery_fed(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = infer_research_mode(
                IDEA_ID,
                explicit_discovery_dir="/some/discovery/dir",
            )

        assert result.mode is ResearchMode.DISCOVERY_FED
        assert result.discovery_dir == "/some/discovery/dir"
        assert result.planning_dir == ""
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "--discovery-dir" in str(w[0].message)


# ---------------------------------------------------------------------------
# Edge cases: invalid mode string
# ---------------------------------------------------------------------------


class TestInvalidMode:
    """Invalid --research-mode value raises RoutingError."""

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(RoutingError, match="Invalid research mode"):
            infer_research_mode(IDEA_ID, explicit_mode="invalid-value")

    def test_error_lists_valid_modes(self) -> None:
        with pytest.raises(RoutingError, match="groundwork.*discovery-fed.*spike"):
            infer_research_mode(IDEA_ID, explicit_mode="bogus")
