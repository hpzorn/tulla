"""Tests for project_init workflows (req-69-3-2, req-69-4-1, req-69-6-9).

Verifies:
  - Unscoped ADRs receive ``isaqb:scope "idea"`` via add_triple()
  - Already-scoped ADRs are skipped
  - Idempotency: second call returns 0
  - init_project creates project instance, stores ADRs with correct scope/links
  - promote_adr updates scope and adds prd:hasADR link
  - req-69-6-9: Focused test cases for migration idempotency, project entity
    creation, confirmed ADR storage, and promote_adr behaviour
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tulla.namespaces import ARCH_NS, ISAQB_NS, PRD_NS, RDF_TYPE
from tulla.ports.claude import ClaudePort, ClaudeRequest, ClaudeResult
from tulla.ports.ontology import OntologyPort
from tulla.workflows.project_init import (
    RDFS_LABEL,
    CandidateADR,
    init_project,
    migrate_existing_adrs,
    promote_adr,
)

# ---------------------------------------------------------------------------
# Mock OntologyPort with scope-aware SPARQL simulation
# ---------------------------------------------------------------------------


class _MockOntologyPort(OntologyPort):
    """Minimal OntologyPort mock that tracks triples and simulates the
    ``FILTER NOT EXISTS { ?adr isaqb:scope ?s }`` pattern used by
    migrate_existing_adrs.
    """

    def __init__(self, adrs: list[dict[str, Any]]) -> None:
        # Each ADR dict: {"uri": str, "has_scope": bool}
        self._adrs = {a["uri"]: a["has_scope"] for a in adrs}
        self.add_triple_calls: list[dict[str, Any]] = []

    # -- OntologyPort ABC implementation ------------------------------------

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.add_triple_calls.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": object,
                "is_literal": is_literal,
            }
        )
        # Simulate the triple being stored — mark this ADR as scoped
        if predicate == f"{ISAQB_NS}scope" and subject in self._adrs:
            self._adrs[subject] = True
        return {"status": "added"}

    def remove_triples_by_subject(
        self,
        subject: str,
        *,
        ontology: str | None = None,
    ) -> int:
        return 0

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {"conforms": True, "violations": []}

    def sparql_query(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        """Return unscoped ADRs when the migration query is detected."""
        if "FILTER NOT EXISTS" in query and "isaqb:scope" in query:
            return {
                "results": [
                    {"adr": uri} for uri, has_scope in self._adrs.items() if not has_scope
                ],
            }
        return {"results": []}

    def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        return {"status": "ok"}

    # -- convenience stubs not needed by this test --------------------------

    def query_ideas(self, **kw: Any) -> dict[str, Any]:
        return {"ideas": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(self, **kw: Any) -> dict[str, Any]:
        return {"stored": True}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(self, **kw: Any) -> dict[str, Any]:
        return {"facts": []}

    def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(self, idea_id: str, new_state: str, **kw: Any) -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMigrateExistingAdrs:
    """req-69-3-2: migrate_existing_adrs annotates unscoped ADRs."""

    def test_annotates_unscoped_adrs(self) -> None:
        """3 unscoped + 1 scoped => 3 add_triple calls, returns 3."""
        port = _MockOntologyPort(
            adrs=[
                {"uri": "arch:adr-1", "has_scope": False},
                {"uri": "arch:adr-2", "has_scope": False},
                {"uri": "arch:adr-3", "has_scope": False},
                {"uri": "arch:adr-4", "has_scope": True},
            ]
        )

        result = migrate_existing_adrs(port)

        assert result == 3
        assert len(port.add_triple_calls) == 3

        # Each call should set isaqb:scope "idea" as a literal
        for call in port.add_triple_calls:
            assert call["predicate"] == f"{ISAQB_NS}scope"
            assert call["object"] == "idea"
            assert call["is_literal"] is True

        # Verify the correct subjects were annotated
        annotated = {c["subject"] for c in port.add_triple_calls}
        assert annotated == {"arch:adr-1", "arch:adr-2", "arch:adr-3"}

    def test_idempotent_second_call(self) -> None:
        """Second call after migration returns 0 — all ADRs already scoped."""
        port = _MockOntologyPort(
            adrs=[
                {"uri": "arch:adr-1", "has_scope": False},
                {"uri": "arch:adr-2", "has_scope": False},
                {"uri": "arch:adr-3", "has_scope": False},
                {"uri": "arch:adr-4", "has_scope": True},
            ]
        )

        first = migrate_existing_adrs(port)
        assert first == 3

        # Reset call tracker to count only second-run calls
        port.add_triple_calls.clear()

        second = migrate_existing_adrs(port)
        assert second == 0
        assert len(port.add_triple_calls) == 0

    def test_all_already_scoped(self) -> None:
        """If every ADR already has a scope, returns 0 immediately."""
        port = _MockOntologyPort(
            adrs=[
                {"uri": "arch:adr-1", "has_scope": True},
                {"uri": "arch:adr-2", "has_scope": True},
            ]
        )

        assert migrate_existing_adrs(port) == 0
        assert len(port.add_triple_calls) == 0

    def test_no_adrs_at_all(self) -> None:
        """Empty ontology => 0 annotated."""
        port = _MockOntologyPort(adrs=[])

        assert migrate_existing_adrs(port) == 0
        assert len(port.add_triple_calls) == 0


# ---------------------------------------------------------------------------
# Mock ClaudePort that returns 4 candidate ADRs as JSON
# ---------------------------------------------------------------------------

_FOUR_ADR_JSON = json.dumps(
    [
        {
            "title": "Use Python 3.11+ for new code",
            "context": (
                "Consistency with existing infrastructure"
                " (ontology-server, MCP tools)"
            ),
            "consequences": (
                "(+) Uniform toolchain."
                " (-) Excludes older runtimes."
                " (~) Migration path clear."
            ),
            "arc42_section": 4,
        },
        {
            "title": "Ports and Adapters architecture",
            "context": "Decoupling domain from infrastructure for testability",
            "consequences": "(+) Easy mocking. (+) Swap adapters. (-) More boilerplate.",
            "arc42_section": 5,
        },
        {
            "title": "RDF/Turtle for ontology storage",
            "context": "Knowledge graph approach for semantic queries and SHACL validation",
            "consequences": "(+) SPARQL queries. (+) SHACL validation. (-) Learning curve.",
            "arc42_section": 9,
        },
        {
            "title": "Additive-only ontology changes",
            "context": "Prevent breaking existing data when evolving the schema",
            "consequences": (
                "(+) Backwards compatible."
                " (-) Schema bloat over time."
                " (~) Requires migration helpers."
            ),
            "arc42_section": 9,
        },
    ]
)


class _MockClaudePort(ClaudePort):
    """Mock ClaudePort that returns pre-configured JSON output."""

    def __init__(self, output_text: str) -> None:
        self._output_text = output_text
        self.calls: list[ClaudeRequest] = []

    def run(self, request: ClaudeRequest) -> ClaudeResult:
        self.calls.append(request)
        return ClaudeResult(exit_code=0, output_text=self._output_text)


# ---------------------------------------------------------------------------
# Tests for init_project (req-69-4-1)
# ---------------------------------------------------------------------------


class TestInitProject:
    """req-69-4-1: init_project orchestrates project initialisation."""

    def test_creates_project_and_adrs(self, tmp_path: Path) -> None:
        """Mock claude_port returning 4 ADRs; verify project instance
        is created, ADRs are stored with correct scope and links,
        arc42 links are created.
        """
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Guidelines\nUse Python 3.11+\n")

        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort(_FOUR_ADR_JSON)

        result = init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="test-proj",
            claude_md_path=claude_md,
        )

        # Verify result metadata
        assert result.project_uri == f"{PRD_NS}project-test-proj"
        assert result.adr_count == 4
        assert len(result.candidates) == 4

        # Collect all add_triple calls for analysis
        calls = ont_port.add_triple_calls

        # --- Project instance triples ---
        project_uri = f"{PRD_NS}project-test-proj"

        # rdf:type prd:Project
        type_calls = [
            c
            for c in calls
            if c["subject"] == project_uri
            and c["predicate"] == RDF_TYPE
            and c["object"] == f"{PRD_NS}Project"
        ]
        assert len(type_calls) == 1

        # rdfs:label
        label_calls = [
            c for c in calls if c["subject"] == project_uri and c["predicate"] == RDFS_LABEL
        ]
        assert len(label_calls) == 1
        assert label_calls[0]["is_literal"] is True

        # prd:projectId
        pid_calls = [
            c
            for c in calls
            if c["subject"] == project_uri and c["predicate"] == f"{PRD_NS}projectId"
        ]
        assert len(pid_calls) == 1
        assert pid_calls[0]["object"] == "test-proj"
        assert pid_calls[0]["is_literal"] is True

        # --- ADR triples (4 ADRs) ---
        for idx in range(1, 5):
            adr_uri = f"{ARCH_NS}adr-test-proj-{idx}"

            # rdf:type isaqb:ArchitectureDecision
            adr_type = [
                c
                for c in calls
                if c["subject"] == adr_uri
                and c["predicate"] == RDF_TYPE
                and c["object"] == f"{ISAQB_NS}ArchitectureDecision"
            ]
            assert len(adr_type) == 1, f"ADR {idx} missing rdf:type"

            # isaqb:scope "project"
            scope = [
                c
                for c in calls
                if c["subject"] == adr_uri
                and c["predicate"] == f"{ISAQB_NS}scope"
                and c["object"] == "project"
            ]
            assert len(scope) == 1, f"ADR {idx} missing scope"
            assert scope[0]["is_literal"] is True

            # prd:hasADR link from project
            has_adr = [
                c
                for c in calls
                if c["subject"] == project_uri
                and c["predicate"] == f"{PRD_NS}hasADR"
                and c["object"] == adr_uri
            ]
            assert len(has_adr) == 1, f"ADR {idx} missing prd:hasADR link"

            # isaqb:documentedIn link to arc42 section
            doc_in = [
                c
                for c in calls
                if c["subject"] == adr_uri and c["predicate"] == f"{ISAQB_NS}documentedIn"
            ]
            assert len(doc_in) == 1, f"ADR {idx} missing documentedIn"

        # Verify specific arc42 section mappings
        adr1_doc = [
            c
            for c in calls
            if c["subject"] == f"{ARCH_NS}adr-test-proj-1"
            and c["predicate"] == f"{ISAQB_NS}documentedIn"
        ]
        assert adr1_doc[0]["object"] == f"{ISAQB_NS}Arc42_04"  # section 4

        adr3_doc = [
            c
            for c in calls
            if c["subject"] == f"{ARCH_NS}adr-test-proj-3"
            and c["predicate"] == f"{ISAQB_NS}documentedIn"
        ]
        assert adr3_doc[0]["object"] == f"{ISAQB_NS}Arc42_09"  # section 9

    def test_interactive_reject(self, tmp_path: Path) -> None:
        """Interactive mode: reject 2 of 4 ADRs => only 2 stored."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Test\n")

        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort(_FOUR_ADR_JSON)

        call_count = 0

        def _confirm(candidate: CandidateADR) -> str:
            nonlocal call_count
            call_count += 1
            # Reject the 2nd and 4th candidates
            if call_count in (2, 4):
                return "reject"
            return "accept"

        result = init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="rej-proj",
            claude_md_path=claude_md,
            interactive=True,
            confirm_fn=_confirm,
        )

        assert result.adr_count == 2
        # 4 candidates total, 2 confirmed
        assert len(result.candidates) == 4
        confirmed = [c for c in result.candidates if c.confirmed]
        assert len(confirmed) == 2

    def test_sends_claude_md_content_to_llm(self, tmp_path: Path) -> None:
        """Verify the CLAUDE.md content is included in the LLM prompt."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My Unique Project Rules\nAlways use Turtle.\n")

        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort("[]")  # No ADRs extracted

        init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="prompt-test",
            claude_md_path=claude_md,
        )

        assert len(claude_port.calls) == 1
        prompt = claude_port.calls[0].prompt
        assert "My Unique Project Rules" in prompt
        assert "Always use Turtle" in prompt

    def test_missing_claude_md(self, tmp_path: Path) -> None:
        """Missing CLAUDE.md => returns empty result without error."""
        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort("[]")

        result = init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="missing",
            claude_md_path=tmp_path / "nonexistent.md",
        )

        assert result.adr_count == 0
        assert result.project_uri == ""
        assert len(claude_port.calls) == 0  # LLM never called


# ---------------------------------------------------------------------------
# Tests for promote_adr (req-69-4-1)
# ---------------------------------------------------------------------------


class TestPromoteAdr:
    """req-69-4-1: promote_adr updates scope and adds prd:hasADR link."""

    def test_scope_changes_and_link_added(self) -> None:
        """Verify scope changes to 'project' and prd:hasADR link is created."""
        port = _MockOntologyPort(adrs=[])
        adr_uri = f"{ARCH_NS}adr-42-1"
        project_uri = f"{PRD_NS}project-main"

        promote_adr(port, adr_uri, project_uri)

        calls = port.add_triple_calls

        # Verify isaqb:scope "project" was added
        scope_calls = [
            c
            for c in calls
            if c["subject"] == adr_uri
            and c["predicate"] == f"{ISAQB_NS}scope"
            and c["object"] == "project"
        ]
        assert len(scope_calls) == 1
        assert scope_calls[0]["is_literal"] is True

        # Verify prd:hasADR link from project to ADR
        link_calls = [
            c
            for c in calls
            if c["subject"] == project_uri
            and c["predicate"] == f"{PRD_NS}hasADR"
            and c["object"] == adr_uri
        ]
        assert len(link_calls) == 1

    def test_sparql_delete_attempted(self) -> None:
        """Verify SPARQL UPDATE DELETE is attempted to remove old scope."""
        update_calls: list[str] = []

        class _TrackingUpdatePort(_MockOntologyPort):
            def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
                update_calls.append(query)
                return {"status": "ok"}

        port = _TrackingUpdatePort(adrs=[])
        promote_adr(port, f"{ARCH_NS}adr-99-1", f"{PRD_NS}project-x")

        # At least one SPARQL UPDATE call with DELETE
        assert any("DELETE" in q for q in update_calls)


# ---------------------------------------------------------------------------
# req-69-6-9: Focused test cases for project-init workflow and migration
# ---------------------------------------------------------------------------


class TestMigrateIdempotency:
    """req-69-6-9(a): migrate_existing_adrs annotates only unscoped ADRs
    and is idempotent."""

    def test_only_unscoped_adrs_annotated(self) -> None:
        """Mixed set: 2 unscoped + 2 scoped => only 2 annotated."""
        port = _MockOntologyPort(
            adrs=[
                {"uri": f"{ARCH_NS}adr-a", "has_scope": False},
                {"uri": f"{ARCH_NS}adr-b", "has_scope": True},
                {"uri": f"{ARCH_NS}adr-c", "has_scope": False},
                {"uri": f"{ARCH_NS}adr-d", "has_scope": True},
            ]
        )

        count = migrate_existing_adrs(port)

        assert count == 2
        annotated_subjects = {c["subject"] for c in port.add_triple_calls}
        assert annotated_subjects == {f"{ARCH_NS}adr-a", f"{ARCH_NS}adr-c"}

        # All calls must set isaqb:scope "idea" as literal
        for call in port.add_triple_calls:
            assert call["predicate"] == f"{ISAQB_NS}scope"
            assert call["object"] == "idea"
            assert call["is_literal"] is True

        # Scoped ADRs must NOT be touched
        assert f"{ARCH_NS}adr-b" not in annotated_subjects
        assert f"{ARCH_NS}adr-d" not in annotated_subjects

    def test_idempotent_returns_zero_on_rerun(self) -> None:
        """Second call after first migration returns 0 — all already scoped."""
        port = _MockOntologyPort(
            adrs=[
                {"uri": f"{ARCH_NS}adr-x", "has_scope": False},
                {"uri": f"{ARCH_NS}adr-y", "has_scope": False},
            ]
        )

        first = migrate_existing_adrs(port)
        assert first == 2

        port.add_triple_calls.clear()

        second = migrate_existing_adrs(port)
        assert second == 0
        assert len(port.add_triple_calls) == 0

    def test_empty_ontology_returns_zero(self) -> None:
        """No ADRs at all => 0 annotated, no calls made."""
        port = _MockOntologyPort(adrs=[])
        assert migrate_existing_adrs(port) == 0
        assert len(port.add_triple_calls) == 0


class TestInitProjectEntity:
    """req-69-6-9(b): init_project creates project entity with correct triples."""

    def test_project_type_label_and_id(self, tmp_path: Path) -> None:
        """Project instance carries rdf:type, rdfs:label, prd:projectId."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Rules\nUse Python.\n")

        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort("[]")  # No ADRs — focus on project entity

        result = init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="entity-test",
            claude_md_path=claude_md,
        )

        project_uri = f"{PRD_NS}project-entity-test"
        assert result.project_uri == project_uri
        calls = ont_port.add_triple_calls

        # rdf:type prd:Project
        type_calls = [
            c
            for c in calls
            if c["subject"] == project_uri
            and c["predicate"] == RDF_TYPE
            and c["object"] == f"{PRD_NS}Project"
        ]
        assert len(type_calls) == 1
        assert type_calls[0]["is_literal"] is False

        # rdfs:label "Project entity-test" (literal)
        label_calls = [
            c for c in calls if c["subject"] == project_uri and c["predicate"] == RDFS_LABEL
        ]
        assert len(label_calls) == 1
        assert label_calls[0]["object"] == "Project entity-test"
        assert label_calls[0]["is_literal"] is True

        # prd:projectId "entity-test" (literal)
        pid_calls = [
            c
            for c in calls
            if c["subject"] == project_uri and c["predicate"] == f"{PRD_NS}projectId"
        ]
        assert len(pid_calls) == 1
        assert pid_calls[0]["object"] == "entity-test"
        assert pid_calls[0]["is_literal"] is True


class TestInitProjectConfirmedADRs:
    """req-69-6-9(c): init_project stores confirmed ADRs with correct scope
    and links."""

    def test_confirmed_adrs_have_project_scope_and_links(self, tmp_path: Path) -> None:
        """Each confirmed ADR gets isaqb:scope "project", prd:hasADR link,
        isaqb:documentedIn, and all required predicates."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Architecture\nPorts and Adapters.\n")

        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort(_FOUR_ADR_JSON)

        result = init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="scope-test",
            claude_md_path=claude_md,
        )

        assert result.adr_count == 4
        project_uri = f"{PRD_NS}project-scope-test"
        calls = ont_port.add_triple_calls

        for idx in range(1, 5):
            adr_uri = f"{ARCH_NS}adr-scope-test-{idx}"

            # isaqb:scope "project" (literal)
            scope = [
                c
                for c in calls
                if c["subject"] == adr_uri and c["predicate"] == f"{ISAQB_NS}scope"
            ]
            assert len(scope) == 1, f"ADR {idx} missing scope"
            assert scope[0]["object"] == "project"
            assert scope[0]["is_literal"] is True

            # prd:hasADR link from project to ADR (not a literal)
            has_adr = [
                c
                for c in calls
                if c["subject"] == project_uri
                and c["predicate"] == f"{PRD_NS}hasADR"
                and c["object"] == adr_uri
            ]
            assert len(has_adr) == 1, f"ADR {idx} missing hasADR link"
            assert has_adr[0]["is_literal"] is False

            # rdf:type isaqb:ArchitectureDecision
            adr_type = [
                c
                for c in calls
                if c["subject"] == adr_uri
                and c["predicate"] == RDF_TYPE
                and c["object"] == f"{ISAQB_NS}ArchitectureDecision"
            ]
            assert len(adr_type) == 1, f"ADR {idx} missing rdf:type"

            # isaqb:context (literal)
            ctx = [
                c
                for c in calls
                if c["subject"] == adr_uri and c["predicate"] == f"{ISAQB_NS}context"
            ]
            assert len(ctx) == 1, f"ADR {idx} missing context"
            assert ctx[0]["is_literal"] is True

            # isaqb:consequences (literal)
            cons = [
                c
                for c in calls
                if c["subject"] == adr_uri and c["predicate"] == f"{ISAQB_NS}consequences"
            ]
            assert len(cons) == 1, f"ADR {idx} missing consequences"
            assert cons[0]["is_literal"] is True

            # isaqb:decisionStatus (URI, not literal)
            status = [
                c
                for c in calls
                if c["subject"] == adr_uri and c["predicate"] == f"{ISAQB_NS}decisionStatus"
            ]
            assert len(status) == 1, f"ADR {idx} missing decisionStatus"
            assert status[0]["object"] == f"{ISAQB_NS}StatusProposed"
            assert status[0]["is_literal"] is False

            # isaqb:documentedIn (URI)
            doc_in = [
                c
                for c in calls
                if c["subject"] == adr_uri and c["predicate"] == f"{ISAQB_NS}documentedIn"
            ]
            assert len(doc_in) == 1, f"ADR {idx} missing documentedIn"
            assert doc_in[0]["is_literal"] is False

    def test_rejected_adrs_not_stored(self, tmp_path: Path) -> None:
        """Interactive rejection excludes ADRs from storage; only confirmed
        ADRs produce triples."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Rules\n")

        ont_port = _MockOntologyPort(adrs=[])
        claude_port = _MockClaudePort(_FOUR_ADR_JSON)

        call_idx = 0

        def _reject_odds(candidate: CandidateADR) -> str:
            nonlocal call_idx
            call_idx += 1
            return "reject" if call_idx % 2 == 0 else "accept"

        result = init_project(
            ontology_port=ont_port,
            claude_port=claude_port,
            project_id="rej-test",
            claude_md_path=claude_md,
            interactive=True,
            confirm_fn=_reject_odds,
        )

        # 2 accepted, 2 rejected
        assert result.adr_count == 2
        assert len(result.candidates) == 4
        assert sum(1 for c in result.candidates if c.confirmed) == 2

        calls = ont_port.add_triple_calls

        # Only 2 ADR URIs should have scope triples
        scope_calls = [
            c for c in calls if c["predicate"] == f"{ISAQB_NS}scope" and c["object"] == "project"
        ]
        assert len(scope_calls) == 2

        # No rejected ADR URIs should appear
        adr_uri_3 = f"{ARCH_NS}adr-rej-test-3"
        adr_uri_4 = f"{ARCH_NS}adr-rej-test-4"
        stored_subjects = {c["subject"] for c in calls}
        # Rejected candidates are #2 and #4 (1-indexed in the confirmed list
        # they don't appear at all, so adr-rej-test-{idx} only goes to 2)
        assert adr_uri_3 not in stored_subjects
        assert adr_uri_4 not in stored_subjects


class TestPromoteAdrReq69_6_9:
    """req-69-6-9(d): promote_adr updates scope and adds hasADR link."""

    def test_adds_project_scope_and_link(self) -> None:
        """After promotion, ADR has isaqb:scope 'project' and prd:hasADR link."""
        port = _MockOntologyPort(adrs=[])
        adr_uri = f"{ARCH_NS}adr-idea-7"
        project_uri = f"{PRD_NS}project-promo"

        promote_adr(port, adr_uri, project_uri)

        calls = port.add_triple_calls

        # isaqb:scope "project" as literal
        scope = [
            c
            for c in calls
            if c["subject"] == adr_uri
            and c["predicate"] == f"{ISAQB_NS}scope"
            and c["object"] == "project"
        ]
        assert len(scope) == 1
        assert scope[0]["is_literal"] is True

        # prd:hasADR link (not a literal)
        link = [
            c
            for c in calls
            if c["subject"] == project_uri
            and c["predicate"] == f"{PRD_NS}hasADR"
            and c["object"] == adr_uri
        ]
        assert len(link) == 1
        assert link[0]["is_literal"] is False

    def test_sparql_delete_removes_old_scope(self) -> None:
        """promote_adr issues a SPARQL UPDATE DELETE to remove any existing scope."""
        update_queries: list[str] = []

        class _UpdateTracker(_MockOntologyPort):
            def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
                update_queries.append(query)
                return {"status": "ok"}

        port = _UpdateTracker(adrs=[])
        adr_uri = f"{ARCH_NS}adr-old-scope-1"

        promote_adr(port, adr_uri, f"{PRD_NS}project-del")

        # A DELETE query targeting the specific ADR URI must be issued
        delete_queries = [q for q in update_queries if "DELETE" in q]
        assert len(delete_queries) >= 1
        assert adr_uri in delete_queries[0]

    def test_sparql_delete_failure_non_fatal(self) -> None:
        """If SPARQL UPDATE DELETE fails, promote_adr still adds new scope and link."""

        class _FailingUpdate(_MockOntologyPort):
            def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
                if "DELETE" in query:
                    raise RuntimeError("SPARQL endpoint unavailable")
                return {"status": "ok"}

        port = _FailingUpdate(adrs=[])
        adr_uri = f"{ARCH_NS}adr-fail-del"
        project_uri = f"{PRD_NS}project-fail"

        # Should not raise
        promote_adr(port, adr_uri, project_uri)

        calls = port.add_triple_calls

        # Scope and link must still be added despite DELETE failure
        scope = [
            c
            for c in calls
            if c["subject"] == adr_uri
            and c["predicate"] == f"{ISAQB_NS}scope"
            and c["object"] == "project"
        ]
        assert len(scope) == 1

        link = [
            c
            for c in calls
            if c["subject"] == project_uri
            and c["predicate"] == f"{PRD_NS}hasADR"
            and c["object"] == adr_uri
        ]
        assert len(link) == 1


# ---------------------------------------------------------------------------
# In-memory triple store mock for integration testing
# ---------------------------------------------------------------------------


class _InMemoryOntologyPort(OntologyPort):
    """OntologyPort mock with in-memory triple store behaviour.

    Tracks triples added via ``add_triple`` and answers SPARQL queries
    for ``migrate_existing_adrs`` (``FILTER NOT EXISTS`` pattern) and
    ``collect_project_decisions`` (scope-based + URI-prefix matching).
    """

    def __init__(self) -> None:
        # Each triple: (subject, predicate, object, is_literal)
        self.triples: list[tuple[str, str, str, bool]] = []

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.triples.append((subject, predicate, object, is_literal))
        return {"status": "added"}

    def remove_triples_by_subject(
        self,
        subject: str,
        *,
        ontology: str | None = None,
    ) -> int:
        before = len(self.triples)
        self.triples = [t for t in self.triples if t[0] != subject]
        return before - len(self.triples)

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {"conforms": True, "violations": []}

    def sparql_query(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        rdfs_label = "http://www.w3.org/2000/01/rdf-schema#label"

        # Pattern 1: migrate_existing_adrs — find unscoped ADRs
        if "FILTER NOT EXISTS" in query and "isaqb:scope" in query:
            scope_pred = f"{ISAQB_NS}scope"
            adr_type = f"{ISAQB_NS}ArchitectureDecision"
            # Find all ADRs
            adr_uris = {t[0] for t in self.triples if t[1] == RDF_TYPE and t[2] == adr_type}
            # Find which have a scope
            scoped_uris = {t[0] for t in self.triples if t[1] == scope_pred}
            unscoped = adr_uris - scoped_uris
            return {"results": [{"adr": uri} for uri in sorted(unscoped)]}

        # Pattern 2: collect_project_decisions — project-scoped ADRs
        if "isaqb:scope" in query and '"project"' in query and "rdfs:label" in query:
            scope_pred = f"{ISAQB_NS}scope"
            adr_type = f"{ISAQB_NS}ArchitectureDecision"

            # Find ADRs with scope "project"
            project_scoped = {
                t[0]
                for t in self.triples
                if t[1] == scope_pred and t[2] == "project" and t[3] is True
            }
            # Also include URI-prefix matches (STRSTARTS pattern)
            # Extract project_id from query: STRSTARTS(STR(?adr), "...adr-{pid}-")
            import re as _re

            prefix_match = _re.search(r'STRSTARTS\(STR\(\?adr\),\s*"([^"]+)"\)', query)
            if prefix_match:
                uri_prefix = prefix_match.group(1)
                uri_matched = {
                    t[0]
                    for t in self.triples
                    if t[1] == RDF_TYPE and t[2] == adr_type and t[0].startswith(uri_prefix)
                }
                project_scoped = project_scoped | uri_matched

            # Build result rows with labels, context, status, consequences
            results = []
            for uri in sorted(project_scoped):
                row: dict[str, str] = {"adr": uri}
                for t in self.triples:
                    if t[0] != uri:
                        continue
                    if t[1] == rdfs_label:
                        row["title"] = t[2]
                    elif t[1] == f"{ISAQB_NS}context":
                        row["context"] = t[2]
                    elif t[1] == f"{ISAQB_NS}decisionStatus":
                        row["status"] = t[2]
                    elif t[1] == f"{ISAQB_NS}consequences":
                        row["consequences"] = t[2]
                row.setdefault("title", "")
                row.setdefault("context", "")
                row.setdefault("status", "")
                row.setdefault("consequences", "")
                row["quality_attributes"] = ""
                results.append(row)
            return {"results": results}

        return {"results": []}

    def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        """Handle SPARQL UPDATE operations (DELETE WHERE from promote_adr)."""
        return {"status": "ok"}

    # -- convenience stubs not needed by integration test -------------------

    def query_ideas(self, **kw: Any) -> dict[str, Any]:
        return {"ideas": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(self, **kw: Any) -> dict[str, Any]:
        return {"stored": True}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(self, **kw: Any) -> dict[str, Any]:
        return {"facts": []}

    def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(self, idea_id: str, new_state: str, **kw: Any) -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Full Integration Test (req-69-6-10)
# ---------------------------------------------------------------------------

# Three-ADR JSON for the mock LLM to return during init_project
_THREE_ADR_JSON = json.dumps(
    [
        {
            "title": "Use Python 3.11+ for new code",
            "context": "Consistency with existing infrastructure",
            "consequences": "(+) Uniform toolchain. (-) Excludes older runtimes.",
            "arc42_section": 4,
        },
        {
            "title": "Ports and Adapters architecture",
            "context": "Decoupling domain from infrastructure for testability",
            "consequences": "(+) Easy mocking. (+) Swap adapters. (-) Boilerplate.",
            "arc42_section": 5,
        },
        {
            "title": "RDF/Turtle for ontology storage",
            "context": "Knowledge graph approach for semantic queries",
            "consequences": "(+) SPARQL queries. (+) SHACL validation. (-) Learning curve.",
            "arc42_section": 9,
        },
    ]
)


class TestIntegration:
    """req-69-6-10: Full end-to-end integration test.

    Exercises the data flow: ontology → query → prompt → extraction.
    Uses an in-memory triple store mock to validate the complete pipeline.
    """

    def test_integration_full_flow(self, tmp_path: Path) -> None:
        """End-to-end: migrate → init → collect → prompt → extract."""
        from tulla.core.phase import PhaseContext
        from tulla.core.phase_facts import collect_project_decisions
        from tulla.phases.planning.p3 import P3Phase, _extract_adrs

        ont = _InMemoryOntologyPort()

        # -----------------------------------------------------------------
        # Step 1: Seed 2 existing ADRs without scope, then migrate
        # -----------------------------------------------------------------
        rdfs_label = "http://www.w3.org/2000/01/rdf-schema#label"

        for i in (1, 2):
            uri = f"{ARCH_NS}adr-legacy-{i}"
            ont.add_triple(
                subject=uri,
                predicate=RDF_TYPE,
                object=f"{ISAQB_NS}ArchitectureDecision",
            )
            ont.add_triple(
                subject=uri,
                predicate=rdfs_label,
                object=f"Legacy ADR {i}",
                is_literal=True,
            )

        migrated = migrate_existing_adrs(ont)
        assert migrated == 2, f"Expected 2 migrated, got {migrated}"

        # Verify both now carry isaqb:scope "idea"
        scope_triples = [t for t in ont.triples if t[1] == f"{ISAQB_NS}scope" and t[2] == "idea"]
        assert len(scope_triples) == 2

        # -----------------------------------------------------------------
        # Step 2: init_project with mock CLAUDE.md producing 3 ADRs
        # -----------------------------------------------------------------
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Project Rules\nUse Python 3.11+\n")

        claude_port = _MockClaudePort(_THREE_ADR_JSON)

        init_result = init_project(
            ontology_port=ont,
            claude_port=claude_port,
            project_id="integ",
            claude_md_path=claude_md,
        )

        assert init_result.adr_count == 3
        assert init_result.project_uri == f"{PRD_NS}project-integ"

        # -----------------------------------------------------------------
        # Step 3: collect_project_decisions → 3 project ADRs
        # -----------------------------------------------------------------
        decisions = collect_project_decisions(ont, "integ")

        assert len(decisions) == 3, f"Expected 3 project decisions, got {len(decisions)}"
        for d in decisions:
            assert d["scope"] == "project"
            assert d["title"]  # non-empty title

        # -----------------------------------------------------------------
        # Step 4: Build P3 prompt and verify project ADR section present
        # -----------------------------------------------------------------
        p3 = P3Phase()
        ctx = PhaseContext(
            idea_id="test-idea",
            work_dir=tmp_path,
            config={
                "project_decisions": decisions,
            },
        )
        prompt = p3.build_prompt(ctx)

        assert "## Project ADRs in Effect" in prompt
        # Verify at least one project ADR title appears in the prompt
        assert "Use Python 3.11+ for new code" in prompt
        assert "Ports and Adapters architecture" in prompt
        assert "RDF/Turtle for ontology storage" in prompt
        # Verify governance instructions are present
        assert "DO NOT" in prompt
        assert "feature-specific" in prompt

        # -----------------------------------------------------------------
        # Step 5: Extract feature ADRs and verify scope is "idea"
        # -----------------------------------------------------------------
        # Simulate P3 output containing feature ADRs (pattern: ADR-N: Title)
        feature_adr_content = """\
# P3: Architecture Design

## Architecture Decisions (ADRs)

### ADR-1: Use event sourcing for state management
**Status**: Proposed
**Context**: Need to track all state changes for auditability.
**Decision**: Adopt event sourcing pattern for domain state.
**Consequences**: (+) Full audit trail. (-) Increased complexity. (~) Migration needed.

### ADR-2: gRPC for inter-service communication
**Status**: Proposed
**Context**: Need efficient binary protocol for high-throughput paths.
**Decision**: Use gRPC with protobuf for all internal service communication.
**Consequences**: (+) Performance. (+) Type safety. (-) Browser support limited.
"""
        feature_adrs = _extract_adrs(feature_adr_content)

        assert len(feature_adrs) == 2, f"Expected 2 feature ADRs, got {len(feature_adrs)}"
        for adr in feature_adrs:
            assert adr["scope"] == "idea", (
                f"Feature ADR scope should be 'idea', got {adr['scope']}"
            )


# ---------------------------------------------------------------------------
# pyshacl Integration Tests (req-69-6-8)
# ---------------------------------------------------------------------------

import pyshacl  # noqa: E402
from rdflib import Graph, Literal, Namespace, URIRef  # noqa: E402
from rdflib.namespace import RDF, RDFS, XSD  # noqa: E402

PRD = Namespace("http://tulla.dev/prd#")
ISAQB = Namespace("http://tulla.dev/isaqb#")
SH = Namespace("http://www.w3.org/ns/shacl#")

_PRD_SHAPES_PATH = "ontologies/prd-ontology.ttl"
_ISAQB_SHAPES_PATH = "ontologies/isaqb-ontology.ttl"


def _load_shapes(path: str) -> Graph:
    """Load an ontology file as a SHACL shapes graph."""
    g = Graph()
    g.parse(path, format="turtle")
    return g


class TestProjectShapePyshacl:
    """req-69-6-8: Validate prd:ProjectShape using pyshacl against real ontology."""

    def test_valid_project_conforms(self) -> None:
        """A project with rdfs:label, prd:projectId, prd:hasADR, and
        prd:hasQualityGoal passes validation with no violations."""
        shapes = _load_shapes(_PRD_SHAPES_PATH)
        data = Graph()
        data.bind("prd", PRD)
        data.bind("rdfs", RDFS)

        proj = PRD["project-valid"]
        data.add((proj, RDF.type, PRD["Project"]))
        data.add((proj, RDFS.label, Literal("Valid Project", datatype=XSD.string)))
        data.add((proj, PRD["projectId"], Literal("valid-1", datatype=XSD.string)))
        # Provide an ADR and quality goal to avoid warnings
        adr = ISAQB["adr-valid-1"]
        data.add((proj, PRD["hasADR"], adr))
        qg = ISAQB["qg-valid-1"]
        data.add((proj, PRD["hasQualityGoal"], qg))

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        # Filter results specifically for our project
        project_results = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            if focus and focus[0] == proj:
                project_results.append(result)

        assert len(project_results) == 0, (
            f"Expected 0 violations for valid project, got {len(project_results)}.\n"
            f"Full results:\n{results_text}"
        )

    def test_missing_label_triggers_violation(self) -> None:
        """A project without rdfs:label triggers sh:Violation."""
        shapes = _load_shapes(_PRD_SHAPES_PATH)
        data = Graph()
        data.bind("prd", PRD)

        proj = PRD["project-no-label"]
        data.add((proj, RDF.type, PRD["Project"]))
        data.add((proj, PRD["projectId"], Literal("nolabel-1", datatype=XSD.string)))

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        # Find violations for this project on rdfs:label
        label_violations = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            severity = list(results_graph.objects(result, SH["resultSeverity"]))
            path = list(results_graph.objects(result, SH["resultPath"]))
            if (
                focus
                and focus[0] == proj
                and severity
                and severity[0] == SH["Violation"]
                and path
                and path[0] == RDFS.label
            ):
                label_violations.append(result)

        assert len(label_violations) >= 1, (
            f"Expected sh:Violation for missing label, got {len(label_violations)}.\n"
            f"Full results:\n{results_text}"
        )

    def test_missing_adrs_triggers_warning(self) -> None:
        """A project with label and projectId but no prd:hasADR triggers sh:Warning."""
        shapes = _load_shapes(_PRD_SHAPES_PATH)
        data = Graph()
        data.bind("prd", PRD)
        data.bind("rdfs", RDFS)

        proj = PRD["project-no-adrs"]
        data.add((proj, RDF.type, PRD["Project"]))
        data.add((proj, RDFS.label, Literal("No ADRs Project", datatype=XSD.string)))
        data.add((proj, PRD["projectId"], Literal("noadr-1", datatype=XSD.string)))

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        # Find warnings for missing prd:hasADR
        adr_warnings = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            severity = list(results_graph.objects(result, SH["resultSeverity"]))
            path = list(results_graph.objects(result, SH["resultPath"]))
            if (
                focus
                and focus[0] == proj
                and severity
                and severity[0] == SH["Warning"]
                and path
                and path[0] == PRD["hasADR"]
            ):
                adr_warnings.append(result)

        assert len(adr_warnings) >= 1, (
            f"Expected sh:Warning for missing ADRs, got {len(adr_warnings)}.\n"
            f"Full results:\n{results_text}"
        )


def _make_full_adr(g: Graph, uri: URIRef, label: str, scope: str) -> None:
    """Add a fully-valid ADR instance to graph *g* (satisfies ADRShapeStrict)."""
    g.add((uri, RDF.type, ISAQB["ArchitectureDecision"]))
    g.add((uri, RDFS.label, Literal(label)))
    g.add((uri, ISAQB["scope"], Literal(scope)))
    g.add((uri, ISAQB["context"], Literal(f"Context for {label}")))
    g.add((uri, ISAQB["rationale"], Literal(f"Rationale for {label}")))
    g.add((uri, ISAQB["consequences"], Literal(f"Consequences for {label}")))
    g.add((uri, ISAQB["decisionStatus"], ISAQB["Accepted"]))
    # ADRShapeStrict warns on < 2 options
    opt1 = URIRef(str(uri) + "-opt1")
    opt2 = URIRef(str(uri) + "-opt2")
    g.add((opt1, RDF.type, ISAQB["DecisionOption"]))
    g.add((opt2, RDF.type, ISAQB["DecisionOption"]))
    g.add((uri, ISAQB["hasOption"], opt1))
    g.add((uri, ISAQB["hasOption"], opt2))


class TestADRScopeCoherenceShapePyshacl:
    """req-69-6-8: Validate isaqb:ADRScopeCoherenceShape using pyshacl."""

    @staticmethod
    def _build_base_graph() -> tuple[Graph, URIRef]:
        """Build a data graph with a project-scope ADR addressing Maintainability.

        Returns (graph, qa_uri) so tests can add idea-scope ADRs.
        """
        g = Graph()
        g.bind("isaqb", ISAQB)
        g.bind("rdfs", RDFS)

        qa = ISAQB["Maintainability"]
        g.add((qa, RDF.type, ISAQB["QualityAttribute"]))
        g.add((qa, RDFS.label, Literal("Maintainability")))

        adr_project = ISAQB["adr-project-maint"]
        _make_full_adr(g, adr_project, "Use Layered Architecture", "project")
        g.add((adr_project, ISAQB["addresses"], qa))

        return g, qa

    def test_unlinked_idea_adr_triggers_warning(self) -> None:
        """Idea-scope ADR addressing same QA as project-scope ADR
        WITHOUT refinesDecision/supersedes triggers sh:Warning."""
        shapes = _load_shapes(_ISAQB_SHAPES_PATH)
        data, qa = self._build_base_graph()

        adr_idea = ISAQB["adr-idea-unlinked"]
        _make_full_adr(data, adr_idea, "Use Plugin Pattern", "idea")
        data.add((adr_idea, ISAQB["addresses"], qa))

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        # Find warnings from ADRScopeCoherenceShape for the unlinked ADR
        coherence_warnings = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            source = list(results_graph.objects(result, SH["sourceShape"]))
            if (
                focus
                and focus[0] == adr_idea
                and source
                and source[0] == ISAQB["ADRScopeCoherenceShape"]
            ):
                coherence_warnings.append(result)

        assert len(coherence_warnings) >= 1, (
            f"Expected warning for unlinked idea-scope ADR, "
            f"got {len(coherence_warnings)}.\n"
            f"Full results:\n{results_text}"
        )

        # Verify message mentions the project ADR title
        for w in coherence_warnings:
            msgs = list(results_graph.objects(w, SH["resultMessage"]))
            msg_text = str(msgs[0]) if msgs else ""
            assert "Use Layered Architecture" in msg_text, (
                f"Warning should mention project ADR title, got: {msg_text}"
            )

    def test_idea_adr_with_refinesDecision_no_warning(self) -> None:
        """Idea-scope ADR with isaqb:refinesDecision link to the project ADR
        does NOT trigger ADRScopeCoherenceShape warning."""
        shapes = _load_shapes(_ISAQB_SHAPES_PATH)
        data, qa = self._build_base_graph()

        adr_idea = ISAQB["adr-idea-refines"]
        _make_full_adr(data, adr_idea, "Use Adapter Pattern", "idea")
        data.add((adr_idea, ISAQB["addresses"], qa))
        data.add((adr_idea, ISAQB["refinesDecision"], ISAQB["adr-project-maint"]))

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        coherence_warnings = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            source = list(results_graph.objects(result, SH["sourceShape"]))
            if (
                focus
                and focus[0] == adr_idea
                and source
                and source[0] == ISAQB["ADRScopeCoherenceShape"]
            ):
                coherence_warnings.append(result)

        assert len(coherence_warnings) == 0, (
            f"Expected no warnings for ADR with refinesDecision link, "
            f"got {len(coherence_warnings)}.\n"
            f"Full results:\n{results_text}"
        )

    def test_idea_adr_with_supersedes_no_warning(self) -> None:
        """Idea-scope ADR with isaqb:supersedes link to the project ADR
        does NOT trigger ADRScopeCoherenceShape warning."""
        shapes = _load_shapes(_ISAQB_SHAPES_PATH)
        data, qa = self._build_base_graph()

        adr_idea = ISAQB["adr-idea-supersedes"]
        _make_full_adr(data, adr_idea, "Replace Layered Arch", "idea")
        data.add((adr_idea, ISAQB["addresses"], qa))
        data.add((adr_idea, ISAQB["supersedes"], ISAQB["adr-project-maint"]))

        conforms, results_graph, results_text = pyshacl.validate(
            data_graph=data,
            shacl_graph=shapes,
            advanced=True,
        )

        coherence_warnings = []
        for result in results_graph.subjects(RDF.type, SH["ValidationResult"]):
            focus = list(results_graph.objects(result, SH["focusNode"]))
            source = list(results_graph.objects(result, SH["sourceShape"]))
            if (
                focus
                and focus[0] == adr_idea
                and source
                and source[0] == ISAQB["ADRScopeCoherenceShape"]
            ):
                coherence_warnings.append(result)

        assert len(coherence_warnings) == 0, (
            f"Expected no warnings for ADR with supersedes link, "
            f"got {len(coherence_warnings)}.\n"
            f"Full results:\n{results_text}"
        )
