from fastapi import APIRouter

from app.config import settings
from app.core.llm_client import check_ollama_status

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    result = {
        "status": "ok",
        "version": "0.1.0",
        "environment": settings.app_env,
        "llm_provider": settings.llm_provider,
        "services": {
            "n8n": settings.n8n_base_url,
        },
    }

    if settings.llm_provider == "anthropic":
        result["services"]["model"] = settings.anthropic_model
    else:
        result["services"]["model"] = settings.ollama_model
        result["services"]["ollama"] = await check_ollama_status()

    return result
