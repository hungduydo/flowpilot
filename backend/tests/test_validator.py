"""Tests for the 3-layer workflow validator."""

import pytest

from app.workflow.validator import WorkflowValidator


@pytest.fixture
def validator():
    return WorkflowValidator()


class TestSchemaValidation:
    """Layer 1: Schema validation tests."""

    def test_valid_minimal_workflow_passes(self, validator, sample_workflow):
        errors = validator.validate(sample_workflow)
        assert errors == []

    def test_missing_nodes_fails(self, validator):
        wf = {
            "name": "Test",
            "connections": {},
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("nodes" in e for e in errors)

    def test_missing_connections_fails(self, validator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": "abc",
                    "name": "Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "typeVersion": 1.0,
                    "position": [250, 300],
                    "parameters": {},
                }
            ],
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("connections" in e for e in errors)

    def test_empty_nodes_array_fails(self, validator):
        wf = {
            "name": "Test",
            "nodes": [],
            "connections": {},
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("at least one node" in e for e in errors)

    def test_duplicate_node_names_detected(self, validator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": "id1",
                    "name": "Same Name",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {},
                },
                {
                    "id": "id2",
                    "name": "Same Name",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.0,
                    "position": [500, 300],
                    "parameters": {},
                },
            ],
            "connections": {
                "Same Name": {
                    "main": [[{"node": "Same Name", "type": "main", "index": 0}]]
                }
            },
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("duplicate node name" in e for e in errors)


class TestNodeTypeValidation:
    """Layer 2: Node type validation tests."""

    def test_unknown_node_type_is_warning_not_error(self, validator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": "id1",
                    "name": "Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                },
                {
                    "id": "id2",
                    "name": "Custom",
                    "type": "n8n-nodes-community.somethingWeird",
                    "typeVersion": 1.0,
                    "position": [500, 300],
                    "parameters": {},
                },
            ],
            "connections": {
                "Trigger": {
                    "main": [[{"node": "Custom", "type": "main", "index": 0}]]
                }
            },
            "settings": {},
        }
        errors = validator.validate(wf)
        # Unknown node types produce warnings, not errors
        assert errors == []


class TestGraphValidation:
    """Layer 3: Graph validation tests."""

    def test_missing_trigger_node_detected(self, validator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": "id1",
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.0,
                    "position": [250, 300],
                    "parameters": {"url": "https://example.com"},
                },
            ],
            "connections": {},
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("trigger" in e.lower() for e in errors)

    def test_invalid_connection_target_detected(self, validator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": "id1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                },
            ],
            "connections": {
                "Webhook": {
                    "main": [
                        [{"node": "NonExistentNode", "type": "main", "index": 0}]
                    ]
                }
            },
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("NonExistentNode" in e for e in errors)

    def test_invalid_connection_source_detected(self, validator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": "id1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                },
            ],
            "connections": {
                "GhostNode": {
                    "main": [
                        [{"node": "Webhook", "type": "main", "index": 0}]
                    ]
                }
            },
            "settings": {},
        }
        errors = validator.validate(wf)
        assert any("GhostNode" in e for e in errors)
