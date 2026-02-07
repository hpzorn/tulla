"""Integration tests for the research pipeline (R1-R6).

Tests end-to-end pipeline execution in three modes (Groundwork, Discovery-Fed,
Spike), early termination, shape registry wiring, and SHACL validation firing.

Uses existing ``mock_claude`` / ``tmp_work_dir`` fixtures from
``tests/conftest.py`` with a ``response_fn`` that writes phase-appropriate
markdown files so that each phase's ``parse_output`` succeeds.

Requirement: prd:req-58-7-1
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tulla.adapters.claude_mock import MockClaudeAdapter
from tulla.config import TullaConfig
from tulla.core.checkpoint import CheckpointStore
from tulla.core.phase import PhaseStatus
from tulla.ontology.phase_shapes import PHASE_SHAPES
from tulla.phases.research.pipeline import research_pipeline
from tulla.ports.claude import ClaudeRequest, ClaudeResult
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Markdown fixtures — one per phase, minimal but parseable
# ---------------------------------------------------------------------------

R1_MD = """\
# R1: Research Question Refinement
**Idea**: {idea_id}
**Date**: 2026-02-07
**Mode**: Groundwork Research

## Refined Research Questions

### RQ1: How does SHACL validation perform at scale?
**Origin**: Core architecture question
**Methodology**: Experiment
**Acceptance Criteria**: Sub-second validation for 1000 triples

### RQ2: What RDF stores support SPARQL 1.1?
**Origin**: Technology selection
**Methodology**: Literature Review
**Acceptance Criteria**: Comparison table of 3+ stores

## Research Plan
Start with RQ2 then RQ1.
"""

R2_MD = """\
# R2: Source Identification
**Idea**: {idea_id}
**Date**: 2026-02-07

## Sources by Research Question

### RQ1: SHACL validation
| Source | Type | Relevance | URL/Path |
|--------|------|-----------|----------|
| SHACL spec | Doc | High | https://w3.org/shacl |

### RQ2: RDF stores
| Source | Type | Relevance | URL/Path |
|--------|------|-----------|----------|
| Jena docs | Doc | High | https://jena.apache.org |

## Source Gaps
RQ1 has limited benchmarks.
"""

R3_MD = """\
# R3: Research Questions
**Idea**: {idea_id}
**Date**: 2026-02-07

## Investigation Results

### RQ1: SHACL validation
**Status**: Partially Answered
**Confidence**: Medium
**Answer**: pySHACL handles 1000 triples in ~200ms

### RQ2: RDF stores
**Status**: Answered
**Confidence**: High
**Answer**: Jena, Blazegraph, rdflib all support SPARQL 1.1

## Remaining Unknowns
Complex shape performance needs experimentation.
"""

R4_MD = """\
# R4: Literature Review
**Idea**: {idea_id}
**Date**: 2026-02-07

## Reviews by Research Question

### RQ1: SHACL validation
**Sources Reviewed**: 2

#### Key Findings
1. pySHACL is the most mature Python SHACL library

#### Recommendation
Use pySHACL with shape caching.

### RQ2: RDF stores
**Sources Reviewed**: 1

#### Key Findings
1. All three stores support SPARQL 1.1

#### Recommendation
Use rdflib for in-process use.

## Cross-Cutting Themes
Performance vs simplicity trade-off.
"""

R5_MD = """\
# R5: Research Findings
**Idea**: {idea_id}
**Date**: 2026-02-07
**Permission Mode**: acceptEdits

## Experiments

### Experiment 1: pySHACL Benchmark
**RQ**: RQ1
**Hypothesis**: pySHACL validates 1000 triples in under 500ms
**Setup**: Generated 1000 triples
**Result**: PASS
**Retries**: 0 of 2
**Finding**: 180ms for 1000 triples
**Artefacts**: benchmark.py

## Summary
| Experiment | RQ | Result | Retries |
|------------|-----|--------|---------|
| Exp 1 | RQ1 | PASS | 0 |

## Implications for Implementation
Simple validation is fast enough.
"""

R6_MD = """\
# R6: Research Synthesis
**Idea**: {idea_id}
**Date**: 2026-02-07

## Executive Summary
pySHACL is viable; rdflib is sufficient for MVP.

## Findings by Research Question

### RQ1: SHACL validation
**Answer**: Viable with caching
**Confidence**: High
**Evidence**: Literature: 2, Experiments: 1
**Implication**: Implement shape cache

### RQ2: RDF stores
**Answer**: rdflib, Jena, Blazegraph all work
**Confidence**: High
**Evidence**: Literature: 1
**Implication**: Continue with rdflib

## Recommendations
1. Use pySHACL with LRU shape cache

## Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shape growth | Medium | High | Monitor and cache |

## Conclusion
Proceed with implementation.
"""

R1_DERIVATIVE_MD = """\
# R1: Research Question Refinement
**Idea**: {idea_id}
**Date**: 2026-02-07
**Mode**: Groundwork Research

## Capability Decomposition

| # | Capability | Description |
|---|------------|-------------|
| 1 | CLI wrapper | Thin shell around existing tool |
| 2 | Config reader | Reads YAML config files |

## Per-Capability Novelty Assessment

| # | Capability | Novelty | Source / Evidence |
|---|------------|---------|-------------------|
| 1 | CLI wrapper | Derivative | Click, Typer |
| 2 | Config reader | Commoditized | PyYAML |

## Novelty Assessment

**Verdict**: Derivative

All capabilities are derivative or commoditized.

## Research Plan
N/A — early termination recommended.
"""


# ---------------------------------------------------------------------------
# Phase-file mapping: phase_id -> (output filename, markdown template)
# ---------------------------------------------------------------------------

_PHASE_FILES: dict[str, tuple[str, str]] = {
    "r1": ("r1-question-refinement.md", R1_MD),
    "r2": ("r2-source-identification.md", R2_MD),
    "r3": ("r3-research-questions.md", R3_MD),
    "r4": ("r4-literature-review.md", R4_MD),
    "r5": ("r5-research-findings.md", R5_MD),
    "r6": ("r6-research-synthesis.md", R6_MD),
}


def _make_response_fn(
    work_dir: Path,
    idea_id: str,
    phase_files: dict[str, tuple[str, str]] | None = None,
):
    """Create a response_fn that writes phase-appropriate markdown files.

    The function inspects the prompt to determine the current phase and
    writes the corresponding markdown file to *work_dir* before returning
    a successful :class:`ClaudeResult`.
    """
    files = phase_files or _PHASE_FILES

    # Track invocation order to map calls to phases
    phase_order = list(files.keys())
    call_count = [0]

    def _fn(request: ClaudeRequest) -> ClaudeResult:
        # Determine which phase by scanning the prompt for phase markers
        phase_id = None
        for pid in files:
            marker = f"Phase {pid.upper()}:"
            if marker in request.prompt:
                phase_id = pid
                break

        # Fallback: use call order
        if phase_id is None and call_count[0] < len(phase_order):
            phase_id = phase_order[call_count[0]]

        call_count[0] += 1

        if phase_id is not None and phase_id in files:
            filename, template = files[phase_id]
            content = template.format(idea_id=idea_id)
            (work_dir / filename).write_text(content, encoding="utf-8")

        return ClaudeResult(exit_code=0, output_text="ok", cost_usd=0.01)

    return _fn


# ---------------------------------------------------------------------------
# Mock ontology port
# ---------------------------------------------------------------------------


class _MockOntologyPort(OntologyPort):
    """Concrete mock that tracks calls for assertion."""

    def __init__(self) -> None:
        self.add_triple_calls: list[tuple[str, str, str]] = []
        self.remove_calls: list[str] = []
        self.sparql_calls: list[str] = []
        self.validate_calls: list[tuple[str, str]] = []

    def query_ideas(self, **kw: Any) -> dict[str, Any]:
        return {"ideas": []}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def store_fact(self, subject: str, predicate: str, object: str, **kw: Any) -> dict[str, Any]:
        return {"stored": True}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def recall_facts(self, **kw: Any) -> dict[str, Any]:
        return {"facts": []}

    def sparql_query(self, query: str, *, validate: bool = True) -> dict[str, Any]:
        self.sparql_calls.append(query)
        return {"results": []}

    def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def set_lifecycle(self, idea_id: str, new_state: str, *, reason: str = "") -> dict[str, Any]:
        return {}

    def add_triple(
        self, subject: str, predicate: str, object: str, *, is_literal: bool = False, ontology: str | None = None,
    ) -> dict[str, Any]:
        self.add_triple_calls.append((subject, predicate, object))
        return {"status": "added"}

    def remove_triples_by_subject(self, subject: str, *, ontology: str | None = None) -> int:
        self.remove_calls.append(subject)
        return 0

    def validate_instance(
        self, instance_uri: str, shape_uri: str, *, ontology: str | None = None,
    ) -> dict[str, Any]:
        self.validate_calls.append((instance_uri, shape_uri))
        return {"conforms": True, "violations": []}


# ---------------------------------------------------------------------------
# Helper: build a default TullaConfig for tests
# ---------------------------------------------------------------------------


def _test_config() -> TullaConfig:
    return TullaConfig(
        ontology_server_url="http://localhost:9999",
        research={"budget_usd": 10.0, "max_retries": 1},
    )


# ===================================================================
# Test 1: Groundwork end-to-end
# ===================================================================


class TestGroundworkEndToEnd:
    """Groundwork mode: no planning_dir or discovery_dir.

    All 6 phases run to completion with SUCCESS status and checkpoint
    files are written for each phase.
    """

    def test_all_six_phases_succeed(self, tmp_work_dir: Path) -> None:
        idea_id = "test-42"
        mock = MockClaudeAdapter(
            response_fn=_make_response_fn(tmp_work_dir, idea_id),
        )
        config = _test_config()

        pipeline = research_pipeline(
            claude_port=mock,
            work_dir=tmp_work_dir,
            idea_id=idea_id,
            config=config,
            planning_dir="",
            discovery_dir="",
        )
        # Replace ontology_port with our mock so persister is inactive
        # (avoids needing a real ontology server)
        pipeline._config["ontology_port"] = None
        pipeline._persister = None

        result = pipeline.run()

        # All 6 phase results present and SUCCESS
        assert len(result.phase_results) == 6
        for phase_id, pr in result.phase_results:
            assert pr.status == PhaseStatus.SUCCESS, (
                f"Phase {phase_id} failed: {pr.error}"
            )

        # Checkpoint files exist for all phases
        store = CheckpointStore(tmp_work_dir)
        for phase_id in ("r1", "r2", "r3", "r4", "r5", "r6"):
            assert store.exists(phase_id), f"Missing checkpoint for {phase_id}"


# ===================================================================
# Test 2: Discovery-fed end-to-end
# ===================================================================


class TestDiscoveryFedEndToEnd:
    """Discovery-fed mode: discovery_dir is set, R1 prompt references D5 brief."""

    def test_r1_prompt_references_d5_brief(self, tmp_work_dir: Path) -> None:
        idea_id = "test-43"
        discovery_dir = str(tmp_work_dir / "discovery")
        (tmp_work_dir / "discovery").mkdir()
        (tmp_work_dir / "discovery" / "d5-research-brief.md").write_text(
            "# D5 Research Brief\nRQ: How to improve caching?\n",
            encoding="utf-8",
        )

        mock = MockClaudeAdapter(
            response_fn=_make_response_fn(tmp_work_dir, idea_id),
        )
        config = _test_config()

        pipeline = research_pipeline(
            claude_port=mock,
            work_dir=tmp_work_dir,
            idea_id=idea_id,
            config=config,
            planning_dir="",
            discovery_dir=discovery_dir,
        )
        pipeline._config["ontology_port"] = None
        pipeline._persister = None

        pipeline.run()

        # Inspect R1 prompt (first call to mock)
        assert len(mock.calls) >= 1
        r1_prompt = mock.calls[0].prompt
        assert "d5-research-brief.md" in r1_prompt
        assert "Discovery-Fed" in r1_prompt


# ===================================================================
# Test 3: Spike end-to-end
# ===================================================================


class TestSpikeEndToEnd:
    """Spike mode: planning_dir is set, R1 prompt references P5 requests."""

    def test_r1_prompt_references_p5_requests(self, tmp_work_dir: Path) -> None:
        idea_id = "test-44"
        planning_dir = str(tmp_work_dir / "planning")
        (tmp_work_dir / "planning").mkdir()
        (tmp_work_dir / "planning" / "p5-research-requests.md").write_text(
            "# P5 Research Requests\nRR1: Investigate caching strategy\n",
            encoding="utf-8",
        )

        mock = MockClaudeAdapter(
            response_fn=_make_response_fn(tmp_work_dir, idea_id),
        )
        config = _test_config()

        pipeline = research_pipeline(
            claude_port=mock,
            work_dir=tmp_work_dir,
            idea_id=idea_id,
            config=config,
            planning_dir=planning_dir,
            discovery_dir="",
        )
        pipeline._config["ontology_port"] = None
        pipeline._persister = None

        pipeline.run()

        assert len(mock.calls) >= 1
        r1_prompt = mock.calls[0].prompt
        assert "p5-research-requests.md" in r1_prompt
        assert "Targeted Spike" in r1_prompt


# ===================================================================
# Test 4: Groundwork early termination
# ===================================================================


class TestGroundworkEarlyTermination:
    """Groundwork + derivative verdict: only R1 runs, early_terminate metadata set."""

    def test_derivative_verdict_stops_pipeline(self, tmp_work_dir: Path) -> None:
        idea_id = "test-45"

        # response_fn that writes derivative R1 output
        def _derivative_fn(request: ClaudeRequest) -> ClaudeResult:
            content = R1_DERIVATIVE_MD.format(idea_id=idea_id)
            (tmp_work_dir / "r1-question-refinement.md").write_text(
                content, encoding="utf-8",
            )
            return ClaudeResult(exit_code=0, output_text="ok", cost_usd=0.01)

        mock = MockClaudeAdapter(response_fn=_derivative_fn)
        config = _test_config()

        pipeline = research_pipeline(
            claude_port=mock,
            work_dir=tmp_work_dir,
            idea_id=idea_id,
            config=config,
            planning_dir="",
            discovery_dir="",
        )
        pipeline._config["ontology_port"] = None
        pipeline._persister = None

        result = pipeline.run()

        # Only 1 phase result (R1), pipeline stopped due to early termination
        assert len(result.phase_results) == 1
        r1_id, r1_result = result.phase_results[0]
        assert r1_id == "r1"
        assert r1_result.metadata.get("early_terminate") is True

        # R6 synthesis file created by early termination handler
        r6_file = tmp_work_dir / "r6-research-synthesis.md"
        assert r6_file.exists()
        assert "Early Termination" in r6_file.read_text()


# ===================================================================
# Test 5: Shape registry wired
# ===================================================================


class TestShapeRegistryWired:
    """research_pipeline() config contains shape_registry with all R-phase entries."""

    def test_shape_registry_contains_r_phases(self, tmp_work_dir: Path) -> None:
        config = _test_config()
        mock = MockClaudeAdapter()

        pipeline = research_pipeline(
            claude_port=mock,
            work_dir=tmp_work_dir,
            idea_id="test-46",
            config=config,
        )

        shape_registry = pipeline._config.get("shape_registry", {})

        # All 6 R-phase entries must be present
        for phase_id in ("r1", "r2", "r3", "r4", "r5", "r6"):
            assert phase_id in shape_registry, (
                f"Missing shape_registry entry for {phase_id}"
            )
            assert shape_registry[phase_id] == PHASE_SHAPES[phase_id]


# ===================================================================
# Test 6: SHACL validation fires
# ===================================================================


class TestShaclValidationFires:
    """Pipeline with ontology_port calls validate_instance with correct shape URIs."""

    def test_validate_instance_called_with_shape_uris(self, tmp_work_dir: Path) -> None:
        idea_id = "test-47"
        ontology = _MockOntologyPort()

        mock = MockClaudeAdapter(
            response_fn=_make_response_fn(tmp_work_dir, idea_id),
        )
        config = _test_config()

        pipeline = research_pipeline(
            claude_port=mock,
            work_dir=tmp_work_dir,
            idea_id=idea_id,
            config=config,
            planning_dir="",
            discovery_dir="",
        )
        # Wire in our mock ontology port so persister is active
        pipeline._config["ontology_port"] = ontology
        # Re-create persister now that ontology_port is a real OntologyPort
        from tulla.core.phase_facts import PhaseFactPersister
        pipeline._persister = PhaseFactPersister(ontology)

        result = pipeline.run()

        # Pipeline should succeed (validate_instance returns conforms=True)
        assert result.final_status == PhaseStatus.SUCCESS

        # validate_instance must have been called for each successful phase
        # with the correct shape URIs from PHASE_SHAPES
        validated_shapes = {shape for _, shape in ontology.validate_calls}
        for phase_id in ("r1", "r2", "r3", "r4", "r5", "r6"):
            expected_shape = PHASE_SHAPES[phase_id]
            assert expected_shape in validated_shapes, (
                f"validate_instance not called with shape {expected_shape} "
                f"for phase {phase_id}"
            )
