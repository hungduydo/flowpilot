# LLM Workflow Builder — Project Memory

## Architecture
- Backend: Python FastAPI (Docker container, port 8000)
- LLM: **Ollama Cloud** (`https://ollama.com`) — model `qwen3.5:397b`
- n8n: Docker container (port 5678), workflows auto-deployed via REST API
- PostgreSQL (port 5433), Redis (port 6380), ChromaDB (port 8100) in Docker
- Frontend: Next.js 14 + TypeScript + Tailwind CSS (port 3000)

## LLM Provider Setup
- **Primary: Ollama Cloud** — `OLLAMA_BASE_URL=https://ollama.com`, model `qwen3.5:397b`
- Auth: `OLLAMA_API_KEY` in `.env` (Bearer token), get from https://ollama.com/settings/keys
- Available cloud models: qwen3.5:397b, qwen3-coder:480b, mistral-large-3:675b, deepseek-v3.2, gpt-oss:120b, etc.
- Fallback: Anthropic Claude (needs separate API credits from Pro subscription)
- OpenAI key for embeddings only
- Provider selection via `LLM_PROVIDER` env var ("ollama" | "anthropic" | "openai")
- Ollama client uses OpenAI-compatible API at `{OLLAMA_BASE_URL}/v1/chat/completions`

## Phase 1 Status: ✅ COMPLETE
- ✅ Two-phase workflow generation (Plan → Generate JSON)
- ✅ Post-processing & auto-fix node parameters
- ✅ 3-layer validation (schema → node type → graph)
- ✅ Auto-deploy to n8n via REST API
- ✅ Return n8n editor URL to user
- ✅ Intent classification (CREATE/EDIT/ASK/CLARIFY)
- ✅ Function-calling workflow editor (add/remove/update nodes)
- ✅ Multi-provider LLM client (OpenAI/Anthropic/Ollama local+cloud)
- ✅ Health check endpoint with Ollama status
- ✅ End-to-end tested: chat → generate → validate → deploy → view on n8n

## Known LLM Generation Issues & Fixes

### 1. Python str.format() KeyError with JSON in prompts
- **Problem**: System prompts contain JSON examples with `{curly braces}`. `.format(node_catalog=...)` treats them as placeholders → KeyError.
- **Fix**: Escape all braces as `{{` / `}}` in prompt strings, EXCEPT `{node_catalog}`.
- **File**: `backend/app/core/prompt_engine.py`

### 2. Schedule Trigger wrong parameters format
- **Problem**: LLMs generate cron strings `"rule": "0 */5 * * *"` or `"cronExpression": "..."` but n8n expects object format.
- **Correct format**: `{"rule": {"interval": [{"field": "minutes", "minutesInterval": N}]}}` or `{"field": "hours", "hoursInterval": N}`
- **Fix**: `_fix_node_parameters()` in `generator.py` auto-converts. Compact prompt shows correct format.

### 3. If node conditions format
- **Problem**: LLMs generate string or list conditions instead of proper n8n object.
- **Correct format**: `{"conditions": {"options": {...}, "conditions": [{leftValue, rightValue, operator}], "combinator": "and"}}`
- **Fix**: `_fix_node_parameters()` replaces invalid formats with default condition.

### 4. Slack node wrong resource/operation names
- **Problem**: `"resource": "webclient"`, `"operation": "sendMessage"`.
- **Correct**: `"resource": "message"`, `"operation": "send"`
- **Fix**: `_fix_node_parameters()` auto-corrects.

### 5. Extra node properties rejected by n8n API
- **Problem**: LLM adds `"decision_node": true` etc. → n8n API 400 error.
- **Fix**: `_post_process()` strips keys not in `VALID_NODE_KEYS`.

### 6. Non-standard connection keys
- **Problem**: LLM generates `"true"/"false"/"else"` keys instead of `"main"` array indices.
- **Fix**: `_post_process()` converts to `main[0]`/`main[1]`.

### 7. Compact prompt for Ollama (local small models)
- **Problem**: Full system prompt + few-shot overwhelm small models.
- **Fix**: `OLLAMA_COMPACT_SYSTEM` with concise rules + 1 inline example. Note: cloud models (397B) handle full prompts fine but compact prompt still used for consistency.

### 8. n8n editor URL shows Docker internal hostname
- **Fix**: `get_workflow_editor_url()` uses `settings.n8n_public_url` (`http://localhost:5678`).

### 9. Claude API message order
- **Fix**: `_fix_message_order()` merges consecutive same-role messages.

### 10. Ollama Cloud auth
- **Problem**: Cloud requires Bearer token, local doesn't.
- **Fix**: `_ollama_headers()` returns auth header only when `ollama_api_key` is set. Applied to health check, model pull, and OpenAI client.

### 11. Webhook node missing webhookId
- **Problem**: LLM generates `webhookId: null` → n8n can't register webhook for production mode.
- **Fix**: `_post_process()` auto-generates UUID for `webhookId` on any webhook-type node.

### 12. Webhook + Respond to Webhook missing responseMode
- **Problem**: LLM puts `responseMode` on Respond node instead of Webhook Trigger → "Unused Respond to Webhook" error.
- **Fix**: `_post_process()` detects `respondToWebhook` node → auto-adds `responseMode: "responseNode"` to Webhook Trigger.

### 13. Duplicate workflow creation
- **Problem**: n8n API doesn't check duplicate names → multiple POST calls create duplicates.
- **Fix**: `create_workflow()` in `n8n_client.py` checks existing workflows by name first → updates instead of creating duplicate.

### 14. Ollama Cloud structured output max_tokens
- **Problem**: qwen3.5 uses thinking tokens internally, `max_tokens=4096` not enough → truncated/empty JSON.
- **Fix**: `_structured_ollama()` uses `max_tokens=8192` for JSON generation.

### 15. Google Sheets Service Account needs Drive API
- **Problem**: Service Account gets "Forbidden" when creating spreadsheets.
- **Fix**: Must enable both **Google Sheets API** AND **Google Drive API** in Google Cloud Console. Share target folder with Service Account email (Editor role).

## Google Service Account Setup (n8n)
- Credential type: `googleApi` (Service Account)
- Credential ID in n8n: `3q0OFkU9JaBP9gqJ`
- Shared folder ID: `1vHFfkR7ia9kJCG_Kk-8DfcS9vlPOF2ex`
- Required APIs: Google Sheets API + Google Drive API (both enabled in Cloud Console)
- When creating spreadsheets in shared folder, use `options.folderId`

## Key File Locations
- LLM client (all providers): `backend/app/core/llm_client.py`
- Workflow generator (2-phase + post-processing): `backend/app/workflow/generator.py`
- Prompt templates: `backend/app/core/prompt_engine.py`
- n8n API client: `backend/app/core/n8n_client.py`
- Node registry (30+ types): `backend/app/workflow/node_registry.py`
- Validator (3-layer): `backend/app/workflow/validator.py`
- Chat API route: `backend/app/api/routes/chat.py`
- Workflow API routes: `backend/app/api/routes/workflows.py`
- Health check: `backend/app/api/routes/health.py`
- Config: `backend/app/config.py`
- Chat schemas: `backend/app/schemas/chat.py`
- Docker: `docker-compose.yml`, `.env`

## Development Commands
```bash
# Start infrastructure (n8n, postgres, redis, chromadb, backend)
docker compose up -d

# No need for local Ollama — using Ollama Cloud
# To switch back to local: set OLLAMA_BASE_URL=http://host.docker.internal:11434 and clear OLLAMA_API_KEY

# Test end-to-end
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tạo workflow gửi Slack khi có webhook"}'

# Health check
curl http://localhost:8000/api/v1/health

# View workflow on n8n
open http://localhost:5678
```

## Phase 2 Status: ✅ COMPLETE
- ✅ SQLAlchemy models (Conversation, Message, Workflow) with relationships
- ✅ Alembic migrations (tables created in PostgreSQL)
- ✅ Repository layer (CRUD for conversations, messages, workflows)
- ✅ Conversation engine (multi-turn chat, intent dispatch, DB persistence)
- ✅ Context window manager (token-bounded sliding window)
- ✅ WebSocket streaming (`/api/v1/ws/chat`) — real-time token streaming for chat
- ✅ REST conversation endpoints (`/api/v1/conversations`)
- ✅ All messages & workflows saved to PostgreSQL with conversation linking
- ✅ Streaming for ASK_QUESTION/CLARIFY, non-streaming for CREATE/EDIT workflow

## Phase 3 Status: ✅ COMPLETE
- ✅ ChromaDB integration (local embeddings via all-MiniLM-L6-v2, no OpenAI needed)
- ✅ Knowledge base: 49 chunks across 7 markdown files (patterns, nodes, examples)
- ✅ RAG retriever integrated into conversation engine (auto-search on every request)
- ✅ Auto-ingest on startup (main.py lifespan)
- ✅ API endpoints: POST /api/v1/rag/ingest, GET /api/v1/rag/search?q=
- ✅ Knowledge docs: webhook patterns, schedule patterns, conditional patterns, integrations, error handling, node reference, example workflows
- ✅ End-to-end tested: RAG context improves LLM workflow generation accuracy

### RAG File Locations
- ChromaDB client + ingestion: `backend/app/rag/chroma_client.py`
- Knowledge base: `backend/app/rag/knowledge/{patterns,nodes,examples}/*.md`
- Collections: workflow_patterns, node_reference, example_workflows

## Phase 4 Status: ✅ COMPLETE
- ✅ Next.js 14 + TypeScript + Tailwind CSS frontend
- ✅ Chat UI with markdown rendering (react-markdown + syntax highlighting)
- ✅ Welcome screen with suggestion chips (4 common workflow patterns)
- ✅ WorkflowCard component: name, node count, node tags, trigger info
- ✅ "Open in n8n" button (links to n8n editor URL)
- ✅ Copy JSON, Download JSON, View JSON (expandable) actions
- ✅ Sidebar: Conversations tab (list, create, delete, switch)
- ✅ Sidebar: n8n Workflows tab (lists all workflows from n8n server with status dots)
- ✅ Typing indicator with status text ("Thinking...")
- ✅ Zustand state management (chat-store)
- ✅ REST API integration (chat, conversations, n8n proxy)
- ✅ WebSocket hook ready (use-websocket.ts)
- ✅ Docker Compose integration (frontend service on port 3000)
- ✅ End-to-end tested: chat → generate workflow → WorkflowCard → Open in n8n

### Frontend API Response Mapping
- Chat API returns `message` (not `response`), `workflow` (not `workflow_json`)
- `workflow` is nested: `{ workflow_json, n8n_workflow_id, n8n_editor_url, is_new, validation_errors }`
- Conversation detail returns `metadata: { intent, has_workflow, workflow_json, n8n_url }` on messages
- Conversation titles may be null/empty — frontend shows "Untitled chat" fallback

### Frontend File Locations
- App layout/page: `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`
- Chat components: `frontend/src/components/chat/{ChatContainer,MessageBubble,ChatInput,TypingIndicator,WelcomeScreen}.tsx`
- Layout components: `frontend/src/components/layout/{Header,Sidebar}.tsx`
- Workflow components: `frontend/src/components/workflow/{WorkflowCard,WorkflowJsonViewer}.tsx`
- Hooks: `frontend/src/hooks/{use-chat,use-websocket}.ts`
- Store: `frontend/src/stores/chat-store.ts`
- API client: `frontend/src/lib/api.ts`
- Types: `frontend/src/lib/types.ts`
- Utils: `frontend/src/lib/utils.ts`

## Pending Work (Next Phase)
- **Phase 5**: Polish — retry logic, error handling, logging, tests
- **Phase 5**: Visual node graph renderer
- **Phase 5**: Workflow version history UI
- **Phase 5**: Conversation title auto-generation from first message
- Add `anthropic` package to `pyproject.toml`
