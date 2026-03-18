"""
n8n REST API Client

Communicates with a self-hosted n8n instance to create, read, update,
delete, activate, and deactivate workflows programmatically.

Auth: X-N8N-API-KEY header
API Spec: /Users/user/Downloads/n8n-api.json (OpenAPI 3.0)
"""

from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class N8nClientError(Exception):
    """Raised when n8n API returns an error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"n8n API error ({status_code}): {detail}")


class N8nClient:
    """Async client for n8n REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or settings.n8n_base_url).rstrip("/")
        self.api_key = api_key or settings.n8n_api_key
        self._headers = {
            "X-N8N-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self.base_url}/api/v1",
            headers=self._headers,
            timeout=30.0,
        )

    async def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle n8n API response, raising on errors."""
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.text)
            except Exception:
                detail = response.text
            logger.error(
                "n8n API error",
                status_code=response.status_code,
                detail=detail,
                url=str(response.url),
            )
            raise N8nClientError(response.status_code, detail)
        return response.json()

    # ─── Workflow CRUD ───

    async def create_workflow(self, workflow_json: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new workflow on n8n.
        If a workflow with the same name exists, update it instead of creating a duplicate.

        POST /api/v1/workflows
        Body: { name, nodes, connections, settings }
        Returns: Created/updated workflow with id
        """
        # Check for existing workflow with same name to avoid duplicates
        wf_name = workflow_json.get("name", "")
        if wf_name:
            try:
                existing = await self.list_workflows(name=wf_name)
                for wf in existing.get("data", []):
                    if wf.get("name") == wf_name:
                        logger.info(
                            "Workflow with same name exists, updating instead",
                            existing_id=wf["id"],
                            name=wf_name,
                        )
                        return await self.update_workflow(wf["id"], workflow_json)
            except Exception:
                pass  # If check fails, proceed with create

        async with self._client() as client:
            response = await client.post("/workflows", json=workflow_json)
            result = await self._handle_response(response)
            logger.info(
                "Workflow created on n8n",
                workflow_id=result.get("id"),
                name=result.get("name"),
            )
            return result

    async def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        """
        Get a workflow by ID.

        GET /api/v1/workflows/{id}
        Returns: Full workflow object with nodes, connections, settings
        """
        async with self._client() as client:
            response = await client.get(f"/workflows/{workflow_id}")
            return await self._handle_response(response)

    async def update_workflow(
        self, workflow_id: str, workflow_json: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an existing workflow (full replace).

        PUT /api/v1/workflows/{id}
        Body: Complete workflow JSON (partial updates NOT supported)
        Note: If workflow is active, updated version is auto-republished
        """
        async with self._client() as client:
            response = await client.put(f"/workflows/{workflow_id}", json=workflow_json)
            result = await self._handle_response(response)
            logger.info(
                "Workflow updated on n8n",
                workflow_id=workflow_id,
                name=result.get("name"),
            )
            return result

    async def delete_workflow(self, workflow_id: str) -> dict[str, Any]:
        """
        Delete a workflow.

        DELETE /api/v1/workflows/{id}
        """
        async with self._client() as client:
            response = await client.delete(f"/workflows/{workflow_id}")
            result = await self._handle_response(response)
            logger.info("Workflow deleted from n8n", workflow_id=workflow_id)
            return result

    async def list_workflows(
        self,
        active: bool | None = None,
        tags: str | None = None,
        name: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """
        List all workflows.

        GET /api/v1/workflows
        Query params: active, tags, name, limit, cursor
        Returns: { data: [...], nextCursor: "..." }
        """
        params: dict[str, Any] = {"limit": limit}
        if active is not None:
            params["active"] = active
        if tags:
            params["tags"] = tags
        if name:
            params["name"] = name
        if cursor:
            params["cursor"] = cursor

        async with self._client() as client:
            response = await client.get("/workflows", params=params)
            return await self._handle_response(response)

    # ─── Workflow Lifecycle ───

    async def activate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """
        Activate (publish) a workflow.

        POST /api/v1/workflows/{id}/activate
        """
        async with self._client() as client:
            response = await client.post(f"/workflows/{workflow_id}/activate")
            result = await self._handle_response(response)
            logger.info("Workflow activated on n8n", workflow_id=workflow_id)
            return result

    async def deactivate_workflow(self, workflow_id: str) -> dict[str, Any]:
        """
        Deactivate a workflow.

        POST /api/v1/workflows/{id}/deactivate
        """
        async with self._client() as client:
            response = await client.post(f"/workflows/{workflow_id}/deactivate")
            result = await self._handle_response(response)
            logger.info("Workflow deactivated on n8n", workflow_id=workflow_id)
            return result

    # ─── Workflow Versions ───

    async def get_workflow_version(
        self, workflow_id: str, version_id: str
    ) -> dict[str, Any]:
        """
        Get a specific version of a workflow.

        GET /api/v1/workflows/{id}/{versionId}
        """
        async with self._client() as client:
            response = await client.get(f"/workflows/{workflow_id}/{version_id}")
            return await self._handle_response(response)

    # ─── Executions ───

    async def list_executions(
        self,
        workflow_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """
        List execution history.

        GET /api/v1/executions
        Query params: workflowId, status, limit, cursor
        Status values: canceled, crashed, error, new, running, success, unknown, waiting
        """
        params: dict[str, Any] = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor

        async with self._client() as client:
            response = await client.get("/executions", params=params)
            return await self._handle_response(response)

    async def get_execution(
        self, execution_id: str, include_data: bool = True
    ) -> dict[str, Any]:
        """
        Get a specific execution.

        GET /api/v1/executions/{id}
        """
        params = {"includeData": include_data}
        async with self._client() as client:
            response = await client.get(f"/executions/{execution_id}", params=params)
            return await self._handle_response(response)

    # ─── Credentials ───

    async def list_credentials(self) -> dict[str, Any]:
        """
        List all credentials (secrets not included).

        GET /api/v1/credentials
        """
        async with self._client() as client:
            response = await client.get("/credentials")
            return await self._handle_response(response)

    # ─── Tags ───

    async def list_tags(self) -> dict[str, Any]:
        """
        List all tags.

        GET /api/v1/tags
        """
        async with self._client() as client:
            response = await client.get("/tags")
            return await self._handle_response(response)

    # ─── Utility ───

    async def health_check(self) -> bool:
        """Check if n8n is reachable."""
        try:
            async with self._client() as client:
                response = await client.get("/workflows", params={"limit": 1})
                return response.status_code == 200
        except Exception:
            return False

    def get_workflow_editor_url(self, workflow_id: str) -> str:
        """Get the direct URL to open workflow in n8n editor (browser-accessible)."""
        return f"{settings.n8n_public_url}/workflow/{workflow_id}"


# Singleton instance
n8n_client = N8nClient()
