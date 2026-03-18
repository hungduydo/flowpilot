"""
Prompt Engine — assembles system prompts dynamically for workflow generation/editing.

Includes:
- System identity and instructions
- n8n workflow JSON schema specification
- Node catalog (relevant subset via RAG or full)
- Few-shot examples
- Constraints and positioning rules
"""

from app.workflow.node_registry import get_node_catalog_summary

# ─── System Prompts ───

SYSTEM_PROMPT_CREATE = """You are an expert n8n workflow architect. Your job is to create n8n workflows based on natural language descriptions.

## Your Capabilities
- Create complete, valid n8n workflow JSON that can be directly imported into n8n
- Choose the right nodes, configure their parameters correctly
- Connect nodes with proper connections structure
- Handle complex patterns: branching, merging, error handling, loops

## n8n Workflow JSON Structure

A valid n8n workflow has this structure:
```json
{{
  "name": "Workflow Name",
  "nodes": [
    {{
      "id": "unique-uuid",
      "name": "Node Display Name",
      "type": "n8n-nodes-base.nodeType",
      "typeVersion": 1.0,
      "position": [x, y],
      "parameters": {{...}},
      "credentials": null,
      "disabled": null,
      "notes": null,
      "webhookId": null
    }}
  ],
  "connections": {{
    "Source Node Name": {{
      "main": [
        [
          {{ "node": "Target Node Name", "type": "main", "index": 0 }}
        ]
      ]
    }}
  }},
  "settings": {{
    "executionOrder": "v1"
  }}
}}
```

## Connection Rules
- The connections key maps source node NAMES (not IDs) to their outputs
- "main" is an array of output arrays. Index 0 = first output, index 1 = second output (for If/Switch nodes)
- For If node: output index 0 = "true" branch, output index 1 = "false" branch
- Each output array contains connection targets
- A node with no outputs has no entry in connections
- The trigger node is the starting point (no inputs)

## Node Positioning
- Start the trigger node at position [250, 300]
- Each subsequent node: offset +250 horizontally (x)
- For parallel branches: offset +200 vertically (y)
- Keep the layout clean and readable

## Available Node Types
{node_catalog}

## Rules
1. Every workflow MUST have exactly one trigger node (type ending in 'Trigger' or 'webhook')
2. All node names must be unique within the workflow
3. Node IDs must be valid UUIDs
4. All connection references must point to existing node names
5. Parameters must match the node type's expected format
6. For credential-dependent nodes, set credentials to null (user will configure in n8n)
7. Use descriptive node names that explain what the node does
"""

SYSTEM_PROMPT_PLAN = """You are an expert n8n workflow architect. Analyze the user's request and create a detailed plan for the workflow.

Your plan should include:
1. **Trigger**: What starts the workflow and the trigger node type
2. **Nodes**: List each node needed with:
   - Node type (from the catalog below)
   - Purpose/what it does
   - Key parameters
3. **Connections**: How nodes connect (linear, parallel branches, merge points)
4. **Logic**: Any conditions, filters, or transformations needed

## Available Node Types
{node_catalog}

Output your plan as a structured analysis. Be specific about which n8n node types to use.
"""

SYSTEM_PROMPT_EDIT = """You are an expert n8n workflow editor. You modify existing n8n workflows based on natural language instructions.

You have access to these editing functions:
- add_node: Add a new node to the workflow
- remove_node: Remove a node (optionally reconnecting neighbors)
- update_node_parameters: Change a node's parameters
- add_connection: Add a connection between two nodes
- remove_connection: Remove a connection between two nodes
- replace_node: Replace a node with a different type
- rename_node: Rename a node

## Rules
1. Preserve all parts of the workflow the user did NOT ask to change
2. Maintain valid connections after any modification
3. Keep node names unique
4. Auto-position new nodes near their connected neighbors

## Available Node Types
{node_catalog}
"""

SYSTEM_PROMPT_CHAT = """You are a helpful n8n workflow assistant. You help users:
- Understand what workflows they need
- Design workflow architecture
- Choose the right n8n nodes
- Debug workflow issues
- Explain how existing workflows work

When the user describes what they want to automate, help them think through:
1. What triggers the workflow?
2. What data transformations are needed?
3. What services/APIs are involved?
4. What error handling is needed?

Once the user is ready, you can create the workflow for them.

You have knowledge of these n8n node types:
{node_catalog}
"""

# ─── Few-Shot Examples ───

FEW_SHOT_EXAMPLES = [
    {
        "description": "When a new GitHub issue is created, send a Slack notification",
        "workflow": {
            "name": "GitHub Issue to Slack",
            "nodes": [
                {
                    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "name": "GitHub Trigger",
                    "type": "n8n-nodes-base.githubTrigger",
                    "typeVersion": 1.0,
                    "position": [250, 300],
                    "parameters": {
                        "owner": "={{$parameter.owner}}",
                        "repository": "={{$parameter.repository}}",
                        "events": ["issues"],
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                    "name": "Send Slack Message",
                    "type": "n8n-nodes-base.slack",
                    "typeVersion": 2.2,
                    "position": [500, 300],
                    "parameters": {
                        "resource": "message",
                        "operation": "send",
                        "channel": "#github-notifications",
                        "text": "=New issue: {{ $json.issue.title }}\nBy: {{ $json.issue.user.login }}\nURL: {{ $json.issue.html_url }}",
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
            ],
            "connections": {
                "GitHub Trigger": {
                    "main": [
                        [{"node": "Send Slack Message", "type": "main", "index": 0}]
                    ]
                }
            },
            "settings": {"executionOrder": "v1"},
        },
    },
    {
        "description": "Every hour, check a website and if the status is not 200, send an email alert",
        "workflow": {
            "name": "Website Health Monitor",
            "nodes": [
                {
                    "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                    "name": "Check Every Hour",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "typeVersion": 1.2,
                    "position": [250, 300],
                    "parameters": {
                        "rule": {
                            "interval": [{"field": "hours", "hoursInterval": 1}]
                        }
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [500, 300],
                    "parameters": {
                        "url": "https://example.com",
                        "options": {"redirect": {"redirect": {"followRedirects": True}}},
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "e5f6a7b8-c9d0-1234-efab-345678901234",
                    "name": "Check Status",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2.2,
                    "position": [750, 300],
                    "parameters": {
                        "conditions": {
                            "options": {"caseSensitive": True, "leftValue": ""},
                            "conditions": [
                                {
                                    "leftValue": "={{ $json.statusCode }}",
                                    "rightValue": 200,
                                    "operator": {
                                        "type": "number",
                                        "operation": "notEquals",
                                    },
                                }
                            ],
                            "combinator": "and",
                        }
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "f6a7b8c9-d0e1-2345-fabc-456789012345",
                    "name": "Send Alert Email",
                    "type": "n8n-nodes-base.emailSend",
                    "typeVersion": 2.1,
                    "position": [1000, 200],
                    "parameters": {
                        "fromEmail": "monitor@example.com",
                        "toEmail": "admin@example.com",
                        "subject": "Website Down Alert!",
                        "text": "=The website returned status {{ $json.statusCode }} at {{ $now.toISO() }}",
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
            ],
            "connections": {
                "Check Every Hour": {
                    "main": [
                        [{"node": "HTTP Request", "type": "main", "index": 0}]
                    ]
                },
                "HTTP Request": {
                    "main": [
                        [{"node": "Check Status", "type": "main", "index": 0}]
                    ]
                },
                "Check Status": {
                    "main": [
                        [{"node": "Send Alert Email", "type": "main", "index": 0}],
                        [],
                    ]
                },
            },
            "settings": {"executionOrder": "v1"},
        },
    },
    {
        "description": "Receive a webhook with customer data, save to Google Sheets, and send a welcome email",
        "workflow": {
            "name": "New Customer Onboarding",
            "nodes": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "name": "Receive Customer Data",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {
                        "httpMethod": "POST",
                        "path": "new-customer",
                        "responseMode": "responseNode",
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "name": "Save to Google Sheets",
                    "type": "n8n-nodes-base.googleSheets",
                    "typeVersion": 4.5,
                    "position": [500, 200],
                    "parameters": {
                        "resource": "sheet",
                        "operation": "appendOrUpdate",
                        "documentId": "your-spreadsheet-id",
                        "sheetName": "Customers",
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "33333333-3333-3333-3333-333333333333",
                    "name": "Send Welcome Email",
                    "type": "n8n-nodes-base.emailSend",
                    "typeVersion": 2.1,
                    "position": [500, 400],
                    "parameters": {
                        "fromEmail": "welcome@example.com",
                        "toEmail": "={{ $json.email }}",
                        "subject": "Welcome aboard, {{ $json.name }}!",
                        "text": "Hi {{ $json.name }},\n\nThank you for signing up!",
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
                {
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "Respond OK",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "typeVersion": 1.0,
                    "position": [750, 300],
                    "parameters": {
                        "respondWith": "json",
                        "responseBody": '={"status": "ok", "message": "Customer registered"}',
                    },
                    "credentials": None,
                    "disabled": None,
                    "notes": None,
                    "webhookId": None,
                },
            ],
            "connections": {
                "Receive Customer Data": {
                    "main": [
                        [
                            {"node": "Save to Google Sheets", "type": "main", "index": 0},
                            {"node": "Send Welcome Email", "type": "main", "index": 0},
                        ]
                    ]
                },
                "Save to Google Sheets": {
                    "main": [
                        [{"node": "Respond OK", "type": "main", "index": 0}]
                    ]
                },
            },
            "settings": {"executionOrder": "v1"},
        },
    },
]


def build_create_prompt(rag_context: str = "") -> str:
    """Build the system prompt for workflow creation."""
    node_catalog = get_node_catalog_summary()
    prompt = SYSTEM_PROMPT_CREATE.format(node_catalog=node_catalog)

    if rag_context:
        prompt += f"\n\n## Additional Context (from knowledge base)\n{rag_context}"

    return prompt


def build_plan_prompt(rag_context: str = "") -> str:
    """Build the system prompt for workflow planning (phase 1)."""
    node_catalog = get_node_catalog_summary()
    prompt = SYSTEM_PROMPT_PLAN.format(node_catalog=node_catalog)

    if rag_context:
        prompt += f"\n\n## Additional Context\n{rag_context}"

    return prompt


def build_edit_prompt(current_workflow_json: dict, rag_context: str = "") -> str:
    """Build the system prompt for workflow editing."""
    import json

    node_catalog = get_node_catalog_summary()
    prompt = SYSTEM_PROMPT_EDIT.format(node_catalog=node_catalog)
    prompt += f"\n\n## Current Workflow\n```json\n{json.dumps(current_workflow_json, indent=2)}\n```"

    if rag_context:
        prompt += f"\n\n## Additional Context\n{rag_context}"

    return prompt


def build_chat_prompt(rag_context: str = "") -> str:
    """Build the system prompt for general chat/guidance."""
    node_catalog = get_node_catalog_summary()
    prompt = SYSTEM_PROMPT_CHAT.format(node_catalog=node_catalog)

    if rag_context:
        prompt += f"\n\n## Additional Context\n{rag_context}"

    return prompt


def get_few_shot_messages() -> list[dict]:
    """Get few-shot examples formatted as chat messages."""
    import json

    messages = []
    for example in FEW_SHOT_EXAMPLES[:2]:  # Use 2 examples to save tokens
        messages.append({
            "role": "user",
            "content": f"Create a workflow: {example['description']}",
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps(example["workflow"], indent=2),
        })
    return messages
