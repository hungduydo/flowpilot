# n8n Node Quick Reference

## Triggers
| Node | Type | Key Parameters |
|------|------|---------------|
| Webhook | n8n-nodes-base.webhook | httpMethod, path, responseMode |
| Schedule Trigger | n8n-nodes-base.scheduleTrigger | rule.interval (NOT cron) |
| Manual Trigger | n8n-nodes-base.manualTrigger | (none) |
| Email Trigger (IMAP) | n8n-nodes-base.emailReadImap | mailbox, options |
| Telegram Trigger | n8n-nodes-base.telegramTrigger | updates (message, callback_query) |
| GitHub Trigger | n8n-nodes-base.githubTrigger | owner, repository, events |
| Cron | n8n-nodes-base.cron | cronExpression |

## Flow Control
| Node | Type | Key Parameters |
|------|------|---------------|
| If | n8n-nodes-base.if | conditions (object with combinator) |
| Switch | n8n-nodes-base.switch | rules, fallbackOutput |
| Merge | n8n-nodes-base.merge | mode (append/combine/multiplex) |
| Split In Batches | n8n-nodes-base.splitInBatches | batchSize |
| Wait | n8n-nodes-base.wait | amount, unit |
| No Operation | n8n-nodes-base.noOp | (none) |

## Data
| Node | Type | Key Parameters |
|------|------|---------------|
| Set | n8n-nodes-base.set | mode, assignments or jsonOutput |
| Code | n8n-nodes-base.code | language (javaScript/python), jsCode/pythonCode |
| Filter | n8n-nodes-base.filter | conditions |
| Sort | n8n-nodes-base.sort | sortFieldsUi |
| Limit | n8n-nodes-base.limit | maxItems |
| Aggregate | n8n-nodes-base.aggregate | aggregate |
| Respond to Webhook | n8n-nodes-base.respondToWebhook | respondWith, responseBody |

## Network
| Node | Type | Key Parameters |
|------|------|---------------|
| HTTP Request | n8n-nodes-base.httpRequest | method, url, authentication |
| GraphQL | n8n-nodes-base.graphql | endpoint, query |
| FTP | n8n-nodes-base.ftp | host, operation |

## Communication
| Node | Type | Key Parameters |
|------|------|---------------|
| Slack | n8n-nodes-base.slack | resource:"message", operation:"send", channel, text |
| Email Send | n8n-nodes-base.emailSend | fromEmail, toEmail, subject, text |
| Telegram | n8n-nodes-base.telegram | resource, operation, chatId, text |
| Discord | n8n-nodes-base.discord | webhookUri, content |

## Productivity
| Node | Type | Key Parameters |
|------|------|---------------|
| Google Sheets | n8n-nodes-base.googleSheets | resource, operation, documentId, sheetName |
| Google Drive | n8n-nodes-base.googleDrive | resource, operation, folderId |
| Notion | n8n-nodes-base.notion | resource, operation, databaseId |
| Airtable | n8n-nodes-base.airtable | application, table, operation |

## Database
| Node | Type | Key Parameters |
|------|------|---------------|
| Postgres | n8n-nodes-base.postgres | operation, query |
| MySQL | n8n-nodes-base.mySql | operation, query |
| MongoDB | n8n-nodes-base.mongoDb | collection, operation |
| Redis | n8n-nodes-base.redis | operation, key |

## AI
| Node | Type | Key Parameters |
|------|------|---------------|
| OpenAI | n8n-nodes-base.openAi | resource, operation, model, prompt |
| HTTP Request (AI API) | n8n-nodes-base.httpRequest | Use for any AI API via HTTP |
