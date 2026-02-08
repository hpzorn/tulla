"""Tests for parse_output content extraction in research phases R1-R6."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tulla.core.phase import EarlyTermination, PhaseContext
from tulla.phases.research.r1 import R1Phase
from tulla.phases.research.r2 import R2Phase
from tulla.phases.research.r3 import R3Phase
from tulla.phases.research.r4 import R4Phase
from tulla.phases.research.r5 import R5Phase
from tulla.phases.research.r6 import R6Phase


def _ctx(tmp_path: Path) -> PhaseContext:
    import logging

    return PhaseContext(
        idea_id="42",
        work_dir=tmp_path,
        config={},
        budget_remaining_usd=5.0,
        logger=logging.getLogger("test.parse"),
    )


# ---------------------------------------------------------------------------
# R1 parse_output
# ---------------------------------------------------------------------------


R1_MARKDOWN = """\
# R1: Research Question Refinement
**Idea**: 42
**Date**: 2026-01-15
**Mode**: Groundwork Research

## Refined Research Questions

### RQ1: How does SHACL validation perform at scale?
**Origin**: Core architecture question
**Impact**: Determines if we need caching
**Methodology**: Experiment
**Acceptance Criteria**: Sub-second validation for 1000 triples

### RQ2: What existing RDF stores support SPARQL 1.1?
**Origin**: Technology selection
**Impact**: Store choice affects all queries
**Methodology**: Literature Review
**Acceptance Criteria**: Comparison table of 3+ stores

## Research Plan
Start with RQ2 (literature), then RQ1 (experiment).
"""


class TestR1ParseOutput:
    def test_extracts_research_questions_json(self, tmp_path: Path) -> None:
        (tmp_path / "r1-question-refinement.md").write_text(R1_MARKDOWN)
        result = R1Phase().parse_output(_ctx(tmp_path), "")
        rqs = json.loads(result.research_questions)
        assert len(rqs) == 2
        assert rqs[0]["id"] == "RQ1"
        assert rqs[0]["question"] == "How does SHACL validation perform at scale?"
        assert rqs[0]["methodology"] == "Experiment"
        assert rqs[0]["acceptance_criteria"] == "Sub-second validation for 1000 triples"
        assert rqs[1]["methodology"] == "Literature Review"

    def test_count_matches_json_length(self, tmp_path: Path) -> None:
        (tmp_path / "r1-question-refinement.md").write_text(R1_MARKDOWN)
        result = R1Phase().parse_output(_ctx(tmp_path), "")
        assert result.questions_refined == len(json.loads(result.research_questions))

    def test_empty_when_no_rqs(self, tmp_path: Path) -> None:
        (tmp_path / "r1-question-refinement.md").write_text("# R1\nNo questions here.\n")
        result = R1Phase().parse_output(_ctx(tmp_path), "")
        assert result.questions_refined == 0
        assert json.loads(result.research_questions) == []


# ---------------------------------------------------------------------------
# R1 early termination (groundwork + derivative verdict)
# ---------------------------------------------------------------------------


R1_DERIVATIVE_MARKDOWN = """\
# R1: Research Question Refinement
**Idea**: 42
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

All capabilities are derivative or commoditized. No novel research needed.

## Research Plan
N/A — early termination recommended.
"""


class TestR1EarlyTermination:
    def test_derivative_verdict_raises_early_termination(self, tmp_path: Path) -> None:
        """Groundwork mode + Verdict: Derivative → EarlyTermination raised."""
        (tmp_path / "r1-question-refinement.md").write_text(R1_DERIVATIVE_MARKDOWN)
        ctx = _ctx(tmp_path)  # config={} → groundwork mode

        with pytest.raises(EarlyTermination, match="derivative") as exc_info:
            R1Phase().parse_output(ctx, "")

        assert exc_info.value.r1_output is not None
        assert exc_info.value.r1_output.questions_refined == 0

    def test_derivative_verdict_writes_r6_synthesis(self, tmp_path: Path) -> None:
        """Early termination writes r6-research-synthesis.md."""
        (tmp_path / "r1-question-refinement.md").write_text(R1_DERIVATIVE_MARKDOWN)
        ctx = _ctx(tmp_path)

        with pytest.raises(EarlyTermination):
            R1Phase().parse_output(ctx, "")

        r6_file = tmp_path / "r6-research-synthesis.md"
        assert r6_file.exists()
        r6_content = r6_file.read_text()
        assert "Early Termination" in r6_content
        assert "Do not proceed to discovery" in r6_content
        assert "Derivative" in r6_content or "derivative" in r6_content

    def test_derivative_verdict_ignored_in_spike_mode(self, tmp_path: Path) -> None:
        """Spike mode (planning_dir set) does NOT trigger early termination."""
        import logging

        (tmp_path / "r1-question-refinement.md").write_text(R1_DERIVATIVE_MARKDOWN)
        ctx = PhaseContext(
            idea_id="42",
            work_dir=tmp_path,
            config={"planning_dir": "/some/planning/dir"},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.parse"),
        )

        # Should NOT raise — returns R1Output normally
        result = R1Phase().parse_output(ctx, "")
        assert result.questions_refined == 0

    def test_derivative_verdict_ignored_in_discovery_mode(self, tmp_path: Path) -> None:
        """Discovery-fed mode (discovery_dir set) does NOT trigger early termination."""
        import logging

        (tmp_path / "r1-question-refinement.md").write_text(R1_DERIVATIVE_MARKDOWN)
        ctx = PhaseContext(
            idea_id="42",
            work_dir=tmp_path,
            config={"discovery_dir": "/some/discovery/dir"},
            budget_remaining_usd=5.0,
            logger=logging.getLogger("test.parse"),
        )

        result = R1Phase().parse_output(ctx, "")
        assert result.questions_refined == 0


# ---------------------------------------------------------------------------
# R2 parse_output
# ---------------------------------------------------------------------------


R2_MARKDOWN = """\
# R2: Source Identification
**Idea**: 42
**Date**: 2026-01-15

## Sources by Research Question

### RQ1: How does SHACL validation perform at scale?
| Source | Type | Relevance | URL/Path |
|--------|------|-----------|----------|
| SHACL spec | Doc | High | https://w3.org/shacl |
| pySHACL repo | Code | Medium | https://github.com/pyshacl |

### RQ2: What RDF stores support SPARQL 1.1?
| Source | Type | Relevance | URL/Path |
|--------|------|-----------|----------|
| Apache Jena docs | Doc | High | https://jena.apache.org |

## Codebase Patterns Found
Existing ontology-server uses rdflib in-memory store.

## Source Gaps
RQ1 has limited benchmarking data available.
"""


class TestR2ParseOutput:
    def test_extracts_source_map(self, tmp_path: Path) -> None:
        (tmp_path / "r2-source-identification.md").write_text(R2_MARKDOWN)
        result = R2Phase().parse_output(_ctx(tmp_path), "")
        sources = json.loads(result.source_map)
        assert len(sources) == 3
        assert sources[0]["rq"] == "RQ1"
        assert sources[0]["source"] == "SHACL spec"
        assert sources[0]["type"] == "Doc"
        assert sources[2]["rq"] == "RQ2"

    def test_extracts_source_gaps(self, tmp_path: Path) -> None:
        (tmp_path / "r2-source-identification.md").write_text(R2_MARKDOWN)
        result = R2Phase().parse_output(_ctx(tmp_path), "")
        assert "limited benchmarking" in result.source_gaps

    def test_empty_when_no_tables(self, tmp_path: Path) -> None:
        (tmp_path / "r2-source-identification.md").write_text("# R2\nNo sources.\n")
        result = R2Phase().parse_output(_ctx(tmp_path), "")
        assert json.loads(result.source_map) == []
        assert result.source_gaps == ""


# ---------------------------------------------------------------------------
# R3 parse_output
# ---------------------------------------------------------------------------


R3_MARKDOWN = """\
# R3: Research Questions
**Idea**: 42
**Date**: 2026-01-15

## Investigation Results

### RQ1: How does SHACL validation perform at scale?
**Status**: Partially Answered
**Confidence**: Medium
**Answer**: pySHACL handles 1000 triples in ~200ms but degrades with complex shapes
**Evidence**:
- pySHACL benchmarks: 200ms for 1000 simple triples
- Complex shapes add 3x overhead
**Caveats**: Only tested with pySHACL, not other implementations

### RQ2: What RDF stores support SPARQL 1.1?
**Status**: Answered
**Confidence**: High
**Answer**: Apache Jena, Blazegraph, and rdflib all support SPARQL 1.1
**Evidence**:
- Official docs confirm support
**Caveats**: None

## Summary
| RQ | Status | Confidence |
|----|--------|------------|
| RQ1 | Partially Answered | Medium |
| RQ2 | Answered | High |

## Remaining Unknowns
Complex shape performance needs experimentation with real ontology.
"""


class TestR3ParseOutput:
    def test_extracts_rq_answers(self, tmp_path: Path) -> None:
        (tmp_path / "r3-research-questions.md").write_text(R3_MARKDOWN)
        result = R3Phase().parse_output(_ctx(tmp_path), "")
        answers = json.loads(result.rq_answers)
        assert len(answers) == 2
        assert answers[0]["id"] == "RQ1"
        assert answers[0]["status"] == "Partially Answered"
        assert answers[0]["confidence"] == "Medium"
        assert "pySHACL" in answers[0]["answer"]
        assert answers[1]["status"] == "Answered"

    def test_extracts_remaining_unknowns(self, tmp_path: Path) -> None:
        (tmp_path / "r3-research-questions.md").write_text(R3_MARKDOWN)
        result = R3Phase().parse_output(_ctx(tmp_path), "")
        assert "Complex shape performance" in result.remaining_unknowns


# ---------------------------------------------------------------------------
# R4 parse_output
# ---------------------------------------------------------------------------


R4_MARKDOWN = """\
# R4: Literature Review
**Idea**: 42
**Date**: 2026-01-15

## Reviews by Research Question

### RQ1: How does SHACL validation perform at scale?
**Sources Reviewed**: 4

#### Key Findings
1. pySHACL is the most mature Python implementation
2. Validation scales linearly with triple count for simple shapes

#### Approaches Compared
| Approach | Pros | Cons | Source |
|----------|------|------|--------|
| pySHACL | Mature, Python native | Slower on complex shapes | GitHub |
| SHACL.js | Fast | JS only | npm |

#### Recommendation
Use pySHACL with shape caching for production workloads.

### RQ2: What RDF stores support SPARQL 1.1?
**Sources Reviewed**: 3

#### Key Findings
1. All three major stores support SPARQL 1.1 fully

#### Recommendation
Use rdflib for in-process, Apache Jena for production scale.

## Cross-Cutting Themes
Performance vs simplicity trade-off across all RQs.

## Open Items for Experimentation
Benchmark pySHACL with the actual phase ontology.
"""


class TestR4ParseOutput:
    def test_extracts_key_findings(self, tmp_path: Path) -> None:
        (tmp_path / "r4-literature-review.md").write_text(R4_MARKDOWN)
        result = R4Phase().parse_output(_ctx(tmp_path), "")
        findings = json.loads(result.key_findings)
        assert len(findings) == 2
        assert findings[0]["rq"] == "RQ1"
        assert "pySHACL" in findings[0]["recommendation"]
        assert "pySHACL is the most mature" in findings[0]["finding_summary"]
        assert findings[1]["rq"] == "RQ2"

    def test_count_fields_still_work(self, tmp_path: Path) -> None:
        (tmp_path / "r4-literature-review.md").write_text(R4_MARKDOWN)
        result = R4Phase().parse_output(_ctx(tmp_path), "")
        assert result.rqs_addressed == 2
        assert result.papers_reviewed == 7  # 4 + 3


# ---------------------------------------------------------------------------
# R5 parse_output
# ---------------------------------------------------------------------------


R5_MARKDOWN = """\
# R5: Research Findings
**Idea**: 42
**Date**: 2026-01-15
**Permission Mode**: acceptEdits

## Experiments

### Experiment 1: pySHACL Benchmark
**RQ**: RQ1
**Hypothesis**: pySHACL validates 1000 triples in under 500ms
**Setup**: Generated 1000 triples, ran pySHACL validation
**Result**: PASS
**Retries**: 0 of 2
**Finding**: 180ms for 1000 triples with the phase ontology shapes
**Artefacts**: benchmark.py, results.json

### Experiment 2: Complex Shape Stress Test
**RQ**: RQ1
**Hypothesis**: Complex shapes stay under 1s for 1000 triples
**Setup**: Used full phase-ontology.ttl shapes
**Result**: FAIL
**Retries**: 2 of 2
**Finding**: 1.8s for complex shapes — needs shape caching
**Artefacts**: stress_test.py

## Summary
| Experiment | RQ | Result | Retries |
|------------|-----|--------|---------|
| Exp 1 | RQ1 | PASS | 0 |
| Exp 2 | RQ1 | FAIL | 2 |

## Implications for Implementation
Shape caching is required for production use. Simple validation is fast enough.
"""


class TestR5ParseOutput:
    def test_extracts_experiment_results(self, tmp_path: Path) -> None:
        (tmp_path / "r5-research-findings.md").write_text(R5_MARKDOWN)
        result = R5Phase().parse_output(_ctx(tmp_path), "")
        exps = json.loads(result.experiment_results)
        assert len(exps) == 2
        assert exps[0]["title"] == "pySHACL Benchmark"
        assert exps[0]["rq"] == "RQ1"
        assert exps[0]["result"] == "PASS"
        assert "180ms" in exps[0]["finding"]
        assert exps[1]["result"] == "FAIL"

    def test_counts_match(self, tmp_path: Path) -> None:
        (tmp_path / "r5-research-findings.md").write_text(R5_MARKDOWN)
        result = R5Phase().parse_output(_ctx(tmp_path), "")
        assert result.experiments_run == 2
        assert result.experiments_passed == 1

    def test_extracts_impl_implications(self, tmp_path: Path) -> None:
        (tmp_path / "r5-research-findings.md").write_text(R5_MARKDOWN)
        result = R5Phase().parse_output(_ctx(tmp_path), "")
        assert "Shape caching" in result.impl_implications


# ---------------------------------------------------------------------------
# R6 parse_output
# ---------------------------------------------------------------------------


R6_MARKDOWN = """\
# R6: Research Synthesis
**Idea**: 42
**Date**: 2026-01-15

## Executive Summary
pySHACL is viable but needs shape caching. rdflib is sufficient for MVP.

## Findings by Research Question

### RQ1: How does SHACL validation perform at scale?
**Answer**: Viable with caching; 180ms base, 1.8s for complex shapes without cache
**Confidence**: High
**Evidence**: Literature: 4 sources, Experiments: 2
**Implication**: Implement shape cache before production deployment

### RQ2: What RDF stores support SPARQL 1.1?
**Answer**: rdflib, Apache Jena, and Blazegraph all fully support SPARQL 1.1
**Confidence**: High
**Evidence**: Literature: 3 sources, Experiments: 0
**Implication**: Continue with rdflib for in-process use

## Recommendations
1. Use pySHACL with an LRU shape cache
2. Stay with rdflib unless scale demands Jena

## Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shape complexity growth | Medium | High | Monitor validation time, add cache |
| rdflib memory limits | Low | Medium | Profile memory, migrate to Jena if needed |

## Conclusion
Proceed with implementation. All research questions answered with high confidence.
"""


class TestR6ParseOutput:
    def test_extracts_synthesised_answers(self, tmp_path: Path) -> None:
        (tmp_path / "r6-research-synthesis.md").write_text(R6_MARKDOWN)
        result = R6Phase().parse_output(_ctx(tmp_path), "")
        synth = json.loads(result.synthesised_answers)
        assert len(synth) == 2
        assert synth[0]["rq"] == "RQ1"
        assert "caching" in synth[0]["answer"]
        assert synth[0]["confidence"] == "High"
        assert "shape cache" in synth[0]["implication"]

    def test_extracts_risks(self, tmp_path: Path) -> None:
        (tmp_path / "r6-research-synthesis.md").write_text(R6_MARKDOWN)
        result = R6Phase().parse_output(_ctx(tmp_path), "")
        risks = json.loads(result.risks)
        assert len(risks) == 2
        assert risks[0]["Risk"] == "Shape complexity growth"
        assert risks[0]["Likelihood"] == "Medium"

    def test_recommendation_extracted(self, tmp_path: Path) -> None:
        (tmp_path / "r6-research-synthesis.md").write_text(R6_MARKDOWN)
        result = R6Phase().parse_output(_ctx(tmp_path), "")
        assert result.recommendation == "proceed"

    def test_findings_count(self, tmp_path: Path) -> None:
        (tmp_path / "r6-research-synthesis.md").write_text(R6_MARKDOWN)
        result = R6Phase().parse_output(_ctx(tmp_path), "")
        assert result.findings_count == 2
