import contextlib
import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, conversations, debug, health, knowledge, templates, workflows, ws
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

    # ── Request ID + Timing Middleware ──
    @application.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Let the global exception handler deal with it
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response

    # ── Global Exception Handler ──
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.exception(
            "unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": type(exc).__name__,
                "detail": str(exc),
                "request_id": request_id,
            },
        )

    # Routes
    application.include_router(health.router, prefix="/api/v1", tags=["Health"])
    application.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
    application.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
    application.include_router(workflows.router, prefix="/api/v1", tags=["Workflows"])
    application.include_router(ws.router, prefix="/api/v1", tags=["WebSocket"])
    application.include_router(knowledge.router, prefix="/api/v1", tags=["Knowledge"])
    application.include_router(templates.router, prefix="/api/v1", tags=["Templates"])
    application.include_router(debug.router, prefix="/api/v1", tags=["Debug"])

    return application


app = create_app()
