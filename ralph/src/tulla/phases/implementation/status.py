"""StatusPhase — updates ontology requirement status.

Part of the Implementation loop. This phase updates the requirement's
status in the ontology after implementation and verification. It does
NOT invoke Claude.
"""

from __future__ import annotations

import logging

from ralph.ports.ontology import OntologyPort

from .models import RequirementStatus, StatusOutput

logger = logging.getLogger(__name__)


class StatusPhase:
    """Update a requirement's status in the ontology.

    Stores a new ``prd:status`` fact for the requirement, replacing
    the previous status value.
    """

    phase_id: str = "status"

    def execute(
        self,
        ontology: OntologyPort,
        requirement_id: str,
        new_status: RequirementStatus,
        prd_context: str,
    ) -> StatusOutput:
        """Update the requirement status in the ontology.

        Parameters:
            ontology: Ontology port for storing facts.
            requirement_id: The ``prd:req-*`` identifier.
            new_status: The new status to set.
            prd_context: The ontology context holding PRD facts.

        Returns:
            A :class:`StatusOutput` confirming the update.
        """
        try:
            # Find and forget the old status fact
            old_facts = ontology.recall_facts(
                subject=requirement_id,
                predicate="prd:status",
                context=prd_context,
            )
            for fact in old_facts.get("result", []):
                fact_id = fact.get("fact_id", "")
                if fact_id:
                    ontology.forget_fact(fact_id)

            # Store the new status
            ontology.store_fact(
                subject=requirement_id,
                predicate="prd:status",
                object=new_status.value,
                context=prd_context,
            )

            logger.info(
                "Updated %s status to %s",
                requirement_id,
                new_status.value,
            )
            return StatusOutput(
                requirement_id=requirement_id,
                new_status=new_status,
                updated=True,
            )

        except Exception as exc:
            logger.error(
                "Failed to update status for %s: %s",
                requirement_id,
                exc,
            )
            return StatusOutput(
                requirement_id=requirement_id,
                new_status=new_status,
                updated=False,
            )
