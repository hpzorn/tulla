"""Abstract port for ontology-server operations.

Defines the :class:`OntologyPort` ABC whose method surface mirrors the
ontology-server MCP tools (query_ideas, get_idea, store_fact, etc.).
Concrete adapters (MCP client, mock) are provided in ``tulla.adapters``
and belong to Phase 2.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OntologyPort(ABC):
    """Abstract interface for ontology-server interactions.

    Each method corresponds to an ontology-server MCP tool and uses
    compatible typed signatures with ``dict[str, Any]`` return types.
    Concrete implementations live in ``tulla.adapters``.
    """

    @abstractmethod
    def query_ideas(
        self,
        *,
        sparql: str | None = None,
        lifecycle: str | None = None,
        author: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query ideas from the knowledge graph.

        Supports SPARQL queries, filter queries, or text search.
        """

    @abstractmethod
    def get_idea(self, idea_id: str) -> dict[str, Any]:
        """Get a single idea by ID with all metadata."""

    @abstractmethod
    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        """Store a fact in agent memory."""

    @abstractmethod
    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        """Remove a fact from agent memory."""

    @abstractmethod
    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Recall facts from agent memory."""

    @abstractmethod
    def sparql_query(
        self,
        query: str,
        *,
        validate: bool = True,
    ) -> dict[str, Any]:
        """Execute a SPARQL SELECT/ASK query across the knowledge graph."""

    @abstractmethod
    def sparql_update(
        self,
        query: str,
        *,
        validate: bool = True,
    ) -> dict[str, Any]:
        """Execute a SPARQL UPDATE (INSERT/DELETE) against the knowledge graph."""

    @abstractmethod
    def update_idea(
        self,
        idea_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        content: str | None = None,
        lifecycle: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing idea."""

    @abstractmethod
    def forget_by_context(self, context: str) -> int:
        """Remove all facts with the given context. Returns count deleted."""

    @abstractmethod
    def set_lifecycle(
        self,
        idea_id: str,
        new_state: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """Update an idea's lifecycle state with transition validation."""

    @abstractmethod
    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        """Add a direct SPO triple to an ontology graph."""

    @abstractmethod
    def remove_triples_by_subject(
        self,
        subject: str,
        *,
        ontology: str | None = None,
    ) -> int:
        """Remove all triples with the given subject. Returns count removed."""

    @abstractmethod
    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        """Validate an instance against a SHACL shape via the ontology-server."""

    def get_adrs(self, idea_id: str) -> list[dict[str, Any]]:
        """Retrieve structured ADRs for an idea via SPARQL.

        Queries for ``isaqb:ArchitectureDecision`` instances with URIs
        matching ``arch:adr-{idea_id}-*``.  Falls back to legacy string
        facts if no structured ADRs exist.

        Returns a list of dicts with keys: id, title, context, status,
        consequences, addresses, challenges.
        """
        # Default implementation uses SPARQL — subclasses can override
        query = f'''
            SELECT ?adr ?title ?context ?status ?consequences WHERE {{
                ?adr a isaqb:ArchitectureDecision .
                ?adr rdfs:label ?title .
                OPTIONAL {{ ?adr isaqb:context ?context }}
                OPTIONAL {{ ?adr isaqb:decisionStatus ?status }}
                OPTIONAL {{ ?adr isaqb:consequences ?consequences }}
                FILTER(STRSTARTS(STR(?adr), "http://impl-ralph.io/arch#adr-{idea_id}-"))
            }}
        '''
        try:
            result = self.sparql_query(query)
            bindings = result.get("results", [])
            adrs: list[dict[str, Any]] = []
            for row in bindings:
                adr_uri = row.get("adr", "")
                adrs.append({
                    "id": adr_uri.split("#")[-1] if "#" in adr_uri else adr_uri,
                    "title": row.get("title", ""),
                    "context": row.get("context", ""),
                    "status": row.get("status", ""),
                    "consequences": row.get("consequences", ""),
                })
            if adrs:
                return adrs
        except Exception:
            pass  # Fall back to legacy

        # Fallback: legacy string facts
        legacy = self.recall_facts(
            predicate="arch:decision",
            context=f"arch-idea-{idea_id}",
        )
        legacy_adrs: list[dict[str, Any]] = []
        for f in legacy.get("result", []):
            subj = f.get("subject", "")
            obj = f.get("object", "")
            if subj and obj:
                # Parse "Title: decision text" format
                parts = obj.split(":", 1)
                title = parts[0].strip() if parts else obj
                decision = parts[1].strip() if len(parts) > 1 else ""
                legacy_adrs.append({
                    "id": subj,
                    "title": title,
                    "context": "",
                    "status": "Proposed",
                    "consequences": decision,  # Legacy format mixes decision+rationale
                })
        return legacy_adrs
