# FlowPilot

**AI-powered workflow copilot for n8n**

Chat-driven workflow builder that generates, deploys, and manages n8n automations using natural language.

---

## How It Works

```
You: "Create a webhook that posts to Slack when someone submits a form"
                            │
                            ▼
                   ┌─────────────────┐
                   │ Intent Classify  │  CREATE / EDIT / ASK / CLARIFY
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  RAG Retrieval   │  Search knowledge base for patterns
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  Phase 1: Plan   │  LLM plans the workflow freely
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │ Phase 2: Generate│  LLM outputs structured n8n JSON
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  Post-Process    │  Auto-fix 15+ common LLM mistakes
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  3-Layer Valid.  │  Schema → Node types → Graph
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  Deploy to n8n   │  Push via REST API
                   └────────┬────────┘
                            ▼
                  "Here's your workflow!"
                  [Open in n8n Editor →]
```

Keep chatting to refine the same workflow. Say "add an error handler" or "change the schedule to every hour" and FlowPilot edits the existing workflow in place.

---

## Features

- 🗣️ **Natural language to n8n workflows** — two-phase generation (plan, then structured JSON)
- ✏️ **Conversational editing** — keep refining the same workflow across messages
- 🔍 **RAG-powered knowledge base** — 49 chunks across 7 knowledge files for accurate node configs
- 📝 **User knowledge notes** — teach FlowPilot your preferences, credentials, and conventions
- 🚀 **Auto-deploy to n8n** with one-click editor links
- 🔄 **Workflow version history** with rollback to any previous version
- 🛡️ **3-layer validation + auto-fix** for 15+ common LLM generation mistakes
- 💬 **Multi-turn conversations** with persistent history in PostgreSQL
- 🔌 **40+ n8n node types** supported (Slack, Google Sheets, GitHub, Telegram, and more)
- 🌊 **WebSocket streaming** with real-time token delivery and auto-reconnect
- 🍞 **Toast notifications**, loading skeletons, and dark theme UI
- 🏗️ **Retry with exponential backoff** on all external API calls via tenacity

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI    │────▶│     n8n     │
│  Frontend   │◀────│   Backend    │◀────│   Server    │
│  :3000      │     │  :8000       │     │  :5678      │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────┼──────┐
                    ▼      ▼      ▼
               ┌──────┐ ┌─────┐ ┌────────┐
               │Ollama│ │ PG  │ │ChromaDB│
               │Cloud │ │     │ │  (RAG) │
               └──────┘ └─────┘ └────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Zustand, React Markdown |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy (async), Alembic, structlog, tenacity |
| **LLM** | Ollama Cloud (qwen3.5:397b) — supports Anthropic and OpenAI fallback |
| **Database** | PostgreSQL 16 |
| **Vector Store** | ChromaDB with all-MiniLM-L6-v2 local embeddings |
| **Automation** | n8n (self-hosted) |
| **Infrastructure** | Docker Compose (6 services) |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Ollama Cloud API key (get one at [ollama.com/settings/keys](https://ollama.com/settings/keys))

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/flowpilot.git
cd flowpilot

# Configure environment
cp .env.example .env
# Edit .env with your API keys (see Environment Variables below)

# Start all services
docker compose up -d

# Open the app
# Frontend:   http://localhost:3000
# n8n Editor: http://localhost:5678
# API Health: http://localhost:8000/api/v1/health
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_PROVIDER` | LLM backend: `ollama`, `anthropic`, or `openai` | Yes |
| `OLLAMA_BASE_URL` | Ollama endpoint (default: `https://ollama.com`) | Yes |
| `OLLAMA_API_KEY` | Ollama Cloud API key (Bearer token) | Yes (for cloud) |
| `OLLAMA_MODEL` | Model name (default: `qwen3.5:397b`) | No |
| `ANTHROPIC_API_KEY` | Anthropic API key (fallback provider) | No |
| `OPENAI_API_KEY` | OpenAI API key (embeddings only if not using local) | No |
| `N8N_API_KEY` | n8n API key (get from n8n Settings > API after first start) | Yes |
| `POSTGRES_USER` | PostgreSQL username (default: `llmworkflow`) | No |
| `POSTGRES_PASSWORD` | PostgreSQL password (default: `llmworkflow123`) | No |
| `APP_ENV` | Environment: `development` or `production` | No |
| `LOG_LEVEL` | Logging level: `debug`, `info`, `warning`, `error` | No |

---

## API Endpoints

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat` | Main chat endpoint (create, edit, ask) |
| `WS` | `/api/v1/ws/chat` | WebSocket streaming for real-time responses |

### Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/conversations` | List all conversations |
| `GET` | `/api/v1/conversations/:id` | Get conversation with messages |
| `DELETE` | `/api/v1/conversations/:id` | Delete a conversation |

### n8n Workflows

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/n8n/workflows` | List all n8n workflows |
| `POST` | `/api/v1/n8n/workflows/:id/archive` | Archive a workflow |
| `GET` | `/api/v1/n8n/workflows/:id/versions` | Get workflow version history |
| `POST` | `/api/v1/n8n/workflows/:id/versions/:vid/rollback` | Rollback to a specific version |

### Knowledge Notes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/knowledge/notes` | List all knowledge notes |
| `POST` | `/api/v1/knowledge/notes` | Create a knowledge note |
| `PUT` | `/api/v1/knowledge/notes/:id` | Update a knowledge note |
| `DELETE` | `/api/v1/knowledge/notes/:id` | Delete a knowledge note |

### RAG & Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/rag/ingest` | Ingest RAG knowledge base |
| `GET` | `/api/v1/rag/search?q=` | Search RAG knowledge |
| `GET` | `/api/v1/health` | Health check (includes Ollama status) |

---

## Project Structure

```
flowpilot/
├── frontend/                   # Next.js 14 app
│   └── src/
│       ├── app/                # Pages & layout
│       ├── components/         # Chat, Layout, Workflow, UI components
│       ├── hooks/              # useChat, useWebSocket
│       ├── stores/             # Zustand state (chat, toast)
│       └── lib/                # API client, types, utils
├── backend/
│   └── app/
│       ├── api/routes/         # FastAPI endpoints (chat, workflows, health, rag)
│       ├── core/               # LLM client, n8n client, conversation engine
│       ├── workflow/           # Generator, validator, editor, node registry
│       ├── rag/                # ChromaDB client + knowledge base (7 files, 49 chunks)
│       ├── db/                 # SQLAlchemy models, Alembic migrations, repositories
│       └── schemas/            # Pydantic request/response models
├── scripts/                    # DB init scripts
├── docker-compose.yml          # 6 services: frontend, backend, n8n, postgres, redis, chromadb
├── .env.example                # Environment template
└── .env                        # Local environment (not committed)
```

---

## How It Works (Detailed)

### 1. Intent Classification

The LLM classifies every user message into one of four intents:
- **CREATE** — Generate a new workflow from scratch
- **EDIT** — Modify an existing workflow (add/remove/update nodes)
- **ASK** — Answer a question about n8n, workflows, or automation
- **CLARIFY** — Ask the user for more details before proceeding

### 2. RAG Retrieval

On every request, the system searches the ChromaDB knowledge base for relevant patterns, node configurations, and example workflows. This context is injected into the LLM prompt to improve generation accuracy.

### 3. Knowledge Notes

Users can save persistent notes (e.g., "Always use my Slack channel #alerts" or "My Google Sheets credential ID is X"). These are injected into every prompt automatically.

### 4. Two-Phase Generation

- **Phase 1 (Plan):** The LLM reasons freely about what nodes are needed, how they connect, and what parameters each requires.
- **Phase 2 (Generate):** The LLM produces structured n8n-compatible JSON based on the plan.

### 5. Post-Processing & Auto-Fix

The generator automatically corrects 15+ known LLM mistakes including:
- Schedule Trigger cron format conversion
- If node condition structure
- Slack resource/operation naming
- Webhook missing `webhookId`
- Respond to Webhook `responseMode` placement
- Non-standard connection keys (`true`/`false` to `main[0]`/`main[1]`)
- Extra properties rejected by the n8n API

### 6. Three-Layer Validation

1. **Schema validation** — Correct JSON structure, required fields present
2. **Node type validation** — All node types exist in the 40+ node registry
3. **Graph validation** — Connections reference valid nodes, no orphans

### 7. Auto-Deploy

Valid workflows are pushed to n8n via its REST API. Duplicate names are detected and existing workflows are updated instead of creating duplicates.

### 8. Version Tracking

Every create and edit operation saves a version snapshot, enabling full version history and one-click rollback.

---

## Supported Node Types

| Category | Nodes |
|----------|-------|
| **Triggers** | Manual Trigger, Schedule Trigger, Webhook, Email Trigger (IMAP), GitHub Trigger |
| **Flow Control** | If, Switch, Merge, Split In Batches, Wait, No Op |
| **Data** | Set, Code (JavaScript/Python), Aggregate, Item Lists, Date & Time, Crypto |
| **Network** | HTTP Request, Respond to Webhook |
| **Communication** | Slack, Discord, Telegram, Email Send (SMTP), Microsoft Teams |
| **Google** | Google Sheets, Google Drive, Gmail |
| **Database** | PostgreSQL, MySQL, MongoDB |
| **Developer** | GitHub, Jira |
| **AI** | OpenAI, AI Agent |
| **Marketing** | Facebook Graph API |
| **CRM** | HubSpot, Notion, Airtable |
| **Finance** | Stripe |
| **SMS** | Twilio |

---

## Development

```bash
# Run backend tests
cd backend && python -m pytest tests/ -v

# Health check
curl http://localhost:8000/api/v1/health

# Test workflow generation
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a webhook that sends a Slack message"}'

# View logs
docker compose logs -f backend

# Rebuild after code changes
docker compose up -d --build
```

---

## License

MIT

---

Built with ❤️ using Claude + n8n
