"""
Conversation engine — orchestrates multi-turn chat with persistence.

Replaces the stateless approach: loads history from DB, builds context window,
delegates to intent handlers, persists messages + workflows.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context_manager import ContextWindowManager
from app.core.llm_client import chat_completion
from app.core.n8n_client import N8nClientError, n8n_client
from app.core.prompt_engine import build_chat_prompt
from app.rag.chroma_client import search as rag_search
from app.db.models import Conversation, Message
from app.db.repositories import (
    ConversationRepository,
    KnowledgeNoteRepository,
    LearningRepository,
    MessageRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
)
from app.workflow.editor import WorkflowEditor
from app.workflow.generator import WorkflowGenerator

logger = structlog.get_logger()

# Module-level instances
_generator = WorkflowGenerator()
_editor = WorkflowEditor()
_context_mgr = ContextWindowManager()


async def classify_intent(
    message: str,
    has_workflow_context: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Classify user intent from their message."""
    classification_prompt = (
        "Classify this user message into one of these intents:\n"
        "- CREATE_WORKFLOW: User wants to create a new workflow/automation\n"
        "- EDIT_WORKFLOW: User wants to modify an existing workflow\n"
        "- ASK_QUESTION: User is asking a question about n8n or workflows\n"
        "- CLARIFY: User is providing clarification\n"
        f"{'Note: There is an existing workflow in context.' if has_workflow_context else ''}\n\n"
        f'User message: "{message}"\n\n'
        "Respond with ONLY the intent name, nothing else."
    )

    result = await chat_completion(
        [{"role": "user", "content": classification_prompt}],
        temperature=0.1,
        max_tokens=20,
        provider=provider,
        model=model,
    )
    intent = result.strip().upper()

    valid_intents = {"CREATE_WORKFLOW", "EDIT_WORKFLOW", "ASK_QUESTION", "CLARIFY"}
    if intent not in valid_intents:
        if has_workflow_context:
            return "EDIT_WORKFLOW"
        return (
            "CREATE_WORKFLOW"
            if any(
                kw in message.lower()
                for kw in ["tạo", "create", "build", "make", "xây", "workflow", "automate"]
            )
            else "ASK_QUESTION"
        )
    return intent


async def _auto_title(message: str, provider: str | None = None) -> str:
    """Generate a short title from the first user message.
    Uses simple text extraction — LLM-based title gen is unreliable with
    thinking models (qwen3.5 consumes all tokens on <think> tags).
    """
    # Clean up the message
    text = message.strip()

    # Remove common prefixes
    for prefix in ["create ", "tạo ", "make ", "build ", "generate ", "please ", "help me "]:
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break

    # Capitalize first letter
    if text:
        text = text[0].upper() + text[1:]

    # Truncate to reasonable title length
    if len(text) > 50:
        # Try to cut at word boundary
        cut = text[:50].rfind(' ')
        if cut > 20:
            text = text[:cut] + "..."
        else:
            text = text[:50] + "..."

    return text or message[:50]


class ConversationEngine:
    """Orchestrates multi-turn conversations with persistence."""

    def __init__(self):
        self.context_mgr = _context_mgr
        self.generator = _generator
        self.editor = _editor

    # ── Conversation lifecycle ──────────────────────────────────

    async def get_or_create_conversation(
        self,
        session: AsyncSession,
        conversation_id: str | None,
    ) -> Conversation:
        """Get existing or create new conversation."""
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
            except ValueError:
                conv_uuid = None

            if conv_uuid:
                conv = await ConversationRepository.get(session, conv_uuid)
                if conv:
                    return conv

        # Create new
        return await ConversationRepository.create(session)

    # ── Main entry point ────────────────────────────────────────

    async def process_message(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user_message: str,
        *,
        workflow_id: str | None = None,
        workflow_json: dict[str, Any] | None = None,
        deploy_to_n8n: bool = True,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message within a conversation.

        Returns dict with: message, intent, workflow (optional), conversation_id
        """
        conv_id = conversation.id

        # 1. Save user message
        await MessageRepository.create(session, conv_id, "user", user_message)

        # 2. Auto-title on first message
        msg_count = await MessageRepository.count(session, conv_id)
        if msg_count == 1 and not conversation.title:
            title = await _auto_title(user_message, provider)
            await ConversationRepository.update_title(session, conv_id, title)

        # 3. Classify intent
        has_workflow = bool(workflow_id or workflow_json)
        intent = await classify_intent(user_message, has_workflow, provider, model)
        logger.info("Intent classified", intent=intent, conversation_id=str(conv_id))

        # 4. Auto-redirect CREATE to EDIT when there's already an active workflow
        if intent == "CREATE_WORKFLOW" and has_workflow:
            intent = "EDIT_WORKFLOW"
            logger.info(
                "Redirected CREATE to EDIT (active workflow in context)",
                workflow_id=workflow_id,
            )

        # 5. Dispatch to handler
        if intent == "CREATE_WORKFLOW":
            result = await self._handle_create(
                session, conversation, user_message,
                deploy_to_n8n=deploy_to_n8n, provider=provider, model=model,
            )
        elif intent == "EDIT_WORKFLOW":
            result = await self._handle_edit(
                session, conversation, user_message,
                workflow_id=workflow_id, workflow_json=workflow_json,
                deploy_to_n8n=deploy_to_n8n, provider=provider, model=model,
            )
        else:
            result = await self._handle_chat(
                session, conversation, user_message,
                provider=provider, model=model,
            )

        result["intent"] = intent
        result["conversation_id"] = str(conv_id)

        # 6. Save assistant response with workflow metadata
        msg_metadata: dict[str, Any] = {
            "intent": intent,
            "has_workflow": result.get("workflow") is not None,
        }
        if result.get("workflow"):
            wf = result["workflow"]
            msg_metadata["n8n_workflow_id"] = wf.get("n8n_workflow_id")
            msg_metadata["n8n_url"] = wf.get("n8n_editor_url")
            msg_metadata["workflow_json"] = wf.get("workflow_json")

        await MessageRepository.create(
            session, conv_id, "assistant", result["message"],
            metadata=msg_metadata,
        )

        return result

    # ── Intent handlers ─────────────────────────────────────────

    def _get_rag_context(self, user_message: str) -> str:
        """Retrieve relevant knowledge from RAG."""
        try:
            return rag_search(user_message, n_results=3)
        except Exception as e:
            logger.warning("RAG search failed, continuing without context", error=str(e))
            return ""

    async def _get_knowledge_context(self, session: AsyncSession) -> str:
        """Load active knowledge notes and format as prompt context."""
        try:
            notes = await KnowledgeNoteRepository.list_all(session, active_only=True)
            if not notes:
                return ""
            notes_text = "\n".join(f"- {n.content}" for n in notes)
            return f"\n\n## User Knowledge Notes (MUST follow these instructions):\n{notes_text}"
        except Exception as e:
            logger.warning("Failed to load knowledge notes", error=str(e))
            return ""

    async def _get_learning_context(
        self, session: AsyncSession, node_types: list[str] | None = None
    ) -> str:
        """Load auto-learned corrections for prompt injection."""
        try:
            records = await LearningRepository.get_relevant(
                session, node_types=node_types, limit=15
            )
            if not records:
                return ""
            lines = [
                f"- [{r.node_type or 'general'}] {r.description} (seen {r.frequency}x)"
                for r in records
            ]
            return (
                "\n\n## Learned Corrections (avoid these mistakes):\n"
                + "\n".join(lines)
            )
        except Exception:
            return ""

    async def _handle_create(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user_message: str,
        *,
        deploy_to_n8n: bool = True,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generate a new workflow."""
        rag_context = self._get_rag_context(user_message)
        knowledge_context = await self._get_knowledge_context(session)
        learning_context = await self._get_learning_context(session)
        full_context = rag_context + knowledge_context + learning_context
        workflow_json, fixes = await self.generator.generate(
            user_message, rag_context=full_context, provider=provider, model=model,
        )

        # Save auto-fixes as learning records
        if fixes:
            for fix in fixes:
                try:
                    await LearningRepository.record_fix(
                        session,
                        record_type="auto_fix",
                        node_type=fix.get("node_type"),
                        description=fix["description"],
                        fix_data=fix.get("fix_data"),
                    )
                except Exception:
                    pass  # Don't fail on learning save

        # Deploy
        n8n_id = None
        editor_url = None
        status = "draft"
        if deploy_to_n8n:
            try:
                result = await n8n_client.create_workflow(workflow_json)
                n8n_id = result.get("id")
                editor_url = n8n_client.get_workflow_editor_url(n8n_id)
                status = "deployed"
            except N8nClientError as e:
                logger.warning("Failed to deploy", error=str(e))

        # Save to DB
        wf_name = workflow_json.get("name", "Workflow")
        await WorkflowRepository.create(
            session,
            name=wf_name,
            workflow_json=workflow_json,
            conversation_id=conversation.id,
            n8n_workflow_id=n8n_id,
            status=status,
        )

        # Save version snapshot
        if n8n_id:
            try:
                await WorkflowVersionRepository.save_version(
                    session,
                    workflow_id=n8n_id,
                    name=wf_name,
                    workflow_json=workflow_json,
                    change_summary="Initial creation",
                )
            except Exception as e:
                logger.warning("Failed to save workflow version", error=str(e))

        # Build message
        num_nodes = len(workflow_json.get("nodes", []))
        node_names = [n.get("name", "?") for n in workflow_json.get("nodes", [])]
        parts = [
            f'✅ **Workflow "{wf_name}" đã được tạo thành công!**\n',
            f"📊 **{num_nodes} nodes:** {', '.join(node_names)}\n",
        ]
        if editor_url:
            parts.append(f"🔗 **Xem trên n8n:** [{editor_url}]({editor_url})\n")
        else:
            parts.append("⚠️ Chưa deploy lên n8n.\n")
        parts.append(
            "\n💡 Bạn có thể yêu cầu chỉnh sửa, ví dụ:\n"
            '- "Thêm error handling"\n'
            '- "Thêm node gửi email khi thất bại"\n'
            '- "Đổi trigger thành webhook"'
        )

        return {
            "message": "\n".join(parts),
            "workflow": {
                "workflow_json": workflow_json,
                "n8n_workflow_id": n8n_id,
                "n8n_editor_url": editor_url,
                "is_new": True,
                "validation_errors": [],
            },
        }

    async def _handle_edit(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user_message: str,
        *,
        workflow_id: str | None = None,
        workflow_json: dict[str, Any] | None = None,
        deploy_to_n8n: bool = True,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Edit an existing workflow."""
        current_workflow = workflow_json
        if workflow_id and not current_workflow:
            current_workflow = await n8n_client.get_workflow(workflow_id)

        if not current_workflow:
            # Try to find last workflow in conversation
            conv_workflows = await WorkflowRepository.get_by_conversation(
                session, conversation.id
            )
            if conv_workflows:
                current_workflow = conv_workflows[0].workflow_json
                workflow_id = conv_workflows[0].n8n_workflow_id

        if not current_workflow:
            return {
                "message": (
                    "Tôi cần biết bạn muốn chỉnh sửa workflow nào. "
                    "Hãy cung cấp `workflow_id` hoặc tạo workflow trước."
                ),
            }

        knowledge_context = await self._get_knowledge_context(session)
        learning_context = await self._get_learning_context(session)
        edited = await self.editor.edit(
            current_workflow, user_message,
            rag_context=knowledge_context + learning_context,
            provider=provider, model=model,
        )

        # Record user edit as learning record
        try:
            await LearningRepository.record_fix(
                session,
                record_type="user_edit",
                node_type=None,
                description=f"User correction: {user_message[:200]}",
            )
        except Exception:
            pass  # Don't fail on learning save

        n8n_id = workflow_id
        editor_url = None
        if n8n_id and deploy_to_n8n:
            try:
                await n8n_client.update_workflow(n8n_id, edited)
                editor_url = n8n_client.get_workflow_editor_url(n8n_id)
            except N8nClientError:
                try:
                    result = await n8n_client.create_workflow(edited)
                    n8n_id = result.get("id")
                    editor_url = n8n_client.get_workflow_editor_url(n8n_id)
                except N8nClientError as e:
                    logger.warning("Failed to push edit", error=str(e))

        # Save edited workflow to DB
        wf_name = edited.get("name", "Workflow")
        await WorkflowRepository.create(
            session,
            name=wf_name,
            workflow_json=edited,
            conversation_id=conversation.id,
            n8n_workflow_id=n8n_id,
            status="deployed" if n8n_id else "draft",
        )

        # Save version snapshot
        if n8n_id:
            try:
                await WorkflowVersionRepository.save_version(
                    session,
                    workflow_id=n8n_id,
                    name=wf_name,
                    workflow_json=edited,
                    change_summary=f"Edit: {user_message[:100]}",
                )
            except Exception as e:
                logger.warning("Failed to save workflow version", error=str(e))

        num_nodes = len(edited.get("nodes", []))
        parts = [
            f'✏️ **Workflow "{wf_name}" đã được cập nhật!**\n',
            f"📊 **{num_nodes} nodes** sau chỉnh sửa\n",
        ]
        if editor_url:
            parts.append(f"🔗 **Xem trên n8n:** [{editor_url}]({editor_url})\n")

        return {
            "message": "\n".join(parts),
            "workflow": {
                "workflow_json": edited,
                "n8n_workflow_id": n8n_id,
                "n8n_editor_url": editor_url,
                "is_new": False,
                "validation_errors": [],
            },
        }

    async def _handle_chat(
        self,
        session: AsyncSession,
        conversation: Conversation,
        user_message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Handle general chat with conversation history."""
        rag_context = self._get_rag_context(user_message)
        knowledge_context = await self._get_knowledge_context(session)
        system_prompt = build_chat_prompt(rag_context=rag_context + knowledge_context)

        # Load history and build context window
        history = await MessageRepository.get_history(session, conversation.id)
        context = self.context_mgr.build_context(system_prompt, history)

        response_text = await chat_completion(
            context, temperature=0.7, provider=provider, model=model,
        )

        return {"message": response_text}


# Singleton
conversation_engine = ConversationEngine()
