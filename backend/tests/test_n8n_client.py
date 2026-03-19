"""Tests for n8n API client with mocked httpx."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core.n8n_client import N8nClient, N8nClientError


@pytest.fixture
def client():
    return N8nClient(base_url="http://localhost:5678", api_key="test-key")


class TestCreateWorkflow:
    @pytest.mark.asyncio
    async def test_create_workflow_success(self, client, sample_workflow, n8n_workflow_response):
        mock_response_list = MagicMock(spec=httpx.Response)
        mock_response_list.status_code = 200
        mock_response_list.json.return_value = {"data": []}

        mock_response_create = MagicMock(spec=httpx.Response)
        mock_response_create.status_code = 200
        mock_response_create.json.return_value = n8n_workflow_response

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response_list)
        mock_client.post = AsyncMock(return_value=mock_response_create)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_client", return_value=mock_client):
            result = await client.create_workflow(sample_workflow)

        assert result["id"] == "12345"
        assert result["name"] == "Test Workflow"

    @pytest.mark.asyncio
    async def test_create_workflow_duplicate_detection(self, client, sample_workflow):
        """When a workflow with the same name exists, update instead of create."""
        existing_wf = {**sample_workflow, "id": "existing-123"}
        mock_response_list = MagicMock(spec=httpx.Response)
        mock_response_list.status_code = 200
        mock_response_list.json.return_value = {
            "data": [{"id": "existing-123", "name": "Test Workflow"}]
        }

        mock_response_update = MagicMock(spec=httpx.Response)
        mock_response_update.status_code = 200
        mock_response_update.json.return_value = existing_wf

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response_list)
        mock_client.put = AsyncMock(return_value=mock_response_update)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_client", return_value=mock_client):
            result = await client.create_workflow(sample_workflow)

        assert result["id"] == "existing-123"
        # Should have called PUT (update), not POST (create)
        mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_raises_n8n_client_error(self, client):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"message": "Invalid workflow"}
        mock_response.url = "http://localhost:5678/api/v1/workflows"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_client", return_value=mock_client):
            with pytest.raises(N8nClientError) as exc_info:
                await client.get_workflow("nonexistent")

        assert exc_info.value.status_code == 400
        assert "Invalid workflow" in exc_info.value.detail


class TestGetWorkflowEditorUrl:
    def test_uses_public_url(self, client):
        with patch("app.core.n8n_client.settings") as mock_settings:
            mock_settings.n8n_public_url = "http://localhost:5678"
            url = client.get_workflow_editor_url("12345")
        assert url == "http://localhost:5678/workflow/12345"
        assert "host.docker.internal" not in url

    def test_replaces_internal_hostname(self, client):
        with patch("app.core.n8n_client.settings") as mock_settings:
            mock_settings.n8n_public_url = "http://localhost:5678"
            url = client.get_workflow_editor_url("abc-123")
        assert url == "http://localhost:5678/workflow/abc-123"


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_true_on_200(self, client):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_client", return_value=mock_client):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self, client):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(client, "_client", return_value=mock_client):
            result = await client.health_check()

        assert result is False
