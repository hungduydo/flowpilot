"""
WebSocket endpoint for streaming chat responses.

Protocol:
  Client → Server: {"type": "chat_message", "message": "...", "conversation_id": "...", ...}
  Server → Client: {"type": "token", "content": "partial text"}
  Server → Client: {"type": "message_complete", "conversation_id": "...", "intent": "...", ...}
  Server → Client: {"type": "error", "detail": "..."}
"""

import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.conversation_engine import classify_intent, conversation_engine
from app.core.context_manager import ContextWindowManager
from app.core.llm_client import chat_completion_stream
from app.core.prompt_engine import build_chat_prompt
from app.db.repositories import MessageRepository
from app.db.session import async_session_factory

logger = structlog.get_logger()
router = APIRouter()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with streaming."""
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            # Receive message from client
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type", "chat_message")
            if msg_type != "chat_message":
                await websocket.send_json({"type": "error", "detail": f"Unknown type: {msg_type}"})
                continue

            user_message = data.get("message", "").strip()
            if not user_message:
                await websocket.send_json({"type": "error", "detail": "Empty message"})
                continue

            stream_mode = data.get("stream", True)

            # Process within a DB session
            async with async_session_factory() as session:
                try:
                    # Get or create conversation
                    conversation = await conversation_engine.get_or_create_conversation(
                        session, data.get("conversation_id")
                    )

                    # Send processing indicator
                    await websocket.send_json({
                        "type": "status",
                        "status": "processing",
                        "conversation_id": str(conversation.id),
                    })

                    # Classify intent first
                    provider = data.get("provider")
                    model = data.get("model")
                    intent = await classify_intent(user_message, provider=provider, model=model)

                    # Stream for chat intents, non-stream for workflow generation
                    if intent in ("ASK_QUESTION", "CLARIFY") and stream_mode:
                        # Streaming path
                        await websocket.send_json({
                            "type": "status",
                            "status": "streaming",
                            "intent": intent,
                        })

                        # Save user message
                        await MessageRepository.create(
                            session, conversation.id, "user", user_message
                        )

                        # Build context with history
                        system_prompt = build_chat_prompt()
                        history = await MessageRepository.get_history(
                            session, conversation.id
                        )
                        ctx_mgr = ContextWindowManager()
                        context = ctx_mgr.build_context(system_prompt, history)

                        # Stream tokens
                        full_text = ""
                        async for token in chat_completion_stream(
                            context, temperature=0.7, provider=provider, model=model,
                        ):
                            full_text += token
                            await websocket.send_json({
                                "type": "token",
                                "content": token,
                            })

                        # Save assistant response
                        await MessageRepository.create(
                            session, conversation.id, "assistant", full_text,
                            metadata={"intent": intent, "streamed": True},
                        )

                        await session.commit()

                        # Send complete
                        await websocket.send_json({
                            "type": "message_complete",
                            "conversation_id": str(conversation.id),
                            "intent": intent,
                            "message": full_text,
                        })

                    else:
                        # Non-streaming path (workflow generation/editing)
                        result = await conversation_engine.process_message(
                            session,
                            conversation,
                            user_message,
                            workflow_id=data.get("workflow_id"),
                            workflow_json=data.get("workflow_json"),
                            deploy_to_n8n=data.get("deploy_to_n8n", True),
                            provider=provider,
                            model=model,
                        )

                        await session.commit()

                        # Send complete response
                        response = {
                            "type": "message_complete",
                            "conversation_id": result["conversation_id"],
                            "intent": result["intent"],
                            "message": result["message"],
                        }
                        if result.get("workflow"):
                            response["workflow"] = result["workflow"]

                        await websocket.send_json(response)

                except Exception as e:
                    await session.rollback()
                    logger.exception("Error processing WebSocket message", error=str(e))
                    await websocket.send_json({
                        "type": "error",
                        "detail": str(e),
                    })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error", error=str(e))
