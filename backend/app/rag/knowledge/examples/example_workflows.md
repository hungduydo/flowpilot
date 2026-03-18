# Example Workflow Configurations

## Example 1: GitHub Issue → Slack Notification
**Description**: When a new GitHub issue is created, send a Slack notification
**Nodes**:
- GitHub Trigger: `events: ["issues"]`, `owner: "org"`, `repository: "repo"`
- Slack: `resource: "message"`, `operation: "send"`, `channel: "#github"`, `text: "New issue: {{ $json.issue.title }}"`

## Example 2: Website Health Monitor
**Description**: Every hour, check website status, alert if down
**Nodes**:
- Schedule Trigger: `rule: {"interval": [{"field": "hours", "hoursInterval": 1}]}`
- HTTP Request: `method: "GET"`, `url: "https://example.com"`
- If: `conditions.conditions: [{"leftValue": "={{ $json.statusCode }}", "rightValue": 200, "operator": {"type": "number", "operation": "notEquals"}}]`
- Email Send: `subject: "Website Down!"`, `text: "Status: {{ $json.statusCode }}"`

## Example 3: Customer Onboarding (Webhook → Parallel Actions)
**Description**: Receive customer data via webhook, save to sheets and send welcome email simultaneously
**Nodes**:
- Webhook: `httpMethod: "POST"`, `path: "new-customer"`, `responseMode: "responseNode"`
- Google Sheets: `resource: "sheet"`, `operation: "appendOrUpdate"`
- Email Send: `toEmail: "={{ $json.email }}"`, `subject: "Welcome {{ $json.name }}!"`
- Respond to Webhook: `respondWith: "json"`

## Example 4: Data Pipeline (Fetch → Transform → Store)
**Description**: Fetch API data, transform it, store in database
**Nodes**:
- Schedule Trigger: every 6 hours
- HTTP Request: fetch data from API
- Set: transform/map fields
- Postgres: insert into database

## Example 5: Telegram Bot Auto-Reply
**Description**: Telegram bot that replies to messages
**Nodes**:
- Telegram Trigger: listens for messages
- Code: process message, generate response
- Telegram: send reply to same chat

## Example 6: Form Submission Handler
**Description**: Handle form submissions, validate, and send confirmation
**Nodes**:
- Webhook: receive form POST data
- If: validate required fields exist
- True branch: Email Send (confirmation) → Respond to Webhook (success)
- False branch: Respond to Webhook (error: missing fields)

## Example 7: Scheduled Report
**Description**: Generate daily report from multiple sources
**Nodes**:
- Schedule Trigger: daily at 9am (`rule: {"interval": [{"field": "days", "daysInterval": 1}]}`)
- HTTP Request 1: fetch sales data
- HTTP Request 2: fetch user metrics
- Merge: combine data
- Code: format report
- Email Send: send report

## Example 8: Error Monitoring
**Description**: Monitor API for errors, alert on failure
**Nodes**:
- Schedule Trigger: every 5 minutes
- HTTP Request: health check endpoint
- If: check status !== 200
- True: Slack notification + Email alert
- False: No operation (all good)
