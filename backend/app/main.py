import contextlib

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, conversations, health, workflows, ws
from app.config import settings
from app.db.session import close_db, init_db

logger = structlog.get_logger()


@contextlib.asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting LLM Workflow Builder", env=settings.app_env)
    await init_db()

    # Auto-ingest RAG knowledge base
    try:
        from app.rag.chroma_client import ingest_all_knowledge
        results = ingest_all_knowledge()
        logger.info("RAG knowledge base loaded", total_chunks=sum(results.values()))
    except Exception as e:
        logger.warning("RAG ingestion failed (non-critical)", error=str(e))

    yield
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        description="Create and edit n8n workflows using natural language",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    application.include_router(health.router, prefix="/api/v1", tags=["Health"])
    application.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
    application.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
    application.include_router(workflows.router, prefix="/api/v1", tags=["Workflows"])
    application.include_router(ws.router, prefix="/api/v1", tags=["WebSocket"])

    return application


app = create_app()
