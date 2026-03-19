# Test Strategy

FlowPilot uses a layered testing approach to verify workflow generation quality across its entire pipeline — from schema validation to the 4-layer intelligence system and multi-model benchmarking.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Test Layers                                  │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │   Unit       │  │  Integration │  │  Intelligence │  │Benchmark│ │
│  │   Tests      │  │  Tests       │  │  Pipeline     │  │  CLI    │ │
│  │              │  │              │  │  Tests        │  │         │ │
│  │ Validator    │  │ API Routes   │  │ 4-Layer       │  │ Models  │ │
│  │ Generator    │  │ HTTP Client  │  │ Context       │  │ Layers  │ │
│  │ Node Params  │  │ Error Paths  │  │ Assembly      │  │ Prompts │ │
│  └─────────────┘  └──────────────┘  └──────────────┘  └─────────┘ │
│                                                                     │
│  All mocked (no LLM/DB calls)          Real LLM calls ──────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Test Files

| File | Tests | What It Covers |
|------|-------|----------------|
| `tests/conftest.py` | — | Shared fixtures: `mock_settings`, `sample_workflow`, `n8n_workflow_response` |
| `tests/test_validator.py` | 9 | 3-layer workflow validation (schema, node types, graph) |
| `tests/test_generator.py` | 11 | Post-processing auto-fixes and parameter correction |
| `tests/test_n8n_client.py` | 6 | n8n API client (create, duplicate detection, health check) |
| `tests/test_api.py` | 5 | FastAPI route integration (health, chat, conversations, error handling) |
| `tests/test_intelligence_layers.py` | 22 | 4-layer intelligence pipeline (keywords, relevance, context assembly) |
| **Total** | **53** | |

---

## 1. Unit Tests — Workflow Validation

**File**: `tests/test_validator.py`
**Target**: `app/workflow/validator.py` — `WorkflowValidator`

Tests the 3-layer validation pipeline that catches invalid workflows before deployment.

### Layer 1: Schema Validation

| Test | Verifies |
|------|----------|
| `test_valid_minimal_workflow_passes` | Webhook → Slack workflow passes with no errors |
| `test_missing_nodes_fails` | Workflow without `nodes` key is rejected |
| `test_missing_connections_fails` | Workflow without `connections` key is rejected |
| `test_empty_nodes_array_fails` | Empty `nodes: []` is rejected ("at least one node") |
| `test_duplicate_node_names_detected` | Two nodes with same name are flagged |

### Layer 2: Node Type Validation

| Test | Verifies |
|------|----------|
| `test_unknown_node_type_is_warning_not_error` | Community/unknown node types produce warnings, not blocking errors |

### Layer 3: Graph Validation

| Test | Verifies |
|------|----------|
| `test_missing_trigger_node_detected` | Workflows without a trigger node are flagged |
| `test_invalid_connection_target_detected` | Connections pointing to non-existent node names are caught |
| `test_invalid_connection_source_detected` | Connections from non-existent source nodes are caught |

---

## 2. Unit Tests — Generator Post-Processing

**File**: `tests/test_generator.py`
**Target**: `app/workflow/generator.py` — `WorkflowGenerator._post_process()`, `_fix_node_parameters()`

Tests the 15+ auto-fix rules that correct common LLM mistakes in generated workflow JSON.

### Post-Process Tests

| Test | Auto-Fix Rule |
|------|---------------|
| `test_strips_invalid_keys` | Removes non-standard node keys (`decision_node`, `extra_field`) keeping only valid n8n keys |
| `test_converts_true_false_connection_keys` | Converts If node `true/false` connection keys → `main[0]/main[1]` |
| `test_adds_webhook_id` | Auto-generates `webhookId` UUID for Webhook nodes missing it |
| `test_generates_uuid_for_missing_id` | Generates valid UUID for nodes missing `id` field |
| `test_adds_response_mode_for_respond_webhook` | Adds `responseMode: "responseNode"` to Webhook when paired with Respond to Webhook |

### Parameter Fix Tests

| Test | Auto-Fix Rule |
|------|---------------|
| `test_fixes_schedule_trigger_cron_string` | Converts cron string `"0 */5 * * *"` → `rule.interval[]` object |
| `test_fixes_schedule_trigger_empty_rule` | Empty `rule: {}` → default `{interval: [{field: "minutes"}]}` |
| `test_fixes_schedule_trigger_cron_expression` | Converts `cronExpression: "*/10 * * * *"` → `rule.interval[{minutesInterval: 10}]` |
| `test_fixes_slack_resource_operation` | Corrects `resource: "webclient"` → `"message"`, `operation: "sendMessage"` → `"send"` |
| `test_fixes_if_node_string_conditions` | Converts string condition `"status == 200"` → proper nested conditions object |
| `test_fixes_if_node_list_conditions` | Converts list condition `["a > b"]` → proper nested conditions object |

---

## 3. Integration Tests — n8n API Client

**File**: `tests/test_n8n_client.py`
**Target**: `app/core/n8n_client.py` — `N8nClient`

Tests the HTTP client that communicates with the n8n REST API for deployment.

| Test | Verifies |
|------|----------|
| `test_create_workflow_success` | Creates new workflow via POST, returns workflow with `id` |
| `test_create_workflow_duplicate_detection` | When workflow name exists, updates via PUT instead of creating duplicate |
| `test_error_handling_raises_n8n_client_error` | HTTP 400 responses raise `N8nClientError` with status code and detail |
| `test_uses_public_url` | Editor URLs use `n8n_public_url` setting (not internal Docker hostname) |
| `test_replaces_internal_hostname` | `host.docker.internal` is replaced with `localhost` in URLs |
| `test_health_check_returns_true_on_200` | Health check returns `True` on HTTP 200 |
| `test_health_check_returns_false_on_error` | Health check returns `False` on connection error |

---

## 4. Integration Tests — API Routes

**File**: `tests/test_api.py`
**Target**: `app/api/routes/*.py` via FastAPI TestClient

Tests HTTP endpoints with mocked backend dependencies (DB, LLM engine).

### Setup Pattern
```python
@pytest.fixture
def app():
    # Patches DB init, RAG ingestion, and lifespan
    # Returns FastAPI app with noop_lifespan
    ...

@pytest.fixture
def client(app):
    return TestClient(app)
```

| Test | Endpoint | Verifies |
|------|----------|----------|
| `test_health_returns_200` | `GET /api/v1/health` | Returns 200 with `status: "ok"` and `llm_provider` field |
| `test_chat_success` | `POST /api/v1/chat` | Accepts message, returns response with `intent` and `message` |
| `test_list_conversations` | `GET /api/v1/conversations` | Returns conversation list with expected structure |
| `test_unhandled_exception_returns_json` | `POST /api/v1/chat` | Global exception handler returns JSON 500 (not HTML), includes `error` field |

---

## 5. Intelligence Pipeline Tests

**File**: `tests/test_intelligence_layers.py`
**Target**: `app/core/conversation_engine.py` — `ConversationEngine`

Tests the 4-layer context assembly pipeline that enriches LLM prompts with relevant knowledge. All tests use mocks — no real DB, ChromaDB, or LLM calls.

### T1: Keyword Extraction

**Target**: `ConversationEngine._extract_keywords(message)`

| Test | Verifies |
|------|----------|
| `test_extracts_node_keywords` | "send a Slack message when webhook fires" → includes `"slack"`, `"webhook"` |
| `test_excludes_noise_words` | Common words (`"a"`, `"create"`, `"that"`, `"workflow"`) are filtered out |
| `test_expands_with_node_types` | "send Slack notification" expands to include full node type identifiers |
| `test_empty_message` | Empty string returns empty set (no crash) |
| `test_mixed_case` | "SLACK Webhook GitHub" → lowercased keywords extracted correctly |

### T2: Relevance Scoring

**Target**: `ConversationEngine._relevance_score(text, keywords)`

| Test | Verifies |
|------|----------|
| `test_high_relevance` | Text with 3/3 matching keywords → score > 0.5 |
| `test_zero_relevance` | Text with 0 matching keywords → score = 0.0 |
| `test_partial_relevance` | Text with 1/8 matching keywords → 0.0 < score < 1.0 |
| `test_empty_keywords` | Empty keyword set → score = 0.0 |
| `test_case_insensitive` | Uppercase text matches lowercase keywords |

### T3: Knowledge Notes Assembly

**Target**: `ConversationEngine._get_knowledge_context(session, keywords)`

| Test | Verifies |
|------|----------|
| `test_relevant_notes_first` | 5 notes (2 Slack, 3 GitHub) → Slack keywords cause Slack notes to appear first |
| `test_empty_notes` | No notes in DB → returns empty string |

**Mock pattern**: Patches `KnowledgeNoteRepository.list_all` with `SimpleNamespace` objects.

### T4: Learning Records Assembly

**Target**: `ConversationEngine._get_learning_context(session, keywords)`

| Test | Verifies |
|------|----------|
| `test_high_frequency_first` | Slack record (frequency=10) appears before generic record (frequency=1) when Slack keywords active |
| `test_empty_records` | No records → returns empty string |

**Mock pattern**: Patches `LearningRepository.get_relevant` with `SimpleNamespace` objects.

### T5: Token Budget Enforcement

**Target**: `ConversationEngine._get_knowledge_context()`, `_trim_to_budget()`

| Test | Verifies |
|------|----------|
| `test_knowledge_context_within_budget` | 50 notes (~5000 tokens total) → output stays under 1500 token budget |
| `test_rag_trim_to_budget` | Large text (20 paragraphs) trimmed to respect 500 token limit |

**Token estimation**: Uses `app.core.context_manager.estimate_tokens()` (~len/3 chars).

### T6: RAG Context Retrieval

**Target**: `ConversationEngine._get_rag_context(message)`

| Test | Verifies |
|------|----------|
| `test_returns_search_results` | ChromaDB search returns content → non-empty result with expected text |
| `test_handles_search_failure` | ChromaDB exception → returns empty string (graceful degradation) |
| `test_handles_empty_results` | ChromaDB returns nothing → returns empty string |

**Mock pattern**: Patches `app.core.conversation_engine.rag_search`.

### T7: Template Context Retrieval

**Target**: `ConversationEngine._get_template_context(message, keywords)`

| Test | Verifies |
|------|----------|
| `test_returns_with_header` | Template chunks found → output includes "Reference Templates" header |
| `test_handles_no_templates` | No template chunks → returns empty string |
| `test_handles_search_failure` | ChromaDB exception → returns empty string (graceful degradation) |

**Mock pattern**: Patches `app.core.conversation_engine.rag_search` with `collection_names=[COLLECTION_TEMPLATES]`.

---

## 6. Benchmark CLI

**File**: `scripts/benchmark.py`
**Prompts**: `scripts/benchmark_prompts.json`

Interactive benchmark script that runs real LLM generation against test prompts and scores quality. Not part of `pytest` — run manually or in CI with real infrastructure.

### Test Prompts (10)

| ID | Prompt | Expected Nodes |
|----|--------|---------------|
| `slack-webhook` | Webhook → Slack message | `webhook`, `slack` |
| `schedule-email` | Check website every 5 min, email on error | `scheduleTrigger`, `httpRequest`, `if` |
| `google-sheets-webhook` | Webhook → Google Sheets | `webhook`, `googleSheets` |
| `telegram-notification` | Webhook → Telegram | `webhook`, `telegram` |
| `github-slack` | GitHub issue → Slack | `githubTrigger`, `slack` |
| `code-transform` | Webhook → Code → Response | `webhook`, `code` |
| `http-json-parse` | Hourly API fetch → Sheets | `scheduleTrigger`, `httpRequest`, `googleSheets` |
| `if-branching` | Webhook → If amount > 100 → Slack | `webhook`, `if`, `slack` |
| `rss-slack` | RSS feed → Slack | `rssFeedRead` |
| `gmail-sheets` | Gmail trigger → Google Sheets | `gmailTrigger`, `googleSheets` |

### Quality Metrics

| Metric | How Measured | Source |
|--------|-------------|--------|
| `validation_errors` | Count from `WorkflowValidator.validate()` | `validator.py` |
| `fix_count` | Length of auto-fix list from `_post_process()` | `generator.py` |
| `expected_nodes_found` | % of expected node types present in output | benchmark |
| `param_accuracy` | % of expected params correct before post-processing | benchmark |
| `node_count_in_range` | Is actual node count within `min_nodes..max_nodes`? | benchmark |
| `has_trigger` | Does workflow contain a trigger node? | benchmark |
| `all_connected` | Are all nodes reachable in the connection graph? | benchmark |
| `generation_time_ms` | Wall clock time for generation | benchmark |

### Overall Score Formula (0–100)

```
score = valid_rate × 25 + (1 − fix_rate) × 25 + node_accuracy × 25 + param_accuracy × 25
```

### Layer Configurations

| Config | RAG | Knowledge | Learning | Templates |
|--------|-----|-----------|----------|-----------|
| `all` | Yes | Yes | Yes | Yes |
| `none` | — | — | — | — |
| `rag-only` | Yes | — | — | — |
| `templates-only` | — | — | — | Yes |
| `no-templates` | Yes | Yes | Yes | — |

### Model Comparison

Models specified as `provider:model_name`:

| Spec | Provider | Model |
|------|----------|-------|
| `ollama:qwen3.5:397b` | Ollama Cloud | Qwen 3.5 397B |
| `ollama:mistral-large-3:675b` | Ollama Cloud | Mistral Large 3 |
| `ollama:deepseek-v3.2` | Ollama Cloud | DeepSeek V3.2 |
| `ollama:qwen3-coder:480b` | Ollama Cloud | Qwen3 Coder |
| `anthropic:claude-sonnet-4-20250514` | Anthropic | Claude Sonnet 4 |
| `openai:gpt-4o` | OpenAI | GPT-4o |

### Usage

```bash
# Default: all vs none layers, default model
docker compose exec backend python -m scripts.benchmark

# Compare models
docker compose exec backend python -m scripts.benchmark \
  --models ollama:qwen3.5:397b ollama:deepseek-v3.2 anthropic:claude-sonnet-4-20250514

# Compare layers
docker compose exec backend python -m scripts.benchmark --layers all none rag-only

# Full matrix (3 models × 2 configs × 10 prompts = 60 LLM calls)
docker compose exec backend python -m scripts.benchmark \
  --models ollama:qwen3.5:397b ollama:deepseek-v3.2 \
  --layers all none

# Dry run (no LLM calls, shows context assembly)
docker compose exec backend python -m scripts.benchmark --dry-run

# Single prompt with verbose output
docker compose exec backend python -m scripts.benchmark --only slack-webhook --verbose
```

---

## 7. Debug API Endpoint

**File**: `app/api/routes/debug.py`
**Endpoint**: `POST /api/v1/debug/context`

Read-only endpoint that shows what context each intelligence layer would inject for a given message, without making any LLM call. Used for pipeline transparency and debugging.

**Request**:
```json
{ "message": "Create a webhook that sends a Slack message" }
```

**Response**:
```json
{
  "message": "Create a webhook that sends a Slack message",
  "keywords": ["slack", "webhook", "n8n-nodes-base.slack", "n8n-nodes-base.webhook", ...],
  "rag": { "text": "...", "tokens": 1847, "budget": 2000 },
  "knowledge_notes": { "text": "...", "tokens": 450, "budget": 1500 },
  "learning_records": { "text": "...", "tokens": 280, "budget": 1000 },
  "templates": { "text": "...", "tokens": 1200, "budget": 1500 },
  "total_tokens": 3777
}
```

---

## Running Tests

```bash
# All tests (53 tests, ~1 second)
cd backend && python -m pytest tests/ -v

# By category
python -m pytest tests/test_validator.py -v            # Validation (9 tests)
python -m pytest tests/test_generator.py -v            # Generator fixes (11 tests)
python -m pytest tests/test_n8n_client.py -v           # n8n client (6 tests)
python -m pytest tests/test_api.py -v                  # API routes (5 tests)
python -m pytest tests/test_intelligence_layers.py -v  # Intelligence pipeline (22 tests)

# Run benchmark (requires Docker services running)
docker compose exec backend python -m scripts.benchmark --dry-run
```

---

## Test Conventions

### Mocking Strategy
- **No real external calls**: All unit/integration tests use `unittest.mock` (AsyncMock, MagicMock, patch)
- **DB models as SimpleNamespace**: Mock DB records with `types.SimpleNamespace(id=..., content=..., ...)`
- **FastAPI TestClient**: API tests use synchronous `TestClient` with dependency overrides
- **Async tests**: Use `@pytest.mark.asyncio` (auto mode configured in `pyproject.toml`)

### Fixture Pattern
```python
# conftest.py — shared across all test files
@pytest.fixture
def sample_workflow():
    """Minimal valid n8n workflow (Webhook → Slack)."""
    return { ... }

# Per-file fixtures
@pytest.fixture
def generator():
    return WorkflowGenerator()
```

### Naming Convention
- Test files: `test_{component}.py`
- Test classes: `Test{Feature}` (e.g., `TestSchemaValidation`, `TestKeywordExtraction`)
- Test methods: `test_{what_is_verified}` (e.g., `test_fixes_slack_resource_operation`)

### Configuration
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```
