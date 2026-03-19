"""Template distillation engine.

Converts raw n8n template workflow JSON into embedding-friendly text
that matches the format of existing example_workflows.md knowledge base.
"""

from typing import Any

import structlog

logger = structlog.get_logger()

# Node types to skip (noise, not useful for learning)
SKIP_NODE_TYPES = {
    "n8n-nodes-base.stickyNote",
    "n8n-nodes-base.noOp",
}

# Key parameters to extract per node (skip noise like position, id, credentials)
IMPORTANT_PARAMS = {"resource", "operation", "method", "url", "path", "channel",
                    "toEmail", "subject", "event", "events", "httpMethod",
                    "table", "schema", "collection", "query", "jsCode",
                    "text", "content", "chatId", "webhookId", "responseMode",
                    "rule", "conditions", "mode", "functionCode"}


def distill_template(template_data: dict[str, Any]) -> str:
    """
    Convert a full n8n template API response into embedding-friendly text.

    Args:
        template_data: Full response from GET /api/templates/workflows/{id}

    Returns:
        Distilled text suitable for ChromaDB embedding (300-800 chars target)
    """
    wf_outer = template_data.get("workflow", {})
    name = wf_outer.get("name", "Unknown")
    description = wf_outer.get("description", "")
    categories = template_data.get("categories", [])
    category_names = [c.get("name", "") for c in categories if c.get("name")]

    # Get the actual workflow JSON (nested under workflow.workflow)
    workflow = wf_outer.get("workflow", {})
    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", {})

    # Filter out noise nodes
    useful_nodes = [n for n in nodes if n.get("type") not in SKIP_NODE_TYPES]

    if not useful_nodes:
        return ""

    # Build distilled text
    parts = []

    # Header
    parts.append(f"## Template: {name}")

    # Categories
    if category_names:
        parts.append(f"**Category**: {', '.join(category_names)}")

    # Description (truncated)
    if description:
        desc = _clean_description(description)
        if desc:
            parts.append(f"**Description**: {desc}")

    # Pattern detection
    trigger = _extract_trigger(useful_nodes)
    pattern = _detect_pattern(useful_nodes, connections)
    if trigger and pattern:
        parts.append(f"**Pattern**: {trigger} ({pattern})")

    # Node list with key params
    parts.append(f"**Nodes** ({len(useful_nodes)}):")
    for node in useful_nodes:
        node_line = _format_node(node)
        if node_line:
            parts.append(f"- {node_line}")

    # Connection chain
    chain = _build_connection_chain(useful_nodes, connections)
    if chain:
        parts.append(f"**Connections**: {chain}")

    return "\n".join(parts)


def extract_metadata(template_data: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata for DB storage from a template response."""
    wf_outer = template_data.get("workflow", {})
    workflow = wf_outer.get("workflow", {})
    nodes = workflow.get("nodes", [])
    categories = template_data.get("categories", [])

    useful_nodes = [n for n in nodes if n.get("type") not in SKIP_NODE_TYPES]
    node_types = list({n.get("type", "") for n in useful_nodes if n.get("type")})

    return {
        "n8n_template_id": wf_outer.get("id"),
        "name": wf_outer.get("name", "Unknown"),
        "description": (wf_outer.get("description") or "")[:500],
        "categories": [c.get("name", "") for c in categories if c.get("name")],
        "node_types": node_types,
        "node_count": len(useful_nodes),
        "total_views": wf_outer.get("totalViews", 0),
    }


def _clean_description(description: str) -> str:
    """Clean and truncate HTML/markdown description."""
    import re
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", description)
    # Remove markdown formatting
    text = re.sub(r"[*_#`\[\]]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate
    if len(text) > 200:
        cut = text[:200].rfind(" ")
        text = text[: cut if cut > 100 else 200] + "..."
    return text


def _extract_trigger(nodes: list[dict]) -> str | None:
    """Find the trigger node and describe it."""
    for node in nodes:
        node_type = node.get("type", "")
        if "trigger" in node_type.lower() or node_type.endswith("Trigger"):
            display = node.get("name", node_type.split(".")[-1])
            return f"{display} trigger"
        if "webhook" in node_type.lower():
            return "Webhook trigger"
    return None


def _detect_pattern(nodes: list[dict], connections: dict) -> str:
    """Classify the workflow pattern."""
    node_count = len(nodes)
    if node_count <= 1:
        return "single"

    # Count nodes with multiple outputs (branching)
    branch_count = 0
    merge_inputs: dict[str, int] = {}

    for source_name, conn_data in connections.items():
        main_outputs = conn_data.get("main", [])
        if len(main_outputs) > 1:
            branch_count += 1
        for output_group in main_outputs:
            if isinstance(output_group, list):
                for conn in output_group:
                    target = conn.get("node", "")
                    merge_inputs[target] = merge_inputs.get(target, 0) + 1
                    # Check for parallel (single output to multiple targets)
                    if len(output_group) > 1:
                        return "parallel"

    # Check for merge (node with multiple inputs)
    if any(count > 1 for count in merge_inputs.values()):
        return "merge"

    if branch_count > 0:
        return "branching"

    return "linear"


def _format_node(node: dict) -> str:
    """Format a single node for the distilled text."""
    node_type = node.get("type", "unknown")
    name = node.get("name", node_type.split(".")[-1])
    params = node.get("parameters", {})

    # Extract only important parameters
    key_params = {}
    for key, value in params.items():
        if key in IMPORTANT_PARAMS:
            # Truncate long values
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            elif isinstance(value, (dict, list)):
                # Just note presence, don't dump full structure
                value = f"<{type(value).__name__}>"
            key_params[key] = value

    type_short = node_type.split(".")[-1] if "." in node_type else node_type
    param_str = ", ".join(f'{k}="{v}"' for k, v in key_params.items()) if key_params else ""

    if param_str:
        return f"{name} (`{node_type}`): {param_str}"
    return f"{name} (`{node_type}`)"


def _build_connection_chain(nodes: list[dict], connections: dict) -> str:
    """Build a human-readable connection chain description."""
    if not connections:
        return ""

    # Build adjacency for topological ordering
    node_names = {n.get("name", "") for n in nodes}
    adj: dict[str, list[str]] = {name: [] for name in node_names}
    has_incoming: dict[str, bool] = {name: False for name in node_names}

    for source, conn_data in connections.items():
        if source not in node_names:
            continue
        for output_group in conn_data.get("main", []):
            if isinstance(output_group, list):
                for conn in output_group:
                    target = conn.get("node", "")
                    if target in node_names:
                        adj[source].append(target)
                        has_incoming[target] = True

    # Find starting nodes (no incoming edges)
    starts = [n for n, incoming in has_incoming.items() if not incoming]
    if not starts:
        starts = list(node_names)[:1]

    # Simple chain from first start node
    chain = []
    visited = set()

    def walk(node: str):
        if node in visited:
            return
        visited.add(node)
        chain.append(node)
        for target in adj.get(node, []):
            walk(target)

    for start in starts[:1]:  # Just follow the main path
        walk(start)

    if len(chain) > 6:
        return " → ".join(chain[:3]) + " → ... → " + chain[-1]
    return " → ".join(chain) if chain else ""
