# Webhook Workflow Patterns

## Pattern 1: Simple Webhook → Response
**Use case**: Receive HTTP request and respond immediately
**Nodes**: webhook → respondToWebhook
**Key config**:
- Webhook: `httpMethod: "POST"`, `path: "your-path"`, `responseMode: "responseNode"`
- Respond: `respondWith: "json"`, `responseBody: "={{ $json }}"`
**Important**: Webhook MUST have `responseMode: "responseNode"` when using Respond to Webhook node.

## Pattern 2: Webhook → Process → Response
**Use case**: Receive data, transform it, then respond
**Nodes**: webhook → set/code → respondToWebhook
**Key config**:
- Set node transforms data between webhook and response
- Code node can run custom JavaScript/Python logic

## Pattern 3: Webhook → Save to Database/Sheet
**Use case**: Receive data and store it
**Nodes**: webhook → googleSheets/postgres
**Key config**:
- Google Sheets: `resource: "sheet"`, `operation: "appendOrUpdate"`
- For Service Account: `authentication: "serviceAccount"`, use `options.folderId` for shared folders

## Pattern 4: Webhook → Multiple Actions (Parallel)
**Use case**: Receive data and do multiple things simultaneously
**Nodes**: webhook → [slack, email, sheets] (parallel branches)
**Connection**: One webhook output connects to multiple target nodes in same output array:
```json
"Webhook": {"main": [[{"node": "Slack"}, {"node": "Email"}, {"node": "Sheets"}]]}
```

## Pattern 5: Webhook → Validate → Conditional Response
**Use case**: Validate incoming data, respond differently based on validation
**Nodes**: webhook → if → [respondOK, respondError]
**Key config**:
- If node checks data validity
- Output 0 (true) → success response
- Output 1 (false) → error response
