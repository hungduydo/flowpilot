# Scheduled Workflow Patterns

## Pattern 1: Schedule → HTTP Check → Alert
**Use case**: Monitor a website/API periodically
**Nodes**: scheduleTrigger → httpRequest → if → emailSend/slack
**Key config**:
- Schedule Trigger: `rule.interval: [{"field": "minutes", "minutesInterval": 5}]`
- NEVER use cron string format. Always use interval object.
- Available intervals: minutes (minutesInterval), hours (hoursInterval), days (daysInterval)

## Pattern 2: Schedule → Fetch Data → Store
**Use case**: Periodically collect data and save
**Nodes**: scheduleTrigger → httpRequest → googleSheets/postgres
**Example intervals**:
- Every 5 min: `{"field": "minutes", "minutesInterval": 5}`
- Every hour: `{"field": "hours", "hoursInterval": 1}`
- Every day: `{"field": "days", "daysInterval": 1}`

## Pattern 3: Schedule → Batch Process
**Use case**: Run batch operations on schedule
**Nodes**: scheduleTrigger → httpRequest → splitInBatches → process → merge
**Key config**:
- SplitInBatches for handling large datasets
- Merge node to combine results

## Schedule Trigger Parameter Format (CRITICAL)
```json
{
  "rule": {
    "interval": [
      {"field": "minutes", "minutesInterval": 10}
    ]
  }
}
```
DO NOT use: `"rule": "*/10 * * * *"` (cron format is WRONG)
DO NOT use: `"cronExpression": "..."` (not valid parameter)
