"""Client for the public n8n template API (api.n8n.io).

Fetches community templates for knowledge base enrichment.
Separate from n8n_client.py which talks to the local n8n instance.
"""

import asyncio
from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

# Rate limiting
_semaphore = asyncio.Semaphore(5)
_DELAY_BETWEEN_FETCHES = 0.2  # seconds


def _get_client() -> httpx.AsyncClient:
    """Create an HTTP client for the n8n template API."""
    return httpx.AsyncClient(
        base_url=settings.n8n_template_api_url,
        timeout=30.0,
        headers={"Accept": "application/json"},
    )


async def search_templates(
    query: str | None = None,
    category: str | None = None,
    page: int = 1,
    rows: int = 20,
) -> dict[str, Any]:
    """
    Search n8n community templates.

    Returns dict with keys: totalWorkflows, workflows, filters
    """
    params: dict[str, Any] = {"page": page, "rows": rows}
    if query:
        params["search"] = query
    if category:
        params["category"] = category

    async with _semaphore:
        async with _get_client() as client:
            try:
                resp = await client.get("/search", params=params)
                resp.raise_for_status()
                data = resp.json()
                logger.debug(
                    "Template search",
                    query=query,
                    category=category,
                    total=data.get("totalWorkflows"),
                    returned=len(data.get("workflows", [])),
                )
                return data
            except httpx.HTTPStatusError as e:
                logger.warning("Template search failed", status=e.response.status_code)
                raise
            except httpx.HTTPError as e:
                logger.warning("Template search error", error=str(e))
                raise


async def get_template(template_id: int) -> dict[str, Any] | None:
    """
    Fetch full template detail including workflow JSON.

    Returns the full template response or None if not found.
    """
    async with _semaphore:
        async with _get_client() as client:
            try:
                resp = await client.get(f"/workflows/{template_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
                logger.debug(
                    "Template fetched",
                    template_id=template_id,
                    name=data.get("workflow", {}).get("name"),
                )
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    logger.warning("Template not found", template_id=template_id)
                    return None
                raise
            except httpx.HTTPError as e:
                logger.warning("Template fetch error", template_id=template_id, error=str(e))
                raise


async def get_categories() -> list[dict[str, Any]]:
    """Extract available template categories from the search API filters."""
    data = await search_templates(page=1, rows=1)
    filters = data.get("filters", [])
    for f in filters:
        if f.get("field_name") == "category":
            return [
                {"name": c["value"], "count": c["count"]}
                for c in f.get("counts", [])
                if c.get("value")
            ]
    return []


async def fetch_templates_batch(
    template_ids: list[int],
) -> list[dict[str, Any]]:
    """
    Fetch multiple templates with rate limiting.

    Returns list of successfully fetched templates.
    """
    results = []
    for i, tid in enumerate(template_ids):
        try:
            data = await get_template(tid)
            if data:
                results.append(data)
        except Exception as e:
            logger.warning("Failed to fetch template", template_id=tid, error=str(e))

        # Rate limit delay between fetches
        if i < len(template_ids) - 1:
            await asyncio.sleep(_DELAY_BETWEEN_FETCHES)

    logger.info(
        "Batch fetch complete",
        requested=len(template_ids),
        fetched=len(results),
    )
    return results


async def fetch_popular_templates(
    max_count: int = 100,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch the most popular templates (by totalViews).

    Paginates through search results and fetches full details.
    """
    # First, collect template IDs from search
    all_ids = []
    page = 1
    rows = 50

    while len(all_ids) < max_count:
        data = await search_templates(category=category, page=page, rows=rows)
        workflows = data.get("workflows", [])
        if not workflows:
            break

        # Sort by views (highest first) and collect IDs
        workflows.sort(key=lambda w: w.get("totalViews", 0), reverse=True)
        for wf in workflows:
            if len(all_ids) >= max_count:
                break
            all_ids.append(wf["id"])

        page += 1
        await asyncio.sleep(_DELAY_BETWEEN_FETCHES)

    logger.info("Collected template IDs", count=len(all_ids), category=category)

    # Fetch full details in batches
    batch_size = settings.template_import_batch_size
    results = []
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i : i + batch_size]
        batch_results = await fetch_templates_batch(batch)
        results.extend(batch_results)

    return results
