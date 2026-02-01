"""Combined FastAPI + MCP application.

This module provides HTTP endpoints alongside the MCP server.
MCP is served via SSE at /sse for multi-client access.
"""

from typing import Any, TYPE_CHECKING
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..auth import StaticTokenVerifier
from ..config import Settings
from ..core.store import OntologyStore
from ..core.validation import SHACLValidator
from ..mcp.server import create_mcp_server

if TYPE_CHECKING:
    from knowledge_graph import KnowledgeGraphStore

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger(f"{__name__}.audit")


def create_app(
    settings: Settings,
    store: OntologyStore,
    validator: SHACLValidator,
    kg_store: "KnowledgeGraphStore | None" = None
) -> FastAPI:
    """Create combined FastAPI application with MCP SSE support.

    Args:
        settings: Server configuration
        store: Initialized ontology store
        validator: SHACL validator instance
        kg_store: Optional knowledge graph store for A-Box functionality

    Returns:
        Configured FastAPI application with MCP mounted at /sse
    """
    app = FastAPI(
        title="Ontology Server",
        description="Unified MCP and REST API for ontology management",
        version="0.1.0",
    )

    # Store references for route handlers
    app.state.store = store
    app.state.validator = validator
    app.state.settings = settings

    # CORS middleware for web clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Bearer token authentication middleware (only when api_key is configured)
    if settings.api_key:
        verifier = StaticTokenVerifier(settings.api_key)

        class BearerAuthMiddleware(BaseHTTPMiddleware):
            AUTH_EXEMPT_PATHS = {"/health"}

            async def dispatch(self, request: Request, call_next):
                if request.url.path in self.AUTH_EXEMPT_PATHS:
                    return await call_next(request)

                auth_header = request.headers.get("authorization", "")
                if not auth_header.startswith("Bearer "):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Missing or invalid Authorization header"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                token = auth_header[7:]  # strip "Bearer "
                access_token = await verifier.verify_token(token)
                if access_token is None:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid bearer token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                audit_logger.info(
                    "Authenticated request: %s %s client=%s",
                    request.method,
                    request.url.path,
                    access_token.client_id,
                )
                return await call_next(request)

        app.add_middleware(BearerAuthMiddleware)
        logger.info("Bearer token authentication enabled")

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        ontologies = store.list_ontologies()
        return {
            "status": "healthy",
            "ontology_count": len(ontologies),
            "total_triples": len(store),
        }

    # Basic ontology listing (Phase 3 will add full REST CRUD)
    @app.get("/ontologies")
    async def list_ontologies() -> list[dict[str, Any]]:
        """List all loaded ontologies."""
        return store.list_ontologies()

    @app.get("/ontologies/{uri:path}")
    async def get_ontology(uri: str) -> dict[str, Any]:
        """Get ontology by URI."""
        full_uri = f"ontology://{uri}"
        ttl = store.get_ontology_ttl(full_uri)
        if not ttl:
            return {"error": f"Ontology not found: {full_uri}"}
        return {"uri": full_uri, "content": ttl}

    # Basic SPARQL endpoint
    @app.post("/sparql")
    async def sparql_query(query: str, ontology_uri: str | None = None) -> dict[str, Any]:
        """Execute SPARQL query."""
        try:
            results = store.query(query, ontology_uri)
            output = []
            for row in results:
                row_dict = {}
                for var in row.labels:
                    value = row[var]
                    row_dict[str(var)] = str(value) if value else None
                output.append(row_dict)
            return {"results": output, "count": len(output)}
        except Exception as e:
            return {"error": str(e)}

    # A-Box facts endpoint (exposes memory store for the dashboard)
    if kg_store is not None:
        from knowledge_graph.core.memory import AgentMemory
        agent_memory = AgentMemory(kg_store)
        app.state.kg_store = kg_store
        app.state.agent_memory = agent_memory

        @app.get("/facts")
        async def list_facts(
            context: str | None = None,
            subject: str | None = None,
            predicate: str | None = None,
            limit: int = 200,
        ) -> dict[str, Any]:
            """Query facts from the A-Box memory store."""
            try:
                facts = agent_memory.recall(
                    subject=subject,
                    predicate=predicate,
                    context=context,
                    limit=limit,
                )
                return {"facts": facts, "count": len(facts)}
            except Exception as e:
                return {"error": str(e)}

        @app.get("/facts/stats")
        async def facts_stats() -> dict[str, Any]:
            """Get A-Box memory store statistics."""
            try:
                return {
                    "fact_count": agent_memory.count_facts(),
                    "contexts": agent_memory.get_all_contexts(),
                    "unique_subjects": agent_memory.get_subjects(),
                }
            except Exception as e:
                return {"error": str(e)}

        # -- Ideas endpoints (SKOS+DC in default graph) --------------------

        from knowledge_graph.core.ideas import IdeasStore
        ideas_store = IdeasStore(kg_store)
        app.state.ideas_store = ideas_store

        @app.get("/ideas")
        async def list_ideas(
            lifecycle: str | None = None,
            author: str | None = None,
            tag: str | None = None,
            search: str | None = None,
            limit: int = 100,
            offset: int = 0,
        ) -> dict[str, Any]:
            """List ideas with optional filters."""
            try:
                if search:
                    ideas = ideas_store.search_ideas(search, limit=limit)
                else:
                    ideas = ideas_store.list_ideas(
                        lifecycle=lifecycle,
                        author=author,
                        tag=tag,
                        limit=limit,
                        offset=offset,
                    )
                return {"ideas": ideas, "count": len(ideas)}
            except Exception as e:
                return {"error": str(e)}

        @app.get("/ideas/tags")
        async def list_idea_tags() -> dict[str, Any]:
            """List all idea tags with counts."""
            try:
                tags = ideas_store.get_all_tags()
                return {"tags": tags, "count": len(tags)}
            except Exception as e:
                return {"error": str(e)}

        @app.get("/ideas/{idea_id}")
        async def get_idea(idea_id: str) -> dict[str, Any]:
            """Get full idea detail by ID."""
            try:
                idea = ideas_store.get_idea(idea_id)
                if idea is None:
                    return {"error": f"Idea not found: {idea_id}"}
                from dataclasses import asdict
                data = asdict(idea)
                # Convert datetime fields to ISO strings
                for key in ("created", "lifecycle_updated", "captured_at"):
                    if data.get(key) is not None:
                        data[key] = data[key].isoformat()
                # Drop embedding (large, not useful for display)
                data.pop("embedding", None)
                return data
            except Exception as e:
                return {"error": str(e)}

        # -- Knowledge Graph SPARQL endpoint -------------------------------

        @app.post("/kg/sparql")
        async def kg_sparql_query(query: str) -> dict[str, Any]:
            """Execute SPARQL query against the knowledge graph.

            Queries across all KG graphs:
            - Default graph: Ideas (SKOS:Concept)
            - Named graph memory: Agent facts
            - Named graph wikidata: Wikidata cache
            """
            try:
                results = kg_store.query(query)
                return {
                    "variables": results.variables,
                    "bindings": results.bindings,
                    "count": len(results.bindings),
                }
            except Exception as e:
                return {"error": str(e)}

        # -- Dashboard sub-application ------------------------------------
        # Mount BEFORE the MCP catch-all so /dashboard/* routes resolve
        # before the Starlette "/" mount swallows them.
        from ..dashboard import create_dashboard_app

        dashboard_app = create_dashboard_app(
            ontology_store=store,
            kg_store=kg_store,
            agent_memory=agent_memory,
            ideas_store=ideas_store,
        )
        # Pass auth state so login route can verify tokens and set cookies
        if settings.api_key:
            dashboard_app.state.token_verifier = verifier
            dashboard_app.state.session_cookie_value = _session_cookie
        app.mount("/dashboard", dashboard_app)
        logger.info("Dashboard sub-application mounted at /dashboard")

    # Create MCP server with optional A-Box support
    mcp = create_mcp_server(settings, store, validator, kg_store)

    # Mount MCP SSE app for multi-client access
    # This enables Claude Code and other MCP clients to connect via HTTP
    app.mount("/", mcp.sse_app())

    logger.info("Created FastAPI application with MCP SSE at /sse")
    return app
