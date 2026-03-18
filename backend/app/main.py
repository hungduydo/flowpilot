import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health, workflows
from app.config import settings

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        description="Create and edit n8n workflows using natural language",
        version="0.1.0",
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
    application.include_router(workflows.router, prefix="/api/v1", tags=["Workflows"])

    @application.on_event("startup")
    async def startup():
        logger.info("Starting LLM Workflow Builder", env=settings.app_env)

    return application


app = create_app()
