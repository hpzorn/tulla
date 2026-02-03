"""TracePhase — assembles the final trace model from all prior phase outputs.

# @pattern:EventSourcing -- Produces an immutable LightweightTraceResult from upstream phase outputs for KG persistence
# @pattern:PortsAndAdapters -- Overrides run_claude() for local computation; Pipeline's PhaseFactPersister handles KG persistence
# @principle:SeparationOfConcerns -- Assembles the model only; persistence delegated to PhaseFactPersister post-hook

Architecture decisions: arch:adr-53-1, arch:adr-53-4
Quality focus: isaqb:FunctionalCorrectness
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from tulla.core.phase import Phase, PhaseContext
from tulla.phases.lightweight.models import LightweightTraceResult

logger = logging.getLogger(__name__)


class TracePhase(Phase[LightweightTraceResult]):
    """Assemble the final trace model from all prior phase outputs.

    Overrides ``run_claude()`` to perform local computation instead of
    calling Claude (arch:adr-53-1).  Retrieves ``ExecuteOutput`` from
    ``ctx.config["prev_output"]`` and walks upstream phase outputs stored
    in ``ctx.config`` to construct a ``LightweightTraceResult`` with all
    9 IntentField-annotated fields.

    The Pipeline's automatic ``PhaseFactPersister`` post-hook handles
    the actual KG persistence — this phase only assembles the model
    (arch:adr-53-4).
    """

    phase_id: str = "trace"
    timeout_s: float = 30.0

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
        """Assemble LightweightTraceResult from upstream phase outputs.

        Returns a dict consumed by ``parse_output()`` to build a
        ``LightweightTraceResult``.
        """
        # Retrieve ExecuteOutput from prev_output (the immediately preceding phase)
        prev_output = ctx.config.get("prev_output")

        # Extract fields from ExecuteOutput (model or dict)
        commit_ref = _get_attr_or_key(prev_output, "commit_ref", "")
        changes_summary = _get_attr_or_key(prev_output, "changes_summary", "")
        files_modified: list[str] = _get_attr_or_key(
            prev_output, "files_modified", []
        )

        # Walk upstream outputs from ctx.config
        intake_output = ctx.config.get("intake_output")
        context_scan_output = ctx.config.get("context_scan_output")

        # Extract change_type from IntakeOutput
        change_type = _get_attr_or_key(intake_output, "change_type", "")

        # Extract conformance_assertion from ContextScanOutput
        conformance_assertion = _get_attr_or_key(
            context_scan_output, "conformance_status", ""
        )

        # Build affected_files as comma-separated string
        affected_files = ",".join(files_modified)

        # Timestamp as current UTC in ISO 8601 format
        timestamp = datetime.now(timezone.utc).isoformat()

        # Optional fields from ctx.config (default to None)
        issue_ref = ctx.config.get("issue_ref")
        sprint_id = ctx.config.get("sprint_id")
        story_points = ctx.config.get("story_points")

        return {
            "change_type": change_type,
            "affected_files": affected_files,
            "conformance_assertion": conformance_assertion,
            "commit_ref": commit_ref,
            "change_summary": changes_summary,
            "timestamp": timestamp,
            "issue_ref": issue_ref,
            "sprint_id": sprint_id,
            "story_points": story_points,
        }

    # ------------------------------------------------------------------
    # Parse output — wraps dict into LightweightTraceResult model
    # ------------------------------------------------------------------

    def parse_output(self, ctx: PhaseContext, raw: Any) -> LightweightTraceResult:
        """Wrap the dict returned by ``run_claude()`` into a LightweightTraceResult."""
        return LightweightTraceResult(**raw)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_attr_or_key(obj: Any, name: str, default: Any = None) -> Any:
    """Extract a value from an object by attribute or dict key.

    Supports both Pydantic model instances (attribute access) and plain
    dicts (key access), returning *default* if *obj* is ``None`` or the
    name is not found.
    """
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default
