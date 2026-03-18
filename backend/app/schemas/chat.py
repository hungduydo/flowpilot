"""Request/response models for chat endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for POST /api/v1/chat."""

    message: str = Field(..., description="User's natural language message")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation ID to continue. Creates new if null.",
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="n8n workflow ID to edit (fetches from n8n). If provided, enters edit mode.",
    )
    workflow_json: Optional[dict[str, Any]] = Field(
        default=None,
        description="Workflow JSON to use as context (alternative to workflow_id)",
    )
    deploy_to_n8n: bool = Field(
        default=True,
        description="Whether to automatically deploy generated/edited workflow to n8n",
    )
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider override: 'openai', 'anthropic', or 'ollama'. Uses default if null.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model override, e.g. 'gpt-4o', 'claude-sonnet-4-20250514', 'qwen2.5:14b'. Uses default if null.",
    )


class WorkflowInfo(BaseModel):
    """Workflow info included in chat response."""

    workflow_json: dict[str, Any]
    n8n_workflow_id: Optional[str] = None
    n8n_editor_url: Optional[str] = None
    is_new: bool = True
    validation_errors: list[str] = []


class ChatResponse(BaseModel):
    """Response body for POST /api/v1/chat."""

    message: str = Field(..., description="Assistant's text response")
    conversation_id: str
    intent: str = Field(
        ...,
        description="Classified intent: CREATE_WORKFLOW, EDIT_WORKFLOW, ASK_QUESTION, CLARIFY",
    )
    workflow: Optional[WorkflowInfo] = Field(
        default=None,
        description="Generated/edited workflow info (if applicable)",
    )
