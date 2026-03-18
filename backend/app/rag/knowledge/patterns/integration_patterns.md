# Integration Workflow Patterns

## Pattern 1: Slack Notification
**Nodes**: trigger → slack
**Key config**:
- `resource: "message"` (NOT "webclient")
- `operation: "send"` (NOT "sendMessage")
- `channel: "#channel-name"`
- `text: "Message text with {{ $json.data }} expressions"`

## Pattern 2: Email Alert
**Nodes**: trigger → emailSend
**Key config**:
- `fromEmail: "sender@example.com"`
- `toEmail: "recipient@example.com"`
- `subject: "Subject line"`
- `text: "Email body"`

## Pattern 3: Google Sheets Integration
**Key operations**:
- Create spreadsheet: `resource: "spreadsheet"`, `operation: "create"`
- Append row: `resource: "sheet"`, `operation: "appendOrUpdate"`
- Read data: `resource: "sheet"`, `operation: "read"`
**Auth**: `authentication: "serviceAccount"` for server-side
**Shared folder**: Use `options.folderId` when creating in shared Google Drive folder

## Pattern 4: HTTP API Integration
**Nodes**: trigger → httpRequest → process
**Key config**:
- `method: "GET"|"POST"|"PUT"|"DELETE"`
- `url: "https://api.example.com/endpoint"`
- `authentication: "genericCredentialType"` for API keys
- `sendBody: true` for POST/PUT
- `bodyParameters` or `jsonBody` for request body

## Pattern 5: Database Operations
**Nodes**: trigger → postgres/mysql
**Key config**:
- `operation: "select"|"insert"|"update"|"delete"`
- `query: "SELECT * FROM table WHERE id = {{ $json.id }}"`

## Pattern 6: Telegram Bot
**Nodes**: telegramTrigger → process → telegram
**Key config**:
- Trigger: listens for messages/commands
- Send: `resource: "message"`, `operation: "sendMessage"`
- `chatId: "={{ $json.message.chat.id }}"`
