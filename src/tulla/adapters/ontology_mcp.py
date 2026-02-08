"""Ontology MCP adapter – wraps ontology-server REST calls via HTTP.

Implements :class:`OntologyPort` by sending HTTP requests to the
ontology-server REST endpoints using :mod:`urllib`.

Endpoint mapping (server at ``http://localhost:8100``):
    GET  /facts?context=...&subject=...&predicate=...&limit=...
    POST /facts  (store_fact — JSON body)
    DELETE /facts/{fact_id}  (forget_fact)
    GET  /ideas?lifecycle=...&search=...&limit=...
    GET  /ideas/{idea_id}
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tulla.ports.ontology import OntologyPort

logger = logging.getLogger(__name__)


class OntologyMCPAdapter(OntologyPort):
    """Concrete :class:`OntologyPort` that talks to ontology-server via HTTP.

    Parameters:
        base_url: Base URL of the ontology-server (default ``"http://localhost:8100"``).
        api_key: Optional Bearer token for authentication. If not provided,
            reads from the ``ONTOLOGY_API_KEY`` environment variable.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8100",
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("ONTOLOGY_API_KEY", "")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Return common HTTP headers."""
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send an HTTP GET and return parsed JSON."""
        url = f"{self._base_url}{path}"
        if params:
            qs = urlencode({k: v for k, v in params.items() if v is not None})
            if qs:
                url = f"{url}?{qs}"
        req = Request(url, headers=self._headers())
        return self._do(req)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send an HTTP POST with JSON body and return parsed JSON."""
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers=self._headers())
        return self._do(req)

    def _delete(self, path: str) -> dict[str, Any]:
        """Send an HTTP DELETE and return parsed JSON."""
        url = f"{self._base_url}{path}"
        req = Request(url, method="DELETE", headers=self._headers())
        return self._do(req)

    def _do(self, req: Request) -> dict[str, Any]:
        """Execute a request, returning parsed JSON or an error dict."""
        try:
            with urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except URLError as exc:
            logger.error("Ontology-server %s %s failed: %s", req.get_method(), req.full_url, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # OntologyPort interface — Facts
    # ------------------------------------------------------------------

    def recall_facts(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        context: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        resp = self._get("/facts", {
            "subject": subject,
            "predicate": predicate,
            "context": context,
            "limit": limit,
        })
        # Server returns {"facts": [...]}, callers expect {"result": [...]}
        if "facts" in resp:
            resp["result"] = resp.pop("facts")
        return resp

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
        return self._post("/facts", payload)

    def forget_fact(self, fact_id: str) -> dict[str, Any]:
        return self._delete(f"/facts/{fact_id}")

    def forget_by_context(self, context: str) -> int:
        resp = self.recall_facts(context=context, limit=10000)
        facts = resp.get("result", [])
        count = 0
        for fact in facts:
            fid = fact.get("fact_id", "")
            if fid:
                self.forget_fact(fid)
                count += 1
        return count

    # ------------------------------------------------------------------
    # OntologyPort interface — Ideas
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
        return self._get("/ideas", {
            "lifecycle": lifecycle,
            "author": author,
            "tag": tag,
            "search": search,
            "limit": limit,
        })

    def get_idea(self, idea_id: str) -> dict[str, Any]:
        return self._get(f"/ideas/{idea_id}")

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
        return self._post(f"/ideas/{idea_id}/update", payload)

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
        return self._post(f"/ideas/{idea_id}/lifecycle", payload)

    # ------------------------------------------------------------------
    # OntologyPort interface — Direct triple manipulation
    # ------------------------------------------------------------------

    _PHASE_ONTOLOGY = "phase-ontology"

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        *,
        is_literal: bool = False,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        return self._post("/abox/triples", {
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "is_literal": is_literal,
        })

    def remove_triples_by_subject(
        self,
        subject: str,
        *,
        ontology: str | None = None,
    ) -> int:
        resp = self._post("/abox/triples/remove", {
            "subject": subject,
        })
        return resp.get("removed", 0)

    # ------------------------------------------------------------------
    # OntologyPort interface — SPARQL
    # ------------------------------------------------------------------

    def sparql_query(
        self,
        query: str,
        *,
        validate: bool = True,
    ) -> dict[str, Any]:
        qs = urlencode({"query": query})
        url = f"{self._base_url}/kg/sparql?{qs}"
        req = Request(url, data=b"", headers=self._headers(), method="POST")
        return self._do(req)

    # ------------------------------------------------------------------
    # OntologyPort interface — SHACL Validation
    # ------------------------------------------------------------------

    def validate_instance(
        self,
        instance_uri: str,
        shape_uri: str,
        *,
        ontology: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "instance_uri": instance_uri,
            "shape_uri": shape_uri,
        }
        if ontology is not None:
            payload["ontology"] = ontology
        return self._post("/validate", payload)
