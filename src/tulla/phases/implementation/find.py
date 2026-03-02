"""FindPhase — queries ontology for the next READY requirement.

Part of the Implementation loop. This phase does NOT invoke Claude;
it queries the ontology-server to find the next requirement with
status ``prd:Pending`` that has all dependencies satisfied.
"""

from __future__ import annotations

import logging

import click

from tulla.namespaces import REVERSE_PREFIXES
from tulla.ports.ontology import OntologyPort

from .models import FindOutput

logger = logging.getLogger(__name__)

# Re-export for backward compatibility (used by tests)
_REVERSE_PREFIXES = REVERSE_PREFIXES


class FindPhase:
    """Locate the next actionable requirement from the ontology.

    Queries facts in the PRD context to find requirements whose status
    is ``prd:Pending`` and whose dependencies are all ``prd:Complete``.
    Returns a :class:`FindOutput` describing the requirement, or sets
    ``all_complete=True`` when nothing remains.
    """

    phase_id: str = "find"

    def __init__(
        self,
        max_files_per_requirement: int = 3,
        min_wpf_advisory: float = 15.0,
        ontology_query_limit: int = 500,
    ) -> None:
        self._max_files = max_files_per_requirement
        self._min_wpf = min_wpf_advisory
        self._query_limit = ontology_query_limit

    def execute(
        self,
        ontology: OntologyPort,
        prd_context: str,
    ) -> FindOutput:
        """Find the next READY requirement.

        Parameters:
            ontology: Ontology port for querying facts.
            prd_context: The ontology context holding PRD facts
                (e.g. ``"prd-idea-54"``).

        Returns:
            A :class:`FindOutput` with the requirement details, or
            ``all_complete=True`` if no pending requirements remain.
        """
        # 1. Recall all requirements in this PRD context
        all_facts = ontology.recall_facts(
            predicate="rdf:type",
            context=prd_context,
            limit=self._query_limit,
        )
        results = all_facts.get("result", [])
        req_subjects = [
            f["subject"]
            for f in results
            if f.get("object") == "prd:Requirement"
        ]

        if not req_subjects:
            logger.info("No requirements found in context %s", prd_context)
            return FindOutput(all_complete=True)

        # 2. For each requirement, check status
        pending_reqs: list[str] = []
        completed_reqs: set[str] = set()
        status_map: dict[str, str] = {}

        for req_id in req_subjects:
            status_facts = ontology.recall_facts(
                subject=req_id,
                predicate="prd:status",
                context=prd_context,
            )
            status_results = status_facts.get("result", [])
            if status_results:
                status = status_results[0].get("object", "")
                status_map[req_id] = status
                if status == "prd:Pending":
                    pending_reqs.append(req_id)
                elif status == "prd:Complete":
                    completed_reqs.add(req_id)

        if not pending_reqs:
            logger.info("All requirements complete or blocked in %s", prd_context)
            return FindOutput(all_complete=True)

        # 3. Find first pending req whose dependencies are all complete
        for req_id in sorted(pending_reqs):
            dep_facts = ontology.recall_facts(
                subject=req_id,
                predicate="prd:dependsOn",
                context=prd_context,
            )
            dep_results = dep_facts.get("result", [])
            deps = [d.get("object", "") for d in dep_results]

            deps_satisfied = all(d in completed_reqs for d in deps)
            if not deps_satisfied:
                logger.debug(
                    "Skipping %s: dependencies not met (%s)",
                    req_id,
                    [d for d in deps if d not in completed_reqs],
                )
                continue

            # 4. Load full requirement details
            return self._load_requirement(ontology, req_id, prd_context)

        # All pending reqs have unsatisfied deps — blocked
        logger.warning(
            "All pending requirements have unsatisfied dependencies in %s",
            prd_context,
        )
        return FindOutput(all_complete=True)

    @staticmethod
    def _expand_uri(compact: str) -> str:
        """Expand a compact prefixed URI to its full form.

        Example: ``isaqb:Maintainability`` →
        ``http://tulla.dev/isaqb#Maintainability``

        Returns the input unchanged if no known prefix matches.
        """
        for prefix, full_ns in REVERSE_PREFIXES.items():
            if compact.startswith(prefix):
                return compact.replace(prefix, full_ns, 1)
        return compact

    def _resolve_patterns_via_sparql(
        self,
        ontology: OntologyPort,
        quality_focus: str,
    ) -> tuple[list[str], list[str], list[str]]:
        """Resolve quality_focus to patterns, principles, and design patterns.

        Uses three chained SPARQL queries (arch:adr-65-2) through the
        existing ``OntologyPort.sparql_query()`` interface:

        1. Quality → architectural patterns (direct + via hasSubAttribute)
        2. Patterns → design principles
        3. Principles → design patterns

        Returns:
            A 3-tuple ``(patterns, principles, design_patterns)`` where each
            element is a list of compact URIs (e.g. ``["isaqb:LayeredArchitecture"]``).
            Returns three empty lists if *quality_focus* is empty or queries
            return no results.
        """
        if not quality_focus:
            return [], [], []

        full_uri = self._expand_uri(quality_focus)

        # -- Query 1: quality → architectural patterns (arch:adr-65-2) --
        q1 = (
            "SELECT DISTINCT ?pattern ?quality WHERE {\n"
            "  {\n"
            f"    ?pattern isaqb:addresses <{full_uri}> .\n"
            f"    BIND(<{full_uri}> AS ?quality)\n"
            "  }\n"
            "  UNION\n"
            "  {\n"
            f"    <{full_uri}> isaqb:hasSubAttribute ?sub .\n"
            "    ?pattern isaqb:addresses ?sub .\n"
            "    BIND(?sub AS ?quality)\n"
            "  }\n"
            "}"
        )
        try:
            r1 = ontology.sparql_query(q1)
        except Exception:
            logger.warning("SPARQL query 1 failed for %s", quality_focus, exc_info=True)
            return [], [], []

        bindings1 = r1.get("results", [])
        patterns: list[str] = []
        seen_patterns: set[str] = set()
        for row in bindings1:
            p = row.get("pattern", "")
            if p and p not in seen_patterns:
                seen_patterns.add(p)
                patterns.append(p)

        if not patterns:
            return [], [], []

        # -- Query 2: patterns → principles (arch:adr-65-2) --
        values_patterns = " ".join(f"<{self._expand_uri(p)}>" for p in patterns)
        q2 = (
            "SELECT DISTINCT ?principle ?pattern WHERE {\n"
            f"  VALUES ?pattern {{ {values_patterns} }}\n"
            "  ?pattern isaqb:embodies ?principle .\n"
            "}"
        )
        try:
            r2 = ontology.sparql_query(q2)
        except Exception:
            logger.warning("SPARQL query 2 failed for %s", quality_focus, exc_info=True)
            return patterns, [], []

        bindings2 = r2.get("results", [])
        principles: list[str] = []
        seen_principles: set[str] = set()
        for row in bindings2:
            pr = row.get("principle", "")
            if pr and pr not in seen_principles:
                seen_principles.add(pr)
                principles.append(pr)

        if not principles:
            return patterns, [], []

        # -- Query 3: principles → design patterns (arch:adr-65-2) --
        values_principles = " ".join(f"<{self._expand_uri(p)}>" for p in principles)
        q3 = (
            "SELECT DISTINCT ?designPattern ?principle WHERE {\n"
            f"  VALUES ?principle {{ {values_principles} }}\n"
            "  ?designPattern isaqb:embodies ?principle .\n"
            "  ?designPattern a isaqb:DesignPattern .\n"
            "}"
        )
        try:
            r3 = ontology.sparql_query(q3)
        except Exception:
            logger.warning("SPARQL query 3 failed for %s", quality_focus, exc_info=True)
            return patterns, principles, []

        bindings3 = r3.get("results", [])
        design_patterns: list[str] = []
        seen_design: set[str] = set()
        for row in bindings3:
            dp = row.get("designPattern", "")
            if dp and dp not in seen_design:
                seen_design.add(dp)
                design_patterns.append(dp)

        return patterns, principles, design_patterns

    def _load_requirement(
        self,
        ontology: OntologyPort,
        req_id: str,
        prd_context: str,
    ) -> FindOutput:
        """Load all properties of a requirement into a FindOutput."""
        facts = ontology.recall_facts(
            subject=req_id,
            context=prd_context,
        )
        results = facts.get("result", [])

        props: dict[str, str] = {}
        related_adrs: list[str] = []
        for f in results:
            pred = f.get("predicate", "")
            obj = f.get("object", "")
            if pred == "prd:relatedADR":
                related_adrs.append(obj)
            else:
                props[pred] = obj

        files_str = props.get("prd:files", "")
        files = [f.strip() for f in files_str.split(",") if f.strip()]

        # Advisory warning for requirements that may be too coarse
        description = props.get("prd:description", "")
        word_count = len(description.split())
        wpf = word_count / len(files) if files else 0
        if len(files) > self._max_files or wpf < self._min_wpf:
            msg = (
                f"Requirement {req_id} may be under-specified: "
                f"{len(files)} files, {word_count} words, "
                f"wpf={wpf:.1f} (target ≥{self._min_wpf} wpf, ≤{self._max_files} files)"
            )
            logger.warning(msg)
            click.echo(f"⚠ {msg}", err=True)

        quality_focus = props.get("prd:qualityFocus", "")

        # Resolve quality_focus → patterns/principles via SPARQL (arch:adr-65-1)
        resolved_patterns, resolved_principles, resolved_design_patterns = (
            self._resolve_patterns_via_sparql(ontology, quality_focus)
        )

        return FindOutput(
            requirement_id=req_id,
            title=props.get("prd:title", ""),
            description=props.get("prd:description", ""),
            files=files,
            action=props.get("prd:action", ""),
            verification=props.get("prd:verification", ""),
            all_complete=False,
            related_adrs=related_adrs,
            quality_focus=quality_focus,
            resolved_patterns=resolved_patterns,
            resolved_principles=resolved_principles,
            resolved_design_patterns=resolved_design_patterns,
        )

    def load_lessons(
        self,
        ontology: OntologyPort,
        lesson_context: str,
    ) -> list[str]:
        """Load implementation lessons from the ontology.

        Parameters:
            ontology: Ontology port for querying facts.
            lesson_context: The ontology context holding lesson facts
                (e.g. ``"lesson-idea-54"``).

        Returns:
            A list of lesson strings extracted from stored facts.
        """
        facts = ontology.recall_facts(
            predicate="lesson:text",
            context=lesson_context,
        )
        results = facts.get("result", [])
        return [f.get("object", "") for f in results if f.get("object")]
