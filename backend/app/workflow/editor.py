"""
Workflow Editor — modifies existing n8n workflows using function-calling.

Flow:
1. Receive current workflow JSON + user's edit request
2. LLM analyzes the request and calls edit functions
3. Each function call is applied to the workflow JSON
4. Result is validated

This approach is more reliable than asking LLM to regenerate the full JSON,
because it minimizes the surface area for errors.
"""

import json
import uuid
from typing import Any

import structlog

from app.core.llm_client import function_calling
from app.core.prompt_engine import build_edit_prompt
from app.workflow.generator import WorkflowGenerator
from app.workflow.validator import WorkflowValidator

logger = structlog.get_logger()


class WorkflowEditor:
    """Edits n8n workflows based on natural language instructions."""

    def __init__(self):
        self.validator = WorkflowValidator()
        self._generator = WorkflowGenerator()

    async def edit(
        self,
        workflow_json: dict[str, Any],
        edit_instruction: str,
        rag_context: str = "",
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Edit an existing workflow based on natural language instruction.

        Args:
            workflow_json: Current n8n workflow JSON
            edit_instruction: What the user wants to change
            rag_context: Additional context from RAG

        Returns:
            Modified workflow JSON
        """
        # Build prompt with current workflow
        system_prompt = build_edit_prompt(workflow_json, rag_context)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Please modify the workflow as follows:\n\n{edit_instruction}\n\n"
                    "Call the appropriate edit functions to make these changes."
                ),
            },
        ]

        # Get edit operations via function calling
        tool_calls = await function_calling(messages, temperature=0.3, provider=provider, model=model)

        if not tool_calls:
            logger.warning("No edit operations returned by LLM")
            return workflow_json

        # Apply operations sequentially
        modified = json.loads(json.dumps(workflow_json))  # Deep copy
        for call in tool_calls:
            func_name = call["name"]
            args = call["arguments"]
            logger.info("Applying edit operation", operation=func_name, args=args)

            try:
                modified = self._apply_operation(modified, func_name, args)
            except EditOperationError as e:
                logger.error("Edit operation failed", operation=func_name, error=str(e))
                # Continue with other operations

        # Post-process (typeVersion enforcement, resource/operation fixes, etc.)
        modified, _fixes = self._generator._post_process(modified)

        # Validate result
        errors = self.validator.validate(modified)
        if errors:
            logger.warning("Edited workflow has validation errors", errors=errors)
            # Return it anyway — let the caller decide

        return modified

    def _apply_operation(
        self,
        workflow: dict[str, Any],
        operation: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply a single edit operation to the workflow."""
        op_map = {
            "add_node": self._add_node,
            "remove_node": self._remove_node,
            "update_node_parameters": self._update_node_parameters,
            "add_connection": self._add_connection,
            "remove_connection": self._remove_connection,
            "replace_node": self._replace_node,
        }

        handler = op_map.get(operation)
        if not handler:
            raise EditOperationError(f"Unknown operation: {operation}")

        return handler(workflow, args)

    def _add_node(self, workflow: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        """Add a new node to the workflow."""
        new_node = {
            "id": str(uuid.uuid4()),
            "name": args["name"],
            "type": args["node_type"],
            "typeVersion": args.get("type_version", 1.0),
            "position": args["position"],
            "parameters": args.get("parameters", {}),
        }

        workflow["nodes"].append(new_node)

        # Add connections if specified
        connect_after = args.get("connect_after")
        connect_before = args.get("connect_before")
        output_index = args.get("output_index", 0)

        if connect_after:
            self._add_connection(workflow, {
                "from_node": connect_after,
                "to_node": args["name"],
                "from_output_index": output_index,
            })

        if connect_before:
            self._add_connection(workflow, {
                "from_node": args["name"],
                "to_node": connect_before,
            })

        return workflow

    def _remove_node(self, workflow: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        """Remove a node and optionally reconnect neighbors."""
        node_name = args["node_name"]
        reconnect = args.get("reconnect", True)

        # Find incoming and outgoing connections
        incoming_sources: list[str] = []
        outgoing_targets: list[str] = []

        connections = workflow.get("connections", {})

        # Find who connects TO this node
        for source, outputs in connections.items():
            for output_type, output_arrays in outputs.items():
                for targets in output_arrays:
                    for target in targets:
                        if target.get("node") == node_name:
                            incoming_sources.append(source)

        # Find who this node connects TO
        if node_name in connections:
            for output_type, output_arrays in connections[node_name].items():
                for targets in output_arrays:
                    for target in targets:
                        outgoing_targets.append(target.get("node", ""))

        # Reconnect if requested
        if reconnect and incoming_sources and outgoing_targets:
            for source in incoming_sources:
                for target in outgoing_targets:
                    self._add_connection(workflow, {
                        "from_node": source,
                        "to_node": target,
                    })

        # Remove node from nodes list
        workflow["nodes"] = [n for n in workflow["nodes"] if n.get("name") != node_name]

        # Remove all connections involving this node
        # Remove as source
        connections.pop(node_name, None)

        # Remove as target
        for source in list(connections.keys()):
            for output_type in list(connections[source].keys()):
                for i, targets in enumerate(connections[source][output_type]):
                    connections[source][output_type][i] = [
                        t for t in targets if t.get("node") != node_name
                    ]

        return workflow

    def _update_node_parameters(
        self, workflow: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """Update parameters of an existing node (merge)."""
        node_name = args["node_name"]
        new_params = args["parameters"]

        for node in workflow["nodes"]:
            if node.get("name") == node_name:
                node.setdefault("parameters", {}).update(new_params)
                return workflow

        raise EditOperationError(f"Node '{node_name}' not found")

    def _add_connection(
        self, workflow: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """Add a connection between two nodes."""
        from_node = args["from_node"]
        to_node = args["to_node"]
        from_output_index = args.get("from_output_index", 0)
        to_input_index = args.get("to_input_index", 0)

        connections = workflow.setdefault("connections", {})
        source_connections = connections.setdefault(from_node, {})
        main_outputs = source_connections.setdefault("main", [])

        # Ensure enough output arrays
        while len(main_outputs) <= from_output_index:
            main_outputs.append([])

        # Add target
        target = {"node": to_node, "type": "main", "index": to_input_index}

        # Avoid duplicates
        if target not in main_outputs[from_output_index]:
            main_outputs[from_output_index].append(target)

        return workflow

    def _remove_connection(
        self, workflow: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """Remove a connection between two nodes."""
        from_node = args["from_node"]
        to_node = args["to_node"]

        connections = workflow.get("connections", {})
        if from_node in connections:
            for output_type in connections[from_node]:
                for i, targets in enumerate(connections[from_node][output_type]):
                    connections[from_node][output_type][i] = [
                        t for t in targets if t.get("node") != to_node
                    ]

        return workflow

    def _replace_node(
        self, workflow: dict[str, Any], args: dict[str, Any]
    ) -> dict[str, Any]:
        """Replace a node with a different type while preserving connections."""
        old_name = args["old_node_name"]
        new_type = args["new_node_type"]
        new_name = args.get("new_name", old_name)
        new_params = args.get("new_parameters", {})
        new_type_version = args.get("new_type_version", 1.0)

        for node in workflow["nodes"]:
            if node.get("name") == old_name:
                node["type"] = new_type
                node["typeVersion"] = new_type_version
                node["parameters"] = new_params
                if new_name != old_name:
                    node["name"] = new_name
                    # Update connection references
                    self._rename_in_connections(workflow, old_name, new_name)
                return workflow

        raise EditOperationError(f"Node '{old_name}' not found")

    def _rename_in_connections(
        self, workflow: dict[str, Any], old_name: str, new_name: str
    ) -> None:
        """Update all connection references when a node is renamed."""
        connections = workflow.get("connections", {})

        # Rename as source
        if old_name in connections:
            connections[new_name] = connections.pop(old_name)

        # Rename as target
        for source in connections:
            for output_type in connections[source]:
                for targets in connections[source][output_type]:
                    for target in targets:
                        if target.get("node") == old_name:
                            target["node"] = new_name


class EditOperationError(Exception):
    """Raised when an edit operation fails."""

    pass
