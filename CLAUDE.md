# FlowPilot — Project Memory

## Architecture
- Frontend: Next.js 14 + TypeScript + Tailwind CSS (port 3000)
- Backend: Python FastAPI (Docker container, port 8000)
- LLM: **Ollama Cloud** (`https://ollama.com`) — model `qwen3.5:397b`
- n8n: Docker container (port 5678), workflows auto-deployed via REST API
- PostgreSQL (port 5433), Redis (port 6380), ChromaDB (port 8100) in Docker
- All services managed via `docker-compose.yml` (7 services)

## Quick Start
```bash
# 1. Clone & configure
git clone git@github.com:hungduydo/flowpilot.git
cd flowpilot
cp .env.example .env
# Edit .env — add your OLLAMA_API_KEY and N8N_API_KEY

# 2. Start all services
docker compose up -d

# 3. Run database migrations
docker compose exec backend alembic upgrade head

# 4. Open
# Frontend:   http://localhost:3000
# n8n Editor: http://localhost:5678
# API Health: http://localhost:8000/api/v1/health

# 5. Get n8n API key (first time only)
# Open http://localhost:5678 → Settings → n8n API → Create API Key
# Paste into .env as N8N_API_KEY, then restart: docker compose restart backend

# 6. Test
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a webhook that sends Slack message"}'
```

## LLM Provider Setup
- **Primary: Ollama Cloud** — `OLLAMA_BASE_URL=https://ollama.com`, model `qwen3.5:397b`
- Auth: `OLLAMA_API_KEY` in `.env` (Bearer token), get from https://ollama.com/settings/keys
- Available cloud models: qwen3.5:397b, qwen3-coder:480b, mistral-large-3:675b, deepseek-v3.2, gpt-oss:120b, etc.
- Fallback: Anthropic Claude (needs `ANTHROPIC_API_KEY`, set `LLM_PROVIDER=anthropic`)
- Provider selection via `LLM_PROVIDER` env var ("ollama" | "anthropic" | "openai")
- Ollama client uses OpenAI-compatible API at `{OLLAMA_BASE_URL}/v1/chat/completions`
- To switch to local Ollama: set `OLLAMA_BASE_URL=http://host.docker.internal:11434` and clear `OLLAMA_API_KEY`

## Phase 1: Workflow Generation Engine ✅
- Two-phase generation (Plan → Generate JSON)
- Post-processing & auto-fix for 15+ common LLM node parameter mistakes
- 3-layer validation (schema → node type → graph)
- Auto-deploy to n8n via REST API, return editor URL
- Intent classification (CREATE/EDIT/ASK/CLARIFY)
- Function-calling workflow editor (add/remove/update nodes)
- Multi-provider LLM client (OpenAI/Anthropic/Ollama local+cloud)
- 40+ node types in registry

## Phase 2: Conversation Persistence ✅
- SQLAlchemy models (Conversation, Message, Workflow) with relationships
- Alembic migrations (PostgreSQL)
- Conversation engine (multi-turn chat, intent dispatch, DB persistence)
- Context window manager (token-bounded sliding window)
- WebSocket streaming (`/api/v1/ws/chat`)
- REST conversation endpoints (`/api/v1/conversations`)

## Phase 3: RAG Knowledge Base ✅
- ChromaDB integration (local embeddings via all-MiniLM-L6-v2, no OpenAI needed)
- 49 chunks across 7 markdown files (patterns, nodes, examples)
- Auto-ingest on startup
- ONNX model cached in Docker volume (`backend_model_cache`) to avoid 80MB re-download

## Phase 4: Frontend UI ✅
- Chat UI with markdown rendering, syntax highlighting
- Welcome screen with 4 suggestion chips
- WorkflowCard: name, node count, node tags, "Open in n8n" button
- Sidebar: 3 tabs (Conversations, Workflows, Knowledge)
- Workflow list: status badges (Active/Draft/Archived), archive/unarchive with confirm
- Workflow version history panel with rollback
- Active workflow banner ("Editing: [name]") with detach button
- Zustand state management, toast notifications, loading skeletons

## Phase 5: Polish & Intelligence ✅
- Global error handler middleware (consistent JSON errors + request IDs)
- Request timing middleware with structured logging (structlog)
- Retry with exponential backoff (tenacity) on all LLM & n8n API calls
- 53 backend tests (validator, generator, n8n client, API routes, intelligence pipeline)
- Toast notification system (success/error/warning/info, auto-dismiss)
- API retry on network errors (2 retries, 1s delay)
- WebSocket auto-reconnect with exponential backoff
- Workflow version history with rollback (DB + API + UI)
- Knowledge notes system (user-defined rules injected into prompts)
- Auto-learning feedback loop (captures post-processing fixes, reuses in future prompts)
- Relevance-based context injection (keyword extraction → ranked knowledge/learning)
- Token budget system (Knowledge: 1500, Learning: 1000, RAG: 2000, Templates: 1500 tokens)

## Phase 6: Learn from n8n Templates ✅
- n8n public template API client (`api.n8n.io`) — search, fetch, batch import
- Template distillation engine (workflow JSON → embedding-friendly text)
- New ChromaDB collection `n8n_templates` for community templates
- DB model `N8nTemplate` tracking imported templates + ChromaDB chunk IDs
- Background import (FastAPI BackgroundTasks, rate-limited, async)
- Template context injection (4th layer in intelligence pipeline, 1500 token budget)
- Browse/search/import UI in sidebar "Templates" tab
- Bulk "Import Top 50 Popular" feature
- API endpoints: search, import, list imported, stats, delete

## Known LLM Generation Issues & Auto-Fixes
All handled in `generator.py` `_fix_node_parameters()` + `_post_process()`:

1. **Schedule Trigger cron format** → auto-convert to `rule.interval[]` object
2. **If node conditions** → fix string/list to proper nested object + operator parsing
3. **Slack resource/operation** → `webclient→message`, `sendMessage→send`
4. **Resource/operation defaults** — auto-fill for Google Sheets, Gmail, Telegram, GitHub, etc.
5. **Extra node properties** → strip keys not in `VALID_NODE_KEYS`
6. **Non-standard connections** → convert `true/false/else` to `main[0]/main[1]`
7. **typeVersion enforcement** → overwrite from node registry
8. **Webhook missing webhookId** → auto-generate UUID
9. **Respond to Webhook** → auto-add `responseMode: "responseNode"` to Webhook Trigger
10. **Code node** → normalize `code/script` → `jsCode`
11. **Email defaults** → fill `fromEmail`, `toEmail`, `subject`
12. **Set node assignments** → ensure proper format
13. **HTTP Request method** → normalize `httpMethod/requestMethod` → `method`
14. **Duplicate workflows** → check name before create, update instead
15. **Ollama max_tokens** → 8192 for JSON generation (qwen3.5 uses thinking tokens)

## Key File Locations

### Backend
- Config: `backend/app/config.py`
- LLM client (all providers): `backend/app/core/llm_client.py`
- Conversation engine: `backend/app/core/conversation_engine.py`
- Context manager: `backend/app/core/context_manager.py`
- Prompt templates: `backend/app/core/prompt_engine.py`
- n8n API client: `backend/app/core/n8n_client.py`
- n8n Template client: `backend/app/core/n8n_template_client.py`
- Template distiller: `backend/app/rag/template_distiller.py`
- Retry decorators: `backend/app/core/retry.py`
- Workflow generator: `backend/app/workflow/generator.py`
- Workflow validator: `backend/app/workflow/validator.py`
- Workflow editor: `backend/app/workflow/editor.py`
- Node registry (40+ types): `backend/app/workflow/node_registry.py`
- DB models: `backend/app/db/models.py` (Conversation, Message, Workflow, WorkflowVersion, KnowledgeNote, LearningRecord, N8nTemplate)
- Repositories: `backend/app/db/repositories.py`
- API routes: `backend/app/api/routes/{chat,conversations,workflows,knowledge,templates,health}.py`
- RAG: `backend/app/rag/chroma_client.py`
- Knowledge base: `backend/app/rag/knowledge/{patterns,nodes,examples}/*.md`
- Tests: `backend/tests/test_{validator,generator,n8n_client,api,intelligence_layers}.py`
- Benchmark: `backend/scripts/benchmark.py` + `benchmark_prompts.json`
- Debug API: `backend/app/api/routes/debug.py`
- Migrations: `backend/alembic/versions/`

### Frontend
- App: `frontend/src/app/{layout,page}.tsx`
- Chat: `frontend/src/components/chat/{ChatContainer,MessageBubble,ChatInput,TypingIndicator,WelcomeScreen}.tsx`
- Layout: `frontend/src/components/layout/{Header,Sidebar,ModelSelector}.tsx`
- Workflow: `frontend/src/components/workflow/{WorkflowCard,WorkflowJsonViewer,VersionHistory}.tsx`
- Knowledge: `frontend/src/components/knowledge/KnowledgePanel.tsx`
- Templates: `frontend/src/components/templates/{TemplatePanel,TemplateModal}.tsx`
- Debug: `frontend/src/components/debug/{ContextDebugPanel,DebugModal}.tsx`
- UI: `frontend/src/components/ui/{Toast,ToastContainer,Skeleton}.tsx`
- Hooks: `frontend/src/hooks/{use-chat,use-websocket}.ts`
- Stores: `frontend/src/stores/{chat-store,toast-store}.ts`
- API client: `frontend/src/lib/api.ts`
- Types: `frontend/src/lib/types.ts`

### Documentation
- `docs/rag-strategy.md` — RAG & knowledge retrieval architecture
- `docs/test-strategy.md` — Test strategy, all test cases, benchmark CLI
- `docs/benchmark-results.md` — LLM model comparison benchmark results

### Infrastructure
- Docker Compose: `docker-compose.yml` (7 services + 5 volumes)
- Environment: `.env` (not committed), `.env.example`
- Backend Dockerfile: `backend/Dockerfile`
- Frontend Dockerfile: `frontend/Dockerfile`

## Development Commands
```bash
# Start all services
docker compose up -d

# Run migrations
docker compose exec backend alembic upgrade head

# Run tests (53 tests)
cd backend && python -m pytest tests/ -v

# Health check
curl http://localhost:8000/api/v1/health

# Test workflow generation
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a webhook that sends Slack message"}'

# View logs
docker compose logs -f backend

# Rebuild after changes
docker compose up -d --build

# Create new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

## API Endpoints
- `POST /api/v1/chat` — Main chat (create/edit/ask workflows)
- `WS /api/v1/ws/chat` — WebSocket streaming
- `GET /api/v1/conversations` — List conversations
- `GET /api/v1/conversations/:id` — Get conversation + messages
- `DELETE /api/v1/conversations/:id` — Delete conversation
- `GET /api/v1/n8n/workflows` — List n8n workflows
- `POST /api/v1/n8n/workflows/:id/archive` — Archive workflow
- `POST /api/v1/n8n/workflows/:id/unarchive` — Unarchive workflow
- `GET /api/v1/n8n/workflows/:id/versions` — Version history
- `POST /api/v1/n8n/workflows/:id/versions/:vid/rollback` — Rollback
- `GET/POST/PUT/DELETE /api/v1/knowledge/notes` — Knowledge notes
- `GET/DELETE /api/v1/knowledge/learning/records` — Learning records
- `GET /api/v1/templates/search` — Search n8n community templates
- `GET /api/v1/templates/:id` — Get template detail
- `POST /api/v1/templates/import` — Import specific templates (background)
- `POST /api/v1/templates/import/popular` — Import top popular (background)
- `GET /api/v1/templates/imported` — List imported templates
- `GET /api/v1/templates/imported/stats` — Import statistics
- `DELETE /api/v1/templates/imported/:id` — Remove imported template
- `GET /api/v1/templates/categories` — List template categories
- `POST /api/v1/rag/ingest` — Ingest RAG knowledge
- `GET /api/v1/rag/search?q=` — Search RAG
- `POST /api/v1/debug/context` — Inspect intelligence pipeline context assembly (no LLM call)
- `GET /api/v1/health` — Health check

## Database Tables
- `conversations` — Chat sessions
- `messages` — Chat messages with metadata (intent, workflow_json, n8n_url)
- `workflows` — Generated workflows linked to conversations
- `workflow_versions` — Version snapshots for rollback
- `knowledge_notes` — User-defined rules (categories: node, credential, pattern, rule)
- `learning_records` — Auto-captured LLM corrections (type, node_type, frequency)
- `n8n_templates` — Imported community templates (distilled text, ChromaDB chunk IDs)

## Intelligence Pipeline
```
User message → Keyword extraction (node registry lookup)
    ├── RAG search (ChromaDB similarity, 2000 token budget)
    ├── Knowledge notes (relevance-ranked, 1500 token budget)
    ├── Learning records (relevance × frequency, 1000 token budget)
    ├── n8n Templates (community examples, 1500 token budget)
    └── Combined context (≤6000 tokens) → LLM prompt
```

## Git Conventions
- Auto-commit after completing each feature (no push unless asked)
- Commit message format: `feat:`, `fix:`, `docs:`, `refactor:`
- Co-authored-by: Claude Opus 4.6
