"""
Workflow Generator — converts natural language to n8n workflow JSON.

Two-Phase Approach:
  Phase 1 (Plan): LLM reasons freely about which nodes, connections, and logic are needed.
  Phase 2 (Generate): Plan + schema → LLM produces valid n8n JSON via Structured Outputs.

This separation improves reliability: reasoning and JSON generation are decoupled.
"""

import json
import uuid
from typing import Any

import structlog

from app.core.llm_client import chat_completion, structured_output
from app.core.prompt_engine import (
    build_create_prompt,
    build_plan_prompt,
    get_few_shot_messages,
)
from app.workflow.schema import N8nWorkflow
from app.workflow.validator import WorkflowValidator

logger = structlog.get_logger()


class WorkflowGenerator:
    """Generates n8n workflows from natural language descriptions."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.validator = WorkflowValidator()

    async def generate(
        self,
        user_description: str,
        rag_context: str = "",
        conversation_history: list[dict] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete n8n workflow from a natural language description.

        Args:
            user_description: What the user wants the workflow to do
            rag_context: Additional context from RAG retrieval
            conversation_history: Previous chat messages for context

        Returns:
            Valid n8n workflow JSON dict

        Raises:
            WorkflowGenerationError: If generation fails after all retries
        """
        # Phase 1: Plan
        plan = await self._phase1_plan(
            user_description, rag_context, conversation_history,
            provider=provider, model=model,
        )
        logger.info("Phase 1 plan generated", plan_length=len(plan))

        # Phase 2: Generate with retries
        last_errors: list[str] = []
        for attempt in range(1, self.max_retries + 1):
            try:
                workflow_json = await self._phase2_generate(
                    user_description, plan, rag_context, last_errors,
                    provider=provider, model=model,
                )

                # Post-process
                workflow_json = self._post_process(workflow_json)

                # Validate
                errors = self.validator.validate(workflow_json)
                if errors:
                    logger.warning(
                        "Validation failed, retrying",
                        attempt=attempt,
                        errors=errors,
                    )
                    last_errors = errors
                    continue

                logger.info(
                    "Workflow generated successfully",
                    attempt=attempt,
                    name=workflow_json.get("name"),
                    num_nodes=len(workflow_json.get("nodes", [])),
                )
                return workflow_json

            except Exception as e:
                logger.error("Generation error", attempt=attempt, error=str(e))
                last_errors = [str(e)]

        raise WorkflowGenerationError(
            f"Failed to generate valid workflow after {self.max_retries} attempts. "
            f"Last errors: {last_errors}"
        )

    async def _phase1_plan(
        self,
        user_description: str,
        rag_context: str = "",
        conversation_history: list[dict] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        """Phase 1: Generate a structured plan for the workflow."""
        system_prompt = build_plan_prompt(rag_context)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation context if available
        if conversation_history:
            messages.extend(conversation_history[-6:])  # Last 3 turns

        messages.append({
            "role": "user",
            "content": f"Create a plan for this workflow:\n\n{user_description}",
        })

        return await chat_completion(messages, temperature=0.5, provider=provider, model=model)

    async def _phase2_generate(
        self,
        user_description: str,
        plan: str,
        rag_context: str = "",
        previous_errors: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Phase 2: Generate valid n8n JSON from the plan using Structured Outputs."""
        system_prompt = build_create_prompt(rag_context)

        # Build the generation prompt
        generation_prompt = (
            f"## User Request\n{user_description}\n\n"
            f"## Workflow Plan\n{plan}\n\n"
            "## Instructions\n"
            "Based on the plan above, generate a complete, valid n8n workflow JSON. "
            "Ensure every node has a unique UUID id, proper typeVersion, and correct connections."
        )

        if previous_errors:
            error_text = "\n".join(f"- {e}" for e in previous_errors)
            generation_prompt += (
                f"\n\n## IMPORTANT: Previous attempt had these errors, please fix them:\n"
                f"{error_text}"
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add few-shot examples
        messages.extend(get_few_shot_messages())

        messages.append({"role": "user", "content": generation_prompt})

        return await structured_output(messages, temperature=0.3, provider=provider, model=model)

    # Allowed keys for n8n node objects
    VALID_NODE_KEYS = {
        "id", "name", "type", "typeVersion", "position", "parameters",
        "credentials", "disabled", "notes", "webhookId",
    }

    def _fix_node_parameters(self, node: dict[str, Any]) -> None:
        """Fix common LLM mistakes in node parameters for specific node types."""
        node_type = node.get("type", "")
        params = node.get("parameters", {})

        # ── Schedule Trigger: fix cron string → proper interval object ──
        if node_type == "n8n-nodes-base.scheduleTrigger":
            # Try to extract interval from any cron-like field LLM may have set
            cron_source = params.pop("cronExpression", None) or params.pop("cron", None)
            rule = params.get("rule")

            if rule is None or (isinstance(rule, dict) and not rule) or rule == {}:
                # No rule — parse from cron or default
                if cron_source and isinstance(cron_source, str):
                    interval = self._parse_cron_to_interval(cron_source)
                else:
                    interval = {"field": "minutes", "minutesInterval": 5}
                params["rule"] = {"interval": [interval]}
            elif isinstance(rule, str):
                # LLM generated a cron string like "0 */5 * * *"
                interval = self._parse_cron_to_interval(rule)
                params["rule"] = {"interval": [interval]}
            elif isinstance(rule, dict) and "interval" not in rule:
                params["rule"] = {"interval": [{"field": "minutes", "minutesInterval": 5}]}

        # ── If node: fix conditions format ──
        if node_type == "n8n-nodes-base.if":
            conditions = params.get("conditions")
            if isinstance(conditions, str):
                # LLM generated a string instead of proper conditions object
                params["conditions"] = {
                    "options": {"caseSensitive": True, "leftValue": ""},
                    "conditions": [
                        {
                            "leftValue": "={{ $json.statusCode }}",
                            "rightValue": 200,
                            "operator": {"type": "number", "operation": "notEquals"},
                        }
                    ],
                    "combinator": "and",
                }
            elif isinstance(conditions, list):
                # LLM generated a list instead of proper object
                params["conditions"] = {
                    "options": {"caseSensitive": True, "leftValue": ""},
                    "conditions": [
                        {
                            "leftValue": "={{ $json.statusCode }}",
                            "rightValue": 200,
                            "operator": {"type": "number", "operation": "notEquals"},
                        }
                    ],
                    "combinator": "and",
                }

        # ── HTTP Request: ensure url exists ──
        if node_type == "n8n-nodes-base.httpRequest":
            if "url" not in params:
                params["url"] = "https://example.com"
            # Fix httpMethod → method (n8n uses "method" internally but accepts both)

        # ── Webhook: ensure path exists ──
        if node_type == "n8n-nodes-base.webhook":
            if "path" not in params:
                params["path"] = "webhook"
            if "httpMethod" not in params:
                params["httpMethod"] = "POST"

        # ── Slack: fix resource/operation ──
        if node_type == "n8n-nodes-base.slack":
            if params.get("resource") == "webclient":
                params["resource"] = "message"
            if params.get("operation") == "sendMessage":
                params["operation"] = "send"

        node["parameters"] = params

    def _parse_cron_to_interval(self, cron: str) -> dict[str, Any]:
        """Parse a cron-like string to n8n interval format."""
        import re
        parts = cron.strip().split()

        # Try to extract simple intervals from cron parts
        if len(parts) >= 2:
            minute_part = parts[0]
            hour_part = parts[1]

            # "*/N * * * *" or "0 */N * * *" pattern
            if minute_part.startswith("*/"):
                match = re.match(r"\*/(\d+)", minute_part)
                if match:
                    return {"field": "minutes", "minutesInterval": int(match.group(1))}

            if hour_part.startswith("*/"):
                match = re.match(r"\*/(\d+)", hour_part)
                if match:
                    return {"field": "hours", "hoursInterval": int(match.group(1))}

            if minute_part == "0" and hour_part == "*":
                return {"field": "hours", "hoursInterval": 1}

        # Try to find any number in the string (e.g. "every 10 minutes")
        match = re.search(r"(\d+)", cron)
        if match:
            n = int(match.group(1))
            if n <= 59:
                return {"field": "minutes", "minutesInterval": n}
            else:
                return {"field": "hours", "hoursInterval": max(1, n // 60)}

        return {"field": "minutes", "minutesInterval": 5}

    def _post_process(self, workflow_json: dict[str, Any]) -> dict[str, Any]:
        """Post-process the generated workflow JSON to ensure n8n API compatibility."""
        # Ensure all nodes have UUIDs and webhook nodes have webhookId
        for node in workflow_json.get("nodes", []):
            if not node.get("id") or len(node["id"]) < 10:
                node["id"] = str(uuid.uuid4())
            # Webhook nodes need a webhookId for n8n to register them
            if "webhook" in node.get("type", "").lower() and not node.get("webhookId"):
                node["webhookId"] = str(uuid.uuid4())

        # Ensure settings exist
        if "settings" not in workflow_json:
            workflow_json["settings"] = {"executionOrder": "v1"}

        # If workflow has Respond to Webhook node, ensure Webhook trigger has responseMode
        node_types = {n.get("type", "") for n in workflow_json.get("nodes", [])}
        has_respond_node = "n8n-nodes-base.respondToWebhook" in node_types
        if has_respond_node:
            for node in workflow_json.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    node.setdefault("parameters", {})["responseMode"] = "responseNode"

        # Clean nodes: fix parameters, remove invalid keys and null values
        for node in workflow_json.get("nodes", []):
            # Fix common LLM parameter mistakes
            self._fix_node_parameters(node)

            # Remove keys not accepted by n8n API
            extra_keys = [k for k in node if k not in self.VALID_NODE_KEYS]
            for k in extra_keys:
                del node[k]

            # Remove null optional fields for cleaner JSON
            keys_to_remove = [
                k for k, v in node.items()
                if v is None and k not in ("id", "name", "type", "typeVersion", "position", "parameters")
            ]
            for k in keys_to_remove:
                del node[k]

        # Clean connections: fix LLM-generated non-standard formats
        connections = workflow_json.get("connections", {})
        cleaned_connections = {}
        for source_name, conn_data in connections.items():
            if isinstance(conn_data, dict):
                # Normalize: only "main" key is valid, merge "true"/"else"/"false" into "main"
                main_outputs = conn_data.get("main", [])

                # If LLM used "true"/"false" keys (If node pattern), convert to main[0]/main[1]
                if "true" in conn_data or "false" in conn_data:
                    true_branch = conn_data.get("true", [[]])[0] if conn_data.get("true") else []
                    false_branch = conn_data.get("false", [[]])[0] if conn_data.get("false") else []
                    main_outputs = [true_branch, false_branch]

                # Remove "else" connections (not valid in n8n)
                cleaned_connections[source_name] = {"main": main_outputs}
            else:
                cleaned_connections[source_name] = conn_data

        # Remove empty connection entries
        workflow_json["connections"] = {
            k: v for k, v in cleaned_connections.items()
            if v.get("main") and any(outputs for outputs in v["main"])
        }

        return workflow_json

    async def generate_simple(self, user_description: str) -> dict[str, Any]:
        """
        Simplified single-phase generation for simple workflows.
        Skips the planning phase for speed.
        """
        system_prompt = build_create_prompt()

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(get_few_shot_messages())
        messages.append({
            "role": "user",
            "content": f"Create a workflow: {user_description}",
        })

        workflow_json = await structured_output(messages, temperature=0.3)
        workflow_json = self._post_process(workflow_json)

        errors = self.validator.validate(workflow_json)
        if errors:
            raise WorkflowGenerationError(f"Validation failed: {errors}")

        return workflow_json


class WorkflowGenerationError(Exception):
    """Raised when workflow generation fails."""

    pass
