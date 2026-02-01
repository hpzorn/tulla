"""FindPhase — queries ontology for the next READY requirement.

Part of the Implementation loop. This phase does NOT invoke Claude;
it queries the ontology-server to find the next requirement with
status ``prd:Pending`` that has all dependencies satisfied.
"""

from __future__ import annotations

import logging
from typing import Any

from ralph.ports.ontology import OntologyPort

from .models import FindOutput

logger = logging.getLogger(__name__)


class FindPhase:
    """Locate the next actionable requirement from the ontology.

    Queries facts in the PRD context to find requirements whose status
    is ``prd:Pending`` and whose dependencies are all ``prd:Complete``.
    Returns a :class:`FindOutput` describing the requirement, or sets
    ``all_complete=True`` when nothing remains.
    """

    phase_id: str = "find"

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
            limit=500,
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
        for f in results:
            pred = f.get("predicate", "")
            obj = f.get("object", "")
            props[pred] = obj

        files_str = props.get("prd:files", "")
        files = [f.strip() for f in files_str.split(",") if f.strip()]

        return FindOutput(
            requirement_id=req_id,
            title=props.get("prd:title", ""),
            description=props.get("prd:description", ""),
            files=files,
            action=props.get("prd:action", ""),
            verification=props.get("prd:verification", ""),
            all_complete=False,
        )
