"""Ontology MCP adapter – wraps ontology-server REST/MCP calls via HTTP POST.

Implements :class:`OntologyPort` by sending HTTP POST requests with JSON
payloads to the ontology-server REST endpoints using :mod:`urllib`.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from ralph.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)


class OntologyMCPAdapter(OntologyPort):
    """Concrete :class:`OntologyPort` that talks to ontology-server via HTTP.

    Parameters:
        base_url: Base URL of the ontology-server (default ``"http://localhost:3000"``).
    """

    def __init__(self, base_url: str = "http://localhost:3000") -> None:
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _call(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send an HTTP POST with JSON *payload* to *endpoint*.

        Returns the parsed JSON response on success or
        ``{"error": <message>}`` on :class:`URLError`.
        """
        url = f"{self._base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except URLError as exc:
            logger.error("Ontology-server request to %s failed: %s", url, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # OntologyPort interface
    # ------------------------------------------------------------------

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
        payload: dict[str, Any] = {"limit": limit}
        if sparql is not None:
            payload["sparql"] = sparql
        if lifecycle is not None:
            payload["lifecycle"] = lifecycle
        if author is not None:
            payload["author"] = author
        if tag is not None:
            payload["tag"] = tag
        if search is not None:
            payload["search"] = search
        return self._call("/api/ideas", payload)

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return self._call(f"/api/ideas/{idea_id}", {})

    def store_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        context: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "confidence": confidence,
        }
        if context is not None:
            payload["context"] = context
        return self._call("/api/facts", payload)

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return self._call("/api/facts/forget", {"fact_id": fact_id})

    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"limit": limit}
        if subject is not None:
            payload["subject"] = subject
        if predicate is not None:
            payload["predicate"] = predicate
        if context is not None:
            payload["context"] = context
        return self._call("/api/facts/recall", payload)

    def sparql_query(
        self,
        query: str,
        *,
        validate: bool = True,
    ) -> dict[str, Any]:
        return self._call("/api/sparql", {"query": query, "validate": validate})

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
        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if content is not None:
            payload["content"] = content
        if lifecycle is not None:
            payload["lifecycle"] = lifecycle
        if tags is not None:
            payload["tags"] = tags
        return self._call(f"/api/ideas/{idea_id}/update", payload)

    def set_lifecycle(
        self,
        idea_id: str,
        new_state: str,
        *,
        reason: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"new_state": new_state}
        if reason:
            payload["reason"] = reason
        return self._call(f"/api/ideas/{idea_id}/lifecycle", payload)
