"""End-to-end Discovery integration test (req-73-5-1).

Simulates a 5-phase Discovery pipeline run using _MockOntologyPort:
  1. Creates mock phase results for D1-D5 with realistic IntentField values.
  2. Calls persist() for each phase in sequence, asserting stored triple counts.
  3. Calls collect_upstream_facts() before each subsequent phase, verifying
     expected upstream triples.
  4. Calls group_upstream_facts() on collected triples, verifying grouped dict
     has correct phase keys and typed values.
  5. Calls traverse_chain() from D5, verifying it walks back through D4-D1.

# @pattern:PortsAndAdapters -- _MockOntologyPort implements OntologyPort
#   ABC so the full persist/collect/traverse cycle runs without a live
#   ontology-server
# @principle:DependencyInversion -- All test code depends on OntologyPort
#   and PhaseFactPersister abstractions; the mock adapter is injected at
#   fixture level
# @principle:LooseCoupling -- Each test class validates one integration
#   concern (persist, collect, group, traverse) and couples only to
#   phase_facts public API
# @pattern:LayeredArchitecture -- Tests exercise the full layer stack:
#   D1-D5 models -> PhaseFactPersister -> _MockOntologyPort, each
#   assertion targets a specific layer boundary
# @principle:SeparationOfConcerns -- persist/collect/group/traverse are
#   tested as composable stages; group_upstream_facts wraps collect output
#   without changing its contract
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tulla.core.phase import PhaseResult, PhaseStatus
from tulla.core.phase_facts import (
    PhaseFactPersister,
    collect_upstream_facts,
    group_upstream_facts,
    traverse_chain,
)
from tulla.namespaces import PHASE_NS, TRACE_NS
from tulla.phases.discovery.models import (
    D1Output,
    D2Output,
    D3Output,
    D4Output,
    D5Output,
)
from tulla.ports.ontology import OntologyPort

# ---------------------------------------------------------------------------
# Discovery pipeline constants
# ---------------------------------------------------------------------------

IDEA_ID = "73"
DISCOVERY_PHASES = ["d1", "d2", "d3", "d4", "d5"]

# Realistic IntentField values matching the field map:
# D1(key_capabilities, ecosystem_context, reuse_opportunities),
# D2(personas, non_negotiable_needs, primary_persona_jtbd),
# D3(quadrant, strategic_constraints, verdict),
# D4(blockers, root_blocker, recommended_next_steps),
# D5(mode, recommendation, northstar, mandatory_features, key_constraints)

D1_VALUES = {
    "key_capabilities": '[{"name": "ontology-server"}]',
    "ecosystem_context": "Core MCP platform",
    "reuse_opportunities": "Existing discovery pipeline",
}
D2_VALUES = {
    "personas": '[{"name": "Dev", "role": "Engineer", "primary_jtbd": "Automate"}]',
    "non_negotiable_needs": '["Fast iteration"]',
    "primary_persona_jtbd": "When I build features, I want automation, so I can ship faster",
}
D3_VALUES = {
    "quadrant": "high-value-low-effort",
    "strategic_constraints": '["Python 3.11+ only"]',
    "verdict": "P1-High | Strong ROI | High confidence",
}
D4_VALUES = {
    "blockers": "No API endpoint blocks core functionality",
    "root_blocker": "No API endpoint: blocks core functionality",
    "recommended_next_steps": "Build API endpoint first, then auth layer",
}
D5_VALUES = {"mode": "implement", "recommendation": "Proceed with implementation"}


# ---------------------------------------------------------------------------
# _MockOntologyPort — full in-process triple store with SPARQL simulation
# ---------------------------------------------------------------------------


class _MockOntologyPort(OntologyPort):
    """In-memory OntologyPort that records triples and simulates SPARQL queries.

    Unlike the unit-test mock, this version implements sparql_query() to
    return stored triples matching the query patterns, enabling realistic
    collect_upstream_facts() and traverse_chain() integration testing.
    """

    def __init__(self) -> None:
        self.triples: list[dict[str, Any]] = []
        self.removed_subjects: list[str] = []

    # -- triple operations ---------------------------------------------------

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        self.triples.append(
            {
                "subject": subject,
                "predicate": predicate,
                "object": object,
                "is_literal": is_literal,
            }
        )
        return {"status": "added"}

    def remove_triples_by_subject(
        self,
        subject: str,
        *,
        ontology: str | None = None,
    ) -> int:
        before = len(self.triples)
        self.triples = [t for t in self.triples if t["subject"] != subject]
        removed = before - len(self.triples)
        self.removed_subjects.append(subject)
        return removed

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {"conforms": True, "violations": []}

    def sparql_query(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        """Simulate SPARQL by inspecting stored triples.

        Handles three query patterns used by phase_facts:
        1. collect_upstream_facts:
           SELECT ?s ?p ?o WHERE { ?s phase:forRequirement "ID" .
           ?s ?p ?o }
        2. traverse_chain ancestor query:
           SELECT ?ancestor WHERE { <subject> trace:tracesTo+
           ?ancestor }
        3. traverse_chain facts query:
           SELECT ?p ?o WHERE { <subject> ?p ?o }
        """
        import re

        # Pattern 1: collect_upstream_facts query
        if "forRequirement" in query and "?s ?p ?o" in query:
            match = re.search(r'forRequirement\s+"([^"]+)"', query)
            if match:
                idea_id = match.group(1)
                results = []
                for t in self.triples:
                    subj = t["subject"]
                    has_req = any(
                        tr["subject"] == subj
                        and tr["predicate"] == f"{PHASE_NS}forRequirement"
                        and tr["object"] == idea_id
                        for tr in self.triples
                    )
                    if has_req:
                        results.append(
                            {
                                "s": t["subject"],
                                "p": t["predicate"],
                                "o": t["object"],
                            }
                        )
                return {"results": results}

        # Pattern 2: traverse_chain ancestor query (trace:tracesTo+)
        if "tracesTo" in query and "?ancestor" in query:
            # Extract the subject URI from the WHERE clause body, not PREFIX lines
            match = re.search(r"WHERE\s*\{[^}]*<([^>]+)>", query, re.DOTALL)
            if match:
                start_uri = match.group(1)
                ancestors = self._walk_traces_to(start_uri)
                return {"results": [{"ancestor": a} for a in ancestors]}

        # Pattern 3: traverse_chain facts query (single subject)
        if "?p ?o" in query and "?s" not in query:
            match = re.search(r"WHERE\s*\{[^}]*<([^>]+)>", query, re.DOTALL)
            if match:
                subj_uri = match.group(1)
                results = [
                    {"p": t["predicate"], "o": t["object"]}
                    for t in self.triples
                    if t["subject"] == subj_uri
                ]
                return {"results": results}

        return {"results": []}

    def _walk_traces_to(self, start_uri: str) -> list[str]:
        """Walk trace:tracesTo chain from start_uri, returning ancestors in order."""
        ancestors: list[str] = []
        current = start_uri
        seen: set[str] = {current}
        while True:
            next_uri = None
            for t in self.triples:
                if t["subject"] == current and t["predicate"] == f"{TRACE_NS}tracesTo":
                    next_uri = t["object"]
                    break
            if next_uri is None or next_uri in seen:
                break
            ancestors.append(next_uri)
            seen.add(next_uri)
            current = next_uri
        return ancestors

    def sparql_update(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        return {"status": "ok"}

    # -- unused stubs (satisfy ABC) ------------------------------------------

    def query_ideas(self, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(self, subject: str, predicate: str, object: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(self, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}

    def update_idea(self, idea_id: str, **kwargs: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(self, idea_id: str, new_state: str, *, reason: str = "") -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Helpers — build realistic phase results
# ---------------------------------------------------------------------------


def _make_d1() -> PhaseResult[D1Output]:
    return PhaseResult(
        status=PhaseStatus.SUCCESS,
        data=D1Output(
            inventory_file=Path("/work/d1/inventory.json"),
            key_capabilities=D1_VALUES["key_capabilities"],
            ecosystem_context=D1_VALUES["ecosystem_context"],
            reuse_opportunities=D1_VALUES["reuse_opportunities"],
        ),
    )


def _make_d2() -> PhaseResult[D2Output]:
    return PhaseResult(
        status=PhaseStatus.SUCCESS,
        data=D2Output(
            personas_file=Path("/work/d2/personas.md"),
            personas=D2_VALUES["personas"],
            non_negotiable_needs=D2_VALUES["non_negotiable_needs"],
            primary_persona_jtbd=D2_VALUES["primary_persona_jtbd"],
        ),
    )


def _make_d3() -> PhaseResult[D3Output]:
    return PhaseResult(
        status=PhaseStatus.SUCCESS,
        data=D3Output(
            value_mapping_file=Path("/work/d3/value-map.md"),
            quadrant=D3_VALUES["quadrant"],
            strategic_constraints=D3_VALUES["strategic_constraints"],
            verdict=D3_VALUES["verdict"],
        ),
    )


def _make_d4() -> PhaseResult[D4Output]:
    return PhaseResult(
        status=PhaseStatus.SUCCESS,
        data=D4Output(
            gap_analysis_file=Path("/work/d4/gaps.md"),
            blockers=D4_VALUES["blockers"],
            root_blocker=D4_VALUES["root_blocker"],
            recommended_next_steps=D4_VALUES["recommended_next_steps"],
        ),
    )


def _make_d5() -> PhaseResult[D5Output]:
    return PhaseResult(
        status=PhaseStatus.SUCCESS,
        data=D5Output(
            output_file=Path("/work/d5/summary.md"),
            mode=D5_VALUES["mode"],
            recommendation=D5_VALUES["recommendation"],
        ),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_port() -> _MockOntologyPort:
    return _MockOntologyPort()


@pytest.fixture()
def persister(mock_port: _MockOntologyPort) -> PhaseFactPersister:
    return PhaseFactPersister(mock_port)


# ===================================================================
# 1. Persist each phase in sequence — verify stored triple counts
# ===================================================================


class TestPersistDiscoveryPipeline:
    """Persist D1-D5 in sequence with realistic IntentField values.

    Each phase stores: rdf:type + intent fields + producedBy + forRequirement
    + optional tracesTo predecessor.
    D1: rdf:type + 3 intent + producedBy + forRequirement = 6 (no predecessor)
    D2: rdf:type + 3 intent + producedBy + forRequirement + tracesTo = 7
    D3: rdf:type + 3 intent + producedBy + forRequirement + tracesTo = 7
    D4: rdf:type + 3 intent + producedBy + forRequirement + tracesTo = 7
    D5: rdf:type + 5 intent + producedBy + forRequirement + tracesTo = 9
    """

    def test_d1_persist_produces_6_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        result = persister.persist(
            idea_id=IDEA_ID,
            phase_id="d1",
            phase_result=_make_d1(),
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )
        assert result.stored_count == 6
        assert len(mock_port.triples) == 6

    def test_d2_persist_produces_7_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        persister.persist(
            idea_id=IDEA_ID,
            phase_id="d1",
            phase_result=_make_d1(),
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )
        result = persister.persist(
            idea_id=IDEA_ID,
            phase_id="d2",
            phase_result=_make_d2(),
            predecessor_phase_id="d1",
            shacl_shape_id=None,
        )
        assert result.stored_count == 7

    def test_d3_persist_produces_7_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        persister.persist(
            idea_id=IDEA_ID,
            phase_id="d1",
            phase_result=_make_d1(),
            predecessor_phase_id=None,
            shacl_shape_id=None,
        )
        persister.persist(
            idea_id=IDEA_ID,
            phase_id="d2",
            phase_result=_make_d2(),
            predecessor_phase_id="d1",
            shacl_shape_id=None,
        )
        result = persister.persist(
            idea_id=IDEA_ID,
            phase_id="d3",
            phase_result=_make_d3(),
            predecessor_phase_id="d2",
            shacl_shape_id=None,
        )
        assert result.stored_count == 7

    def test_d4_persist_produces_7_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        for phase_id, make_fn, pred in [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
        ]:
            persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )
        result = persister.persist(
            idea_id=IDEA_ID,
            phase_id="d4",
            phase_result=_make_d4(),
            predecessor_phase_id="d3",
            shacl_shape_id=None,
        )
        assert result.stored_count == 7

    def test_d5_persist_produces_9_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        for phase_id, make_fn, pred in [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
            ("d4", _make_d4, "d3"),
        ]:
            persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )
        result = persister.persist(
            idea_id=IDEA_ID,
            phase_id="d5",
            phase_result=_make_d5(),
            predecessor_phase_id="d4",
            shacl_shape_id=None,
        )
        assert result.stored_count == 9

    def test_full_pipeline_total_triples(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """Total triples after all 5 phases: 6 + 7 + 7 + 7 + 9 = 36."""
        pipeline = [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
            ("d4", _make_d4, "d3"),
            ("d5", _make_d5, "d4"),
        ]
        total = 0
        for phase_id, make_fn, pred in pipeline:
            result = persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )
            total += result.stored_count
        assert total == 36
        assert len(mock_port.triples) == 36

    def test_intent_field_values_persisted_correctly(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """Verify each phase's IntentField values appear as preserves- literals."""
        pipeline = [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
            ("d4", _make_d4, "d3"),
            ("d5", _make_d5, "d4"),
        ]
        for phase_id, make_fn, pred in pipeline:
            persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )

        # Collect all preserves- triples keyed by phase
        preserves: dict[str, dict[str, str]] = {}
        for t in mock_port.triples:
            if f"{PHASE_NS}preserves-" in t["predicate"]:
                phase_id = t["subject"].split("-")[-1]
                field_name = t["predicate"].replace(f"{PHASE_NS}preserves-", "")
                preserves.setdefault(phase_id, {})[field_name] = t["object"]

        # D1 fields
        assert preserves["d1"]["key_capabilities"] == D1_VALUES["key_capabilities"]
        assert preserves["d1"]["ecosystem_context"] == D1_VALUES["ecosystem_context"]
        assert preserves["d1"]["reuse_opportunities"] == D1_VALUES["reuse_opportunities"]
        # D2 fields
        assert preserves["d2"]["personas"] == D2_VALUES["personas"]
        assert preserves["d2"]["non_negotiable_needs"] == D2_VALUES["non_negotiable_needs"]
        assert preserves["d2"]["primary_persona_jtbd"] == D2_VALUES["primary_persona_jtbd"]
        # D3 fields
        assert preserves["d3"]["quadrant"] == D3_VALUES["quadrant"]
        assert preserves["d3"]["strategic_constraints"] == D3_VALUES["strategic_constraints"]
        assert preserves["d3"]["verdict"] == D3_VALUES["verdict"]
        # D4 fields
        assert preserves["d4"]["blockers"] == D4_VALUES["blockers"]
        assert preserves["d4"]["root_blocker"] == D4_VALUES["root_blocker"]
        assert preserves["d4"]["recommended_next_steps"] == D4_VALUES["recommended_next_steps"]
        # D5 fields
        assert preserves["d5"]["mode"] == "implement"
        assert preserves["d5"]["recommendation"] == "Proceed with implementation"
        assert preserves["d5"]["northstar"] == ""
        assert preserves["d5"]["mandatory_features"] == "[]"
        assert preserves["d5"]["key_constraints"] == "[]"


# ===================================================================
# 2. collect_upstream_facts — verify upstream triples before each phase
# ===================================================================


class TestCollectUpstreamFacts:
    """Call collect_upstream_facts() before each phase and verify upstream triples."""

    @pytest.fixture(autouse=True)
    def _persist_all_phases(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        """Persist all 5 phases so collect can find them."""
        pipeline = [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
            ("d4", _make_d4, "d3"),
            ("d5", _make_d5, "d4"),
        ]
        for phase_id, make_fn, pred in pipeline:
            persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )

    def test_d1_has_no_upstream(self, mock_port: _MockOntologyPort) -> None:
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d1")
        assert facts == []

    def test_d2_collects_d1_facts(self, mock_port: _MockOntologyPort) -> None:
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d2")
        subjects = {f["subject"] for f in facts}
        assert subjects == {f"{PHASE_NS}{IDEA_ID}-d1"}

    def test_d3_collects_d1_and_d2_facts(self, mock_port: _MockOntologyPort) -> None:
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d3")
        subjects = {f["subject"] for f in facts}
        assert subjects == {
            f"{PHASE_NS}{IDEA_ID}-d1",
            f"{PHASE_NS}{IDEA_ID}-d2",
        }

    def test_d4_collects_d1_through_d3_facts(self, mock_port: _MockOntologyPort) -> None:
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d4")
        subjects = {f["subject"] for f in facts}
        assert subjects == {
            f"{PHASE_NS}{IDEA_ID}-d1",
            f"{PHASE_NS}{IDEA_ID}-d2",
            f"{PHASE_NS}{IDEA_ID}-d3",
        }

    def test_d5_collects_d1_through_d4_facts(self, mock_port: _MockOntologyPort) -> None:
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        subjects = {f["subject"] for f in facts}
        assert subjects == {
            f"{PHASE_NS}{IDEA_ID}-d1",
            f"{PHASE_NS}{IDEA_ID}-d2",
            f"{PHASE_NS}{IDEA_ID}-d3",
            f"{PHASE_NS}{IDEA_ID}-d4",
        }

    def test_d2_upstream_contains_d1_intent_triples(self, mock_port: _MockOntologyPort) -> None:
        """D2's upstream should include D1's preserves- triples."""
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d2")
        predicates = {f["predicate"] for f in facts}
        assert f"{PHASE_NS}preserves-key_capabilities" in predicates
        assert f"{PHASE_NS}preserves-ecosystem_context" in predicates

    def test_d5_upstream_triple_count(self, mock_port: _MockOntologyPort) -> None:
        """D5 upstream should contain all triples from D1-D4 (6+7+7+7 = 27)."""
        facts = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        assert len(facts) == 27


# ===================================================================
# 3. group_upstream_facts — verify grouped dict with typed values
# ===================================================================


class TestGroupUpstreamFacts:
    """Call group_upstream_facts() on collected triples and verify structure."""

    @pytest.fixture(autouse=True)
    def _persist_all_phases(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        pipeline = [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
            ("d4", _make_d4, "d3"),
            ("d5", _make_d5, "d4"),
        ]
        for phase_id, make_fn, pred in pipeline:
            persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )

    def test_d5_grouped_has_correct_phase_keys(self, mock_port: _MockOntologyPort) -> None:
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        grouped = group_upstream_facts(raw)
        assert set(grouped.keys()) == {"d1", "d2", "d3", "d4"}

    def test_d3_grouped_has_d1_and_d2(self, mock_port: _MockOntologyPort) -> None:
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d3")
        grouped = group_upstream_facts(raw)
        assert set(grouped.keys()) == {"d1", "d2"}

    def test_grouped_d1_fields_are_semantic(self, mock_port: _MockOntologyPort) -> None:
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        grouped = group_upstream_facts(raw)
        assert type(grouped["d1"]["key_capabilities"]) is list
        assert grouped["d1"]["ecosystem_context"] == "Core MCP platform"
        assert type(grouped["d1"]["ecosystem_context"]) is str

    def test_grouped_d2_has_jtbd(self, mock_port: _MockOntologyPort) -> None:
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        grouped = group_upstream_facts(raw)
        assert "When I build features" in grouped["d2"]["primary_persona_jtbd"]
        assert type(grouped["d2"]["primary_persona_jtbd"]) is str

    def test_grouped_d3_has_verdict_and_quadrant(self, mock_port: _MockOntologyPort) -> None:
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        grouped = group_upstream_facts(raw)
        assert grouped["d3"]["quadrant"] == "high-value-low-effort"
        assert type(grouped["d3"]["quadrant"]) is str
        assert "P1-High" in grouped["d3"]["verdict"]
        assert type(grouped["d3"]["verdict"]) is str

    def test_grouped_d4_has_blockers_and_root(self, mock_port: _MockOntologyPort) -> None:
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        grouped = group_upstream_facts(raw)
        assert "API endpoint" in grouped["d4"]["blockers"]
        assert type(grouped["d4"]["blockers"]) is str
        assert "API endpoint" in grouped["d4"]["root_blocker"]
        assert type(grouped["d4"]["root_blocker"]) is str

    def test_grouped_matches_full_field_map(self, mock_port: _MockOntologyPort) -> None:
        """Verify the complete field map: D1-D4 grouped with correct typed values."""
        raw = collect_upstream_facts(mock_port, IDEA_ID, DISCOVERY_PHASES, "d5")
        grouped = group_upstream_facts(raw)
        assert grouped == {
            "d1": {
                "key_capabilities": [{"name": "ontology-server"}],
                "ecosystem_context": "Core MCP platform",
                "reuse_opportunities": "Existing discovery pipeline",
            },
            "d2": {
                "personas": [{"name": "Dev", "role": "Engineer", "primary_jtbd": "Automate"}],
                "non_negotiable_needs": ["Fast iteration"],
                "primary_persona_jtbd": (
                    "When I build features, I want automation,"
                    " so I can ship faster"
                ),
            },
            "d3": {
                "quadrant": "high-value-low-effort",
                "strategic_constraints": ["Python 3.11+ only"],
                "verdict": "P1-High | Strong ROI | High confidence",
            },
            "d4": {
                "blockers": "No API endpoint blocks core functionality",
                "root_blocker": "No API endpoint: blocks core functionality",
                "recommended_next_steps": "Build API endpoint first, then auth layer",
            },
        }


# ===================================================================
# 4. traverse_chain — verify D5 walks back through D4, D3, D2, D1
# ===================================================================


class TestTraverseChain:
    """Call traverse_chain() from D5 and verify it walks back through D4-D1."""

    @pytest.fixture(autouse=True)
    def _persist_all_phases(
        self, mock_port: _MockOntologyPort, persister: PhaseFactPersister
    ) -> None:
        pipeline = [
            ("d1", _make_d1, None),
            ("d2", _make_d2, "d1"),
            ("d3", _make_d3, "d2"),
            ("d4", _make_d4, "d3"),
            ("d5", _make_d5, "d4"),
        ]
        for phase_id, make_fn, pred in pipeline:
            persister.persist(
                idea_id=IDEA_ID,
                phase_id=phase_id,
                phase_result=make_fn(),
                predecessor_phase_id=pred,
                shacl_shape_id=None,
            )

    def test_d5_chain_has_5_entries(self, mock_port: _MockOntologyPort) -> None:
        """Chain from D5 includes D5 itself plus D4, D3, D2, D1 = 5 entries."""
        chain = traverse_chain(mock_port, IDEA_ID, "d5")
        assert len(chain) == 5

    def test_d5_chain_order_is_reverse_chronological(self, mock_port: _MockOntologyPort) -> None:
        """Chain order: D5, D4, D3, D2, D1 (most recent first)."""
        chain = traverse_chain(mock_port, IDEA_ID, "d5")
        expected_order = [
            f"{PHASE_NS}{IDEA_ID}-d5",
            f"{PHASE_NS}{IDEA_ID}-d4",
            f"{PHASE_NS}{IDEA_ID}-d3",
            f"{PHASE_NS}{IDEA_ID}-d2",
            f"{PHASE_NS}{IDEA_ID}-d1",
        ]
        actual_order = [entry["subject"] for entry in chain]
        assert actual_order == expected_order

    def test_d5_chain_each_entry_has_facts(self, mock_port: _MockOntologyPort) -> None:
        """Every entry in the chain has a non-empty facts list."""
        chain = traverse_chain(mock_port, IDEA_ID, "d5")
        for entry in chain:
            assert "facts" in entry
            assert len(entry["facts"]) > 0

    def test_d3_chain_has_3_entries(self, mock_port: _MockOntologyPort) -> None:
        """Chain from D3 includes D3, D2, D1 = 3 entries."""
        chain = traverse_chain(mock_port, IDEA_ID, "d3")
        assert len(chain) == 3

    def test_d1_chain_has_1_entry(self, mock_port: _MockOntologyPort) -> None:
        """Chain from D1 includes only D1 (no predecessors)."""
        chain = traverse_chain(mock_port, IDEA_ID, "d1")
        assert len(chain) == 1
        assert chain[0]["subject"] == f"{PHASE_NS}{IDEA_ID}-d1"

    def test_d5_chain_d1_entry_contains_intent_facts(self, mock_port: _MockOntologyPort) -> None:
        """The D1 entry in the D5 chain contains preserves-key_capabilities."""
        chain = traverse_chain(mock_port, IDEA_ID, "d5")
        d1_entry = chain[-1]  # Last in reverse-chronological order
        assert d1_entry["subject"] == f"{PHASE_NS}{IDEA_ID}-d1"
        fact_predicates = {f["predicate"] for f in d1_entry["facts"]}
        assert f"{PHASE_NS}preserves-key_capabilities" in fact_predicates
        assert f"{PHASE_NS}preserves-ecosystem_context" in fact_predicates

    def test_d5_chain_d4_entry_contains_gap_facts(self, mock_port: _MockOntologyPort) -> None:
        """The D4 entry in the D5 chain contains preserves-blockers."""
        chain = traverse_chain(mock_port, IDEA_ID, "d5")
        d4_entry = chain[1]  # Second in reverse-chronological order (D5, D4, ...)
        assert d4_entry["subject"] == f"{PHASE_NS}{IDEA_ID}-d4"
        fact_predicates = {f["predicate"] for f in d4_entry["facts"]}
        assert f"{PHASE_NS}preserves-blockers" in fact_predicates
        assert f"{PHASE_NS}preserves-root_blocker" in fact_predicates
