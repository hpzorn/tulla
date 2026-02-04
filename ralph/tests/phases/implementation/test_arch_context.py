"""Tests for architecture context & verification lessons enrichment.

Covers changes to:
- models.py (FindOutput new fields)
- find.py (architecture refs, load_lessons)
- implement.py (prompt enrichment)
- verify.py (architecture compliance, extract_lesson)
- loop.py (orchestration, lesson storage)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from tulla.phases.implementation.find import FindPhase
from tulla.phases.implementation.implement import ImplementPhase
from tulla.phases.implementation.models import FindOutput, ImplementOutput, VerifyOutput
from tulla.phases.implementation.verify import VerifyPhase
from tulla.ports.ontology import OntologyPort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubOntology(OntologyPort):
    """Minimal ontology stub returning pre-configured fact lists."""

    def __init__(
        self,
        facts_by_key: dict[str, list[dict[str, str]]] | None = None,
        sparql_results: dict[str, dict[str, Any]] | None = None,
    ):
        self._facts = facts_by_key or {}
        self._sparql_results = sparql_results or {}
        self.store_calls: list[dict[str, Any]] = []

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

    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        self.store_calls.append(
            {"subject": subject, "predicate": predicate, "object": object, "context": context}
        )
        return {"status": "ok"}

    # -- stubs for abstract methods not used in these tests --
    def query_ideas(self, **kw: Any) -> dict[str, Any]:
        return {}

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return {}

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return {}

    def sparql_query(self, query: str, **kw: Any) -> dict[str, Any]:
        for substring, result in self._sparql_results.items():
            if substring in query:
                return result
        return {}

    def update_idea(self, idea_id: str, **kw: Any) -> dict[str, Any]:
        return {}

    def set_lifecycle(self, idea_id: str, new_state: str, **kw: Any) -> dict[str, Any]:
        return {}

    def forget_by_context(self, context: str) -> int:
        return 0

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return {}

    def add_triple(self, subject: str, predicate: str, object: str, *, is_literal: bool = False, ontology: str | None = None) -> dict[str, Any]:
        return {"status": "added"}

    def remove_triples_by_subject(self, subject: str, *, ontology: str | None = None) -> int:
        return 0


def _make_requirement(**overrides: Any) -> FindOutput:
    defaults = dict(
        requirement_id="prd:req-42-1-1",
        title="Test requirement",
        description="Do the thing",
        files=["src/foo.py"],
        action="modify",
        verification="Run tests",
    )
    defaults.update(overrides)
    return FindOutput(**defaults)


SAMPLE_ARCH_CONTEXT: dict[str, Any] = {
    "quality_goals": ["Testability: high coverage needed"],
    "design_principles": [
        "Separation of Concerns: each module independent",
        "KISS: prefer simple solutions",
    ],
    "adrs": {
        "arch:adr-42-1": "Use Template Method: common phase structure",
        "arch:adr-42-2": "Use MCP for all ontology access",
    },
}


# ===================================================================
# FindOutput new fields
# ===================================================================


class TestFindOutputFields:
    """FindOutput.related_adrs and quality_focus fields."""

    def test_defaults_empty(self) -> None:
        out = FindOutput()
        assert out.related_adrs == []
        assert out.quality_focus == ""

    def test_can_set_values(self) -> None:
        out = FindOutput(
            related_adrs=["arch:adr-42-1", "arch:adr-42-2"],
            quality_focus="Testability",
        )
        assert out.related_adrs == ["arch:adr-42-1", "arch:adr-42-2"]
        assert out.quality_focus == "Testability"


# ===================================================================
# FindPhase._load_requirement collects architecture refs
# ===================================================================


class TestLoadRequirementArchRefs:
    """FindPhase._load_requirement() collects prd:relatedADR and prd:qualityFocus."""

    def test_collects_related_adrs(self) -> None:
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "My Task"},
                {"predicate": "prd:description", "object": "Do stuff"},
                {"predicate": "prd:files", "object": "src/a.py"},
                {"predicate": "prd:action", "object": "modify"},
                {"predicate": "prd:verification", "object": "pytest"},
                {"predicate": "prd:relatedADR", "object": "arch:adr-42-1"},
                {"predicate": "prd:relatedADR", "object": "arch:adr-42-2"},
                {"predicate": "prd:qualityFocus", "object": "Testability"},
            ],
        })
        phase = FindPhase()
        result = phase._load_requirement(ontology, "prd:req-42-1-1", "prd-idea-42")

        assert result.related_adrs == ["arch:adr-42-1", "arch:adr-42-2"]
        assert result.quality_focus == "Testability"

    def test_empty_when_no_arch_refs(self) -> None:
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-1-1": [
                {"predicate": "prd:title", "object": "Plain Task"},
                {"predicate": "prd:description", "object": "No arch refs"},
                {"predicate": "prd:files", "object": "src/b.py"},
                {"predicate": "prd:action", "object": "create"},
                {"predicate": "prd:verification", "object": "exists"},
            ],
        })
        phase = FindPhase()
        result = phase._load_requirement(ontology, "prd:req-42-1-1", "prd-idea-42")

        assert result.related_adrs == []
        assert result.quality_focus == ""


# ===================================================================
# FindPhase.load_lessons
# ===================================================================


class TestLoadLessons:
    """FindPhase.load_lessons() retrieves lesson facts."""

    def test_returns_lesson_strings(self) -> None:
        ontology = StubOntology({
            "context=lesson-idea-42|predicate=lesson:text": [
                {"subject": "lesson:42", "object": "req-42-1-1: Fixed after 1 retry. Issue: missing import"},
                {"subject": "lesson:42", "object": "req-42-1-2: Failed. Issue: wrong return type"},
            ],
        })
        phase = FindPhase()
        lessons = phase.load_lessons(ontology, "lesson-idea-42")
        assert len(lessons) == 2
        assert "missing import" in lessons[0]

    def test_empty_when_no_lessons(self) -> None:
        ontology = StubOntology()
        phase = FindPhase()
        assert phase.load_lessons(ontology, "lesson-idea-99") == []

    def test_filters_empty_objects(self) -> None:
        ontology = StubOntology({
            "context=lesson-idea-42|predicate=lesson:text": [
                {"subject": "lesson:42", "object": "a real lesson"},
                {"subject": "lesson:42", "object": ""},
            ],
        })
        phase = FindPhase()
        lessons = phase.load_lessons(ontology, "lesson-idea-42")
        assert lessons == ["a real lesson"]


# ===================================================================
# ImplementPhase._build_prompt — architecture context
# ===================================================================


class TestImplementPromptArchContext:
    """ImplementPhase._build_prompt() injects architecture context."""

    def test_no_arch_section_when_none(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        prompt = phase._build_prompt(req, "")
        assert "## Architecture Context" not in prompt

    def test_includes_arch_section_with_context(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement(
            related_adrs=["arch:adr-42-1"],
            quality_focus="Testability",
        )
        prompt = phase._build_prompt(req, "", SAMPLE_ARCH_CONTEXT)

        assert "## Architecture Context" in prompt
        assert "Testability" in prompt
        assert "arch:adr-42-1" in prompt
        assert "Use Template Method" in prompt
        assert "Separation of Concerns" in prompt
        assert "Respect these architecture decisions" in prompt

    def test_no_adr_subsection_when_no_related_adrs(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()  # no related_adrs
        prompt = phase._build_prompt(req, "", SAMPLE_ARCH_CONTEXT)

        assert "## Architecture Context" in prompt
        assert "Relevant Architecture Decisions" not in prompt
        # But design principles are always included
        assert "Separation of Concerns" in prompt

    def test_design_principles_always_included(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        prompt = phase._build_prompt(req, "", SAMPLE_ARCH_CONTEXT)
        assert "KISS" in prompt


# ===================================================================
# ImplementPhase._build_prompt — lessons
# ===================================================================


class TestImplementPromptLessons:
    """ImplementPhase._build_prompt() injects lessons."""

    def test_no_lesson_section_when_none(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        prompt = phase._build_prompt(req, "")
        assert "## Lessons from Previous Requirements" not in prompt

    def test_no_lesson_section_when_empty(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        prompt = phase._build_prompt(req, "", lessons=[])
        assert "## Lessons from Previous Requirements" not in prompt

    def test_includes_lessons(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        lessons = ["req-42-1-1: Fixed after 1 retry. Issue: missing import"]
        prompt = phase._build_prompt(req, "", lessons=lessons)

        assert "## Lessons from Previous Requirements" in prompt
        assert "missing import" in prompt
        assert "Avoid repeating these mistakes." in prompt

    def test_lessons_before_feedback(self) -> None:
        phase = ImplementPhase()
        req = _make_requirement()
        lessons = ["lesson one"]
        prompt = phase._build_prompt(req, "fix the bug", lessons=lessons)

        lessons_pos = prompt.index("## Lessons from Previous Requirements")
        feedback_pos = prompt.index("## Previous Attempt Feedback")
        assert lessons_pos < feedback_pos


# ===================================================================
# VerifyPhase._build_prompt — architecture compliance
# ===================================================================


class TestVerifyPromptArchCompliance:
    """VerifyPhase._build_prompt() adds Architecture Compliance section."""

    def test_no_compliance_when_none(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement()
        impl = ImplementOutput(requirement_id="prd:req-42-1-1", files_changed=["src/foo.py"])
        prompt = phase._build_prompt(req, impl)
        assert "## Architecture Compliance" not in prompt

    def test_includes_compliance_with_context(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement(related_adrs=["arch:adr-42-1"])
        impl = ImplementOutput(requirement_id="prd:req-42-1-1", files_changed=["src/foo.py"])
        prompt = phase._build_prompt(req, impl, SAMPLE_ARCH_CONTEXT)

        assert "## Architecture Compliance" in prompt
        assert "arch:adr-42-1" in prompt
        assert "Use Template Method" in prompt
        assert "Design Principles" in prompt

    def test_step_5_added_when_arch_context(self) -> None:
        phase = VerifyPhase()
        req = _make_requirement()
        impl = ImplementOutput(requirement_id="prd:req-42-1-1", files_changed=["src/foo.py"])
        prompt = phase._build_prompt(req, impl, SAMPLE_ARCH_CONTEXT)

        assert "5. Check that the implementation respects the architecture" in prompt


# ===================================================================
# VerifyPhase.extract_lesson
# ===================================================================


class TestExtractLesson:
    """VerifyPhase.extract_lesson() returns lesson strings."""

    def test_pass_first_try_returns_none(self) -> None:
        vo = VerifyOutput(requirement_id="prd:req-42-1-1", passed=True, feedback="")
        assert VerifyPhase.extract_lesson(vo, retries_used=0) is None

    def test_pass_after_retry(self) -> None:
        vo = VerifyOutput(
            requirement_id="prd:req-42-1-1",
            passed=True,
            feedback="missing import statement\nextra details",
        )
        lesson = VerifyPhase.extract_lesson(vo, retries_used=1)
        assert lesson is not None
        assert "Fixed after 1 retry" in lesson
        assert "missing import statement" in lesson

    def test_pass_after_multiple_retries(self) -> None:
        vo = VerifyOutput(
            requirement_id="prd:req-42-1-1",
            passed=True,
            feedback="wrong return type",
        )
        lesson = VerifyPhase.extract_lesson(vo, retries_used=2)
        assert lesson is not None
        assert "2 retries" in lesson

    def test_failed(self) -> None:
        vo = VerifyOutput(
            requirement_id="prd:req-42-1-1",
            passed=False,
            feedback="tests still failing\ndetails here",
        )
        lesson = VerifyPhase.extract_lesson(vo, retries_used=2)
        assert lesson is not None
        assert "Failed" in lesson
        assert "tests still failing" in lesson

    def test_failed_empty_feedback(self) -> None:
        vo = VerifyOutput(requirement_id="prd:req-42-1-1", passed=False, feedback="")
        lesson = VerifyPhase.extract_lesson(vo, retries_used=0)
        assert lesson is not None
        assert "Failed" in lesson


# ===================================================================
# Loop: _load_architecture_and_lessons
# ===================================================================


class TestLoopLoadArchAndLessons:
    """ImplementationLoop._load_architecture_and_lessons() loads from ontology."""

    def test_loads_all_context(self) -> None:
        from tulla.phases.implementation.loop import ImplementationLoop

        ontology = StubOntology({
            "context=arch-idea-42|predicate=arch:qualityGoal": [
                {"subject": "arch:idea-42", "object": "Testability: needed"},
            ],
            "context=arch-idea-42|predicate=arch:designPrinciple": [
                {"subject": "arch:idea-42", "object": "SoC: modules independent"},
            ],
            "context=arch-idea-42|predicate=arch:decision": [
                {"subject": "arch:adr-42-1", "object": "Template Method for phases"},
            ],
            "context=lesson-idea-42|predicate=lesson:text": [
                {"subject": "lesson:42", "object": "lesson one"},
            ],
        })

        config = MagicMock()
        loop = ImplementationLoop(
            claude_port=MagicMock(),
            ontology_port=ontology,
            project_root=Path("/tmp"),
            prd_context="prd-idea-42",
            config=config,
        )
        loop._load_architecture_and_lessons()

        assert loop._architecture_context is not None
        assert loop._architecture_context["quality_goals"] == ["Testability: needed"]
        assert loop._architecture_context["design_principles"] == ["SoC: modules independent"]
        assert loop._architecture_context["adrs"] == {"arch:adr-42-1": "Template Method for phases"}
        assert loop._lessons == ["lesson one"]

    def test_no_context_when_empty(self) -> None:
        from tulla.phases.implementation.loop import ImplementationLoop

        ontology = StubOntology()
        config = MagicMock()
        loop = ImplementationLoop(
            claude_port=MagicMock(),
            ontology_port=ontology,
            project_root=Path("/tmp"),
            prd_context="prd-idea-99",
            config=config,
        )
        loop._load_architecture_and_lessons()

        assert loop._architecture_context is None
        assert loop._lessons == []


# ===================================================================
# Loop: _store_lesson
# ===================================================================


class TestLoopStoreLesson:
    """ImplementationLoop._store_lesson() stores a fact and appends to cache."""

    def test_stores_and_appends(self) -> None:
        from tulla.phases.implementation.loop import ImplementationLoop

        ontology = StubOntology()
        config = MagicMock()
        loop = ImplementationLoop(
            claude_port=MagicMock(),
            ontology_port=ontology,
            project_root=Path("/tmp"),
            prd_context="prd-idea-42",
            config=config,
        )

        loop._store_lesson("req-42-1-1: Fixed after 1 retry. Issue: missing import")

        assert len(ontology.store_calls) == 1
        stored = ontology.store_calls[0]
        assert stored["subject"] == "lesson:42"
        assert stored["predicate"] == "lesson:text"
        assert "missing import" in stored["object"]
        assert stored["context"] == "lesson-idea-42"
        assert len(loop._lessons) == 1

    def test_tolerates_store_failure(self) -> None:
        from tulla.phases.implementation.loop import ImplementationLoop

        ontology = MagicMock(spec=OntologyPort)
        ontology.store_fact.side_effect = RuntimeError("network error")
        ontology.recall_facts.return_value = {"result": []}

        config = MagicMock()
        loop = ImplementationLoop(
            claude_port=MagicMock(),
            ontology_port=ontology,
            project_root=Path("/tmp"),
            prd_context="prd-idea-42",
            config=config,
        )

        # Should not raise
        loop._store_lesson("some lesson")
        # Lesson NOT appended on failure
        assert loop._lessons == []


# ===================================================================
# FindPhase._load_requirement — advisory warning
# ===================================================================


class TestLoadRequirementAdvisoryWarning:
    """FindPhase._load_requirement() warns when requirement may be under-specified."""

    def test_warns_on_many_files_short_description(self, caplog: pytest.LogCaptureFixture) -> None:
        """5-file requirement with short description triggers warning."""
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-2-1": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "Big Task"},
                {"predicate": "prd:description", "object": "Do the thing quickly"},
                {"predicate": "prd:files", "object": "src/a.py, src/b.py, src/c.py, src/d.py, src/e.py"},
                {"predicate": "prd:action", "object": "modify"},
                {"predicate": "prd:verification", "object": "pytest"},
            ],
        })
        phase = FindPhase()
        with caplog.at_level(logging.WARNING, logger="tulla.phases.implementation.find"):
            result = phase._load_requirement(ontology, "prd:req-42-2-1", "prd-idea-42")

        assert result.requirement_id == "prd:req-42-2-1"
        assert len(result.files) == 5
        assert any("under-specified" in r.message for r in caplog.records)
        assert any("5 files" in r.message for r in caplog.records)

    def test_no_warning_when_within_thresholds(self, caplog: pytest.LogCaptureFixture) -> None:
        """3 files with long enough description does not trigger warning."""
        # 3 files, 50 words → wpf ~16.7 → no warning
        long_desc = " ".join(["word"] * 50)
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-3-1": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "OK Task"},
                {"predicate": "prd:description", "object": long_desc},
                {"predicate": "prd:files", "object": "src/a.py, src/b.py, src/c.py"},
                {"predicate": "prd:action", "object": "modify"},
                {"predicate": "prd:verification", "object": "pytest"},
            ],
        })
        phase = FindPhase()
        with caplog.at_level(logging.WARNING, logger="tulla.phases.implementation.find"):
            result = phase._load_requirement(ontology, "prd:req-42-3-1", "prd-idea-42")

        assert result.requirement_id == "prd:req-42-3-1"
        assert not any("under-specified" in r.message for r in caplog.records)

    def test_warns_on_low_wpf(self, caplog: pytest.LogCaptureFixture) -> None:
        """2 files but wpf < 15 triggers warning."""
        # 2 files, 10 words → wpf = 5 → warning
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-4-1": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "Small Task"},
                {"predicate": "prd:description", "object": "Fix the bug in the module now please ok"},
                {"predicate": "prd:files", "object": "src/a.py, src/b.py"},
                {"predicate": "prd:action", "object": "modify"},
                {"predicate": "prd:verification", "object": "pytest"},
            ],
        })
        phase = FindPhase()
        with caplog.at_level(logging.WARNING, logger="tulla.phases.implementation.find"):
            result = phase._load_requirement(ontology, "prd:req-42-4-1", "prd-idea-42")

        assert result.requirement_id == "prd:req-42-4-1"
        assert any("under-specified" in r.message for r in caplog.records)
        assert any("wpf=" in r.message for r in caplog.records)


# ===================================================================
# TestFindPhaseAdvisory — fine vs coarse requirement advisory
# ===================================================================


class TestFindPhaseAdvisory:
    """FindPhase._load_requirement() advisory: fine vs coarse requirements.

    Uses MockOntology (StubOntology) test double.
    """

    def test_no_warning_for_fine_requirement(self, caplog: pytest.LogCaptureFixture) -> None:
        """1 file with detailed description → no advisory warning."""
        # 1 file, 30 words → wpf = 30 → well above threshold; files ≤ 3
        detailed_desc = (
            "Add unit tests for the FindPhase advisory warning logic. "
            "The tests should cover both the fine-grained requirement case "
            "where no warning is expected and the coarse-grained case where "
            "a warning is emitted to stderr"
        )
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-5-1": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "Fine Requirement"},
                {"predicate": "prd:description", "object": detailed_desc},
                {"predicate": "prd:files", "object": "tests/test_advisory.py"},
                {"predicate": "prd:action", "object": "create"},
                {"predicate": "prd:verification", "object": "pytest tests/"},
            ],
        })
        phase = FindPhase()
        with caplog.at_level(logging.WARNING, logger="tulla.phases.implementation.find"):
            result = phase._load_requirement(ontology, "prd:req-42-5-1", "prd-idea-42")

        assert result.requirement_id == "prd:req-42-5-1"
        assert len(result.files) == 1
        assert not any("under-specified" in r.message for r in caplog.records)

    def test_warning_for_coarse_requirement(self, caplog: pytest.LogCaptureFixture) -> None:
        """5 files with short description → advisory warning emitted."""
        ontology = StubOntology({
            "context=prd-idea-42|subject=prd:req-42-5-2": [
                {"predicate": "rdf:type", "object": "prd:Requirement"},
                {"predicate": "prd:title", "object": "Coarse Requirement"},
                {"predicate": "prd:description", "object": "Update all modules"},
                {"predicate": "prd:files", "object": "src/a.py, src/b.py, src/c.py, src/d.py, src/e.py"},
                {"predicate": "prd:action", "object": "modify"},
                {"predicate": "prd:verification", "object": "pytest"},
            ],
        })
        phase = FindPhase()
        with caplog.at_level(logging.WARNING, logger="tulla.phases.implementation.find"):
            result = phase._load_requirement(ontology, "prd:req-42-5-2", "prd-idea-42")

        assert result.requirement_id == "prd:req-42-5-2"
        assert len(result.files) == 5
        warning_msgs = [r.message for r in caplog.records if "under-specified" in r.message]
        assert len(warning_msgs) == 1
        assert "5 files" in warning_msgs[0]
        assert "wpf=" in warning_msgs[0]
