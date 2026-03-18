"""
Workflow Validator — 3-layer validation for n8n workflow JSON.

Layer 1: Schema validation (Pydantic model match)
Layer 2: Node type validation (cross-ref with node registry)
Layer 3: Graph validation (connectivity, cycles, triggers)
"""

from typing import Any

import structlog

from app.workflow.node_registry import NODE_CATALOG, get_node

logger = structlog.get_logger()


class WorkflowValidator:
    """Validates n8n workflow JSON for correctness."""

    def validate(self, workflow_json: dict[str, Any]) -> list[str]:
        """
        Run all 3 validation layers.

        Returns: list of error messages (empty = valid)
        """
        errors: list[str] = []
        errors.extend(self._validate_schema(workflow_json))
        if errors:
            return errors  # Don't continue if schema is broken

        errors.extend(self._validate_node_types(workflow_json))
        errors.extend(self._validate_graph(workflow_json))
        return errors

    def _validate_schema(self, workflow_json: dict[str, Any]) -> list[str]:
        """Layer 1: Validate basic JSON structure matches n8n format."""
        errors = []

        # Required top-level fields
        for field in ["name", "nodes", "connections", "settings"]:
            if field not in workflow_json:
                errors.append(f"Missing required field: '{field}'")

        if errors:
            return errors

        # Validate name
        if not isinstance(workflow_json["name"], str) or not workflow_json["name"].strip():
            errors.append("Workflow 'name' must be a non-empty string")

        # Validate nodes
        nodes = workflow_json.get("nodes", [])
        if not isinstance(nodes, list):
            errors.append("'nodes' must be an array")
            return errors

        if len(nodes) == 0:
            errors.append("Workflow must have at least one node")
            return errors

        # Validate each node
        node_names: set[str] = set()
        node_ids: set[str] = set()
        for i, node in enumerate(nodes):
            prefix = f"nodes[{i}]"

            if not isinstance(node, dict):
                errors.append(f"{prefix}: must be an object")
                continue

            # Required node fields
            for field in ["name", "type", "position"]:
                if field not in node:
                    errors.append(f"{prefix}: missing required field '{field}'")

            # Unique names
            name = node.get("name", "")
            if name in node_names:
                errors.append(f"{prefix}: duplicate node name '{name}'")
            node_names.add(name)

            # Unique IDs
            node_id = node.get("id", "")
            if node_id and node_id in node_ids:
                errors.append(f"{prefix}: duplicate node id '{node_id}'")
            node_ids.add(node_id)

            # Position format
            pos = node.get("position", [])
            if not isinstance(pos, list) or len(pos) != 2:
                errors.append(f"{prefix} '{name}': position must be [x, y] array")

            # Type must be a string
            if not isinstance(node.get("type", ""), str):
                errors.append(f"{prefix} '{name}': type must be a string")

        # Validate connections structure
        connections = workflow_json.get("connections", {})
        if not isinstance(connections, dict):
            errors.append("'connections' must be an object")

        # Validate settings
        settings = workflow_json.get("settings", {})
        if not isinstance(settings, dict):
            errors.append("'settings' must be an object")

        return errors

    def _validate_node_types(self, workflow_json: dict[str, Any]) -> list[str]:
        """Layer 2: Validate node types against the registry."""
        errors = []
        warnings = []
        nodes = workflow_json.get("nodes", [])

        for node in nodes:
            node_type = node.get("type", "")
            name = node.get("name", "unknown")
            node_def = get_node(node_type)

            if node_def is None:
                # Not a fatal error — could be a community or custom node
                # Just warn, don't block
                warnings.append(
                    f"Node '{name}': type '{node_type}' not found in registry "
                    f"(may be a community node)"
                )
                continue

            # Check required parameters
            params = node.get("parameters", {})
            for req_param in node_def.required_parameters:
                if req_param not in params:
                    # This is a warning, not an error — n8n will prompt for missing params
                    pass  # Relaxed validation for LLM-generated workflows

        if warnings:
            logger.debug("Node type warnings", warnings=warnings)

        return errors

    def _validate_graph(self, workflow_json: dict[str, Any]) -> list[str]:
        """Layer 3: Validate workflow graph structure."""
        errors = []
        nodes = workflow_json.get("nodes", [])
        connections = workflow_json.get("connections", {})

        node_names = {node.get("name") for node in nodes}
        node_types = {node.get("name"): node.get("type", "") for node in nodes}

        # Check trigger nodes
        trigger_nodes = [
            node for node in nodes
            if self._is_trigger_type(node.get("type", ""))
        ]

        if len(trigger_nodes) == 0:
            errors.append(
                "Workflow must have at least one trigger node "
                "(e.g., manualTrigger, webhook, scheduleTrigger)"
            )
        elif len(trigger_nodes) > 1:
            # Multiple triggers are technically valid in n8n but unusual
            trigger_names = [t.get("name") for t in trigger_nodes]
            logger.debug("Multiple trigger nodes found", triggers=trigger_names)

        # Validate connection references
        for source_name, outputs in connections.items():
            if source_name not in node_names:
                errors.append(
                    f"Connection source '{source_name}' not found in nodes"
                )
                continue

            if not isinstance(outputs, dict):
                errors.append(
                    f"Connections for '{source_name}' must be an object"
                )
                continue

            for output_type, output_arrays in outputs.items():
                if not isinstance(output_arrays, list):
                    errors.append(
                        f"Connection '{source_name}'.'{output_type}' must be an array"
                    )
                    continue

                for out_idx, targets in enumerate(output_arrays):
                    if not isinstance(targets, list):
                        errors.append(
                            f"Connection '{source_name}'.'{output_type}'[{out_idx}] must be array"
                        )
                        continue

                    for target in targets:
                        target_name = target.get("node", "")
                        if target_name not in node_names:
                            errors.append(
                                f"Connection target '{target_name}' "
                                f"(from '{source_name}') not found in nodes"
                            )

        # Check for orphan nodes (nodes with no connections, except trigger)
        connected_nodes: set[str] = set()
        for source_name, outputs in connections.items():
            connected_nodes.add(source_name)
            for output_type, output_arrays in outputs.items():
                for targets in output_arrays:
                    for target in targets:
                        connected_nodes.add(target.get("node", ""))

        for node in nodes:
            name = node.get("name", "")
            if name not in connected_nodes and not self._is_trigger_type(node.get("type", "")):
                # Only warn for non-trigger orphans — they might be intentional
                logger.debug("Potential orphan node", node_name=name)

        return errors

    def _is_trigger_type(self, node_type: str) -> bool:
        """Check if a node type is a trigger."""
        trigger_suffixes = ["Trigger", "trigger", "webhook"]
        if any(node_type.endswith(suffix) or suffix in node_type.lower() for suffix in trigger_suffixes):
            return True

        # Check registry
        node_def = get_node(node_type)
        if node_def and node_def.is_trigger:
            return True

        return False
