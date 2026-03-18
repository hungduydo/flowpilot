"""
Chat endpoint — the main interaction point for users.

Flow:
1. User sends a message (natural language)
2. Classify intent: CREATE_WORKFLOW, EDIT_WORKFLOW, ASK_QUESTION, CLARIFY
3. Based on intent:
   - CREATE: Generate workflow → validate → deploy to n8n → return link
   - EDIT: Fetch from n8n → LLM edit → validate → push back → return link
   - ASK/CLARIFY: Regular chat response
4. Return response with optional workflow info
"""

import json
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException

from app.core.llm_client import chat_completion
from app.core.n8n_client import N8nClientError, n8n_client
from app.core.prompt_engine import build_chat_prompt
from app.schemas.chat import ChatRequest, ChatResponse, WorkflowInfo
from app.workflow.editor import WorkflowEditor
from app.workflow.generator import WorkflowGenerationError, WorkflowGenerator

logger = structlog.get_logger()
router = APIRouter()

# Module-level instances
generator = WorkflowGenerator()
editor = WorkflowEditor()


async def classify_intent(
    message: str,
    has_workflow_context: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Classify user intent from their message."""
    classification_prompt = f"""Classify this user message into one of these intents:
- CREATE_WORKFLOW: User wants to create a new workflow/automation
- EDIT_WORKFLOW: User wants to modify an existing workflow (add, remove, change nodes)
- ASK_QUESTION: User is asking a question about n8n, workflows, or automation
- CLARIFY: User is providing clarification or answering a previous question

{"Note: There is an existing workflow in context." if has_workflow_context else ""}

User message: "{message}"

Respond with ONLY the intent name, nothing else."""

    result = await chat_completion(
        [{"role": "user", "content": classification_prompt}],
        temperature=0.1,
        max_tokens=20,
        provider=provider,
        model=model,
    )
    intent = result.strip().upper()

    # Validate intent
    valid_intents = {"CREATE_WORKFLOW", "EDIT_WORKFLOW", "ASK_QUESTION", "CLARIFY"}
    if intent not in valid_intents:
        # Default based on context
        if has_workflow_context:
            return "EDIT_WORKFLOW"
        return "CREATE_WORKFLOW" if any(
            kw in message.lower()
            for kw in ["tạo", "create", "build", "make", "xây", "workflow", "automate"]
        ) else "ASK_QUESTION"

    return intent


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.

    Accepts natural language, generates/edits n8n workflows,
    and automatically deploys them to n8n server.
    """
    conversation_id = request.conversation_id or str(uuid.uuid4())
    has_workflow = bool(request.workflow_id or request.workflow_json)

    try:
        # 1. Classify intent
        intent = await classify_intent(
            request.message, has_workflow,
            provider=request.provider, model=request.model,
        )
        logger.info("Intent classified", intent=intent, conversation_id=conversation_id,
                     provider=request.provider or "default")

        # 2. Handle based on intent
        if intent == "CREATE_WORKFLOW":
            return await _handle_create(request, conversation_id, intent)
        elif intent == "EDIT_WORKFLOW":
            return await _handle_edit(request, conversation_id, intent)
        else:
            return await _handle_chat(request, conversation_id, intent)

    except WorkflowGenerationError as e:
        logger.error("Workflow generation failed", error=str(e))
        return ChatResponse(
            message=f"Xin lỗi, tôi không thể tạo workflow. Lỗi: {str(e)}\n\nHãy thử mô tả lại yêu cầu rõ hơn.",
            conversation_id=conversation_id,
            intent="CREATE_WORKFLOW",
        )
    except N8nClientError as e:
        logger.error("n8n API error", error=str(e))
        return ChatResponse(
            message=f"Workflow đã được tạo nhưng không thể deploy lên n8n: {e.detail}",
            conversation_id=conversation_id,
            intent=intent,
        )
    except Exception as e:
        logger.exception("Unexpected error in chat", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_create(
    request: ChatRequest,
    conversation_id: str,
    intent: str,
) -> ChatResponse:
    """Handle CREATE_WORKFLOW intent."""
    # Generate workflow
    workflow_json = await generator.generate(
        request.message,
        provider=request.provider,
        model=request.model,
    )

    # Deploy to n8n if requested
    n8n_id = None
    editor_url = None
    if request.deploy_to_n8n:
        try:
            result = await n8n_client.create_workflow(workflow_json)
            n8n_id = result.get("id")
            editor_url = n8n_client.get_workflow_editor_url(n8n_id)
            logger.info("Workflow deployed to n8n", n8n_id=n8n_id)
        except N8nClientError as e:
            logger.warning("Failed to deploy to n8n", error=str(e))

    # Build response message
    wf_name = workflow_json.get("name", "Workflow")
    num_nodes = len(workflow_json.get("nodes", []))
    node_names = [n.get("name", "?") for n in workflow_json.get("nodes", [])]

    message_parts = [
        f"✅ **Workflow \"{wf_name}\" đã được tạo thành công!**\n",
        f"📊 **{num_nodes} nodes:** {', '.join(node_names)}\n",
    ]

    if editor_url:
        message_parts.append(f"🔗 **Xem trên n8n:** [{editor_url}]({editor_url})\n")
    else:
        message_parts.append("⚠️ Chưa deploy lên n8n. Bạn có thể download JSON và import thủ công.\n")

    message_parts.append(
        "\n💡 Bạn có thể yêu cầu chỉnh sửa, ví dụ:\n"
        "- \"Thêm error handling\"\n"
        "- \"Thêm node gửi email khi thất bại\"\n"
        "- \"Đổi trigger thành webhook\""
    )

    return ChatResponse(
        message="\n".join(message_parts),
        conversation_id=conversation_id,
        intent=intent,
        workflow=WorkflowInfo(
            workflow_json=workflow_json,
            n8n_workflow_id=n8n_id,
            n8n_editor_url=editor_url,
            is_new=True,
        ),
    )


async def _handle_edit(
    request: ChatRequest,
    conversation_id: str,
    intent: str,
) -> ChatResponse:
    """Handle EDIT_WORKFLOW intent."""
    # Get current workflow
    current_workflow: dict[str, Any] | None = None

    if request.workflow_id:
        # Fetch from n8n
        current_workflow = await n8n_client.get_workflow(request.workflow_id)
    elif request.workflow_json:
        current_workflow = request.workflow_json

    if not current_workflow:
        return ChatResponse(
            message=(
                "Tôi cần biết bạn muốn chỉnh sửa workflow nào. "
                "Hãy cung cấp `workflow_id` (ID trên n8n) hoặc `workflow_json`."
            ),
            conversation_id=conversation_id,
            intent=intent,
        )

    # Edit workflow
    edited_workflow = await editor.edit(
        current_workflow, request.message,
        provider=request.provider, model=request.model,
    )

    # Push back to n8n
    n8n_id = request.workflow_id or current_workflow.get("id")
    editor_url = None
    if n8n_id and request.deploy_to_n8n:
        try:
            result = await n8n_client.update_workflow(n8n_id, edited_workflow)
            editor_url = n8n_client.get_workflow_editor_url(n8n_id)
        except N8nClientError:
            # If update fails, try creating as new
            try:
                result = await n8n_client.create_workflow(edited_workflow)
                n8n_id = result.get("id")
                editor_url = n8n_client.get_workflow_editor_url(n8n_id)
            except N8nClientError as e:
                logger.warning("Failed to push edited workflow to n8n", error=str(e))

    # Build response
    wf_name = edited_workflow.get("name", "Workflow")
    num_nodes = len(edited_workflow.get("nodes", []))

    message_parts = [
        f"✏️ **Workflow \"{wf_name}\" đã được cập nhật!**\n",
        f"📊 **{num_nodes} nodes** sau chỉnh sửa\n",
    ]

    if editor_url:
        message_parts.append(f"🔗 **Xem thay đổi trên n8n:** [{editor_url}]({editor_url})\n")

    return ChatResponse(
        message="\n".join(message_parts),
        conversation_id=conversation_id,
        intent=intent,
        workflow=WorkflowInfo(
            workflow_json=edited_workflow,
            n8n_workflow_id=n8n_id,
            n8n_editor_url=editor_url,
            is_new=False,
        ),
    )


async def _handle_chat(
    request: ChatRequest,
    conversation_id: str,
    intent: str,
) -> ChatResponse:
    """Handle ASK_QUESTION / CLARIFY intents."""
    system_prompt = build_chat_prompt()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.message},
    ]

    response_text = await chat_completion(
        messages, temperature=0.7,
        provider=request.provider, model=request.model,
    )

    return ChatResponse(
        message=response_text,
        conversation_id=conversation_id,
        intent=intent,
    )
