"""Tests for ralph.commands.status (query_prd_status, format_status_table, CLI).

16 tests across three classes:
- TestQueryPrdStatus (7): empty context, single complete, blocked deps,
  complete deps, all six states, missing title, missing status.
- TestFormatStatusTable (3): empty summary, header+rows, truncation.
- TestStatusCommand (6): help, missing idea, exit 0, exit 2, exit 1, empty context.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ralph.cli import EXIT_INCOMPLETE, EXIT_SUCCESS, main
from ralph.commands.status import (
    RequirementRow,
    StatusSummary,
    format_status_table,
    query_prd_status,
)
from ralph.phases.implementation.models import RequirementStatus
from ralph.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRD_CTX = "prd-idea-99"


def _make_ontology_mock(
    requirements: list[str],
    statuses: dict[str, str] | None = None,
    titles: dict[str, str] | None = None,
    deps: dict[str, list[str]] | None = None,
) -> OntologyPort:
    """Build a mock OntologyPort with structured recall_facts data.

    Parameters:
        requirements: List of requirement IDs (e.g. ``["prd:req-1", ...]``).
        statuses: Mapping from req_id to raw status string (e.g. ``"prd:Complete"``).
        titles: Optional mapping from req_id to title string.
        deps: Optional mapping from req_id to list of dependency req_ids.
    """
    statuses = statuses or {}
    titles = titles or {}
    deps = deps or {}

    def recall_facts_side_effect(
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        # rdf:type query -- return all requirements
        if predicate == "rdf:type" and subject is None:
            return {
                "result": [
                    {"subject": rid, "predicate": "rdf:type", "object": "prd:Requirement"}
                    for rid in requirements
                ]
            }

        # prd:status query for a specific requirement
        if predicate == "prd:status" and subject is not None:
            raw = statuses.get(subject)
            if raw:
                return {
                    "result": [
                        {"subject": subject, "predicate": "prd:status", "object": raw}
                    ]
                }
            return {"result": []}

        # prd:title query for a specific requirement
        if predicate == "prd:title" and subject is not None:
            title = titles.get(subject, "")
            if title:
                return {
                    "result": [
                        {"subject": subject, "predicate": "prd:title", "object": title}
                    ]
                }
            return {"result": []}

        # prd:dependsOn query for a specific requirement
        if predicate == "prd:dependsOn" and subject is not None:
            dep_list = deps.get(subject, [])
            return {
                "result": [
                    {"subject": subject, "predicate": "prd:dependsOn", "object": d}
                    for d in dep_list
                ]
            }

        return {"result": []}

    mock = MagicMock(spec=OntologyPort)
    mock.recall_facts.side_effect = recall_facts_side_effect
    return mock


# ---------------------------------------------------------------------------
# TestQueryPrdStatus — 7 tests
# ---------------------------------------------------------------------------


class TestQueryPrdStatus:
    """Tests for query_prd_status() at the OntologyPort level."""

    def test_empty_context(self) -> None:
        """No requirements in context returns an empty StatusSummary."""
        ontology = _make_ontology_mock(requirements=[])
        result = query_prd_status(ontology, PRD_CTX)

        assert isinstance(result, StatusSummary)
        assert result.total == 0
        assert result.rows == []

    def test_single_complete(self) -> None:
        """One requirement with status Complete is counted correctly."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1"],
            statuses={"prd:req-1": "prd:Complete"},
            titles={"prd:req-1": "Setup DB"},
        )
        result = query_prd_status(ontology, PRD_CTX)

        assert result.total == 1
        assert result.complete == 1
        assert result.pending == 0
        assert result.rows[0].status == RequirementStatus.COMPLETE
        assert result.rows[0].display_status == "Complete"
        assert result.rows[0].title == "Setup DB"

    def test_blocked_deps(self) -> None:
        """Pending req with incomplete dependency gets 'Blocked (deps)'."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1", "prd:req-2"],
            statuses={
                "prd:req-1": "prd:Pending",
                "prd:req-2": "prd:Pending",
            },
            deps={
                "prd:req-2": ["prd:req-1"],  # req-2 depends on req-1
            },
        )
        result = query_prd_status(ontology, PRD_CTX)

        row_map = {r.requirement_id: r for r in result.rows}
        assert row_map["prd:req-1"].display_status == "Pending"
        assert row_map["prd:req-2"].display_status == "Blocked (deps)"
        # Underlying enum stays PENDING
        assert row_map["prd:req-2"].status == RequirementStatus.PENDING

    def test_complete_deps(self) -> None:
        """Pending req with all deps complete stays 'Pending'."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1", "prd:req-2"],
            statuses={
                "prd:req-1": "prd:Complete",
                "prd:req-2": "prd:Pending",
            },
            deps={
                "prd:req-2": ["prd:req-1"],
            },
        )
        result = query_prd_status(ontology, PRD_CTX)

        row_map = {r.requirement_id: r for r in result.rows}
        assert row_map["prd:req-2"].display_status == "Pending"

    def test_all_six_states(self) -> None:
        """Six requirements covering Pending, InProgress, Complete, Blocked, Failed, and Blocked (deps)."""
        ontology = _make_ontology_mock(
            requirements=[
                "prd:req-1", "prd:req-2", "prd:req-3",
                "prd:req-4", "prd:req-5", "prd:req-6",
            ],
            statuses={
                "prd:req-1": "prd:Pending",
                "prd:req-2": "prd:InProgress",
                "prd:req-3": "prd:Complete",
                "prd:req-4": "prd:Blocked",
                "prd:req-5": "prd:Failed",
                "prd:req-6": "prd:Pending",  # Will be Blocked (deps)
            },
            deps={
                "prd:req-6": ["prd:req-1"],  # req-1 is Pending, so req-6 is Blocked (deps)
            },
        )
        result = query_prd_status(ontology, PRD_CTX)

        assert result.total == 6
        assert result.pending == 2  # req-1 and req-6 both have PENDING enum
        assert result.in_progress == 1
        assert result.complete == 1
        assert result.blocked == 1
        assert result.failed == 1

        row_map = {r.requirement_id: r for r in result.rows}
        assert row_map["prd:req-1"].display_status == "Pending"
        assert row_map["prd:req-2"].display_status == "In Progress"
        assert row_map["prd:req-3"].display_status == "Complete"
        assert row_map["prd:req-4"].display_status == "Blocked"
        assert row_map["prd:req-5"].display_status == "Failed"
        assert row_map["prd:req-6"].display_status == "Blocked (deps)"

    def test_missing_title(self) -> None:
        """Requirement with no title fact gets empty string."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1"],
            statuses={"prd:req-1": "prd:Pending"},
            titles={},  # No titles
        )
        result = query_prd_status(ontology, PRD_CTX)

        assert result.rows[0].title == ""

    def test_missing_status(self) -> None:
        """Requirement with no status fact defaults to Pending."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1"],
            statuses={},  # No status facts
        )
        result = query_prd_status(ontology, PRD_CTX)

        assert result.total == 1
        assert result.pending == 1
        assert result.rows[0].status == RequirementStatus.PENDING
        assert result.rows[0].display_status == "Pending"


# ---------------------------------------------------------------------------
# TestFormatStatusTable — 3 tests
# ---------------------------------------------------------------------------


class TestFormatStatusTable:
    """Tests for format_status_table() rendering."""

    def test_empty_summary(self) -> None:
        """Empty StatusSummary produces guard message."""
        result = format_status_table(StatusSummary())
        assert result == "No requirements found."

        result_with_id = format_status_table(StatusSummary(), idea_id=42)
        assert result_with_id == "No requirements found for idea 42."

    @patch("ralph.commands.status._terminal_width", return_value=100)
    def test_header_and_rows(self, _mock_tw: Any) -> None:
        """Table contains header columns and row data with summary line."""
        rows = [
            RequirementRow(
                requirement_id="prd:req-1",
                title="Setup DB",
                status=RequirementStatus.COMPLETE,
                display_status="Complete",
            ),
            RequirementRow(
                requirement_id="prd:req-2",
                title="Add API",
                status=RequirementStatus.PENDING,
                display_status="Blocked (deps)",
            ),
        ]
        summary = StatusSummary(
            total=2, complete=1, pending=1, rows=rows,
        )
        output = format_status_table(summary)

        # Box-drawing characters present
        assert "\u250c" in output  # top-left corner
        assert "\u2518" in output  # bottom-right corner
        assert "\u2502" in output  # vertical pipe
        assert "\u2500" in output  # horizontal line

        # Headers present
        assert "ID" in output
        assert "Title" in output
        assert "Status" in output
        assert "Deps" in output

        # Row data present
        assert "prd:req-1" in output
        assert "Setup DB" in output
        assert "Complete" in output
        assert "prd:req-2" in output
        assert "Add API" in output
        assert "Blocked (deps)" in output

        # Summary line
        last_line = output.strip().split("\n")[-1]
        assert "Total: 2" in last_line
        assert "Complete: 1" in last_line
        assert "Pending: 1" in last_line

        # Deps column shows "yes" for blocked row
        lines = output.split("\n")
        req2_line = [ln for ln in lines if "prd:req-2" in ln][0]
        assert "yes" in req2_line

    @patch("ralph.commands.status._terminal_width", return_value=50)
    def test_truncation(self, _mock_tw: Any) -> None:
        """Long title is truncated with ellipsis at narrow width."""
        rows = [
            RequirementRow(
                requirement_id="prd:req-1",
                title="A very long title that should be truncated at narrow terminal width",
                status=RequirementStatus.PENDING,
                display_status="Pending",
            ),
        ]
        summary = StatusSummary(total=1, pending=1, rows=rows)
        output = format_status_table(summary)
        assert "\u2026" in output  # ellipsis present


# ---------------------------------------------------------------------------
# TestStatusCommand — 6 tests (Click CLI integration)
# ---------------------------------------------------------------------------


class TestStatusCommand:
    """Tests for the ``ralph status`` Click command."""

    def test_help(self) -> None:
        """``ralph status --help`` exits 0 and shows help text."""
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--help"])

        assert result.exit_code == 0
        assert "Show implementation status" in result.output
        assert "--idea" in result.output

    def test_missing_idea(self) -> None:
        """``ralph status`` without --idea exits with error."""
        runner = CliRunner()
        result = runner.invoke(main, ["status"])

        assert result.exit_code != 0
        assert "Missing" in result.output or "required" in result.output.lower() or "Error" in result.output

    @patch("ralph.cli.OntologyMCPAdapter")
    def test_exit_0_all_complete(self, mock_adapter_cls: MagicMock) -> None:
        """Exit 0 when all requirements are complete."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1"],
            statuses={"prd:req-1": "prd:Complete"},
            titles={"prd:req-1": "Done task"},
        )
        mock_adapter_cls.return_value = ontology

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "99"])

        assert result.exit_code == EXIT_SUCCESS

    @patch("ralph.cli.OntologyMCPAdapter")
    def test_exit_2_incomplete(self, mock_adapter_cls: MagicMock) -> None:
        """Exit 2 when work remains (not all complete)."""
        ontology = _make_ontology_mock(
            requirements=["prd:req-1", "prd:req-2"],
            statuses={
                "prd:req-1": "prd:Complete",
                "prd:req-2": "prd:Pending",
            },
        )
        mock_adapter_cls.return_value = ontology

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "99"])

        assert result.exit_code == EXIT_INCOMPLETE

    @patch("ralph.cli.OntologyMCPAdapter")
    def test_exit_1_on_error(self, mock_adapter_cls: MagicMock) -> None:
        """Exit 1 when query_prd_status raises an exception."""
        mock_ontology = MagicMock(spec=OntologyPort)
        mock_ontology.recall_facts.side_effect = RuntimeError("connection refused")
        mock_adapter_cls.return_value = mock_ontology

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "99"])

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("ralph.cli.OntologyMCPAdapter")
    def test_empty_context(self, mock_adapter_cls: MagicMock) -> None:
        """Empty context (no requirements) exits 0 with guard message."""
        ontology = _make_ontology_mock(requirements=[])
        mock_adapter_cls.return_value = ontology

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "99"])

        assert result.exit_code == EXIT_SUCCESS
        assert "No requirements found" in result.output
