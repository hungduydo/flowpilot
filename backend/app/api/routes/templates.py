"""API routes for n8n community template browsing and import."""

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, async_session_factory
from app.db.repositories import N8nTemplateRepository
from app.core.n8n_template_client import (
    fetch_popular_templates,
    fetch_templates_batch,
    get_categories,
    get_template,
    search_templates,
)
from app.rag.chroma_client import ingest_template, remove_template_chunks
from app.rag.template_distiller import distill_template, extract_metadata

logger = structlog.get_logger()
router = APIRouter()


# ── Request models ──────────────────────────────────────────


class ImportRequest(BaseModel):
    template_ids: list[int]


class ImportPopularRequest(BaseModel):
    max_count: int = 50
    category: str | None = None


# ── Browse templates (proxy to n8n API) ────────────────────


@router.get("/templates/search")
async def search_n8n_templates(
    q: str | None = None,
    category: str | None = None,
    page: int = 1,
    rows: int = 20,
    session: AsyncSession = Depends(get_db),
):
    """Search n8n community templates."""
    try:
        data = await search_templates(query=q, category=category, page=page, rows=rows)
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch templates from n8n: {e}")

    # Enrich with import status
    imported_ids = await N8nTemplateRepository.get_imported_ids(session)
    workflows = data.get("workflows", [])
    for wf in workflows:
        wf["is_imported"] = wf.get("id") in imported_ids

    return data


@router.get("/templates/categories")
async def list_template_categories():
    """Get available template categories from n8n."""
    try:
        return await get_categories()
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch categories: {e}")


# ── Import templates ────────────────────────────────────────


async def _import_single_template(
    session: AsyncSession,
    template_data: dict,
) -> dict | None:
    """Import a single template: distill → ChromaDB → DB. Returns None if already imported."""
    meta = extract_metadata(template_data)
    n8n_id = meta.get("n8n_template_id")
    if not n8n_id:
        return None

    # Check if already imported
    existing = await N8nTemplateRepository.get_by_n8n_id(session, n8n_id)
    if existing:
        return None

    # Distill
    distilled = distill_template(template_data)
    if not distilled:
        logger.warning("Empty distillation", template_id=n8n_id)
        return None

    # Ingest into ChromaDB
    chroma_metadata = {
        "categories": ",".join(meta.get("categories", [])),
        "node_types": ",".join(meta.get("node_types", [])),
    }
    chroma_ids = ingest_template(n8n_id, distilled, chroma_metadata)

    # Save to DB
    template = await N8nTemplateRepository.create(
        session,
        n8n_template_id=n8n_id,
        name=meta["name"],
        description=meta.get("description"),
        categories=meta.get("categories"),
        node_types=meta.get("node_types"),
        node_count=meta.get("node_count", 0),
        total_views=meta.get("total_views", 0),
        distilled_text=distilled,
        chroma_doc_ids=chroma_ids,
    )

    return {
        "id": str(template.id),
        "n8n_template_id": n8n_id,
        "name": meta["name"],
        "chunks": len(chroma_ids),
    }


async def _background_import_templates(template_ids: list[int]):
    """Background task: fetch and import multiple templates."""
    logger.info("Background import started", count=len(template_ids))

    # Fetch full template data
    templates = await fetch_templates_batch(template_ids)

    imported = 0
    async with async_session_factory() as session:
        for tpl_data in templates:
            try:
                result = await _import_single_template(session, tpl_data)
                if result:
                    imported += 1
            except Exception as e:
                logger.warning(
                    "Failed to import template",
                    error=str(e),
                )
        await session.commit()

    logger.info("Background import complete", imported=imported, total=len(templates))


async def _background_import_popular(max_count: int, category: str | None):
    """Background task: fetch and import popular templates."""
    logger.info("Background popular import started", max_count=max_count, category=category)

    templates = await fetch_popular_templates(max_count=max_count, category=category)

    imported = 0
    async with async_session_factory() as session:
        for tpl_data in templates:
            try:
                result = await _import_single_template(session, tpl_data)
                if result:
                    imported += 1
            except Exception as e:
                logger.warning("Failed to import template", error=str(e))
        await session.commit()

    logger.info("Background popular import complete", imported=imported, total=len(templates))


@router.post("/templates/import", status_code=202)
async def import_templates(
    body: ImportRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
):
    """Import specific templates by ID. Runs in background."""
    if not body.template_ids:
        raise HTTPException(400, "No template IDs provided")
    if len(body.template_ids) > 200:
        raise HTTPException(400, "Max 200 templates per import")

    # Check which are already imported
    imported_ids = await N8nTemplateRepository.get_imported_ids(session)
    new_ids = [tid for tid in body.template_ids if tid not in imported_ids]

    if not new_ids:
        return {"message": "All templates already imported", "new_count": 0}

    background_tasks.add_task(_background_import_templates, new_ids)

    return {
        "message": f"Import started for {len(new_ids)} templates",
        "new_count": len(new_ids),
        "skipped": len(body.template_ids) - len(new_ids),
    }


@router.post("/templates/import/popular", status_code=202)
async def import_popular_templates(
    body: ImportPopularRequest,
    background_tasks: BackgroundTasks,
):
    """Import top popular templates. Runs in background."""
    if body.max_count > 500:
        raise HTTPException(400, "Max 500 templates per import")

    background_tasks.add_task(_background_import_popular, body.max_count, body.category)

    return {
        "message": f"Import started for top {body.max_count} templates",
        "category": body.category,
    }


# ── Manage imported templates ──────────────────────────────


@router.get("/templates/imported")
async def list_imported_templates(
    category: str | None = None,
    page: int = 1,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
):
    """List imported templates."""
    offset = (page - 1) * limit
    templates = await N8nTemplateRepository.list_all(
        session, category=category, limit=limit, offset=offset,
    )
    return [
        {
            "id": str(t.id),
            "n8n_template_id": t.n8n_template_id,
            "name": t.name,
            "description": t.description,
            "categories": t.categories,
            "node_types": t.node_types,
            "node_count": t.node_count,
            "total_views": t.total_views,
            "chunks": len(t.chroma_doc_ids or []),
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in templates
    ]


@router.get("/templates/imported/stats")
async def imported_template_stats(
    session: AsyncSession = Depends(get_db),
):
    """Get import statistics."""
    stats = await N8nTemplateRepository.get_stats(session)
    return stats


@router.delete("/templates/imported/{template_id}", status_code=204)
async def delete_imported_template(
    template_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Remove an imported template from DB and ChromaDB."""
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(400, "Invalid template ID")

    template = await N8nTemplateRepository.delete(session, tid)
    if not template:
        raise HTTPException(404, "Template not found")

    # Remove from ChromaDB
    if template.chroma_doc_ids:
        remove_template_chunks(template.chroma_doc_ids)


# ── Single template detail (must be LAST — {template_id} is a catch-all) ──


@router.get("/templates/{template_id}")
async def get_template_detail(template_id: int):
    """Get full template detail from n8n."""
    try:
        data = await get_template(template_id)
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch template: {e}")
    if not data:
        raise HTTPException(404, "Template not found")
    return data
