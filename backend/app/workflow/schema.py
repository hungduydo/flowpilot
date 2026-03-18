"""
Pydantic models for n8n workflow JSON structure.

These models serve dual purposes:
1. Validation of LLM-generated workflow JSON
2. OpenAI Structured Outputs schema enforcement

Based on n8n Public API spec: /Users/user/Downloads/n8n-api.json
"""

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeCredential(BaseModel):
    """Reference to a credential stored in n8n."""

    id: str
    name: str


class WorkflowNode(BaseModel):
    """A single node in an n8n workflow."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Display name of the node")
    type: str = Field(
        ...,
        description="Node type identifier, e.g. 'n8n-nodes-base.httpRequest'",
    )
    typeVersion: float = Field(default=1.0, description="Version of the node type")
    position: list[int] = Field(
        ...,
        description="[x, y] position on the canvas",
        min_length=2,
        max_length=2,
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific configuration parameters",
    )
    credentials: Optional[dict[str, NodeCredential]] = Field(
        default=None,
        description="Credential references for this node",
    )
    disabled: Optional[bool] = Field(default=None, description="Whether node is disabled")
    notes: Optional[str] = Field(default=None, description="Notes attached to this node")
    notesInFlow: Optional[bool] = Field(default=None)
    executeOnce: Optional[bool] = Field(default=None)
    alwaysOutputData: Optional[bool] = Field(default=None)
    retryOnFail: Optional[bool] = Field(default=None)
    maxTries: Optional[int] = Field(default=None)
    waitBetweenTries: Optional[int] = Field(default=None)
    onError: Optional[str] = Field(default=None, description="e.g. 'stopWorkflow'")
    webhookId: Optional[str] = Field(default=None)


class ConnectionTarget(BaseModel):
    """A connection endpoint pointing to a target node."""

    node: str = Field(..., description="Target node name")
    type: str = Field(default="main", description="Connection type")
    index: int = Field(default=0, description="Input/output index")


class WorkflowSettings(BaseModel):
    """Workflow-level settings."""

    executionOrder: str = Field(default="v1")
    saveDataErrorExecution: Optional[str] = Field(default=None)
    saveDataSuccessExecution: Optional[str] = Field(default=None)
    saveManualExecutions: Optional[bool] = Field(default=None)
    callerPolicy: Optional[str] = Field(default=None)
    errorWorkflow: Optional[str] = Field(default=None)
    timezone: Optional[str] = Field(default=None)
    executionTimeout: Optional[int] = Field(default=None)


class N8nWorkflow(BaseModel):
    """
    Complete n8n workflow structure.

    Required fields for n8n API: name, nodes, connections, settings
    """

    name: str = Field(..., description="Workflow display name")
    nodes: list[WorkflowNode] = Field(
        ...,
        description="List of nodes in the workflow",
        min_length=1,
    )
    connections: dict[str, dict[str, list[list[ConnectionTarget]]]] = Field(
        default_factory=dict,
        description=(
            "Node connections map. Format: "
            '{"SourceNodeName": {"main": [[{"node": "TargetName", "type": "main", "index": 0}]]}}'
        ),
    )
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    active: bool = Field(default=False)
    staticData: Optional[Any] = Field(default=None)


# ─── Schema for OpenAI Structured Outputs ───
# This is the JSON schema version used with response_format

WORKFLOW_JSON_SCHEMA = {
    "type": "object",
    "required": ["name", "nodes", "connections", "settings"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "type", "typeVersion", "position", "parameters"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "typeVersion": {"type": "number"},
                    "position": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "parameters": {"type": "object"},
                    "credentials": {
                        "anyOf": [{"type": "object"}, {"type": "null"}],
                    },
                    "disabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                    },
                    "notes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                    "webhookId": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
            },
        },
        "connections": {"type": "object"},
        "settings": {
            "type": "object",
            "required": ["executionOrder"],
            "additionalProperties": False,
            "properties": {
                "executionOrder": {"type": "string"},
            },
        },
    },
}
