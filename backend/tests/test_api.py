"""Tests for API routes with FastAPI TestClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create app with mocked dependencies."""
    # Patch DB init and RAG before importing app
    with (
        patch("app.db.session.init_db", new_callable=AsyncMock),
        patch("app.db.session.close_db", new_callable=AsyncMock),
        patch("app.main.lifespan") as mock_lifespan,
    ):
        import contextlib

        @contextlib.asynccontextmanager
        async def noop_lifespan(app):
            yield

        mock_lifespan.side_effect = noop_lifespan

        from app.main import create_app

        application = create_app()
        # Override lifespan for testing
        application.router.lifespan_context = noop_lifespan
        yield application


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        with patch(
            "app.api.routes.health.check_ollama_status",
            new_callable=AsyncMock,
            return_value={"status": "online", "models": []},
        ):
            response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "llm_provider" in data


class TestChatEndpoint:
    def test_chat_success(self, client):
        mock_result = {
            "message": "Here is your workflow.",
            "conversation_id": "test-conv-id",
            "intent": "CREATE_WORKFLOW",
            "workflow": None,
        }

        mock_conv = MagicMock()
        mock_conv.id = "test-conv-id"

        with (
            patch(
                "app.api.routes.chat.conversation_engine"
            ) as mock_engine,
            patch("app.api.routes.chat.get_db") as mock_get_db,
        ):
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            mock_engine.get_or_create_conversation = AsyncMock(return_value=mock_conv)
            mock_engine.process_message = AsyncMock(return_value=mock_result)

            # Override the dependency
            from app.db.session import get_db

            client.app.dependency_overrides[get_db] = lambda: mock_db

            response = client.post(
                "/api/v1/chat",
                json={"message": "Create a webhook workflow"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Here is your workflow."
        assert data["intent"] == "CREATE_WORKFLOW"

        # Clean up
        client.app.dependency_overrides.clear()


class TestConversationsEndpoint:
    def test_list_conversations(self, client):
        mock_conv = MagicMock()
        mock_conv.id = "conv-123"
        mock_conv.title = "Test Conversation"
        mock_conv.created_at = "2024-01-01T00:00:00"
        mock_conv.updated_at = "2024-01-01T00:00:00"

        with (
            patch(
                "app.api.routes.conversations.ConversationRepository"
            ) as mock_repo,
            patch(
                "app.api.routes.conversations.MessageRepository"
            ) as mock_msg_repo,
        ):
            mock_repo.list_recent = AsyncMock(return_value=[mock_conv])
            mock_msg_repo.count = AsyncMock(return_value=5)

            from app.db.session import get_db

            mock_db = AsyncMock()
            client.app.dependency_overrides[get_db] = lambda: mock_db

            response = client.get("/api/v1/conversations")

        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data

        # Clean up
        client.app.dependency_overrides.clear()


class TestGlobalExceptionHandler:
    def test_unhandled_exception_returns_json(self, client):
        """The global exception handler should catch unhandled errors."""
        from app.db.session import get_db

        mock_db = AsyncMock()

        client.app.dependency_overrides[get_db] = lambda: mock_db

        with patch(
            "app.api.routes.chat.conversation_engine"
        ) as mock_engine:
            mock_engine.get_or_create_conversation = AsyncMock(
                side_effect=RuntimeError("Unexpected error")
            )

            response = client.post(
                "/api/v1/chat",
                json={"message": "test"},
            )

        # Should return 500 with JSON body (not HTML)
        assert response.status_code == 500
        data = response.json()
        assert "error" in data or "detail" in data

        # Clean up
        client.app.dependency_overrides.clear()
