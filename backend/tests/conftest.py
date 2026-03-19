"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_settings():
    from app.config import Settings

    s = Settings(
        n8n_base_url="http://localhost:5678",
        n8n_api_key="test-key",
        ollama_base_url="http://localhost:11434",
        openai_api_key="test-key",
        llm_provider="ollama",
        database_url="sqlite+aiosqlite:///test.db",
    )
    return s


@pytest.fixture
def sample_workflow():
    """A minimal valid n8n workflow JSON."""
    return {
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2.0,
                "position": [250, 300],
                "parameters": {"httpMethod": "POST", "path": "hook"},
            },
            {
                "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "name": "Send Slack",
                "type": "n8n-nodes-base.slack",
                "typeVersion": 2.2,
                "position": [500, 300],
                "parameters": {"channel": "#general", "text": "Hello"},
            },
        ],
        "connections": {
            "Webhook": {
                "main": [[{"node": "Send Slack", "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1"},
    }


@pytest.fixture
def n8n_workflow_response(sample_workflow):
    """A workflow response as returned by n8n API (with id added)."""
    wf = sample_workflow.copy()
    wf["id"] = "12345"
    wf["active"] = False
    wf["createdAt"] = "2024-01-01T00:00:00Z"
    wf["updatedAt"] = "2024-01-01T00:00:00Z"
    return wf
