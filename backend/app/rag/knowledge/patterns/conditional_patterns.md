# Conditional & Branching Patterns

## Pattern 1: If/Else Branch
**Use case**: Route data based on a condition
**Nodes**: trigger → if → [trueAction, falseAction]
**Connection format**:
```json
"If Node": {
  "main": [
    [{"node": "True Branch Node", "type": "main", "index": 0}],
    [{"node": "False Branch Node", "type": "main", "index": 0}]
  ]
}
```
- Output index 0 = TRUE branch
- Output index 1 = FALSE branch

## If Node Parameters (CRITICAL)
```json
{
  "conditions": {
    "options": {"caseSensitive": true, "leftValue": ""},
    "conditions": [
      {
        "leftValue": "={{ $json.statusCode }}",
        "rightValue": 200,
        "operator": {"type": "number", "operation": "equals"}
      }
    ],
    "combinator": "and"
  }
}
```
DO NOT use string conditions like `"conditions": "statusCode != 200"`
DO NOT use array conditions like `"conditions": ["statusCode", "!=", 200]`

## Available operators:
- number: equals, notEquals, gt, lt, gte, lte
- string: equals, notEquals, contains, notContains, startsWith, endsWith, regex
- boolean: true, false

## Pattern 2: Switch (Multiple Branches)
**Use case**: Route to different nodes based on value
**Nodes**: trigger → switch → [case1, case2, case3, default]
**Type**: `n8n-nodes-base.switch`

## Pattern 3: Merge After Branch
**Use case**: Rejoin branches after conditional processing
**Nodes**: trigger → if → [branch1, branch2] → merge → continue
**Type**: `n8n-nodes-base.merge`
