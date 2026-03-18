"""
Workflow endpoints — CRUD + n8n proxy operations.

Provides both local workflow management and n8n server proxy.
"""

from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm_client import check_ollama_status, pull_ollama_model
from app.core.n8n_client import N8nClientError, n8n_client
from app.workflow.node_registry import NODE_CATALOG, get_node_catalog_summary, search_nodes
from app.workflow.validator import WorkflowValidator

logger = structlog.get_logger()
router = APIRouter()
validator = WorkflowValidator()


# ─── Request/Response Models ───

class ValidateRequest(BaseModel):
    workflow_json: dict[str, Any]


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str]


class DeployRequest(BaseModel):
    workflow_json: dict[str, Any]
    name: Optional[str] = None
    activate: bool = False


class DeployResponse(BaseModel):
    n8n_workflow_id: str
    n8n_editor_url: str
    active: bool


class NodeInfo(BaseModel):
    type: str
    display_name: str
    category: str
    description: str
    is_trigger: bool
    keywords: list[str]


# ─── Validation ───

@router.post("/workflows/validate", response_model=ValidateResponse)
async def validate_workflow(request: ValidateRequest):
    """Validate a workflow JSON without deploying."""
    errors = validator.validate(request.workflow_json)
    return ValidateResponse(valid=len(errors) == 0, errors=errors)


# ─── Deploy to n8n ───

@router.post("/workflows/deploy", response_model=DeployResponse)
async def deploy_workflow(request: DeployRequest):
    """Deploy a workflow to n8n server."""
    # Validate first
    errors = validator.validate(request.workflow_json)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Invalid workflow", "errors": errors},
        )

    try:
        # Override name if provided
        workflow = request.workflow_json.copy()
        if request.name:
            workflow["name"] = request.name

        # Create on n8n
        result = await n8n_client.create_workflow(workflow)
        n8n_id = result["id"]

        # Activate if requested
        if request.activate:
            await n8n_client.activate_workflow(n8n_id)

        return DeployResponse(
            n8n_workflow_id=n8n_id,
            n8n_editor_url=n8n_client.get_workflow_editor_url(n8n_id),
            active=request.activate,
        )
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ─── n8n Proxy Endpoints ───

@router.get("/n8n/workflows")
async def list_n8n_workflows(
    active: Optional[bool] = None,
    name: Optional[str] = None,
    limit: int = Query(default=50, le=100),
):
    """List workflows from n8n server. Merges isArchived from n8n + 'archived' tag."""
    try:
        result = await n8n_client.list_workflows(active=active, name=name, limit=limit)
        # Ensure isArchived reflects both native field and 'archived' tag
        for wf in result.get("data", []):
            if not wf.get("isArchived"):
                wf["isArchived"] = _has_archived_tag(wf.get("tags", []))
        return result
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/n8n/workflows/{workflow_id}")
async def get_n8n_workflow(workflow_id: str):
    """Get a specific workflow from n8n server."""
    try:
        return await n8n_client.get_workflow(workflow_id)
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/n8n/workflows/{workflow_id}")
async def delete_n8n_workflow(workflow_id: str):
    """Delete a workflow from n8n server."""
    try:
        return await n8n_client.delete_workflow(workflow_id)
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/n8n/workflows/{workflow_id}/activate")
async def activate_n8n_workflow(workflow_id: str):
    """Activate (publish) a workflow on n8n."""
    try:
        return await n8n_client.activate_workflow(workflow_id)
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/n8n/workflows/{workflow_id}/deactivate")
async def deactivate_n8n_workflow(workflow_id: str):
    """Deactivate a workflow on n8n."""
    try:
        return await n8n_client.deactivate_workflow(workflow_id)
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _ensure_tag(tag_name: str) -> dict[str, Any]:
    """Get or create a tag by name on n8n."""
    tags_resp = await n8n_client.list_tags()
    tag_list = tags_resp.get("data", []) if isinstance(tags_resp, dict) else tags_resp
    for tag in tag_list:
        if tag.get("name") == tag_name:
            return tag
    # Create new tag
    async with n8n_client._client() as client:
        response = await client.post("/tags", json={"name": tag_name})
        return await n8n_client._handle_response(response)


def _has_archived_tag(tags: list) -> bool:
    """Check if tags list contains 'archived' tag."""
    return any(
        isinstance(t, dict) and t.get("name") == "archived"
        for t in (tags or [])
    )


@router.post("/n8n/workflows/{workflow_id}/archive")
async def archive_n8n_workflow(workflow_id: str):
    """Archive a workflow on n8n (deactivate + add 'archived' tag)."""
    try:
        workflow = await n8n_client.get_workflow(workflow_id)

        # Deactivate if active
        if workflow.get("active"):
            await n8n_client.deactivate_workflow(workflow_id)

        # Ensure "archived" tag exists
        archived_tag = await _ensure_tag("archived")

        # Get current tags and add "archived" if not present
        tags = workflow.get("tags", []) or []
        tag_ids = [{"id": t["id"]} for t in tags if isinstance(t, dict) and t.get("id")]
        if not any(t["id"] == archived_tag["id"] for t in tag_ids):
            tag_ids.append({"id": archived_tag["id"]})

        # Use PUT /workflows/{id}/tags to assign tags
        async with n8n_client._client() as client:
            response = await client.put(f"/workflows/{workflow_id}/tags", json=tag_ids)
            await n8n_client._handle_response(response)

        logger.info("Workflow archived on n8n", workflow_id=workflow_id)
        return {"id": workflow_id, "isArchived": True, "status": "archived"}
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/n8n/workflows/{workflow_id}/unarchive")
async def unarchive_n8n_workflow(workflow_id: str):
    """Unarchive a workflow on n8n (remove 'archived' tag)."""
    try:
        workflow = await n8n_client.get_workflow(workflow_id)

        # Get current tags, remove "archived"
        tags = workflow.get("tags", []) or []
        tag_ids = [
            {"id": t["id"]}
            for t in tags
            if isinstance(t, dict) and t.get("id") and t.get("name") != "archived"
        ]

        # Use PUT /workflows/{id}/tags to assign tags
        async with n8n_client._client() as client:
            response = await client.put(f"/workflows/{workflow_id}/tags", json=tag_ids)
            await n8n_client._handle_response(response)

        logger.info("Workflow unarchived on n8n", workflow_id=workflow_id)
        return {"id": workflow_id, "isArchived": False, "status": "unarchived"}
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/n8n/executions")
async def list_n8n_executions(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
):
    """List execution history from n8n."""
    try:
        return await n8n_client.list_executions(
            workflow_id=workflow_id,
            status=status,
            limit=limit,
        )
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ─── Node Registry ───

@router.get("/nodes")
async def list_nodes(
    search: Optional[str] = None,
    category: Optional[str] = None,
):
    """List available n8n node types from the registry."""
    if search:
        nodes = search_nodes(search)
    elif category:
        from app.workflow.node_registry import get_nodes_by_category
        nodes = get_nodes_by_category(category)
    else:
        nodes = list(NODE_CATALOG.values())

    return [
        NodeInfo(
            type=n.type,
            display_name=n.display_name,
            category=n.category,
            description=n.description,
            is_trigger=n.is_trigger,
            keywords=n.keywords,
        )
        for n in nodes
    ]


# ─── Workflow Export ───

@router.get("/workflows/{workflow_id}/export")
async def export_workflow(workflow_id: str):
    """Export a workflow as downloadable JSON (fetched from n8n)."""
    from fastapi.responses import JSONResponse

    try:
        workflow = await n8n_client.get_workflow(workflow_id)
        # Remove server-specific fields for clean export
        export_data = {
            "name": workflow.get("name"),
            "nodes": workflow.get("nodes"),
            "connections": workflow.get("connections"),
            "settings": workflow.get("settings"),
        }
        return JSONResponse(
            content=export_data,
            headers={
                "Content-Disposition": f'attachment; filename="{workflow.get("name", "workflow")}.json"'
            },
        )
    except N8nClientError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ─── Ollama Management ───


@router.get("/ollama/status")
async def ollama_status():
    """Check Ollama server status and available models."""
    return await check_ollama_status()


@router.post("/ollama/pull")
async def ollama_pull_model(model_name: str | None = None):
    """Pull (download) a model to Ollama. Uses default model if none specified."""
    try:
        message = await pull_ollama_model(model_name)
        return {"status": "ok", "message": message}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm/info")
async def llm_info():
    """Get current LLM provider info."""
    info = {
        "provider": settings.llm_provider,
        "model": settings.ollama_model if settings.llm_provider == "ollama" else settings.anthropic_model,
    }
    if settings.llm_provider == "ollama":
        info["ollama"] = await check_ollama_status()
    return info


# ─── RAG Knowledge Base ───


@router.post("/rag/ingest")
async def rag_ingest():
    """Ingest all knowledge files into ChromaDB for RAG retrieval."""
    from app.rag.chroma_client import ingest_all_knowledge

    try:
        results = ingest_all_knowledge()
        total = sum(results.values())
        return {
            "status": "ok",
            "total_chunks": total,
            "files": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/search")
async def rag_search_endpoint(q: str = Query(..., description="Search query")):
    """Search the RAG knowledge base."""
    from app.rag.chroma_client import search

    try:
        context = search(q, n_results=5)
        return {
            "query": q,
            "context": context,
            "has_results": bool(context),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
