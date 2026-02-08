"""Tests for ContextScanPhase — structural conformance checking.

# @pattern:EventSourcing -- Tests verify that ContextScanPhase produces correct immutable ContextScanOutput from mocked file state
# @principle:FailSafeRouting -- Tests verify SPARQL unavailability degrades gracefully to structural-only:sparql-unavailable

Verification criteria (prd:req-53-2-2):
- Clean files produce structural-only:clean.
- Violation-producing files produce structural-only:violations-found with populated report.
- SPARQL unavailability degrades to structural-only:sparql-unavailable.
- Missing files are handled gracefully without crashing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tulla.core.phase import PhaseContext, PhaseStatus
from tulla.phases.lightweight.context_scan import ContextScanPhase
from tulla.phases.lightweight.models import ContextScanOutput, IntakeOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def phase() -> ContextScanPhase:
    return ContextScanPhase()


def _make_ctx(
    tmp_path: Path,
    affected_files: list[str] | None = None,
    ontology_port: Any = None,
    prev_output: Any = None,
) -> PhaseContext:
    """Build a PhaseContext with prev_output containing affected_files."""
    if prev_output is None:
        prev_output = IntakeOutput(
            change_type="bugfix",
            description="Fix a bug",
            affected_files=affected_files or [],
            scope="single-package",
            lightweight_eligible=True,
        )
    config: dict[str, Any] = {"prev_output": prev_output}
    if ontology_port is not None:
        config["ontology_port"] = ontology_port
    return PhaseContext(idea_id="test-idea", work_dir=tmp_path, config=config)


def _make_clean_file(tmp_path: Path, name: str = "clean.py") -> str:
    """Create a Python file with no import violations."""
    f = tmp_path / name
    f.write_text("x = 1\n", encoding="utf-8")
    return str(f)


def _make_violating_file(tmp_path: Path, name: str = "core/bad.py") -> str:
    """Create a Python file in the inner layer that imports from outer layer.

    The file path includes 'core/' to be classified as inner layer, and
    the import targets 'tulla.cli' which is in the outer layer.
    """
    parent = tmp_path / Path(name).parent
    parent.mkdir(parents=True, exist_ok=True)
    f = tmp_path / name
    f.write_text("from tulla.cli import main\n", encoding="utf-8")
    return str(f)


def _make_ontology_port(sparql_works: bool = True) -> MagicMock:
    """Create a mock ontology port."""
    port = MagicMock()
    if sparql_works:
        port.sparql_query.return_value = [{"s": "http://example.org/x"}]
    else:
        port.sparql_query.side_effect = Exception("SPARQL endpoint unavailable")
    return port


# ---------------------------------------------------------------------------
# Tests: structural-only:clean — no violations
# ---------------------------------------------------------------------------


class TestCleanStatus:
    """Verify that clean files produce structural-only:clean."""

    def test_clean_files_with_sparql(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Clean files + working SPARQL -> structural-only:clean."""
        clean_file = _make_clean_file(tmp_path)
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.return_value = (
                ["PatternA"],
                ["PrincipleB"],
                [],
            )
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(tmp_path, [clean_file], ontology_port=port)
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ContextScanOutput)
        assert result.data.conformance_status == "structural-only:clean"
        assert result.data.violations == []
        assert "No import violations" in result.data.violation_report

    def test_clean_files_no_ontology(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Clean files + no ontology_port -> structural-only:sparql-unavailable.

        Even though there are no violations, the absence of an ontology
        port means SPARQL is unavailable and that status takes precedence.
        """
        clean_file = _make_clean_file(tmp_path)
        ctx = _make_ctx(tmp_path, [clean_file], ontology_port=None)
        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ContextScanOutput)
        assert result.data.conformance_status == "structural-only:sparql-unavailable"
        assert result.data.violations == []

    def test_empty_affected_files_with_sparql(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """No affected files + working SPARQL -> structural-only:clean."""
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.return_value = ([], [], [])
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(tmp_path, [], ontology_port=port)
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.conformance_status == "structural-only:clean"


# ---------------------------------------------------------------------------
# Tests: structural-only:violations-found
# ---------------------------------------------------------------------------


class TestViolationsFoundStatus:
    """Verify that violations produce structural-only:violations-found."""

    def test_violating_file_with_sparql(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """A file with import violations + working SPARQL -> violations-found."""
        bad_file = _make_violating_file(tmp_path)
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.return_value = (
                ["PatternX"],
                ["PrincipleY"],
                [],
            )
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(tmp_path, [bad_file], ontology_port=port)
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert isinstance(result.data, ContextScanOutput)
        assert result.data.conformance_status == "structural-only:violations-found"
        assert len(result.data.violations) > 0
        assert "Violation Report" in result.data.violation_report

    def test_violating_file_report_contains_details(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """The violation report includes file path and import details."""
        bad_file = _make_violating_file(tmp_path)
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.return_value = ([], [], [])
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(tmp_path, [bad_file], ontology_port=port)
            result = phase.execute(ctx)

        assert result.data is not None
        assert "tulla.cli" in result.data.violation_report

    def test_mixed_clean_and_violating_files(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Mix of clean and violating files -> violations-found."""
        clean_file = _make_clean_file(tmp_path)
        bad_file = _make_violating_file(tmp_path)
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.return_value = ([], [], [])
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(
                tmp_path, [clean_file, bad_file], ontology_port=port
            )
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.conformance_status == "structural-only:violations-found"
        assert len(result.data.violations) > 0


# ---------------------------------------------------------------------------
# Tests: structural-only:sparql-unavailable
# ---------------------------------------------------------------------------


class TestSparqlUnavailableStatus:
    """Verify SPARQL unavailability degrades gracefully."""

    def test_sparql_probe_fails(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """SPARQL probe failure -> structural-only:sparql-unavailable."""
        clean_file = _make_clean_file(tmp_path)
        port = _make_ontology_port(sparql_works=False)
        ctx = _make_ctx(tmp_path, [clean_file], ontology_port=port)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.conformance_status == "structural-only:sparql-unavailable"

    def test_no_ontology_port(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """No ontology_port in config -> structural-only:sparql-unavailable."""
        clean_file = _make_clean_file(tmp_path)
        ctx = _make_ctx(tmp_path, [clean_file], ontology_port=None)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.conformance_status == "structural-only:sparql-unavailable"

    def test_sparql_resolution_fails_after_probe(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """SPARQL probe succeeds but pattern resolution fails -> sparql-unavailable."""
        clean_file = _make_clean_file(tmp_path)
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.side_effect = Exception(
                "Resolution failed"
            )
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(tmp_path, [clean_file], ontology_port=port)
            result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.conformance_status == "structural-only:sparql-unavailable"

    def test_violations_with_sparql_unavailable(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Violations + SPARQL unavailable -> sparql-unavailable takes precedence."""
        bad_file = _make_violating_file(tmp_path)
        port = _make_ontology_port(sparql_works=False)
        ctx = _make_ctx(tmp_path, [bad_file], ontology_port=port)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        # SPARQL unavailability takes precedence over violation status
        assert result.data.conformance_status == "structural-only:sparql-unavailable"
        # But violations are still detected and reported
        assert len(result.data.violations) > 0


# ---------------------------------------------------------------------------
# Tests: missing files handled gracefully
# ---------------------------------------------------------------------------


class TestMissingFileHandling:
    """Verify that missing files do not crash the phase."""

    def test_nonexistent_file_skipped(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """A file path that doesn't exist is skipped without crashing."""
        missing_path = str(tmp_path / "does_not_exist.py")
        ctx = _make_ctx(tmp_path, [missing_path], ontology_port=None)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.violations == []

    def test_mix_of_missing_and_existing(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Missing files are skipped; existing files are still scanned."""
        clean_file = _make_clean_file(tmp_path)
        missing_path = str(tmp_path / "gone.py")
        ctx = _make_ctx(
            tmp_path, [missing_path, clean_file], ontology_port=None
        )

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        # No crash, and no violations from the clean file
        assert result.data.violations == []

    def test_all_files_missing(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """All affected files missing -> no violations, phase succeeds."""
        missing_files = [
            str(tmp_path / "a.py"),
            str(tmp_path / "b.py"),
        ]
        ctx = _make_ctx(tmp_path, missing_files, ontology_port=None)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.violations == []
        assert result.data.conformance_status == "structural-only:sparql-unavailable"


# ---------------------------------------------------------------------------
# Tests: prev_output as dict
# ---------------------------------------------------------------------------


class TestPrevOutputAsDict:
    """Verify that prev_output works when passed as a plain dict."""

    def test_dict_prev_output(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """prev_output as a dict should work the same as an IntakeOutput object."""
        clean_file = _make_clean_file(tmp_path)
        prev_dict = {
            "change_type": "bugfix",
            "description": "Fix a bug",
            "affected_files": [clean_file],
            "scope": "single-package",
            "lightweight_eligible": True,
        }
        ctx = _make_ctx(tmp_path, prev_output=prev_dict)

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.violations == []

    def test_no_prev_output(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Missing prev_output -> empty affected_files, no crash."""
        ctx = PhaseContext(
            idea_id="test-idea", work_dir=tmp_path, config={}
        )

        result = phase.execute(ctx)

        assert result.status == PhaseStatus.SUCCESS
        assert result.data is not None
        assert result.data.violations == []


# ---------------------------------------------------------------------------
# Tests: phase metadata
# ---------------------------------------------------------------------------


class TestPhaseMetadata:
    """Verify basic phase attributes."""

    def test_phase_id(self, phase: ContextScanPhase) -> None:
        assert phase.phase_id == "context-scan"

    def test_build_prompt_returns_empty(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path, [])
        assert phase.build_prompt(ctx) == ""

    def test_get_tools_returns_empty(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path, [])
        assert phase.get_tools(ctx) == []

    def test_parse_output_wraps_dict(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        ctx = _make_ctx(tmp_path, [])
        raw = {
            "violations": [],
            "violation_report": "No violations",
            "patterns": [],
            "principles": [],
            "conformance_status": "structural-only:clean",
            "quality_focus": "isaqb:Maintainability",
        }
        output = phase.parse_output(ctx, raw)
        assert isinstance(output, ContextScanOutput)
        assert output.conformance_status == "structural-only:clean"

    def test_quality_focus_defaults_to_maintainability(
        self, phase: ContextScanPhase, tmp_path: Path
    ) -> None:
        """Default quality_focus is isaqb:Maintainability."""
        port = _make_ontology_port(sparql_works=True)

        with patch(
            "tulla.phases.lightweight.context_scan.FindPhase"
        ) as mock_find_cls:
            mock_finder = MagicMock()
            mock_finder._resolve_patterns_via_sparql.return_value = ([], [], [])
            mock_find_cls.return_value = mock_finder

            ctx = _make_ctx(tmp_path, [], ontology_port=port)
            result = phase.execute(ctx)

        assert result.data is not None
        assert result.data.quality_focus == "isaqb:Maintainability"
