"""6-Dimension Structural Rubric Scorer.

Implements the validated 6-dimension structural rubric from R5 Exp 5 for
evaluating mode distinctness across epistemology modes.

The six dimensions are:
  1. Reasoning Direction — top-down | bottom-up | outside-in | lateral
  2. Assumption Stance — accepting | questioning | inverting | suspending
  3. Synthesis Style — additive | dialectical | eliminative | combinatorial
  4. Evidence Grounding — internal | external-established | external-current | cross-domain
  5. Contradiction Handling — ignore | resolve | transcend | preserve
  6. Creativity Type — exploratory | combinational | transformational

Architecture: prd:req-83-5-2
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from tulla.ports.claude import ClaudePort, ClaudeRequest

# ---------------------------------------------------------------------------
# Dimension enums
# ---------------------------------------------------------------------------


class ReasoningDirection(StrEnum):
    TOP_DOWN = "top-down"
    BOTTOM_UP = "bottom-up"
    OUTSIDE_IN = "outside-in"
    LATERAL = "lateral"


class AssumptionStance(StrEnum):
    ACCEPTING = "accepting"
    QUESTIONING = "questioning"
    INVERTING = "inverting"
    SUSPENDING = "suspending"


class SynthesisStyle(StrEnum):
    ADDITIVE = "additive"
    DIALECTICAL = "dialectical"
    ELIMINATIVE = "eliminative"
    COMBINATORIAL = "combinatorial"


class EvidenceGrounding(StrEnum):
    INTERNAL = "internal"
    EXTERNAL_ESTABLISHED = "external-established"
    EXTERNAL_CURRENT = "external-current"
    CROSS_DOMAIN = "cross-domain"


class ContradictionHandling(StrEnum):
    IGNORE = "ignore"
    RESOLVE = "resolve"
    TRANSCEND = "transcend"
    PRESERVE = "preserve"


class CreativityType(StrEnum):
    EXPLORATORY = "exploratory"
    COMBINATIONAL = "combinational"
    TRANSFORMATIONAL = "transformational"


# ---------------------------------------------------------------------------
# RubricScore dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RubricScore:
    """Score across all 6 rubric dimensions for a single mode output."""

    reasoning_direction: ReasoningDirection
    assumption_stance: AssumptionStance
    synthesis_style: SynthesisStyle
    evidence_grounding: EvidenceGrounding
    contradiction_handling: ContradictionHandling
    creativity_type: CreativityType

    def as_tuple(self) -> tuple[str, str, str, str, str, str]:
        """Return dimension values as a 6-tuple of strings."""
        return (
            self.reasoning_direction.value,
            self.assumption_stance.value,
            self.synthesis_style.value,
            self.evidence_grounding.value,
            self.contradiction_handling.value,
            self.creativity_type.value,
        )


# ---------------------------------------------------------------------------
# Mode-label stripping
# ---------------------------------------------------------------------------

_MODE_LABELS = re.compile(
    r"\b(socratic|hegelian|aristotelian|baconian|pyrrhonian|deweyan|"
    r"peircean|abducti(?:on|ve)|catuskoti|nāgārjuna|nagarjuna|"
    r"pool|idea|domain|problem|contradiction|signal)\b",
    re.IGNORECASE,
)


def _strip_mode_labels(text: str) -> str:
    """Remove mode-identifying labels so the rubric judges structure, not vocabulary."""
    return _MODE_LABELS.sub("___", text)


# ---------------------------------------------------------------------------
# Rubric prompt
# ---------------------------------------------------------------------------

_RUBRIC_PROMPT = """\
You are a structural reasoning analyst. Given the text below, classify it on \
exactly 6 dimensions. Respond ONLY with a JSON object — no commentary.

Dimensions and allowed values:
1. reasoning_direction: "top-down" | "bottom-up" | "outside-in" | "lateral"
2. assumption_stance: "accepting" | "questioning" | "inverting" | "suspending"
3. synthesis_style: "additive" | "dialectical" | "eliminative" | "combinatorial"
4. evidence_grounding: "internal" | "external-established" | "external-current" | "cross-domain"
5. contradiction_handling: "ignore" | "resolve" | "transcend" | "preserve"
6. creativity_type: "exploratory" | "combinational" | "transformational"

TEXT:
{text}

JSON:"""


# ---------------------------------------------------------------------------
# score_output
# ---------------------------------------------------------------------------


def score_output(text: str, claude_port: ClaudePort) -> RubricScore:
    """Score a mode output on the 6-dimension rubric.

    Strips mode-identifying labels from *text*, sends the sanitised text to
    Claude via *claude_port* with a structured rubric prompt, and parses the
    response into a :class:`RubricScore`.
    """
    sanitised = _strip_mode_labels(text)
    prompt = _RUBRIC_PROMPT.format(text=sanitised)

    result = claude_port.run(ClaudeRequest(prompt=prompt))

    raw = result.output_text.strip()
    # Extract JSON from possible markdown fences
    json_match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    data: dict[str, Any] = json.loads(raw)

    return RubricScore(
        reasoning_direction=ReasoningDirection(data["reasoning_direction"]),
        assumption_stance=AssumptionStance(data["assumption_stance"]),
        synthesis_style=SynthesisStyle(data["synthesis_style"]),
        evidence_grounding=EvidenceGrounding(data["evidence_grounding"]),
        contradiction_handling=ContradictionHandling(data["contradiction_handling"]),
        creativity_type=CreativityType(data["creativity_type"]),
    )


# ---------------------------------------------------------------------------
# compare_modes
# ---------------------------------------------------------------------------


def compare_modes(scores: dict[str, RubricScore]) -> dict[tuple[str, str], int]:
    """Compute pairwise dimension overlap between scored modes.

    Parameters:
        scores: Mapping of mode name → :class:`RubricScore`.

    Returns:
        Dict mapping each ``(mode_a, mode_b)`` pair (sorted alphabetically)
        to the number of dimensions on which their scores share the same value.
    """
    names = sorted(scores)
    overlaps: dict[tuple[str, str], int] = {}

    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            shared = sum(
                va == vb
                for va, vb in zip(scores[a].as_tuple(), scores[b].as_tuple(), strict=False)
            )
            overlaps[(a, b)] = shared

    return overlaps


# ---------------------------------------------------------------------------
# detect_regression
# ---------------------------------------------------------------------------


def detect_regression(
    scores: dict[str, RubricScore],
    threshold: int = 3,
) -> list[str]:
    """Return alert strings for mode pairs sharing >= *threshold* dimensions.

    A high overlap signals potential mode collapse — two modes reasoning
    in near-identical ways despite different philosophical grounding.

    Parameters:
        scores: Mapping of mode name → :class:`RubricScore`.
        threshold: Minimum shared-dimension count to trigger an alert.

    Returns:
        List of human-readable alert strings, one per problematic pair.
    """
    overlaps = compare_modes(scores)
    alerts: list[str] = []

    for (a, b), count in sorted(overlaps.items()):
        if count >= threshold:
            alerts.append(
                f"COLLAPSE RISK: {a} and {b} share {count}/6 dimensions"
            )

    return alerts
