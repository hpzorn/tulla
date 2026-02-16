"""Tests for the 6-dimension structural rubric scorer.

Architecture: prd:req-83-5-3

Tests the rubric module WITHOUT making LLM calls:
  - RubricScore dataclass construction
  - compare_modes() with synthetic scores (identical → 6/6, maximally different → 0/6)
  - detect_regression() fires alert at/above threshold, silent below
  - Label stripping removes philosopher names and mode identifiers
  - Does NOT test score_output() (requires LLM — integration test territory)
"""

from __future__ import annotations

import pytest

from tulla.evaluation.rubric import (
    AssumptionStance,
    ContradictionHandling,
    CreativityType,
    EvidenceGrounding,
    ReasoningDirection,
    RubricScore,
    SynthesisStyle,
    _strip_mode_labels,
    compare_modes,
    detect_regression,
)


# ---------------------------------------------------------------------------
# Synthetic scores
# ---------------------------------------------------------------------------

SCORE_A = RubricScore(
    reasoning_direction=ReasoningDirection.TOP_DOWN,
    assumption_stance=AssumptionStance.ACCEPTING,
    synthesis_style=SynthesisStyle.ADDITIVE,
    evidence_grounding=EvidenceGrounding.INTERNAL,
    contradiction_handling=ContradictionHandling.IGNORE,
    creativity_type=CreativityType.EXPLORATORY,
)

SCORE_B = RubricScore(
    reasoning_direction=ReasoningDirection.BOTTOM_UP,
    assumption_stance=AssumptionStance.QUESTIONING,
    synthesis_style=SynthesisStyle.ADDITIVE,  # shared with A
    evidence_grounding=EvidenceGrounding.EXTERNAL_ESTABLISHED,
    contradiction_handling=ContradictionHandling.IGNORE,  # shared with A
    creativity_type=CreativityType.COMBINATIONAL,
)

# Maximally different from SCORE_A — zero dimensions overlap.
SCORE_MAX_DIFF = RubricScore(
    reasoning_direction=ReasoningDirection.LATERAL,
    assumption_stance=AssumptionStance.INVERTING,
    synthesis_style=SynthesisStyle.COMBINATORIAL,
    evidence_grounding=EvidenceGrounding.CROSS_DOMAIN,
    contradiction_handling=ContradictionHandling.PRESERVE,
    creativity_type=CreativityType.TRANSFORMATIONAL,
)

SCORE_C = RubricScore(
    reasoning_direction=ReasoningDirection.TOP_DOWN,  # shared with A
    assumption_stance=AssumptionStance.ACCEPTING,  # shared with A
    synthesis_style=SynthesisStyle.DIALECTICAL,
    evidence_grounding=EvidenceGrounding.INTERNAL,  # shared with A
    contradiction_handling=ContradictionHandling.TRANSCEND,
    creativity_type=CreativityType.TRANSFORMATIONAL,
)


# ---------------------------------------------------------------------------
# RubricScore dataclass construction
# ---------------------------------------------------------------------------


class TestRubricScore:
    def test_construction_all_fields(self) -> None:
        """All 6 dimensions are stored correctly."""
        score = RubricScore(
            reasoning_direction=ReasoningDirection.OUTSIDE_IN,
            assumption_stance=AssumptionStance.SUSPENDING,
            synthesis_style=SynthesisStyle.ELIMINATIVE,
            evidence_grounding=EvidenceGrounding.EXTERNAL_CURRENT,
            contradiction_handling=ContradictionHandling.RESOLVE,
            creativity_type=CreativityType.COMBINATIONAL,
        )
        assert score.reasoning_direction == ReasoningDirection.OUTSIDE_IN
        assert score.assumption_stance == AssumptionStance.SUSPENDING
        assert score.synthesis_style == SynthesisStyle.ELIMINATIVE
        assert score.evidence_grounding == EvidenceGrounding.EXTERNAL_CURRENT
        assert score.contradiction_handling == ContradictionHandling.RESOLVE
        assert score.creativity_type == CreativityType.COMBINATIONAL

    def test_as_tuple(self) -> None:
        t = SCORE_A.as_tuple()
        assert t == (
            "top-down", "accepting", "additive",
            "internal", "ignore", "exploratory",
        )

    def test_as_tuple_length(self) -> None:
        assert len(SCORE_A.as_tuple()) == 6

    def test_frozen(self) -> None:
        with pytest.raises(AttributeError):
            SCORE_A.reasoning_direction = ReasoningDirection.LATERAL  # type: ignore[misc]

    def test_equality(self) -> None:
        clone = RubricScore(
            reasoning_direction=ReasoningDirection.TOP_DOWN,
            assumption_stance=AssumptionStance.ACCEPTING,
            synthesis_style=SynthesisStyle.ADDITIVE,
            evidence_grounding=EvidenceGrounding.INTERNAL,
            contradiction_handling=ContradictionHandling.IGNORE,
            creativity_type=CreativityType.EXPLORATORY,
        )
        assert clone == SCORE_A

    def test_inequality(self) -> None:
        assert SCORE_A != SCORE_B


# ---------------------------------------------------------------------------
# compare_modes — synthetic score tests
# ---------------------------------------------------------------------------


class TestCompareModes:
    """Verify pairwise dimension overlap computation."""

    def test_identical_scores_full_overlap(self) -> None:
        """Two identical scores → 6/6 overlap."""
        result = compare_modes({"x": SCORE_A, "y": SCORE_A})
        assert result[("x", "y")] == 6

    def test_maximally_different_zero_overlap(self) -> None:
        """Maximally different scores → 0/6 overlap."""
        result = compare_modes({"a": SCORE_A, "z": SCORE_MAX_DIFF})
        assert result[("a", "z")] == 0

    def test_two_modes_partial_overlap(self) -> None:
        """A and B share synthesis_style + contradiction_handling → 2/6."""
        result = compare_modes({"a": SCORE_A, "b": SCORE_B})
        assert result[("a", "b")] == 2

    def test_three_modes_pairwise(self) -> None:
        result = compare_modes({"a": SCORE_A, "b": SCORE_B, "c": SCORE_C})
        assert result[("a", "b")] == 2  # additive + ignore
        assert result[("a", "c")] == 3  # top-down + accepting + internal
        assert result[("b", "c")] == 0  # no overlap

    def test_single_mode_no_pairs(self) -> None:
        result = compare_modes({"only": SCORE_A})
        assert result == {}

    def test_empty_input(self) -> None:
        result = compare_modes({})
        assert result == {}

    def test_keys_sorted_alphabetically(self) -> None:
        """Pair keys are always (alphabetically_first, second)."""
        result = compare_modes({"z": SCORE_A, "a": SCORE_A})
        assert ("a", "z") in result
        assert ("z", "a") not in result


# ---------------------------------------------------------------------------
# detect_regression
# ---------------------------------------------------------------------------


class TestDetectRegression:
    def test_silent_below_threshold(self) -> None:
        """No alerts when overlap < threshold."""
        alerts = detect_regression({"a": SCORE_A, "b": SCORE_B}, threshold=3)
        assert alerts == []

    def test_fires_at_threshold(self) -> None:
        """Alert when overlap == threshold."""
        alerts = detect_regression({"a": SCORE_A, "c": SCORE_C}, threshold=3)
        assert len(alerts) == 1
        assert "a" in alerts[0] and "c" in alerts[0]
        assert "3/6" in alerts[0]

    def test_fires_above_threshold(self) -> None:
        """Alert when overlap > threshold (identical scores → 6/6)."""
        alerts = detect_regression({"x": SCORE_A, "y": SCORE_A}, threshold=3)
        assert len(alerts) == 1
        assert "6/6" in alerts[0]

    def test_silent_for_maximally_different(self) -> None:
        """No alert for 0/6 overlap even with low threshold."""
        alerts = detect_regression(
            {"a": SCORE_A, "z": SCORE_MAX_DIFF}, threshold=1
        )
        assert alerts == []

    def test_mixed_pairs_only_problematic_flagged(self) -> None:
        scores = {"a": SCORE_A, "b": SCORE_B, "c": SCORE_C}
        alerts = detect_regression(scores, threshold=3)
        # Only (a, c) with 3 overlaps triggers
        assert len(alerts) == 1
        assert "a" in alerts[0] and "c" in alerts[0]


# ---------------------------------------------------------------------------
# Label stripping
# ---------------------------------------------------------------------------


class TestStripModeLabels:
    """Verify _strip_mode_labels removes philosopher names and mode identifiers."""

    @pytest.mark.parametrize(
        "label",
        [
            "Socratic",
            "socratic",
            "Hegelian",
            "hegelian",
            "Aristotelian",
            "aristotelian",
            "Baconian",
            "baconian",
            "Pyrrhonian",
            "pyrrhonian",
            "Deweyan",
            "deweyan",
            "Peircean",
            "peircean",
            "abduction",
            "Abduction",
            "abductive",
            "Abductive",
            "catuskoti",
            "Catuskoti",
            "nagarjuna",
            "Nagarjuna",
            "nāgārjuna",
        ],
    )
    def test_strips_philosopher_names(self, label: str) -> None:
        text = f"The {label} method produces insight."
        result = _strip_mode_labels(text)
        assert label not in result
        assert "___" in result

    @pytest.mark.parametrize(
        "label",
        ["pool", "idea", "domain", "problem", "contradiction", "signal"],
    )
    def test_strips_old_mode_names(self, label: str) -> None:
        text = f"Running in {label} mode."
        result = _strip_mode_labels(text)
        assert label not in result

    def test_preserves_non_label_text(self) -> None:
        text = "Analyzing market trends and user feedback."
        assert _strip_mode_labels(text) == text

    def test_strips_multiple_labels_in_one_text(self) -> None:
        text = "The Socratic method leads to Hegelian synthesis via abduction"
        result = _strip_mode_labels(text)
        assert "Socratic" not in result
        assert "Hegelian" not in result
        assert "abduction" not in result

    def test_word_boundary_respected(self) -> None:
        """Labels inside larger words should not be stripped (e.g., 'ideation')."""
        # 'idea' is a mode label, but 'ideation' is not — word boundary \\b
        # should prevent partial matching.
        text = "The ideation process continues."
        result = _strip_mode_labels(text)
        # 'idea' inside 'ideation' should NOT be stripped
        assert "ideation" in result
