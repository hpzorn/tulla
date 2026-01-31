"""Dashboard route handlers.

Ports all 12 routes from the standalone viewer ``app.py`` into the
dashboard sub-package.  Each handler obtains a :class:`DashboardService`
from ``request.app.state``, calls the appropriate service method, and
renders a Jinja2 template.

Routes
------
- ``GET /``                              — dashboard landing page
- ``GET /instances``                     — instance list (T-Box browser)
- ``GET /instances/{uri:path}``          — instance detail
- ``GET /ideas``                         — ideas list (A-Box)
- ``GET /ideas/{idea_id}``               — idea detail
- ``GET /facts``                         — facts browser landing
- ``GET /facts/{context}``               — facts for a context
- ``GET /prds``                          — PRD context list
- ``GET /prds/{context}``                — PRD requirement graph
- ``GET /prds/{context}/{subject:path}`` — single requirement detail
- ``GET /partials/instance-rows``        — HTMX partial: instance rows
- ``GET /partials/instance-properties``  — HTMX partial: instance props
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .services import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LIFECYCLE_ORDER = [
    "seed", "backlog", "researching", "planning", "implementing",
    "validating", "completed", "archived", "rejected", "blocked",
]


def _get_service(request: Request) -> DashboardService:
    """Build a :class:`DashboardService` from ``request.app.state`` stores."""
    state = request.app.state
    return DashboardService(
        ontology_store=state.ontology_store,
        kg_store=state.kg_store,
        agent_memory=state.agent_memory,
        ideas_store=state.ideas_store,
    )


# ---------------------------------------------------------------------------
# Dashboard landing page
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the dashboard landing page with summary stats."""
    service = _get_service(request)
    summary = service.get_dashboard_summary()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, **summary},
    )


# ---------------------------------------------------------------------------
# Instance browser (T-Box)
# ---------------------------------------------------------------------------


@router.get("/instances", response_class=HTMLResponse)
async def instance_list(
    request: Request,
    class_uri: str | None = None,
    ontology_uri: str | None = None,
) -> HTMLResponse:
    """Render the instance list, optionally filtered by class or ontology."""
    service = _get_service(request)
    classes = service.list_classes(ontology_uri=ontology_uri)
    instances = (
        service.list_instances(class_uri=class_uri, ontology_uri=ontology_uri)
        if class_uri
        else []
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "instance_list.html",
        {
            "request": request,
            "instances": instances,
            "classes": classes,
            "selected_class": class_uri,
            "selected_ontology": ontology_uri,
        },
    )


@router.get("/instances/{instance_uri:path}", response_class=HTMLResponse)
async def instance_detail(
    request: Request,
    instance_uri: str,
    ontology_uri: str | None = None,
) -> HTMLResponse:
    """Render the detail view for a single instance."""
    service = _get_service(request)
    detail = service.get_instance_detail(
        instance_uri=instance_uri,
        ontology_uri=ontology_uri,
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "instance_detail.html",
        {"request": request, **detail},
    )


# ---------------------------------------------------------------------------
# Ideas browser (A-Box)
# ---------------------------------------------------------------------------


@router.get("/ideas", response_class=HTMLResponse)
async def idea_list(
    request: Request,
    lifecycle: str | None = None,
    search: str | None = None,
) -> HTMLResponse:
    """Render the ideas list with optional filtering."""
    service = _get_service(request)
    ideas = service.list_ideas(lifecycle=lifecycle, search=search)
    lifecycle_counts = service.get_idea_lifecycle_summary()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "idea_list.html",
        {
            "request": request,
            "ideas": ideas,
            "lifecycle_counts": lifecycle_counts,
            "lifecycle_order": LIFECYCLE_ORDER,
            "selected_lifecycle": lifecycle,
            "search_query": search or "",
        },
    )


@router.get("/ideas/{idea_id}", response_class=HTMLResponse)
async def idea_detail(request: Request, idea_id: str) -> HTMLResponse:
    """Render the detail view for a single idea."""
    service = _get_service(request)
    detail = service.get_idea_detail(idea_id)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "idea_detail.html",
        {"request": request, "idea": detail},
    )


# ---------------------------------------------------------------------------
# Facts browser
# ---------------------------------------------------------------------------


@router.get("/facts", response_class=HTMLResponse)
async def facts_browser(request: Request) -> HTMLResponse:
    """Render the facts browser landing page listing all contexts."""
    service = _get_service(request)
    contexts = service.list_fact_contexts()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "facts_browser.html",
        {"request": request, "contexts": contexts},
    )


@router.get("/facts/{context}", response_class=HTMLResponse)
async def facts_context(
    request: Request,
    context: str,
    subject: str | None = None,
) -> HTMLResponse:
    """Render facts for a context, optionally filtered by subject."""
    service = _get_service(request)
    if subject:
        facts = service.list_facts(context=context, subject=subject)
        subjects: list[str] = []
    else:
        subjects = service.get_fact_subjects(context)
        facts: list = []
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "facts_context.html",
        {
            "request": request,
            "context": context,
            "subjects": subjects,
            "facts": facts,
            "selected_subject": subject,
        },
    )


# ---------------------------------------------------------------------------
# PRD / requirements browser
# ---------------------------------------------------------------------------


@router.get("/prds", response_class=HTMLResponse)
async def prd_list(request: Request) -> HTMLResponse:
    """Render the list of all PRD contexts."""
    service = _get_service(request)
    contexts = service.list_prd_contexts()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "prd_list.html",
        {"request": request, "contexts": contexts},
    )


@router.get("/prds/{context}", response_class=HTMLResponse)
async def prd_detail(request: Request, context: str) -> HTMLResponse:
    """Render the requirement list / dependency graph for a PRD."""
    service = _get_service(request)
    requirements = service.get_prd_requirements(context)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "prd_detail.html",
        {
            "request": request,
            "context": context,
            "requirements": requirements,
        },
    )


@router.get("/prds/{context}/{subject:path}", response_class=HTMLResponse)
async def requirement_detail(
    request: Request,
    context: str,
    subject: str,
) -> HTMLResponse:
    """Render the detail view for a single requirement."""
    service = _get_service(request)
    detail = service.get_requirement_detail(context, subject)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "requirement_detail.html",
        {"request": request, **detail},
    )


# ---------------------------------------------------------------------------
# HTMX partial endpoints (HTML fragments, no base layout)
# ---------------------------------------------------------------------------


@router.get("/partials/instance-rows", response_class=HTMLResponse)
async def partial_instance_rows(
    request: Request,
    class_uri: str | None = None,
    ontology_uri: str | None = None,
) -> HTMLResponse:
    """Return instance table rows for HTMX swap."""
    service = _get_service(request)
    instances = (
        service.list_instances(class_uri=class_uri, ontology_uri=ontology_uri)
        if class_uri
        else []
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/instance_rows.html",
        {"request": request, "instances": instances},
    )


@router.get("/partials/instance-properties", response_class=HTMLResponse)
async def partial_instance_properties(
    request: Request,
    instance_uri: str,
    ontology_uri: str | None = None,
) -> HTMLResponse:
    """Return instance properties table for HTMX swap."""
    service = _get_service(request)
    detail = service.get_instance_detail(
        instance_uri=instance_uri,
        ontology_uri=ontology_uri,
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/instance_properties.html",
        {"request": request, **detail},
    )
