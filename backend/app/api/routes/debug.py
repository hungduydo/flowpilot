"""Debug API routes for inspecting intelligence pipeline context assembly."""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context_manager import estimate_tokens
from app.core.conversation_engine import ConversationEngine
from app.db.session import get_db

logger = structlog.get_logger()
router = APIRouter()


class ContextDebugRequest(BaseModel):
    message: str


@router.post("/debug/context")
async def debug_context(
    body: ContextDebugRequest,
    session: AsyncSession = Depends(get_db),
):
    """Inspect what context each intelligence layer would assemble for a given message.

    No LLM call is made — this is a read-only debug tool.
    """
    engine = ConversationEngine()
    keywords = engine._extract_keywords(body.message)

    # Assemble each layer independently
    rag_context = engine._get_rag_context(body.message)
    knowledge_context = await engine._get_knowledge_context(session, keywords)
    learning_context = await engine._get_learning_context(session, keywords)
    template_context = engine._get_template_context(body.message, keywords)

    total_text = rag_context + knowledge_context + learning_context + template_context

    return {
        "message": body.message,
        "keywords": sorted(keywords),
        "rag": {
            "text": rag_context,
            "tokens": estimate_tokens(rag_context),
            "budget": engine.TOKEN_BUDGET_RAG,
        },
        "knowledge_notes": {
            "text": knowledge_context,
            "tokens": estimate_tokens(knowledge_context),
            "budget": engine.TOKEN_BUDGET_KNOWLEDGE,
        },
        "learning_records": {
            "text": learning_context,
            "tokens": estimate_tokens(learning_context),
            "budget": engine.TOKEN_BUDGET_LEARNING,
        },
        "templates": {
            "text": template_context,
            "tokens": estimate_tokens(template_context),
            "budget": engine.TOKEN_BUDGET_TEMPLATES,
        },
        "total_tokens": estimate_tokens(total_text),
    }
