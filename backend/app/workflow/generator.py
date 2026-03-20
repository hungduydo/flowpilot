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
from app.workflow.node_registry import NODE_CATALOG, get_node
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
    ) -> tuple[dict[str, Any], list[dict]]:
        """
        Generate a complete n8n workflow from a natural language description.

        Args:
            user_description: What the user wants the workflow to do
            rag_context: Additional context from RAG retrieval
            conversation_history: Previous chat messages for context

        Returns:
            Tuple of (valid n8n workflow JSON dict, list of auto-fixes applied)

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
                workflow_json, fixes = self._post_process(workflow_json)

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
                    fixes_applied=len(fixes),
                )
                return workflow_json, fixes

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

        return await chat_completion(messages, temperature=0.5, provider=provider, model=model, _trace_step="phase1_plan")

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

        return await structured_output(messages, temperature=0.3, provider=provider, model=model, _trace_step="phase2_generate")

    # Allowed keys for n8n node objects
    VALID_NODE_KEYS = {
        "id", "name", "type", "typeVersion", "position", "parameters",
        "credentials", "disabled", "notes", "webhookId",
    }

    # ── Correct resource/operation mappings for nodes that need them ──
    RESOURCE_OP_DEFAULTS: dict[str, dict[str, str]] = {
        "n8n-nodes-base.slack": {"resource": "message", "operation": "send"},
        "n8n-nodes-base.telegram": {"resource": "message", "operation": "sendMessage"},
        "n8n-nodes-base.googleSheets": {"resource": "sheet", "operation": "appendOrUpdate"},
        "n8n-nodes-base.googleDrive": {"resource": "file", "operation": "upload"},
        "n8n-nodes-base.gmail": {"resource": "message", "operation": "send"},
        "n8n-nodes-base.github": {"resource": "issue", "operation": "getAll"},
        "n8n-nodes-base.jira": {"resource": "issue", "operation": "create"},
        "n8n-nodes-base.discord": {"resource": "message", "operation": "send"},
        "@n8n/n8n-nodes-langchain.openAi": {"resource": "chat", "operation": "message"},
        "n8n-nodes-base.postgres": {"operation": "executeQuery"},
        "n8n-nodes-base.mySql": {"operation": "executeQuery"},
        "n8n-nodes-base.mongoDb": {"operation": "find"},
        "n8n-nodes-base.facebookGraphApi": {"resource": "post", "operation": "create"},
        "n8n-nodes-base.microsoftTeams": {"resource": "chatMessage", "operation": "create"},
        "n8n-nodes-base.hubspot": {"resource": "contact", "operation": "create"},
        "n8n-nodes-base.notion": {"resource": "page", "operation": "create"},
        "n8n-nodes-base.airtable": {"resource": "record", "operation": "create"},
    }

    # ── Common wrong resource/operation LLM outputs → correct values ──
    RESOURCE_OP_FIXES: dict[str, dict[str, str]] = {
        # Slack
        "webclient": "message",
        "chat": "message",
        # Operations
        "sendMessage": "send",
        "postMessage": "send",
        "post_message": "send",
        "send_message": "send",
        "createMessage": "send",
    }

    def _fix_node_parameters(self, node: dict[str, Any]) -> list[dict]:
        """Fix common LLM mistakes in node parameters for specific node types.

        Returns a list of fix records describing what was corrected.
        """
        fixes: list[dict] = []
        node_type = node.get("type", "")
        params = node.get("parameters", {})
        if not isinstance(params, dict):
            fixes.append({
                "node_type": node_type,
                "description": f"Parameters was {type(params).__name__} instead of dict",
                "fix_data": {"wrong": str(params), "correct": "{}"},
            })
            params = {}
            node["parameters"] = params

        # ── 1. Enforce typeVersion from registry ──
        node_def = get_node(node_type)
        if node_def:
            old_version = node.get("typeVersion")
            if old_version != node_def.type_version:
                fixes.append({
                    "node_type": node_type,
                    "description": f"typeVersion corrected from {old_version} to {node_def.type_version}",
                    "fix_data": {"wrong": old_version, "correct": node_def.type_version},
                })
            node["typeVersion"] = node_def.type_version

        # ── 2. Schedule Trigger: fix cron string → proper interval object ──
        if node_type == "n8n-nodes-base.scheduleTrigger":
            cron_source = params.pop("cronExpression", None) or params.pop("cron", None)
            rule = params.get("rule")

            if rule is None or (isinstance(rule, dict) and not rule) or rule == {}:
                if cron_source and isinstance(cron_source, str):
                    interval = self._parse_cron_to_interval(cron_source)
                    fixes.append({
                        "node_type": node_type,
                        "description": f"Schedule Trigger: converted cron '{cron_source}' to interval object",
                        "fix_data": {"wrong": cron_source, "correct": interval},
                    })
                else:
                    interval = {"field": "minutes", "minutesInterval": 5}
                    if rule is not None:
                        fixes.append({
                            "node_type": node_type,
                            "description": "Schedule Trigger: empty rule replaced with default 5-min interval",
                            "fix_data": {"wrong": rule, "correct": interval},
                        })
                params["rule"] = {"interval": [interval]}
            elif isinstance(rule, str):
                interval = self._parse_cron_to_interval(rule)
                fixes.append({
                    "node_type": node_type,
                    "description": f"Schedule Trigger: converted cron string rule '{rule}' to interval object",
                    "fix_data": {"wrong": rule, "correct": {"interval": [interval]}},
                })
                params["rule"] = {"interval": [interval]}
            elif isinstance(rule, dict) and "interval" not in rule:
                fixes.append({
                    "node_type": node_type,
                    "description": "Schedule Trigger: rule dict missing 'interval' key, replaced with default",
                    "fix_data": {"wrong": rule, "correct": {"interval": [{"field": "minutes", "minutesInterval": 5}]}},
                })
                params["rule"] = {"interval": [{"field": "minutes", "minutesInterval": 5}]}

        # ── 3. If node: fix conditions format ──
        if node_type == "n8n-nodes-base.if":
            conditions = params.get("conditions")
            needs_fix = False

            if isinstance(conditions, (str, list)):
                needs_fix = True
            elif isinstance(conditions, dict):
                # Check if it has the correct nested structure
                inner = conditions.get("conditions")
                if inner is None:
                    needs_fix = True
                elif isinstance(inner, list) and len(inner) > 0:
                    # Validate each condition has leftValue + operator
                    for cond in inner:
                        if not isinstance(cond, dict) or "leftValue" not in cond:
                            needs_fix = True
                            break
                        # Fix operator if it's a string instead of object
                        op = cond.get("operator")
                        if isinstance(op, str):
                            cond["operator"] = self._parse_operator_string(op)
            elif conditions is None:
                needs_fix = True

            if needs_fix:
                fixes.append({
                    "node_type": node_type,
                    "description": f"If node: conditions format was invalid ({type(conditions).__name__}), replaced with default structure",
                    "fix_data": {"wrong": str(conditions)[:200], "correct": "standard n8n conditions object"},
                })
                params["conditions"] = {
                    "options": {"caseSensitive": True, "leftValue": ""},
                    "conditions": [
                        {
                            "leftValue": "={{ $json.value }}",
                            "rightValue": "",
                            "operator": {"type": "string", "operation": "notEmpty"},
                        }
                    ],
                    "combinator": "and",
                }

        # ── 4. HTTP Request: ensure url exists ──
        if node_type == "n8n-nodes-base.httpRequest":
            if "url" not in params:
                fixes.append({
                    "node_type": node_type,
                    "description": "HTTP Request: missing 'url' parameter, added placeholder",
                    "fix_data": {"wrong": None, "correct": "https://example.com"},
                })
                params["url"] = "https://example.com"
            # Normalize method field
            method = params.pop("httpMethod", None) or params.pop("requestMethod", None)
            if method and "method" not in params:
                fixes.append({
                    "node_type": node_type,
                    "description": f"HTTP Request: renamed httpMethod/requestMethod to 'method'",
                    "fix_data": {"wrong": "httpMethod/requestMethod", "correct": "method"},
                })
                params["method"] = method.upper()

        # ── 5. Webhook: ensure path + httpMethod ──
        if node_type == "n8n-nodes-base.webhook":
            if "path" not in params:
                params["path"] = "webhook"
            if "httpMethod" not in params:
                params["httpMethod"] = "POST"

        # ── 6. Fix resource/operation for ALL nodes that need them ──
        defaults = self.RESOURCE_OP_DEFAULTS.get(node_type)
        if defaults:
            # Fix known wrong values
            res = params.get("resource", "")
            if isinstance(res, str) and res in self.RESOURCE_OP_FIXES:
                correct_res = self.RESOURCE_OP_FIXES[res]
                fixes.append({
                    "node_type": node_type,
                    "description": f"Resource corrected from '{res}' to '{correct_res}'",
                    "fix_data": {"wrong": res, "correct": correct_res},
                })
                params["resource"] = correct_res

            op = params.get("operation", "")
            if isinstance(op, str) and op in self.RESOURCE_OP_FIXES:
                correct_op = self.RESOURCE_OP_FIXES[op]
                fixes.append({
                    "node_type": node_type,
                    "description": f"Operation corrected from '{op}' to '{correct_op}'",
                    "fix_data": {"wrong": op, "correct": correct_op},
                })
                params["operation"] = correct_op

            # Fill missing resource/operation from defaults
            for key, default_val in defaults.items():
                if key not in params or not params[key]:
                    fixes.append({
                        "node_type": node_type,
                        "description": f"Missing '{key}' filled with default '{default_val}'",
                        "fix_data": {"wrong": None, "correct": default_val},
                    })
                    params[key] = default_val

        # ── 7. Code node: ensure jsCode field exists ──
        if node_type == "n8n-nodes-base.code":
            if "jsCode" not in params and "pythonCode" not in params:
                # Check if LLM put code in a different field
                code = params.pop("code", None) or params.pop("script", None)
                if code:
                    fixes.append({
                        "node_type": node_type,
                        "description": "Code node: renamed 'code'/'script' field to 'jsCode'",
                        "fix_data": {"wrong": "code/script", "correct": "jsCode"},
                    })
                    params["jsCode"] = code
                else:
                    params["jsCode"] = "// Add your code here\nreturn items;"

        # ── 8. Email: ensure required fields ──
        if node_type == "n8n-nodes-base.emailSend":
            params.setdefault("fromEmail", "noreply@example.com")
            params.setdefault("toEmail", "recipient@example.com")
            params.setdefault("subject", "Notification")

        # ── 9. Set node: ensure assignments format ──
        if node_type == "n8n-nodes-base.set":
            assignments = params.get("assignments")
            if assignments is None or (isinstance(assignments, dict) and not assignments):
                params["assignments"] = {
                    "assignments": [
                        {"id": str(uuid.uuid4()), "name": "key", "value": "value", "type": "string"}
                    ]
                }

        node["parameters"] = params
        return fixes

    @staticmethod
    def _parse_operator_string(op_str: str) -> dict[str, str]:
        """Convert a string operator like '!=' or 'equals' to n8n operator object."""
        mapping = {
            "==": {"type": "string", "operation": "equals"},
            "!=": {"type": "string", "operation": "notEquals"},
            "equals": {"type": "string", "operation": "equals"},
            "notEquals": {"type": "string", "operation": "notEquals"},
            "contains": {"type": "string", "operation": "contains"},
            "notContains": {"type": "string", "operation": "notContains"},
            ">": {"type": "number", "operation": "gt"},
            "<": {"type": "number", "operation": "lt"},
            ">=": {"type": "number", "operation": "gte"},
            "<=": {"type": "number", "operation": "lte"},
            "gt": {"type": "number", "operation": "gt"},
            "lt": {"type": "number", "operation": "lt"},
            "exists": {"type": "string", "operation": "exists"},
            "notEmpty": {"type": "string", "operation": "notEmpty"},
            "empty": {"type": "string", "operation": "empty"},
        }
        return mapping.get(op_str, {"type": "string", "operation": "equals"})

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

    def _post_process(self, workflow_json: dict[str, Any]) -> tuple[dict[str, Any], list[dict]]:
        """Post-process the generated workflow JSON to ensure n8n API compatibility.

        Returns:
            Tuple of (processed_workflow, list_of_fixes_applied).
        """
        all_fixes: list[dict] = []

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
            fixes = self._fix_node_parameters(node)
            all_fixes.extend(fixes)

            # Remove keys not accepted by n8n API
            extra_keys = [k for k in node if k not in self.VALID_NODE_KEYS]
            for k in extra_keys:
                all_fixes.append({
                    "node_type": node.get("type", "unknown"),
                    "description": f"Stripped invalid node key '{k}'",
                    "fix_data": {"wrong": k, "correct": None},
                })
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
                    all_fixes.append({
                        "node_type": None,
                        "description": f"Connection '{source_name}': converted true/false keys to main[0]/main[1]",
                        "fix_data": {"wrong": "true/false keys", "correct": "main array"},
                    })

                # Remove "else" connections (not valid in n8n)
                cleaned_connections[source_name] = {"main": main_outputs}
            else:
                cleaned_connections[source_name] = conn_data

        # Remove empty connection entries
        workflow_json["connections"] = {
            k: v for k, v in cleaned_connections.items()
            if v.get("main") and any(outputs for outputs in v["main"])
        }

        return workflow_json, all_fixes

    async def generate_simple(self, user_description: str) -> tuple[dict[str, Any], list[dict]]:
        """
        Simplified single-phase generation for simple workflows.
        Skips the planning phase for speed.

        Returns:
            Tuple of (valid n8n workflow JSON dict, list of auto-fixes applied)
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
        workflow_json, fixes = self._post_process(workflow_json)

        errors = self.validator.validate(workflow_json)
        if errors:
            raise WorkflowGenerationError(f"Validation failed: {errors}")

        return workflow_json, fixes


class WorkflowGenerationError(Exception):
    """Raised when workflow generation fails."""

    pass
