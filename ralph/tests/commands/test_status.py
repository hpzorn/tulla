"""Tests for tulla.commands.status — 16 tests across three test classes.

TestQueryPrdStatus  (7): empty context, single complete, blocked deps,
                         complete deps, all six states, missing title,
                         missing status.
TestFormatStatusTable (3): empty summary, header+rows, truncation.
TestStatusCommand   (6): help, missing idea, exit 0, exit 2, exit 1,
                         empty context.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from tulla.cli import EXIT_FAILURE, EXIT_INCOMPLETE, EXIT_SUCCESS, main
from tulla.commands.status import (
    RequirementRow,
    StatusSummary,
    format_status_table,
    query_prd_status,
)
from tulla.phases.implementation.models import RequirementStatus
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubOntology(OntologyPort):
    """Minimal ontology stub returning pre-configured fact lists."""

    def __init__(self, facts_by_key: dict[str, list[dict[str, str]]] | None = None):
        self._facts = facts_by_key or {}

    def _key(self, **kw: Any) -> str:
        parts = []
        for k in ("subject", "predicate", "context"):
            if kw.get(k):
                parts.append(f"{k}={kw[k]}")
        return "|".join(sorted(parts))

    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        key = self._key(subject=subject, predicate=predicate, context=context)
        return {"result": self._facts.get(key, [])}

    # -- stubs for abstract methods not used in these tests --
    def store_fact(self, subject: str, predicate: str, object: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def query_ideas(self, **kw: Any) -> dict[str, Any]:
        return {}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def sparql_query(self, query: str, **kw: Any) -> dict[str, Any]:
        return {}

    def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
        return {}

    def set_lifecycle(self, idea_id: str, new_state: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0


# ---------------------------------------------------------------------------
# TestQueryPrdStatus — 7 tests
# ---------------------------------------------------------------------------


class TestQueryPrdStatus:
    """Tests for query_prd_status() covering core query and classification."""

    def test_empty_context(self) -> None:
        """No requirements in the context → empty StatusSummary."""
        ontology = StubOntology()
        result = query_prd_status(ontology, "prd-idea-99")
        assert result == StatusSummary()
        assert result.total == 0
        assert result.rows == []

    def test_single_complete(self) -> None:
        """Single requirement with prd:Complete status."""
        ontology = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "Create module"},
                {"predicate": "prd:status", "object": "prd:Complete"},
            ],
        })
        result = query_prd_status(ontology, "prd-idea-42")
        assert result.total == 1
        assert result.complete == 1
        assert result.rows[0].requirement_id == "prd:req-42-1-1"
        assert result.rows[0].title == "Create module"
        assert result.rows[0].status == RequirementStatus.COMPLETE
        assert result.rows[0].display_status == "Complete"

    def test_blocked_deps(self) -> None:
        """Pending requirement with unmet dependency → Blocked (deps)."""
        ontology = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-2", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "First"},
                {"predicate": "prd:status", "object": "prd:Pending"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-2": [
                {"predicate": "prd:title", "object": "Second"},
                {"predicate": "prd:status", "object": "prd:Pending"},
                {"predicate": "prd:dependsOn", "object": "prd:req-42-1-1"},
            ],
        })
        result = query_prd_status(ontology, "prd-idea-42")

        row2 = next(r for r in result.rows if r.requirement_id == "prd:req-42-1-2")
        assert row2.display_status == "Blocked (deps)"
        assert row2.status == RequirementStatus.PENDING  # raw status unchanged
        assert result.blocked == 1
        assert result.pending == 1

    def test_complete_deps(self) -> None:
        """Pending requirement with all deps complete → stays Pending."""
        ontology = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-2", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "First"},
                {"predicate": "prd:status", "object": "prd:Complete"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-2": [
                {"predicate": "prd:title", "object": "Second"},
                {"predicate": "prd:status", "object": "prd:Pending"},
                {"predicate": "prd:dependsOn", "object": "prd:req-42-1-1"},
            ],
        })
        result = query_prd_status(ontology, "prd-idea-42")

        row2 = next(r for r in result.rows if r.requirement_id == "prd:req-42-1-2")
        assert row2.display_status == "Pending"
        assert result.complete == 1
        assert result.pending == 1
        assert result.blocked == 0

    def test_all_six_states(self) -> None:
        """Six requirements covering all status values plus Blocked (deps)."""
        ontology = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-2", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-3", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-4", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-5", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-6", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "Complete task"},
                {"predicate": "prd:status", "object": "prd:Complete"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-2": [
                {"predicate": "prd:title", "object": "In progress task"},
                {"predicate": "prd:status", "object": "prd:InProgress"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-3": [
                {"predicate": "prd:title", "object": "Pending task"},
                {"predicate": "prd:status", "object": "prd:Pending"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-4": [
                {"predicate": "prd:title", "object": "Blocked task"},
                {"predicate": "prd:status", "object": "prd:Blocked"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-5": [
                {"predicate": "prd:title", "object": "Failed task"},
                {"predicate": "prd:status", "object": "prd:Failed"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-6": [
                {"predicate": "prd:title", "object": "Blocked by deps"},
                {"predicate": "prd:status", "object": "prd:Pending"},
                {"predicate": "prd:dependsOn", "object": "prd:req-42-1-3"},
            ],
        })
        result = query_prd_status(ontology, "prd-idea-42")

        assert result.total == 6
        assert result.complete == 1
        assert result.in_progress == 1
        assert result.pending == 1
        assert result.blocked == 2  # 1 explicit Blocked + 1 Blocked (deps)
        assert result.failed == 1

    def test_missing_title(self) -> None:
        """Requirement without a prd:title → title defaults to empty string."""
        ontology = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:status", "object": "prd:Pending"},
            ],
        })
        result = query_prd_status(ontology, "prd-idea-42")
        assert result.rows[0].title == ""
        assert result.total == 1

    def test_missing_status(self) -> None:
        """Requirement without a prd:status → defaults to PENDING."""
        ontology = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "No status set"},
            ],
        })
        result = query_prd_status(ontology, "prd-idea-42")
        assert result.rows[0].status == RequirementStatus.PENDING
        assert result.rows[0].display_status == "Pending"
        assert result.pending == 1


# ---------------------------------------------------------------------------
# TestFormatStatusTable — 3 tests
# ---------------------------------------------------------------------------


class TestFormatStatusTable:
    """Tests for format_status_table() covering empty, rendering, and truncation."""

    def test_empty_summary(self) -> None:
        """Empty StatusSummary → 'No requirements found' guard message."""
        result = format_status_table(StatusSummary(), idea_number=42)
        assert result == "No requirements found for idea 42."

    def test_header_and_rows(self) -> None:
        """Table contains box-drawing header, data rows, and summary line."""
        summary = StatusSummary(
            rows=[
                RequirementRow(
                    requirement_id="prd:req-42-1-1",
                    title="Create module",
                    status=RequirementStatus.COMPLETE,
                    display_status="Complete",
                    deps=[],
                ),
                RequirementRow(
                    requirement_id="prd:req-42-1-2",
                    title="Add validation",
                    status=RequirementStatus.IN_PROGRESS,
                    display_status="In Progress",
                    deps=["prd:req-42-1-1"],
                ),
            ],
            total=2,
            complete=1,
            in_progress=1,
        )
        table = format_status_table(summary, terminal_width=120)

        # Box-drawing characters present
        assert "┌" in table
        assert "┘" in table
        assert "│" in table
        assert "─" in table

        # Header labels
        assert "Requirement" in table
        assert "Title" in table
        assert "Status" in table
        assert "Deps" in table

        # Data content
        assert "prd:req-42-1-1" in table
        assert "prd:req-42-1-2" in table
        assert "Create module" in table
        assert "Complete" in table
        assert "In Progress" in table

        # Summary line
        assert "Total: 2" in table
        assert "Complete: 1" in table

        # Correct number of lines: top + header + sep + 2 data + bottom + summary
        lines = table.strip().split("\n")
        assert len(lines) == 7

    def test_truncation(self) -> None:
        """Long titles are truncated with ellipsis on narrow terminals."""
        summary = StatusSummary(
            rows=[
                RequirementRow(
                    requirement_id="prd:req-42-1-1",
                    title="A very long title that should definitely be truncated on a narrow terminal window",
                    status=RequirementStatus.PENDING,
                    display_status="Pending",
                    deps=["prd:req-42-1-99", "prd:req-42-1-98"],
                ),
            ],
            total=1,
            pending=1,
        )
        table = format_status_table(summary, terminal_width=80)
        assert "…" in table


# ---------------------------------------------------------------------------
# TestStatusCommand — 6 tests (Click CLI via CliRunner)
# ---------------------------------------------------------------------------


class TestStatusCommand:
    """Tests for the ``tulla status`` CLI command using Click CliRunner."""

    def test_help(self) -> None:
        """``tulla status --help`` exits 0 and shows usage."""
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0
        assert "Show PRD requirement status" in result.output

    def test_missing_idea(self) -> None:
        """``tulla status`` without --idea exits non-zero."""
        runner = CliRunner()
        result = runner.invoke(main, ["status"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

    @patch("tulla.cli.OntologyMCPAdapter")
    def test_exit_0_all_complete(self, mock_adapter_cls: Any) -> None:
        """All requirements complete → exit code 0 (EXIT_SUCCESS)."""
        stub = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "Done"},
                {"predicate": "prd:status", "object": "prd:Complete"},
            ],
        })
        mock_adapter_cls.return_value = stub

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "42"])
        assert result.exit_code == EXIT_SUCCESS
        assert "prd:req-42-1-1" in result.output
        assert "Complete" in result.output

    @patch("tulla.cli.OntologyMCPAdapter")
    def test_exit_2_incomplete(self, mock_adapter_cls: Any) -> None:
        """Some requirements not complete → exit code 2 (EXIT_INCOMPLETE)."""
        stub = StubOntology({
            "context=prd-idea-42|predicate=rdf:type": [
                {"subject": "prd:req-42-1-1", "object": "prd:Requirement"},
                {"subject": "prd:req-42-1-2", "object": "prd:Requirement"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "Done"},
                {"predicate": "prd:status", "object": "prd:Complete"},
            ],
            "context=prd-idea-42|subject=prd:req-42-1-2": [
                {"predicate": "prd:title", "object": "Not done"},
                {"predicate": "prd:status", "object": "prd:Pending"},
            ],
        })
        mock_adapter_cls.return_value = stub

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "42"])
        assert result.exit_code == EXIT_INCOMPLETE

    @patch("tulla.cli.OntologyMCPAdapter")
    def test_exit_1_error(self, mock_adapter_cls: Any) -> None:
        """Exception during query → exit code 1 (EXIT_FAILURE)."""
        mock_adapter_cls.return_value.recall_facts.side_effect = RuntimeError("connection refused")

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "42"])
        assert result.exit_code == EXIT_FAILURE
        assert "Error querying status" in result.output

    @patch("tulla.cli.OntologyMCPAdapter")
    def test_empty_context(self, mock_adapter_cls: Any) -> None:
        """No requirements in context → exit 0 and 'No requirements found' message."""
        stub = StubOntology()  # No facts at all
        mock_adapter_cls.return_value = stub

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--idea", "99"])
        assert result.exit_code == EXIT_SUCCESS
        assert "No requirements found for idea 99" in result.output
