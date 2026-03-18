# Error Handling & Advanced Patterns

## Pattern 1: Try/Catch with Error Trigger
**Use case**: Handle errors gracefully in workflows
**Setup**: On any node, enable "Continue on Error" → route error output to handler
**Nodes**: trigger → riskyNode (continueOnFail) → if (check error) → errorHandler

## Pattern 2: Retry on Failure
**Use case**: Retry HTTP requests that may fail
**Nodes**: trigger → httpRequest (with retry settings)
**Key config on httpRequest**:
- `options.retry.maxTries: 3`
- `options.retry.retryInterval: 1000` (ms)

## Pattern 3: Rate Limiting with Wait
**Use case**: Avoid API rate limits
**Nodes**: trigger → splitInBatches → wait → httpRequest → merge
**Wait node**: `n8n-nodes-base.wait`, `amount: 1`, `unit: "seconds"`

## Pattern 4: Data Transformation Pipeline
**Nodes**: trigger → set → code → filter → output
**Set node**: Add/modify fields
**Code node**: Custom JavaScript/Python logic
**Filter node**: Remove items that don't match criteria

## Pattern 5: Loop Processing
**Use case**: Process items one by one with delay
**Nodes**: trigger → splitInBatches → process → (loop back to splitInBatches)
**SplitInBatches**: `batchSize: 10`

## n8n Expression Syntax Reference
- Access current item: `{{ $json.fieldName }}`
- Access specific node output: `{{ $('Node Name').item.json.field }}`
- Current timestamp: `{{ $now.toISO() }}`
- Conditional: `{{ $json.status === 'active' ? 'Yes' : 'No' }}`
- Math: `{{ $json.price * $json.quantity }}`
