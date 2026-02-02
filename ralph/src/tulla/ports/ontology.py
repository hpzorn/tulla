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
        """Execute a SPARQL query across the knowledge graph."""

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
    def set_lifecycle(
        self,
        idea_id: str,
        new_state: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        """Update an idea's lifecycle state with transition validation."""
