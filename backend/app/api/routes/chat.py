"""
Chat endpoint — the main interaction point for users.

Flow:
1. User sends a message (natural language)
2. Get or create conversation in DB
3. Classify intent → dispatch to handler
4. Persist messages + workflows to DB
5. Return response with optional workflow info
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.conversation_engine import conversation_engine
from app.core.n8n_client import N8nClientError
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, WorkflowInfo
from app.workflow.generator import WorkflowGenerationError

logger = structlog.get_logger()
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint.

    Accepts natural language, generates/edits n8n workflows,
    and automatically deploys them to n8n server.
    Conversations are persisted to the database.
    """
    try:
        # 1. Get or create conversation
        conversation = await conversation_engine.get_or_create_conversation(
            db, request.conversation_id
        )

        # 2. Process message through conversation engine
        result = await conversation_engine.process_message(
            db,
            conversation,
            request.message,
            workflow_id=request.workflow_id,
            workflow_json=request.workflow_json,
            deploy_to_n8n=request.deploy_to_n8n,
            provider=request.provider,
            model=request.model,
        )

        # 3. Build response
        workflow_info = None
        if result.get("workflow"):
            wf = result["workflow"]
            workflow_info = WorkflowInfo(
                workflow_json=wf["workflow_json"],
                n8n_workflow_id=wf.get("n8n_workflow_id"),
                n8n_editor_url=wf.get("n8n_editor_url"),
                is_new=wf.get("is_new", True),
                validation_errors=wf.get("validation_errors", []),
            )

        return ChatResponse(
            message=result["message"],
            conversation_id=result["conversation_id"],
            intent=result["intent"],
            workflow=workflow_info,
        )

    except WorkflowGenerationError as e:
        logger.error("Workflow generation failed", error=str(e))
        return ChatResponse(
            message=f"Xin lỗi, tôi không thể tạo workflow. Lỗi: {str(e)}\n\nHãy thử mô tả lại yêu cầu rõ hơn.",
            conversation_id=request.conversation_id or "",
            intent="CREATE_WORKFLOW",
        )
    except N8nClientError as e:
        logger.error("n8n API error", error=str(e))
        return ChatResponse(
            message=f"Workflow đã được tạo nhưng không thể deploy lên n8n: {e.detail}",
            conversation_id=request.conversation_id or "",
            intent="CREATE_WORKFLOW",
        )
    except Exception as e:
        logger.exception("Unexpected error in chat", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
