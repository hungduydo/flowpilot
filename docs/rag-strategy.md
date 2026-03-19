# RAG & Knowledge Retrieval Strategy

FlowPilot uses a **4-layer knowledge system** to provide the LLM with relevant context for every workflow generation request. This document describes the architecture, retrieval strategies, and token budget management.

---

## Architecture Overview

```
User Message
     │
     ▼
┌─────────────────────┐
│  Keyword Extraction  │  Tokenize → remove noise → expand via Node Registry
└──────────┬──────────┘
           │  keywords: {"slack", "message", "send", "n8n-nodes-base.slack", ...}
           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        4-Layer Context Assembly                              │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Layer 1: RAG │  │ Layer 2:     │  │ Layer 3:    │  │ Layer 4:         │  │
│  │ ChromaDB     │  │ Knowledge    │  │ Auto        │  │ n8n Templates    │  │
│  │ (2000 tok)   │  │ Notes        │  │ Learning    │  │ (1500 tok)       │  │
│  │              │  │ (1500 tok)   │  │ (1000 tok)  │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘  │
│         │                 │                  │                  │            │
│         ▼                 ▼                  ▼                  ▼            │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                   Merged Context (≤6000 tokens)                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
     LLM System Prompt + Context → Workflow Generation
```

---

## Layer 1: RAG Knowledge Base (ChromaDB)

### Vector Store

- **Engine**: ChromaDB (HTTP mode, Docker container on port 8100)
- **Embedding Model**: `all-MiniLM-L6-v2` (runs locally via ONNX — no API key needed)
- **Model Cache**: Docker volume `backend_model_cache:/root/.cache` prevents 80MB re-download on restart

### Collections

| Collection | Content | Source Directory |
|---|---|---|
| `workflow_patterns` | Common workflow architectures (webhooks, schedules, conditionals, integrations, error handling) | `rag/knowledge/patterns/*.md` |
| `node_reference` | Node type configurations, parameters, and gotchas | `rag/knowledge/nodes/*.md` |
| `example_workflows` | Complete example workflow JSON with explanations | `rag/knowledge/examples/*.md` |

### Knowledge Files (7 files, ~49 chunks)

```
backend/app/rag/knowledge/
├── patterns/
│   ├── webhook_patterns.md         # Webhook trigger + Respond to Webhook patterns
│   ├── schedule_patterns.md        # Schedule Trigger interval/cron formats
│   ├── conditional_patterns.md     # If/Switch node condition structures
│   ├── integration_patterns.md     # Slack, Google Sheets, GitHub, etc.
│   └── error_handling_patterns.md  # Try/catch, retry, fallback patterns
├── nodes/
│   └── node_reference.md           # Node type quick-reference (parameters, versions)
└── examples/
    └── example_workflows.md        # Full workflow JSON examples
```

### Chunking Strategy

Markdown files are split into chunks using a **section-aware** strategy:

1. **Split by `## ` headers** — each `## Section` becomes a natural chunk boundary
2. **Large sections** (>800 chars) are further split by word boundary with **100-char overlap** (10 trailing words carried forward)
3. **No headers fallback** — plain text is split at 800-char word boundaries with overlap

This preserves semantic coherence: a section about "Webhook Patterns" stays together rather than being split mid-example.

```python
# Chunk IDs are deterministic (based on file + content hash)
doc_id = f"{filename_stem}_{chunk_index}_{md5_hash[:12]}"
```

### Ingestion

- **Auto-ingest on startup**: `main.py` lifespan event calls `ingest_all_knowledge()`
- **Upsert mode**: Re-ingestion is idempotent (deterministic IDs prevent duplicates)
- **Manual trigger**: `POST /api/v1/rag/ingest` re-indexes all knowledge files
- **Search API**: `GET /api/v1/rag/search?q=send slack message` returns formatted results

### Search & Retrieval

```python
# Search across all 3 collections, return top 5 results sorted by distance
results = search(query="send slack message when webhook fires", n_results=5)
```

- Queries all 3 collections in parallel
- Results sorted by **embedding distance** (lower = more relevant)
- Top N results formatted as `[Source: filename]\n{chunk_text}` blocks
- Trimmed to **2000-token budget** before injection

---

## Layer 2: User Knowledge Notes

User-created persistent rules injected into every prompt. Examples:

- *"Always use my Slack channel #alerts for notifications"*
- *"My Google Sheets credential ID in n8n is 3q0OFkU9JaBP9gqJ"*
- *"Use Vietnamese language for workflow names"*

### Storage

- **Database**: PostgreSQL `knowledge_notes` table
- **Fields**: `content`, `category`, `is_active`, timestamps
- **CRUD API**: `GET/POST/PUT/DELETE /api/v1/knowledge/notes`

### Relevance Scoring

Notes are not injected blindly — they're **ranked by relevance** to the current user message:

```python
# Score = keyword overlap ratio (0.0 to 1.0)
score = count(keywords found in note text) / (len(keywords) * 0.3)
```

Higher-scoring notes are injected first. Notes are added incrementally until the **1500-token budget** is exhausted.

### Prompt Format

```
## User Knowledge Notes (MUST follow these instructions):
- Always use credential ID 3q0OFkU9JaBP9gqJ for Google Sheets
- Send notifications to Slack channel #alerts
- Use Vietnamese for workflow descriptions
```

---

## Layer 3: Auto-Learned Corrections

The system **automatically learns** from post-processing fixes applied during workflow generation. When the generator auto-corrects an LLM mistake (e.g., wrong Slack resource name), it records the fix for future reference.

### How Fixes Are Captured

```
LLM generates: {"resource": "webclient", "operation": "sendMessage"}
Post-processor fixes to: {"resource": "message", "operation": "send"}
                 │
                 ▼
Learning Record saved: {
    node_type: "n8n-nodes-base.slack",
    description: "Slack: resource must be 'message', operation must be 'send'",
    fix_data: {wrong: ..., correct: ...},
    frequency: 1  ← incremented on repeated occurrences
}
```

### Storage

- **Database**: PostgreSQL `learning_records` table
- **Fields**: `record_type`, `node_type`, `description`, `fix_data` (JSONB), `frequency`, timestamps
- **Upsert logic**: Duplicate fixes increment `frequency` instead of creating new records

### Ranking Formula

Records are ranked by **relevance × frequency**:

```python
relevance = keyword_overlap_score(record_text, user_keywords)  # 0.0–1.0
freq_score = log2(frequency + 1)                                # logarithmic dampening
rank = (1.0 if relevance > 0 else 0.0, relevance * freq_score, freq_score)
```

- Relevant records **always** rank above irrelevant ones (tuple comparison)
- Among relevant records, frequently-seen mistakes rank higher
- Logarithmic dampening prevents a single high-frequency fix from dominating

### Token Budget: 1000 tokens

### Prompt Format

```
## Learned Corrections (avoid these mistakes):
- [n8n-nodes-base.slack] resource must be 'message' not 'webclient' (seen 12x)
- [n8n-nodes-base.scheduleTrigger] use interval object not cron string (seen 8x)
- [n8n-nodes-base.if] conditions must be object with combinator (seen 5x)
```

---

## Keyword Extraction Pipeline

The keyword extraction step is critical — it powers relevance scoring for both Knowledge Notes and Learning Records.

### Process

```
User: "create a workflow that posts to facebook when receiving a webhook"
                    │
                    ▼
          ┌─────────────────┐
          │  1. Tokenize     │  Split by spaces, strip punctuation
          │                  │  → {"posts", "facebook", "receiving", "webhook"}
          └────────┬────────┘
                   │
          ┌────────▼────────┐
          │ 2. Remove Noise  │  Filter out noise words (a, the, create, workflow, ...)
          │                  │  → {"posts", "facebook", "receiving", "webhook"}
          └────────┬────────┘
                   │
          ┌────────▼────────────────┐
          │ 3. Node Registry Expand  │  search_nodes("facebook")
          │                          │  → matches FacebookGraphApi node
          │                          │  → adds: {"fb", "meta", "graph",
          │                          │           "n8n-nodes-base.facebookGraphApi"}
          └────────┬────────────────┘
                   │
                   ▼
Final keywords: {"posts", "facebook", "receiving", "webhook",
                 "fb", "meta", "graph", "n8n-nodes-base.facebookGraphApi"}
```

### Noise Words (filtered out)

Common English/Vietnamese words plus action verbs that don't contribute to topic identification:

```python
noise = {"a", "an", "the", "is", "to", "for", "of", "in", "and", "or",
         "create", "make", "build", "tạo", "thêm", "sửa", "xóa",
         "add", "remove", "update", "workflow", "node", "using", ...}
```

### Node Registry Expansion

Each node in the registry has a `keywords` list. When a user word matches, all related keywords are pulled in:

```python
# Node Registry entry example
NodeDef(
    type="n8n-nodes-base.facebookGraphApi",
    name="Facebook Graph API",
    keywords=["facebook", "fb", "meta", "graph", "social"],
    ...
)
```

This ensures that "facebook" in the user message also matches notes/records containing "fb", "meta", or the full node type string.

---

## Token Budget System

Each context layer has a hard token budget to prevent context window overflow:

| Layer | Budget | Priority | Rationale |
|---|---|---|---|
| Knowledge Notes | 1,500 tokens | Highest | User-defined rules must always be followed |
| Learning Records | 1,000 tokens | Medium | Prevent repeated LLM mistakes |
| RAG Results | 2,000 tokens | Standard | General reference material |
| Template Examples | 1,500 tokens | Standard | Proven community workflow patterns |
| **Total** | **≤6,000 tokens** | — | Predictable context size |

### Budget Enforcement

Items are added **incrementally** until the budget is exhausted:

```python
for note in sorted_notes:
    line = f"- {note.content}"
    tokens = estimate_tokens(line)
    if used + tokens > BUDGET:
        break  # stop adding, don't exceed budget
    lines.append(line)
    used += tokens
```

### Token Estimation

Uses a simple character-based heuristic (~4 chars per token):

```python
def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1
```

This is fast and accurate enough for budget management without requiring a tokenizer library.

### Overflow Protection

RAG results use paragraph-boundary trimming: if the full result exceeds the budget, paragraphs are dropped from the end (split on `\n\n---\n\n` separators) until it fits.

---

## Context Assembly Flow (Complete)

```python
async def _handle_create(self, session, conversation, user_message, ...):
    # 1. Extract keywords from user message
    keywords = self._extract_keywords(user_message)

    # 2. Gather context from all 4 layers (with relevance + budgets)
    rag_context = self._get_rag_context(user_message)         # ≤2000 tokens
    knowledge = await self._get_knowledge_context(session, keywords)  # ≤1500 tokens
    learning = await self._get_learning_context(session, keywords)    # ≤1000 tokens
    templates = self._get_template_context(user_message, keywords)    # ≤1500 tokens

    # 3. Merge into supplementary context
    extra_context = rag_context + knowledge + learning + templates    # ≤6000 tokens

    # 4. Build system prompt + inject context
    system_prompt = build_system_prompt() + extra_context

    # 5. Generate workflow with context-enriched prompt
    workflow, fixes = await self.generator.generate(user_message, system_prompt)

    # 6. Save any new fixes as learning records
    for fix in fixes:
        await LearningRepository.record_fix(session, fix)
```

---

## Key Implementation Files

| File | Responsibility |
|---|---|
| `backend/app/rag/chroma_client.py` | ChromaDB connection, chunking, ingestion, search |
| `backend/app/rag/knowledge/**/*.md` | Knowledge base source documents (7 files) |
| `backend/app/core/conversation_engine.py` | Keyword extraction, relevance scoring, budget management, context assembly |
| `backend/app/core/context_manager.py` | Token estimation, context window management |
| `backend/app/db/models.py` | `KnowledgeNote`, `LearningRecord` ORM models |
| `backend/app/db/repositories.py` | `KnowledgeNoteRepository`, `LearningRepository` |
| `backend/app/workflow/generator.py` | Post-processing that captures fix records |
| `backend/app/workflow/node_registry.py` | Node catalog with keywords for expansion |
| `backend/app/api/routes/knowledge.py` | CRUD API for notes and learning records |

---

## Adding New Knowledge

### Add RAG documents

1. Create a new `.md` file in the appropriate `knowledge/` subdirectory
2. Use `## Headers` to define chunk boundaries
3. Restart the backend (auto-ingest on startup) or call `POST /api/v1/rag/ingest`

### Add user knowledge notes

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/notes \
  -H "Content-Type: application/json" \
  -d '{"content": "Always use credential ID xyz for Slack", "category": "credentials"}'
```

Or use the **Knowledge** tab in the sidebar UI.

### Learning records

These are **automatic** — no manual action needed. Every time the post-processor corrects an LLM mistake, a record is created or its frequency is incremented. Over time, the most common mistakes bubble to the top of the injection list.
