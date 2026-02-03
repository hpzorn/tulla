"""ContextScanPhase — structural conformance checking for the lightweight pipeline.

# @pattern:EventSourcing -- Produces an immutable ContextScanOutput from file analysis, consumed by downstream Plan/Trace phases
# @pattern:PortsAndAdapters -- Overrides run_claude() for local computation; delegates SPARQL resolution to FindPhase behind OntologyPort
# @principle:FailSafeRouting -- SPARQL unavailability degrades gracefully to structural-only:sparql-unavailable rather than failing the phase

Architecture decisions: arch:adr-53-1, arch:adr-53-2, arch:adr-53-5
Quality focus: isaqb:Reliability
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tulla.core.phase import Phase, PhaseContext
from tulla.phases.implementation.find import FindPhase
from tulla.phases.implementation.import_graph import (
    ImportViolation,
    check_import_violations,
    format_violation_report,
)
from tulla.phases.lightweight.models import ContextScanOutput

logger = logging.getLogger(__name__)

# Default quality focus when none is provided (arch:adr-53-2)
_DEFAULT_QUALITY_FOCUS = "isaqb:Maintainability"


class ContextScanPhase(Phase[ContextScanOutput]):
    """Perform structural conformance checking on affected files.

    Overrides ``run_claude()`` to perform local computation instead of
    calling Claude (arch:adr-53-1).  Reads ``IntakeOutput`` from
    ``ctx.config["prev_output"]``, scans each affected file for import
    violations, and optionally resolves quality attributes to architectural
    patterns via SPARQL (arch:adr-53-2).

    The ``conformance_status`` follows the ``structural-only:{status}``
    format (arch:adr-53-5) to prevent false assumptions about behavioural
    conformance coverage.
    """

    phase_id: str = "context-scan"
    timeout_s: float = 60.0

    # ------------------------------------------------------------------
    # Template hooks (unused for non-Claude phase)
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Unused — non-Claude phase."""
        return ""

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Unused — non-Claude phase."""
        return []

    # ------------------------------------------------------------------
    # Core logic — overrides run_claude() per arch:adr-53-1
    # ------------------------------------------------------------------

    def run_claude(
        self, ctx: PhaseContext, prompt: str, tools: list[dict[str, Any]]
    ) -> Any:
        """Perform local conformance checking instead of calling Claude.

        Returns a dict consumed by ``parse_output()`` to build a
        ``ContextScanOutput``.
        """
        # Read IntakeOutput from predecessor phase output
        prev_output = ctx.config.get("prev_output")
        affected_files: list[str] = []
        if prev_output is not None:
            if hasattr(prev_output, "affected_files"):
                affected_files = prev_output.affected_files
            elif isinstance(prev_output, dict):
                affected_files = prev_output.get("affected_files", [])

        # Accumulate violations across all affected files
        all_violations: list[dict[str, Any]] = []
        for file_path in affected_files:
            source = _read_file_source(file_path)
            if source is None:
                # FileNotFoundError handled gracefully — skip missing files
                logger.warning("Skipping missing file: %s", file_path)
                continue
            violations = check_import_violations(file_path, source)
            for v in violations:
                all_violations.append(asdict(v))

        # Generate human-readable report
        violation_objects = [ImportViolation(**v) for v in all_violations]
        report = format_violation_report(violation_objects)

        # Resolve quality attributes via SPARQL (arch:adr-53-2)
        patterns: list[str] = []
        principles: list[str] = []
        quality_focus = _DEFAULT_QUALITY_FOCUS
        sparql_available = False

        ontology_port = ctx.config.get("ontology_port")
        if ontology_port is not None:
            sparql_available = _try_sparql_resolution(
                ontology_port, quality_focus, patterns, principles
            )

        # Determine conformance status (arch:adr-53-5)
        if ontology_port is None or not sparql_available:
            conformance_status = "structural-only:sparql-unavailable"
        elif all_violations:
            conformance_status = "structural-only:violations-found"
        else:
            conformance_status = "structural-only:clean"

        return {
            "violations": all_violations,
            "violation_report": report,
            "patterns": patterns,
            "principles": principles,
            "conformance_status": conformance_status,
            "quality_focus": quality_focus,
        }

    # ------------------------------------------------------------------
    # Parse output — wraps dict into ContextScanOutput model
    # ------------------------------------------------------------------

    def parse_output(self, ctx: PhaseContext, raw: Any) -> ContextScanOutput:
        """Wrap the dict returned by ``run_claude()`` into a ContextScanOutput."""
        return ContextScanOutput(**raw)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _try_sparql_resolution(
    ontology_port: Any,
    quality_focus: str,
    patterns: list[str],
    principles: list[str],
) -> bool:
    """Attempt SPARQL-based pattern resolution via FindPhase (arch:adr-53-2).

    Probes the ontology port with a minimal SPARQL query first.  If the
    probe succeeds, delegates to ``FindPhase._resolve_patterns_via_sparql``
    and populates *patterns* and *principles* in-place.

    Returns ``True`` if SPARQL was available and the resolution succeeded,
    ``False`` if SPARQL is unavailable or any query failed.
    """
    # Probe SPARQL availability with a trivial query
    try:
        ontology_port.sparql_query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1")
    except Exception:
        logger.warning(
            "SPARQL probe failed; degrading to structural-only",
            exc_info=True,
        )
        return False

    try:
        finder = FindPhase()
        resolved_patterns, resolved_principles, _ = (
            finder._resolve_patterns_via_sparql(ontology_port, quality_focus)
        )
        patterns.extend(resolved_patterns)
        principles.extend(resolved_principles)
        return True
    except Exception:
        logger.warning(
            "SPARQL pattern resolution failed; degrading to structural-only",
            exc_info=True,
        )
        return False


def _read_file_source(file_path: str) -> str | None:
    """Read a file's source code, returning None if not found.

    Handles ``FileNotFoundError`` gracefully so the phase can continue
    scanning remaining files.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
