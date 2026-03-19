"""Tests for workflow generator post-processing and parameter fixing."""

import pytest
import uuid

from app.workflow.generator import WorkflowGenerator


@pytest.fixture
def generator():
    return WorkflowGenerator()


class TestPostProcess:
    """Test _post_process method."""

    def test_strips_invalid_keys(self, generator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                    "decision_node": True,
                    "extra_field": "should be removed",
                },
            ],
            "connections": {},
            "settings": {"executionOrder": "v1"},
        }
        result, fixes = generator._post_process(wf)
        node = result["nodes"][0]
        assert "decision_node" not in node
        assert "extra_field" not in node
        # Valid keys should remain
        assert "id" in node
        assert "name" in node
        assert "type" in node
        # Fixes should include stripped keys
        stripped_descs = [f["description"] for f in fixes if "Stripped" in f["description"]]
        assert len(stripped_descs) >= 2

    def test_converts_true_false_connection_keys(self, generator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "If",
                    "type": "n8n-nodes-base.if",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {},
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "TrueNode",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.0,
                    "position": [500, 200],
                    "parameters": {},
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "FalseNode",
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.0,
                    "position": [500, 400],
                    "parameters": {},
                },
            ],
            "connections": {
                "If": {
                    "true": [[{"node": "TrueNode", "type": "main", "index": 0}]],
                    "false": [[{"node": "FalseNode", "type": "main", "index": 0}]],
                }
            },
            "settings": {"executionOrder": "v1"},
        }
        result, fixes = generator._post_process(wf)
        if_conn = result["connections"]["If"]
        assert "main" in if_conn
        assert "true" not in if_conn
        assert "false" not in if_conn
        # main[0] = true branch, main[1] = false branch
        assert len(if_conn["main"]) == 2

    def test_adds_webhook_id(self, generator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                },
            ],
            "connections": {},
            "settings": {"executionOrder": "v1"},
        }
        result, fixes = generator._post_process(wf)
        webhook_node = result["nodes"][0]
        assert "webhookId" in webhook_node
        assert len(webhook_node["webhookId"]) > 10  # Valid UUID

    def test_generates_uuid_for_missing_id(self, generator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                },
            ],
            "connections": {},
            "settings": {"executionOrder": "v1"},
        }
        result, fixes = generator._post_process(wf)
        assert "id" in result["nodes"][0]
        # Verify it's a valid UUID
        uuid.UUID(result["nodes"][0]["id"])

    def test_adds_response_mode_for_respond_webhook(self, generator):
        wf = {
            "name": "Test",
            "nodes": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2.0,
                    "position": [250, 300],
                    "parameters": {"path": "hook", "httpMethod": "POST"},
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "Respond",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "typeVersion": 1.0,
                    "position": [500, 300],
                    "parameters": {},
                },
            ],
            "connections": {
                "Webhook": {
                    "main": [[{"node": "Respond", "type": "main", "index": 0}]]
                }
            },
            "settings": {"executionOrder": "v1"},
        }
        result, fixes = generator._post_process(wf)
        webhook = next(n for n in result["nodes"] if n["type"] == "n8n-nodes-base.webhook")
        assert webhook["parameters"]["responseMode"] == "responseNode"


class TestFixNodeParameters:
    """Test _fix_node_parameters method."""

    def test_fixes_schedule_trigger_cron_string(self, generator):
        node = {
            "type": "n8n-nodes-base.scheduleTrigger",
            "parameters": {"rule": "0 */5 * * *"},
        }
        generator._fix_node_parameters(node)
        rule = node["parameters"]["rule"]
        assert isinstance(rule, dict)
        assert "interval" in rule
        assert isinstance(rule["interval"], list)

    def test_fixes_schedule_trigger_empty_rule(self, generator):
        node = {
            "type": "n8n-nodes-base.scheduleTrigger",
            "parameters": {"rule": {}},
        }
        generator._fix_node_parameters(node)
        rule = node["parameters"]["rule"]
        assert "interval" in rule
        assert rule["interval"][0]["field"] == "minutes"

    def test_fixes_schedule_trigger_cron_expression(self, generator):
        node = {
            "type": "n8n-nodes-base.scheduleTrigger",
            "parameters": {"cronExpression": "*/10 * * * *"},
        }
        generator._fix_node_parameters(node)
        assert "cronExpression" not in node["parameters"]
        rule = node["parameters"]["rule"]
        assert "interval" in rule
        assert rule["interval"][0]["minutesInterval"] == 10

    def test_fixes_slack_resource_operation(self, generator):
        node = {
            "type": "n8n-nodes-base.slack",
            "parameters": {
                "resource": "webclient",
                "operation": "sendMessage",
                "channel": "#general",
            },
        }
        fixes = generator._fix_node_parameters(node)
        assert node["parameters"]["resource"] == "message"
        assert node["parameters"]["operation"] == "send"
        # Should have recorded fixes for resource and operation
        assert len(fixes) >= 2

    def test_fixes_if_node_string_conditions(self, generator):
        node = {
            "type": "n8n-nodes-base.if",
            "parameters": {"conditions": "status == 200"},
        }
        generator._fix_node_parameters(node)
        conditions = node["parameters"]["conditions"]
        assert isinstance(conditions, dict)
        assert "conditions" in conditions
        assert "combinator" in conditions

    def test_fixes_if_node_list_conditions(self, generator):
        node = {
            "type": "n8n-nodes-base.if",
            "parameters": {"conditions": ["a > b"]},
        }
        generator._fix_node_parameters(node)
        conditions = node["parameters"]["conditions"]
        assert isinstance(conditions, dict)
        assert "combinator" in conditions
