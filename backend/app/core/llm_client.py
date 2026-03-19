"""
Multi-Provider LLM Client — supports OpenAI, Anthropic Claude, and Ollama (local).

Supports:
- Regular chat completions (for planning, chat)
- JSON generation via tool_use / JSON mode (for workflow generation)
- Tool use / function calling (for workflow editing)

Provider selection:
- Default: settings.llm_provider ("openai" | "anthropic" | "ollama")
- Runtime override: pass provider= parameter to any function
- API parameter: POST /chat with {"provider": "openai", "model": "gpt-4o"}
"""

import json
from typing import Any, Literal

import httpx
import structlog
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.config import settings
from app.core.retry import llm_retry
from app.workflow.schema import WORKFLOW_JSON_SCHEMA

logger = structlog.get_logger()

ProviderType = Literal["openai", "anthropic", "ollama"]

# ─── Singleton clients ───
_anthropic_client: AsyncAnthropic | None = None
_openai_client: AsyncOpenAI | None = None
_ollama_client: AsyncOpenAI | None = None


def get_anthropic_client() -> AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


def get_ollama_client() -> AsyncOpenAI:
    """Ollama exposes OpenAI-compatible API at /v1/. Works for both local and cloud."""
    global _ollama_client
    if _ollama_client is None:
        api_key = settings.ollama_api_key or "ollama"
        _ollama_client = AsyncOpenAI(
            base_url=f"{settings.ollama_base_url}/v1",
            api_key=api_key,
            timeout=300.0,
            default_headers=(
                {"Authorization": f"Bearer {settings.ollama_api_key}"}
                if settings.ollama_api_key else {}
            ),
        )
    return _ollama_client


def _resolve_provider(provider: str | None = None) -> ProviderType:
    """Resolve which provider to use."""
    p = (provider or settings.llm_provider).lower()
    if p not in ("openai", "anthropic", "ollama"):
        raise ValueError(f"Unknown LLM provider: {p}. Must be 'openai', 'anthropic', or 'ollama'")
    return p  # type: ignore


def _resolve_model(provider: ProviderType, model: str | None = None) -> str:
    """Resolve model name for the given provider."""
    if model:
        return model
    return {
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "ollama": settings.ollama_model,
    }[provider]


def _fix_message_order(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Ensure messages alternate between user and assistant.
    Claude requires strict alternation. OpenAI/Ollama are flexible but it doesn't hurt.
    """
    if not messages:
        return [{"role": "user", "content": "Hello"}]

    fixed = []
    last_role = None

    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue
        if role == last_role and fixed:
            fixed[-1]["content"] += "\n\n" + msg["content"]
        else:
            fixed.append({"role": role, "content": msg["content"]})
            last_role = role

    if fixed and fixed[0]["role"] != "user":
        fixed.insert(0, {"role": "user", "content": "Please help me with the following."})
    if not fixed:
        fixed = [{"role": "user", "content": "Hello"}]

    return fixed


def _extract_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Extract system message and return (system_text, other_messages)."""
    system_text = ""
    chat_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            chat_messages.append(msg)
    return system_text, chat_messages


# ═══════════════════════════════════════════════════════════════════
#  CHAT COMPLETION
# ═══════════════════════════════════════════════════════════════════

@llm_retry
async def _chat_openai(
    messages: list[dict], system_text: str,
    model: str, temperature: float, max_tokens: int,
) -> str:
    client = get_openai_client()
    all_messages = []
    if system_text:
        all_messages.append({"role": "system", "content": system_text})
    all_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    logger.debug("Chat [openai]", model=model,
                 tokens=response.usage.total_tokens if response.usage else 0)
    return content


@llm_retry
async def _chat_anthropic(
    messages: list[dict], system_text: str,
    model: str, temperature: float, max_tokens: int,
) -> str:
    client = get_anthropic_client()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_text or "You are a helpful assistant.",
        messages=messages,
    )
    content = response.content[0].text if response.content else ""
    logger.debug("Chat [anthropic]", model=model,
                 input_tokens=response.usage.input_tokens,
                 output_tokens=response.usage.output_tokens)
    return content


@llm_retry
async def _chat_ollama(
    messages: list[dict], system_text: str,
    model: str, temperature: float, max_tokens: int,
) -> str:
    client = get_ollama_client()
    all_messages = []
    if system_text:
        all_messages.append({"role": "system", "content": system_text})
    all_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    logger.debug("Chat [ollama]", model=model,
                 tokens=response.usage.total_tokens if response.usage else 0)
    return content


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    system: str | None = None,
    provider: str | None = None,
) -> str:
    """
    Regular chat completion. Routes to the active or specified provider.
    """
    resolved_provider = _resolve_provider(provider)
    resolved_model = _resolve_model(resolved_provider, model)
    resolved_max_tokens = max_tokens or settings.max_output_tokens

    system_text, chat_messages = _extract_system(messages)
    system_text = system or system_text
    chat_messages = _fix_message_order(chat_messages)

    dispatch = {
        "openai": _chat_openai,
        "anthropic": _chat_anthropic,
        "ollama": _chat_ollama,
    }
    return await dispatch[resolved_provider](
        chat_messages, system_text, resolved_model, temperature, resolved_max_tokens
    )


# ═══════════════════════════════════════════════════════════════════
#  STREAMING CHAT COMPLETION
# ═══════════════════════════════════════════════════════════════════

from collections.abc import AsyncGenerator


async def _stream_ollama(
    messages: list[dict], system_text: str,
    model: str, temperature: float, max_tokens: int,
) -> AsyncGenerator[str, None]:
    client = get_ollama_client()
    all_messages = []
    if system_text:
        all_messages.append({"role": "system", "content": system_text})
    all_messages.extend(messages)

    stream = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


async def _stream_anthropic(
    messages: list[dict], system_text: str,
    model: str, temperature: float, max_tokens: int,
) -> AsyncGenerator[str, None]:
    client = get_anthropic_client()
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_text or "You are a helpful assistant.",
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def _stream_openai(
    messages: list[dict], system_text: str,
    model: str, temperature: float, max_tokens: int,
) -> AsyncGenerator[str, None]:
    client = get_openai_client()
    all_messages = []
    if system_text:
        all_messages.append({"role": "system", "content": system_text})
    all_messages.extend(messages)

    stream = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    system: str | None = None,
    provider: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming chat completion. Yields token strings as they arrive.
    """
    resolved_provider = _resolve_provider(provider)
    resolved_model = _resolve_model(resolved_provider, model)
    resolved_max_tokens = max_tokens or settings.max_output_tokens

    system_text, chat_messages = _extract_system(messages)
    system_text = system or system_text
    chat_messages = _fix_message_order(chat_messages)

    dispatch = {
        "openai": _stream_openai,
        "anthropic": _stream_anthropic,
        "ollama": _stream_ollama,
    }
    async for token in dispatch[resolved_provider](
        chat_messages, system_text, resolved_model, temperature, resolved_max_tokens
    ):
        yield token


# ═══════════════════════════════════════════════════════════════════
#  STRUCTURED OUTPUT (Workflow JSON generation)
# ═══════════════════════════════════════════════════════════════════

@llm_retry
async def _structured_openai(
    messages: list[dict], system_text: str, model: str, temperature: float,
) -> dict[str, Any]:
    """OpenAI structured output using response_format + JSON mode."""
    client = get_openai_client()

    json_system = (system_text or "You are an n8n workflow architect.") + (
        "\n\nIMPORTANT: Respond with valid JSON only. "
        "The JSON must have these top-level keys: name, nodes, connections, settings."
    )

    all_messages = [{"role": "system", "content": json_system}]
    all_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=settings.max_output_tokens,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    logger.debug("Structured output [openai]", model=model,
                 tokens=response.usage.total_tokens if response.usage else 0)
    return json.loads(content)


@llm_retry
async def _structured_anthropic(
    messages: list[dict], system_text: str, model: str, temperature: float,
) -> dict[str, Any]:
    """Anthropic structured output using tool_use."""
    client = get_anthropic_client()

    workflow_tool = {
        "name": "create_n8n_workflow",
        "description": (
            "Create a complete n8n workflow JSON. You MUST use this tool to output "
            "the workflow. Do NOT output JSON as text."
        ),
        "input_schema": WORKFLOW_JSON_SCHEMA,
    }

    response = await client.messages.create(
        model=model,
        max_tokens=settings.max_output_tokens,
        temperature=temperature,
        system=system_text or "You are an n8n workflow architect.",
        messages=messages,
        tools=[workflow_tool],
        tool_choice={"type": "tool", "name": "create_n8n_workflow"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "create_n8n_workflow":
            logger.debug("Structured output [anthropic]", model=model,
                         input_tokens=response.usage.input_tokens,
                         output_tokens=response.usage.output_tokens)
            return block.input

    for block in response.content:
        if block.type == "text":
            return _extract_json(block.text)

    raise ValueError("Claude did not return a valid workflow JSON")


OLLAMA_COMPACT_SYSTEM = """You are an n8n workflow generator. Output ONLY valid JSON.

JSON format:
{"name":"Name","nodes":[{"id":"uuid","name":"Node Name","type":"n8n-nodes-base.xxx","typeVersion":1.0,"position":[x,y],"parameters":{}}],"connections":{"SourceNode":{"main":[[{"node":"TargetNode","type":"main","index":0}]]}},"settings":{"executionOrder":"v1"}}

Rules:
- Every workflow needs exactly 1 trigger node
- Use prefix "n8n-nodes-base." for all types
- Position: start at [250,300], each next node +250 on x-axis
- Node names must be unique, descriptive
- Generate valid UUIDs for node ids
- scheduleTrigger: {"rule":{"interval":[{"field":"minutes","minutesInterval":N}]}} (NOT cron strings)
- For hours: {"rule":{"interval":[{"field":"hours","hoursInterval":N}]}}
- If node: {"conditions":{"options":{"caseSensitive":true,"leftValue":""},"conditions":[{"leftValue":"={{ $json.field }}","rightValue":"value","operator":{"type":"string","operation":"equals"}}],"combinator":"and"}}
- For If node connections: main[0]=true branch, main[1]=false branch

Node resource/operation (MUST include for these nodes):
- slack: resource="message", operation="send", params: channel, text
- googleSheets: resource="sheet", operation="appendOrUpdate", params: documentId, sheetName
- gmail: resource="message", operation="send", params: sendTo, subject, message
- telegram: resource="message", operation="sendMessage", params: chatId, text
- googleDrive: resource="file", operation="upload"
- github: resource="issue", operation="getAll", params: owner, repository
- discord: resource="message", operation="send", params: channelId, content
- postgres/mySql: operation="executeQuery", params: query
- facebookGraphApi: resource="post", operation="create"
- notion: resource="page", operation="create"
- httpRequest: params: url, method (GET/POST/PUT/DELETE)
- webhook: params: httpMethod, path
- emailSend: params: fromEmail, toEmail, subject, text
- set: params: assignments (object with assignments array)
- code: params: jsCode (JavaScript code string)

Example - "Send Slack on webhook":
{"name":"Webhook to Slack","nodes":[{"id":"a1b2c3d4-e5f6-7890-abcd-ef1234567890","name":"Webhook","type":"n8n-nodes-base.webhook","typeVersion":2.0,"position":[250,300],"parameters":{"httpMethod":"POST","path":"hook"}},{"id":"b2c3d4e5-f6a7-8901-bcde-f12345678901","name":"Send Slack","type":"n8n-nodes-base.slack","typeVersion":2.2,"position":[500,300],"parameters":{"resource":"message","operation":"send","channel":"#general","text":"New webhook received"}}],"connections":{"Webhook":{"main":[[{"node":"Send Slack","type":"main","index":0}]]}},"settings":{"executionOrder":"v1"}}"""


@llm_retry
async def _structured_ollama(
    messages: list[dict], system_text: str, model: str, temperature: float,
) -> dict[str, Any]:
    """Ollama structured output using compact prompt + JSON mode."""
    client = get_ollama_client()

    # For small models, use compact prompt instead of the full system prompt
    # Extract only the user's actual request from messages
    user_request = ""
    plan_text = ""
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if "## User Request" in content:
                # This is the phase2 prompt with plan
                parts = content.split("## ")
                for part in parts:
                    if part.startswith("User Request"):
                        user_request = part.replace("User Request\n", "").strip()
                    elif part.startswith("Workflow Plan"):
                        plan_text = part.replace("Workflow Plan\n", "").strip()
            else:
                user_request = content

    # Build compact messages for small models
    compact_messages = [
        {"role": "system", "content": OLLAMA_COMPACT_SYSTEM},
    ]

    if plan_text:
        compact_messages.append({
            "role": "user",
            "content": f"Create n8n workflow JSON for: {user_request}\n\nPlan:\n{plan_text}"
        })
    else:
        compact_messages.append({
            "role": "user",
            "content": f"Create n8n workflow JSON for: {user_request}"
        })

    logger.info("Calling Ollama structured output", model=model,
                num_messages=len(compact_messages),
                user_request=user_request[:100])

    response = await client.chat.completions.create(
        model=model,
        messages=compact_messages,
        temperature=temperature,
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    logger.info("Ollama raw response", model=model,
                content_length=len(content),
                content_preview=content[:300],
                tokens=response.usage.total_tokens if response.usage else 0)

    result = json.loads(content)
    return result


async def structured_output(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    provider: str | None = None,
) -> dict[str, Any]:
    """Generate structured JSON output for n8n workflow."""
    resolved_provider = _resolve_provider(provider)
    resolved_model = _resolve_model(resolved_provider, model)

    system_text, chat_messages = _extract_system(messages)
    chat_messages = _fix_message_order(chat_messages)

    dispatch = {
        "openai": _structured_openai,
        "anthropic": _structured_anthropic,
        "ollama": _structured_ollama,
    }
    return await dispatch[resolved_provider](
        chat_messages, system_text, resolved_model, temperature
    )


# ═══════════════════════════════════════════════════════════════════
#  FUNCTION CALLING (Workflow edit operations)
# ═══════════════════════════════════════════════════════════════════

# Edit operation tool definitions (Anthropic format — also source of truth)
EDIT_TOOLS_ANTHROPIC = [
    {
        "name": "add_node",
        "description": "Add a new node to the workflow",
        "input_schema": {
            "type": "object",
            "required": ["node_type", "name", "parameters", "position"],
            "properties": {
                "node_type": {"type": "string", "description": "n8n node type, e.g. 'n8n-nodes-base.httpRequest'"},
                "name": {"type": "string", "description": "Display name for the node"},
                "type_version": {"type": "number", "description": "Node type version"},
                "parameters": {"type": "object", "description": "Node-specific configuration"},
                "position": {"type": "array", "items": {"type": "integer"}, "description": "[x, y] position"},
                "connect_after": {"type": "string", "description": "Name of node to connect FROM"},
                "connect_before": {"type": "string", "description": "Name of node to connect TO"},
                "output_index": {"type": "integer", "description": "Output index on connect_after node"},
            },
        },
    },
    {
        "name": "remove_node",
        "description": "Remove a node from the workflow",
        "input_schema": {
            "type": "object",
            "required": ["node_name"],
            "properties": {
                "node_name": {"type": "string", "description": "Name of the node to remove"},
                "reconnect": {"type": "boolean", "description": "If true, reconnect neighbors"},
            },
        },
    },
    {
        "name": "update_node_parameters",
        "description": "Update parameters of an existing node",
        "input_schema": {
            "type": "object",
            "required": ["node_name", "parameters"],
            "properties": {
                "node_name": {"type": "string", "description": "Name of the node to update"},
                "parameters": {"type": "object", "description": "Parameters to set (merged with existing)"},
            },
        },
    },
    {
        "name": "add_connection",
        "description": "Add a connection between two nodes",
        "input_schema": {
            "type": "object",
            "required": ["from_node", "to_node"],
            "properties": {
                "from_node": {"type": "string", "description": "Source node name"},
                "to_node": {"type": "string", "description": "Target node name"},
                "from_output_index": {"type": "integer", "description": "Output index"},
                "to_input_index": {"type": "integer", "description": "Input index on target"},
            },
        },
    },
    {
        "name": "remove_connection",
        "description": "Remove a connection between two nodes",
        "input_schema": {
            "type": "object",
            "required": ["from_node", "to_node"],
            "properties": {
                "from_node": {"type": "string", "description": "Source node name"},
                "to_node": {"type": "string", "description": "Target node name"},
            },
        },
    },
    {
        "name": "replace_node",
        "description": "Replace a node with a different type while preserving connections",
        "input_schema": {
            "type": "object",
            "required": ["old_node_name", "new_node_type", "new_parameters"],
            "properties": {
                "old_node_name": {"type": "string"},
                "new_node_type": {"type": "string"},
                "new_name": {"type": "string", "description": "New display name"},
                "new_type_version": {"type": "number"},
                "new_parameters": {"type": "object"},
            },
        },
    },
]

# OpenAI-compatible format (used by OpenAI + Ollama)
EDIT_TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }
    for tool in EDIT_TOOLS_ANTHROPIC
]

# Backward-compatible alias
EDIT_TOOLS = EDIT_TOOLS_ANTHROPIC


async def _fc_openai(
    messages: list[dict], system_text: str, model: str, temperature: float,
) -> list[dict[str, Any]]:
    client = get_openai_client()
    all_messages = []
    if system_text:
        all_messages.append({"role": "system", "content": system_text or "You are an n8n workflow editor."})
    all_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=all_messages,
        temperature=temperature,
        max_tokens=settings.max_output_tokens,
        tools=EDIT_TOOLS_OPENAI,
    )

    tool_calls = []
    choice = response.choices[0]
    if choice.message.tool_calls:
        for tc in choice.message.tool_calls:
            args = tc.function.arguments
            if isinstance(args, str):
                args = json.loads(args)
            tool_calls.append({"name": tc.function.name, "arguments": args})

    logger.debug("Function calling [openai]", model=model, num_tool_calls=len(tool_calls),
                 tokens=response.usage.total_tokens if response.usage else 0)
    return tool_calls


async def _fc_anthropic(
    messages: list[dict], system_text: str, model: str, temperature: float,
) -> list[dict[str, Any]]:
    client = get_anthropic_client()
    response = await client.messages.create(
        model=model,
        max_tokens=settings.max_output_tokens,
        temperature=temperature,
        system=system_text or "You are an n8n workflow editor.",
        messages=messages,
        tools=EDIT_TOOLS_ANTHROPIC,
    )
    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append({"name": block.name, "arguments": block.input})
    logger.debug("Function calling [anthropic]", model=model, num_tool_calls=len(tool_calls),
                 input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
    return tool_calls


async def _fc_ollama(
    messages: list[dict], system_text: str, model: str, temperature: float,
) -> list[dict[str, Any]]:
    """Ollama function calling: try native tool_call, fallback to prompt-based."""
    client = get_ollama_client()
    all_messages = []
    if system_text:
        all_messages.append({"role": "system", "content": system_text or "You are an n8n workflow editor."})
    all_messages.extend(messages)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=all_messages,
            temperature=temperature,
            max_tokens=settings.max_output_tokens,
            tools=EDIT_TOOLS_OPENAI,
        )
        tool_calls = []
        choice = response.choices[0]
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append({"name": tc.function.name, "arguments": args})
        logger.debug("Function calling [ollama]", model=model, num_tool_calls=len(tool_calls))
        return tool_calls
    except Exception as e:
        logger.warning("Ollama native tool_call failed, trying prompt-based", error=str(e))
        return await _fc_ollama_fallback(all_messages, model, temperature)


async def _fc_ollama_fallback(
    messages: list[dict], model: str, temperature: float,
) -> list[dict[str, Any]]:
    """Fallback: ask LLM to output JSON array of tool calls."""
    client = get_ollama_client()

    tool_descriptions = "\n".join(
        f"- {t['name']}: {t['description']} | params: {json.dumps(list(t['input_schema']['properties'].keys()))}"
        for t in EDIT_TOOLS_ANTHROPIC
    )

    fallback_system = (
        "You are an n8n workflow editor. Respond ONLY with a JSON array of tool calls.\n"
        f"Available tools:\n{tool_descriptions}\n\n"
        'Format: [{"name": "tool_name", "arguments": {...}}, ...]\n'
        "No explanation. Only JSON array."
    )

    messages[0] = {"role": "system", "content": fallback_system}

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=settings.max_output_tokens,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "[]"
    result = json.loads(content)

    if isinstance(result, dict):
        result = result.get("tool_calls", result.get("operations", []))
    if not isinstance(result, list):
        result = [result]

    logger.debug("Function calling [ollama/fallback]", model=model, num_tool_calls=len(result))
    return result


async def function_calling(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """
    Use LLM for workflow edit operations (tool use).
    Returns: list of tool calls [{name, arguments}, ...]
    """
    resolved_provider = _resolve_provider(provider)
    resolved_model = _resolve_model(resolved_provider, model)

    system_text, chat_messages = _extract_system(messages)
    chat_messages = _fix_message_order(chat_messages)

    dispatch = {
        "openai": _fc_openai,
        "anthropic": _fc_anthropic,
        "ollama": _fc_ollama,
    }
    return await dispatch[resolved_provider](
        chat_messages, system_text, resolved_model, temperature
    )


# ═══════════════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> dict:
    """Try to extract JSON object from text (with or without code fences)."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0].strip()
        return json.loads(json_str)
    if "```" in text:
        json_str = text.split("```")[1].split("```")[0].strip()
        return json.loads(json_str)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return json.loads(text[start : end + 1])
    raise ValueError(f"Could not extract JSON from response: {text[:200]}...")


def _ollama_headers() -> dict[str, str]:
    """Build auth headers for Ollama (needed for cloud, empty for local)."""
    if settings.ollama_api_key:
        return {"Authorization": f"Bearer {settings.ollama_api_key}"}
    return {}


async def check_ollama_status() -> dict[str, Any]:
    """Check if Ollama is running and what models are available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.ollama_base_url}/api/tags",
                headers=_ollama_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {
                    "status": "online",
                    "models": models,
                    "current_model": settings.ollama_model,
                    "model_loaded": settings.ollama_model in models
                        or any(settings.ollama_model.split(":")[0] in m for m in models),
                }
            return {"status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "offline", "detail": str(e)}


async def pull_ollama_model(model_name: str | None = None) -> str:
    """Pull (download) a model in Ollama."""
    model = model_name or settings.ollama_model
    async with httpx.AsyncClient(timeout=600.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/pull",
            json={"name": model, "stream": False},
            headers=_ollama_headers(),
        )
        if resp.status_code == 200:
            return f"Model '{model}' pulled successfully"
        raise RuntimeError(f"Failed to pull model: {resp.text}")
