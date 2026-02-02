"""Annotation format, extraction, and quality scoring.

Single source of truth for the annotation system consolidated from
research experiments (exp1, exp3, exp4).  All annotation-related
constants, data structures, and scoring functions live here so that
ImplementPhase and VerifyPhase share one definition.

Architecture decision: arch:adr-65-3
Quality focus: isaqb:Maintainability
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Annotation types recognised by the system.
ANNOTATION_TYPES: tuple[str, ...] = ("pattern", "principle", "quality")

#: Comment prefixes supported across languages.
#: ``#`` for Python / Shell, ``//`` for TypeScript / Typst.
COMMENT_PREFIXES: tuple[str, ...] = ("#", "//")

#: Compiled regex that extracts ``(type, identifier, explanation)`` from a
#: single comment line.  Accepts em-dash (``—``) and ASCII (``--``)
#: separators.
ANNOTATION_REGEX: re.Pattern[str] = re.compile(
    r"^\s*(?:#|//)\s*@(pattern|principle|quality):(\w+)\s*(?:—|--)\s*(.+)$"
)

#: Target annotations-per-file range (inclusive).
#: arch:adr-65-6 — class/module-level annotations, 2-5 per file.
APF_TARGET: tuple[int, int] = (2, 5)

# Words excluded from the novel-word count when detecting hollow labels.
_FILLER_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "and", "in", "to", "for", "is", "it",
    "this", "that", "with", "by", "on", "at", "from", "uses", "applies",
    "follows", "pattern", "principle", "quality", "addresses",
})

#: Minimum novel words required for an explanation to be non-hollow.
_NOVEL_WORD_THRESHOLD: int = 5

#: Maximum words before an explanation is classified as verbose.
_VERBOSE_WORD_LIMIT: int = 50

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Annotation:
    """A single parsed annotation extracted from source code."""

    ann_type: str
    """One of :data:`ANNOTATION_TYPES` (``pattern``, ``principle``, ``quality``)."""

    identifier: str
    """PascalCase identifier, e.g. ``PortsAndAdapters``."""

    explanation: str
    """Code-specific explanation text after the separator."""

    line_number: int
    """1-based line number where the annotation appears."""


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_annotations(source: str) -> list[Annotation]:
    """Extract all valid annotations from *source*.

    Each line is tested against :data:`ANNOTATION_REGEX`.  Only lines that
    match fully are returned; malformed attempts are silently skipped.
    """
    results: list[Annotation] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        m = ANNOTATION_REGEX.match(line)
        if m:
            results.append(
                Annotation(
                    ann_type=m.group(1),
                    identifier=m.group(2),
                    explanation=m.group(3).strip(),
                    line_number=line_no,
                )
            )
    return results


# ---------------------------------------------------------------------------
# APF (annotations-per-file) metric
# ---------------------------------------------------------------------------


def calculate_apf(annotations: list[Annotation]) -> int:
    """Return the annotations-per-file count.

    APF is the primary density metric (arch:adr-65-6).  Density percentage
    is only meaningful as a secondary check for files >= 100 lines.
    """
    return len(annotations)


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------


def is_hollow(explanation: str, identifier: str) -> bool:
    """Detect whether *explanation* is a hollow label.

    A hollow explanation restates the identifier without adding
    code-specific information.  The heuristic splits *identifier* by
    PascalCase boundaries, removes filler words, and checks whether
    fewer than :data:`_NOVEL_WORD_THRESHOLD` novel words remain.
    """
    id_words = {
        w.lower()
        for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", identifier)
    }
    explanation_words = {
        w.lower() for w in re.findall(r"[a-z]+", explanation.lower())
    }
    novel_words = explanation_words - id_words - _FILLER_WORDS
    return len(novel_words) < _NOVEL_WORD_THRESHOLD


def classify_adequacy(annotation: Annotation) -> str:
    """Classify *annotation* as ``"adequate"``, ``"hollow"``, or ``"verbose"``.

    Thresholds derived from exp3/exp4 calibration:

    * **verbose** — explanation exceeds :data:`_VERBOSE_WORD_LIMIT` words.
    * **hollow**  — explanation has fewer than :data:`_NOVEL_WORD_THRESHOLD`
      novel words beyond the identifier and filler words.
    * **adequate** — everything else (the desired outcome).
    """
    word_count = len(annotation.explanation.split())

    if word_count > _VERBOSE_WORD_LIMIT:
        return "verbose"

    if is_hollow(annotation.explanation, annotation.identifier):
        return "hollow"

    return "adequate"
