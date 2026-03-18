"""
n8n Node Registry — catalog of common node types with their metadata.

Used for:
1. Validation: checking if LLM-generated node types are valid
2. Prompt context: injecting relevant node info into LLM prompts
3. Node suggestions: recommending nodes based on user intent
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NodeDefinition:
    """Definition of an n8n node type."""

    type: str  # e.g., "n8n-nodes-base.httpRequest"
    display_name: str  # e.g., "HTTP Request"
    category: str  # e.g., "Data Fetching"
    description: str
    type_version: float = 1.0
    required_parameters: list[str] = field(default_factory=list)
    optional_parameters: dict[str, Any] = field(default_factory=dict)
    credential_types: list[str] = field(default_factory=list)
    input_count: int = 1  # 0 for triggers
    output_count: int = 1
    output_names: list[str] = field(default_factory=lambda: ["main"])
    is_trigger: bool = False
    keywords: list[str] = field(default_factory=list)


# ─── Node Catalog: 30+ most common n8n node types ───

NODE_CATALOG: dict[str, NodeDefinition] = {}


def _register(node: NodeDefinition) -> None:
    NODE_CATALOG[node.type] = node


# ═══ Triggers ═══

_register(NodeDefinition(
    type="n8n-nodes-base.manualTrigger",
    display_name="Manual Trigger",
    category="Triggers",
    description="Starts the workflow when manually executed",
    type_version=1.0,
    input_count=0,
    is_trigger=True,
    keywords=["manual", "start", "test", "run"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.scheduleTrigger",
    display_name="Schedule Trigger",
    category="Triggers",
    description="Starts the workflow on a schedule (cron or interval)",
    type_version=1.2,
    input_count=0,
    is_trigger=True,
    required_parameters=["rule"],
    keywords=["schedule", "cron", "timer", "interval", "periodic"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.webhook",
    display_name="Webhook",
    category="Triggers",
    description="Starts the workflow when an HTTP request is received",
    type_version=2.0,
    input_count=0,
    is_trigger=True,
    required_parameters=["httpMethod", "path"],
    keywords=["webhook", "http", "api", "endpoint", "receive"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.emailReadImap",
    display_name="Email Trigger (IMAP)",
    category="Triggers",
    description="Triggers when a new email is received via IMAP",
    type_version=2.0,
    input_count=0,
    is_trigger=True,
    credential_types=["imap"],
    keywords=["email", "imap", "mail", "inbox"],
))

# ═══ Core / Flow Control ═══

_register(NodeDefinition(
    type="n8n-nodes-base.if",
    display_name="If",
    category="Flow",
    description="Routes items based on comparison conditions",
    type_version=2.2,
    output_count=2,
    output_names=["true", "false"],
    required_parameters=["conditions"],
    keywords=["if", "condition", "branch", "filter", "check"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.switch",
    display_name="Switch",
    category="Flow",
    description="Routes items to different outputs based on rules",
    type_version=3.2,
    output_count=4,
    output_names=["output 0", "output 1", "output 2", "output 3"],
    required_parameters=["rules"],
    keywords=["switch", "route", "case", "multiple", "branch"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.merge",
    display_name="Merge",
    category="Flow",
    description="Merges data from multiple inputs",
    type_version=3.0,
    input_count=2,
    required_parameters=["mode"],
    keywords=["merge", "combine", "join", "concat"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.splitInBatches",
    display_name="Split In Batches",
    category="Flow",
    description="Processes items in batches",
    type_version=3.0,
    output_count=2,
    keywords=["batch", "split", "loop", "iterate", "chunk"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.wait",
    display_name="Wait",
    category="Flow",
    description="Pauses execution for a specified time",
    type_version=1.0,
    keywords=["wait", "delay", "pause", "sleep"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.noOp",
    display_name="No Operation",
    category="Flow",
    description="Does nothing, passes data through (useful for organization)",
    type_version=1.0,
    keywords=["noop", "pass", "through"],
))

# ═══ Data Transformation ═══

_register(NodeDefinition(
    type="n8n-nodes-base.set",
    display_name="Edit Fields (Set)",
    category="Data",
    description="Set, rename, or remove fields from items",
    type_version=3.4,
    required_parameters=["assignments"],
    keywords=["set", "edit", "field", "transform", "map", "assign"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.code",
    display_name="Code",
    category="Data",
    description="Execute custom JavaScript or Python code",
    type_version=2.0,
    required_parameters=["jsCode"],
    keywords=["code", "javascript", "python", "script", "custom", "function"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.aggregate",
    display_name="Aggregate",
    category="Data",
    description="Aggregate items together (sum, count, concatenate, etc.)",
    type_version=1.0,
    keywords=["aggregate", "sum", "count", "group"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.itemLists",
    display_name="Item Lists",
    category="Data",
    description="Manipulate item lists (sort, limit, remove duplicates, split)",
    type_version=3.1,
    keywords=["list", "sort", "limit", "unique", "deduplicate", "split"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.dateTime",
    display_name="Date & Time",
    category="Data",
    description="Format, parse, and manipulate dates and times",
    type_version=2.0,
    keywords=["date", "time", "format", "parse", "timezone"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.crypto",
    display_name="Crypto",
    category="Data",
    description="Hash, encrypt, or generate random values",
    type_version=1.0,
    keywords=["hash", "encrypt", "md5", "sha", "random", "uuid"],
))

# ═══ HTTP / API ═══

_register(NodeDefinition(
    type="n8n-nodes-base.httpRequest",
    display_name="HTTP Request",
    category="Network",
    description="Make HTTP requests to any API or URL",
    type_version=4.2,
    required_parameters=["url"],
    keywords=["http", "api", "request", "get", "post", "rest", "fetch", "call"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.respondToWebhook",
    display_name="Respond to Webhook",
    category="Network",
    description="Send a response back to a webhook caller",
    type_version=1.0,
    keywords=["respond", "webhook", "response", "reply"],
))

# ═══ Communication ═══

_register(NodeDefinition(
    type="n8n-nodes-base.slack",
    display_name="Slack",
    category="Communication",
    description="Send messages, manage channels in Slack",
    type_version=2.2,
    credential_types=["slackApi", "slackOAuth2Api"],
    required_parameters=["resource", "operation"],
    keywords=["slack", "message", "channel", "chat", "notify"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.discord",
    display_name="Discord",
    category="Communication",
    description="Send messages to Discord channels",
    type_version=2.1,
    credential_types=["discordApi", "discordBotApi"],
    keywords=["discord", "message", "bot"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.telegram",
    display_name="Telegram",
    category="Communication",
    description="Send messages via Telegram bot",
    type_version=1.2,
    credential_types=["telegramApi"],
    required_parameters=["resource", "operation"],
    keywords=["telegram", "message", "bot", "chat"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.emailSend",
    display_name="Send Email",
    category="Communication",
    description="Send emails via SMTP",
    type_version=2.1,
    credential_types=["smtp"],
    required_parameters=["fromEmail", "toEmail", "subject"],
    keywords=["email", "send", "smtp", "mail"],
))

# ═══ Google ═══

_register(NodeDefinition(
    type="n8n-nodes-base.googleSheets",
    display_name="Google Sheets",
    category="Productivity",
    description="Read, write, and manage Google Sheets",
    type_version=4.5,
    credential_types=["googleSheetsOAuth2Api", "googleApi"],
    required_parameters=["resource", "operation"],
    keywords=["google", "sheets", "spreadsheet", "excel", "csv"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.googleDrive",
    display_name="Google Drive",
    category="Productivity",
    description="Manage files and folders in Google Drive",
    type_version=3.0,
    credential_types=["googleDriveOAuth2Api"],
    required_parameters=["resource", "operation"],
    keywords=["google", "drive", "file", "upload", "download", "folder"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.gmail",
    display_name="Gmail",
    category="Communication",
    description="Send, read, and manage Gmail messages",
    type_version=2.1,
    credential_types=["gmailOAuth2"],
    required_parameters=["resource", "operation"],
    keywords=["gmail", "email", "google", "mail", "send"],
))

# ═══ Databases ═══

_register(NodeDefinition(
    type="n8n-nodes-base.postgres",
    display_name="PostgreSQL",
    category="Database",
    description="Execute queries on PostgreSQL databases",
    type_version=2.5,
    credential_types=["postgres"],
    required_parameters=["operation"],
    keywords=["postgres", "postgresql", "database", "sql", "query", "db"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.mySql",
    display_name="MySQL",
    category="Database",
    description="Execute queries on MySQL databases",
    type_version=2.4,
    credential_types=["mySql"],
    required_parameters=["operation"],
    keywords=["mysql", "database", "sql", "query", "db"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.mongoDb",
    display_name="MongoDB",
    category="Database",
    description="Perform operations on MongoDB collections",
    type_version=1.1,
    credential_types=["mongoDb"],
    required_parameters=["operation", "collection"],
    keywords=["mongodb", "mongo", "nosql", "collection", "document"],
))

# ═══ Dev Tools ═══

_register(NodeDefinition(
    type="n8n-nodes-base.github",
    display_name="GitHub",
    category="Development",
    description="Interact with GitHub repos, issues, and PRs",
    type_version=1.0,
    credential_types=["githubApi", "githubOAuth2Api"],
    required_parameters=["resource", "operation"],
    keywords=["github", "git", "repo", "issue", "pr", "pull request"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.githubTrigger",
    display_name="GitHub Trigger",
    category="Triggers",
    description="Triggers when GitHub events occur (push, PR, issue, etc.)",
    type_version=1.0,
    input_count=0,
    is_trigger=True,
    credential_types=["githubApi"],
    required_parameters=["owner", "repository", "events"],
    keywords=["github", "trigger", "webhook", "event", "push", "pr"],
))

_register(NodeDefinition(
    type="n8n-nodes-base.jira",
    display_name="Jira",
    category="Development",
    description="Create and manage Jira issues",
    type_version=1.0,
    credential_types=["jiraSoftwareCloudApi", "jiraSoftwareServerApi"],
    required_parameters=["resource", "operation"],
    keywords=["jira", "issue", "ticket", "task", "project", "agile"],
))

# ═══ AI ═══

_register(NodeDefinition(
    type="@n8n/n8n-nodes-langchain.openAi",
    display_name="OpenAI",
    category="AI",
    description="Interact with OpenAI models (GPT, embeddings, etc.)",
    type_version=1.0,
    credential_types=["openAiApi"],
    required_parameters=["resource", "operation"],
    keywords=["openai", "gpt", "ai", "chat", "completion", "embedding"],
))

_register(NodeDefinition(
    type="@n8n/n8n-nodes-langchain.agent",
    display_name="AI Agent",
    category="AI",
    description="AI agent that can use tools and make decisions",
    type_version=1.0,
    keywords=["agent", "ai", "tool", "langchain", "reasoning"],
))


# ─── Registry Lookup Functions ───

def get_node(node_type: str) -> NodeDefinition | None:
    """Look up a node definition by type string."""
    return NODE_CATALOG.get(node_type)


def is_valid_node_type(node_type: str) -> bool:
    """Check if a node type exists in the registry."""
    return node_type in NODE_CATALOG


def search_nodes(query: str) -> list[NodeDefinition]:
    """Search for nodes by keyword matching."""
    query_lower = query.lower()
    results = []
    for node in NODE_CATALOG.values():
        # Match against keywords, display_name, description
        if any(query_lower in kw for kw in node.keywords):
            results.append(node)
        elif query_lower in node.display_name.lower():
            results.append(node)
        elif query_lower in node.description.lower():
            results.append(node)
    return results


def get_trigger_nodes() -> list[NodeDefinition]:
    """Get all trigger node types."""
    return [n for n in NODE_CATALOG.values() if n.is_trigger]


def get_nodes_by_category(category: str) -> list[NodeDefinition]:
    """Get all nodes in a category."""
    return [n for n in NODE_CATALOG.values() if n.category == category]


def get_node_catalog_summary() -> str:
    """Get a formatted summary of all nodes for LLM context."""
    lines = []
    categories: dict[str, list[NodeDefinition]] = {}
    for node in NODE_CATALOG.values():
        categories.setdefault(node.category, []).append(node)

    for category, nodes in sorted(categories.items()):
        lines.append(f"\n## {category}")
        for node in sorted(nodes, key=lambda n: n.display_name):
            params = ", ".join(node.required_parameters) if node.required_parameters else "none"
            lines.append(
                f"- **{node.display_name}** (`{node.type}` v{node.type_version}): "
                f"{node.description}. Required params: {params}"
            )
    return "\n".join(lines)
