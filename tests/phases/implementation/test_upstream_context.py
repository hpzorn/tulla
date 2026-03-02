"""Tests for upstream context handoff: ADR reconstruction + northstar/constraints.

Covers:
- _reconstruct_adrs_from_facts() helper in loop.py
- _build_architecture_section() northstar/constraints injection in implement.py
- _build_architecture_compliance() northstar injection in verify.py
- Backward compatibility when no upstream facts exist
"""

from __future__ import annotations

from typing import Any

from tulla.phases.implementation.implement import ImplementPhase
from tulla.phases.implementation.loop import _reconstruct_adrs_from_facts
from tulla.phases.implementation.models import FindOutput
from tulla.phases.implementation.verify import VerifyPhase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_requirement(**overrides: Any) -> FindOutput:
    defaults = dict(
        requirement_id="prd:req-78-1-1",
        title="Test requirement",
        description="Do the thing",
        files=["src/foo.py"],
        action="modify",
        verification="Run tests",
    )
    defaults.update(overrides)
    return FindOutput(**defaults)


SAMPLE_ARCH_CONTEXT: dict[str, Any] = {
    "quality_goals": ["Testability"],
    "design_principles": ["SoC: modules independent"],
    "adrs": {"arch:adr-78-1": "Use Ports and Adapters"},
    "project_adrs": [],
    "project_adr_summary": "",
}


# ===================================================================
# _reconstruct_adrs_from_facts
# ===================================================================


class TestReconstructAdrsFromFacts:
    """_reconstruct_adrs_from_facts() reconstructs ADRs from P6-format facts."""

    def test_reconstructs_adrs(self) -> None:
        facts = [
            {
                "subject": "arch:adr-78-1",
                "predicate": "rdfs:label",
                "object": "Use Ports and Adapters",
            },
            {
                "subject": "arch:adr-78-1",
                "predicate": "isaqb:consequences",
                "object": "All I/O behind ports",
            },
            {
                "subject": "arch:adr-78-2",
                "predicate": "rdfs:label",
                "object": "Use Event Sourcing",
            },
            {
                "subject": "arch:adr-78-2",
                "predicate": "isaqb:consequences",
                "object": "Immutable event log",
            },
            # Unrelated fact — should be ignored
            {"subject": "prd:req-78-1-1", "predicate": "prd:title", "object": "Some Req"},
        ]
        result = _reconstruct_adrs_from_facts(facts, "78")

        assert len(result) == 2
        ids = {adr["id"] for adr in result}
        assert "arch:adr-78-1" in ids
        assert "arch:adr-78-2" in ids

        adr1 = next(a for a in result if a["id"] == "arch:adr-78-1")
        assert adr1["title"] == "Use Ports and Adapters"
        assert adr1["consequences"] == "All I/O behind ports"

    def test_empty_facts(self) -> None:
        result = _reconstruct_adrs_from_facts([], "78")
        assert result == []

    def test_no_matching_facts(self) -> None:
        facts = [
            {"subject": "prd:req-78-1-1", "predicate": "prd:title", "object": "Some Req"},
            {"subject": "arch:adr-99-1", "predicate": "rdfs:label", "object": "Wrong idea"},
        ]
        result = _reconstruct_adrs_from_facts(facts, "78")
        assert result == []

    def test_partial_adr_title_only(self) -> None:
        """ADR with only a title (no consequences) is still returned."""
        facts = [
            {"subject": "arch:adr-78-3", "predicate": "rdfs:label", "object": "Minimal ADR"},
        ]
        result = _reconstruct_adrs_from_facts(facts, "78")
        assert len(result) == 1
        assert result[0]["title"] == "Minimal ADR"
        assert result[0]["consequences"] == ""


# ===================================================================
# _build_architecture_section with northstar/constraints
# ===================================================================


class TestBuildArchitectureSectionWithNorthstar:
    """ImplementPhase._build_architecture_section() injects northstar + constraints."""

    def test_includes_northstar(self) -> None:
        ctx = {**SAMPLE_ARCH_CONTEXT, "northstar": "A semantic implementation agent"}
        req = _make_requirement()
        lines = ImplementPhase._build_architecture_section(req, ctx)
        text = "\n".join(lines)

        assert "**Northstar**" in text
        assert "A semantic implementation agent" in text

    def test_includes_key_constraints_list(self) -> None:
        ctx = {
            **SAMPLE_ARCH_CONTEXT,
            "key_constraints": ["Must use Python 3.11+", "No external DB"],
        }
        req = _make_requirement()
        lines = ImplementPhase._build_architecture_section(req, ctx)
        text = "\n".join(lines)

        assert "**Key Constraints**" in text
        assert "- Must use Python 3.11+" in text
        assert "- No external DB" in text

    def test_includes_key_constraints_string(self) -> None:
        ctx = {**SAMPLE_ARCH_CONTEXT, "key_constraints": "Must use Python 3.11+"}
        req = _make_requirement()
        lines = ImplementPhase._build_architecture_section(req, ctx)
        text = "\n".join(lines)

        assert "**Key Constraints**" in text
        assert "Must use Python 3.11+" in text

    def test_backward_compat_no_northstar(self) -> None:
        """Context without northstar still works (existing behavior)."""
        req = _make_requirement(related_adrs=["arch:adr-78-1"])
        lines = ImplementPhase._build_architecture_section(req, SAMPLE_ARCH_CONTEXT)
        text = "\n".join(lines)

        assert "## Architecture Context" in text
        assert "**Northstar**" not in text
        assert "**Key Constraints**" not in text
        # Existing features still work
        assert "arch:adr-78-1" in text
        assert "SoC: modules independent" in text

    def test_northstar_before_quality_focus(self) -> None:
        """Northstar appears before per-requirement quality focus."""
        ctx = {**SAMPLE_ARCH_CONTEXT, "northstar": "The northstar"}
        req = _make_requirement(quality_focus="Testability")
        lines = ImplementPhase._build_architecture_section(req, ctx)
        text = "\n".join(lines)

        northstar_pos = text.index("**Northstar**")
        quality_pos = text.index("**Quality focus")
        assert northstar_pos < quality_pos

    def test_no_context_returns_empty(self) -> None:
        """None context still returns empty list."""
        req = _make_requirement()
        lines = ImplementPhase._build_architecture_section(req, None)
        assert lines == []


# ===================================================================
# _build_architecture_compliance with northstar
# ===================================================================


class TestBuildArchitectureComplianceWithNorthstar:
    """VerifyPhase._build_architecture_compliance() injects northstar."""

    def test_includes_northstar(self) -> None:
        ctx = {**SAMPLE_ARCH_CONTEXT, "northstar": "A semantic implementation agent"}
        req = _make_requirement()
        lines = VerifyPhase._build_architecture_compliance(req, ctx)
        text = "\n".join(lines)

        assert "**Northstar (must align)**" in text
        assert "A semantic implementation agent" in text

    def test_northstar_before_adr_section(self) -> None:
        """Northstar appears before the ADR and principles listing."""
        ctx = {**SAMPLE_ARCH_CONTEXT, "northstar": "The northstar"}
        req = _make_requirement(related_adrs=["arch:adr-78-1"])
        lines = VerifyPhase._build_architecture_compliance(req, ctx)
        text = "\n".join(lines)

        northstar_pos = text.index("**Northstar (must align)**")
        conform_pos = text.index("verify that the")
        assert northstar_pos < conform_pos

    def test_backward_compat_no_northstar(self) -> None:
        """Context without northstar still works."""
        req = _make_requirement(related_adrs=["arch:adr-78-1"])
        lines = VerifyPhase._build_architecture_compliance(req, SAMPLE_ARCH_CONTEXT)
        text = "\n".join(lines)

        assert "## Architecture Compliance" in text
        assert "**Northstar" not in text
        assert "arch:adr-78-1" in text

    def test_no_context_returns_empty(self) -> None:
        """None context still returns empty list."""
        req = _make_requirement()
        lines = VerifyPhase._build_architecture_compliance(req, None)
        assert lines == []
