const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const MAX_RETRIES = 2
const RETRY_DELAY = 1000

function isNetworkError(err: unknown): boolean {
  return err instanceof TypeError && /failed to fetch|network/i.test(err.message)
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function fetchWithRetry(url: string, options?: RequestInit): Promise<Response> {
  let lastError: unknown
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fetch(url, options)
    } catch (err) {
      lastError = err
      if (isNetworkError(err) && attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY)
        continue
      }
      throw err
    }
  }
  throw lastError
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetchWithRetry(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!res.ok) {
    const error = await res.text().catch(() => 'Unknown error')
    throw new Error(`API Error ${res.status}: ${error}`)
  }

  // 204 No Content — return empty object
  if (res.status === 204) {
    return {} as T
  }

  return res.json()
}

// Chat
export async function sendChatMessage(
  message: string,
  conversationId?: string,
  workflowId?: string,
) {
  return fetchAPI<{
    message: string
    intent: string
    workflow?: Record<string, unknown> | null
    n8n_url?: string | null
    conversation_id?: string
    message_id?: string
  }>('/api/v1/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      workflow_id: workflowId || undefined,
    }),
  })
}

// Conversations
export async function getConversations() {
  return fetchAPI<{
    conversations: Array<{
      id: string
      title: string
      message_count: number
      created_at: string
      updated_at: string
    }>
  }>('/api/v1/conversations')
}

export async function getConversation(id: string) {
  return fetchAPI<{
    id: string
    title: string
    messages: Array<{
      id: string
      role: string
      content: string
      metadata?: {
        intent?: string
        has_workflow?: boolean
        workflow_json?: Record<string, unknown> | null
        n8n_url?: string | null
      } | null
      created_at: string
    }>
  }>(`/api/v1/conversations/${id}`)
}

export async function deleteConversation(id: string) {
  return fetchAPI<{ status: string }>(`/api/v1/conversations/${id}`, {
    method: 'DELETE',
  })
}

// Workflows
export async function getWorkflows() {
  return fetchAPI<{
    workflows: Array<{
      id: string
      name: string
      description?: string
      version: number
      created_at: string
    }>
  }>('/api/v1/workflows')
}

export async function deployWorkflow(workflowJson: Record<string, unknown>) {
  return fetchAPI<{
    status: string
    n8n_url: string
    workflow_id: string
  }>('/api/v1/workflows/deploy', {
    method: 'POST',
    body: JSON.stringify({ workflow_json: workflowJson }),
  })
}

export async function validateWorkflow(workflowJson: Record<string, unknown>) {
  return fetchAPI<{
    valid: boolean
    errors: string[]
    warnings: string[]
  }>('/api/v1/workflows/validate', {
    method: 'POST',
    body: JSON.stringify({ workflow_json: workflowJson }),
  })
}

// n8n proxy
export async function getN8nWorkflows() {
  return fetchAPI<{
    data: Array<{
      id: string
      name: string
      active: boolean
      isArchived?: boolean
      createdAt: string
      updatedAt: string
    }>
  }>('/api/v1/n8n/workflows')
}

// n8n workflow actions
export async function archiveN8nWorkflow(workflowId: string) {
  return fetchAPI<Record<string, unknown>>(`/api/v1/n8n/workflows/${workflowId}/archive`, {
    method: 'POST',
  })
}

export async function unarchiveN8nWorkflow(workflowId: string) {
  return fetchAPI<Record<string, unknown>>(`/api/v1/n8n/workflows/${workflowId}/unarchive`, {
    method: 'POST',
  })
}

// Workflow Versions
export async function getWorkflowVersions(workflowId: string) {
  return fetchAPI<Array<{
    id: string
    workflow_id: string
    version: number
    name: string
    workflow_json: Record<string, unknown>
    change_summary: string | null
    created_at: string
    created_by: string
  }>>(`/api/v1/n8n/workflows/${workflowId}/versions`)
}

export async function rollbackWorkflowVersion(workflowId: string, versionId: string) {
  return fetchAPI<{ message: string }>(`/api/v1/n8n/workflows/${workflowId}/versions/${versionId}/rollback`, {
    method: 'POST',
  })
}

// Knowledge Notes
export interface KnowledgeNote {
  id: string
  content: string
  category: string | null
  is_active: boolean
  created_at: string | null
  updated_at?: string | null
}

export async function getKnowledgeNotes(activeOnly: boolean = true) {
  return fetchAPI<KnowledgeNote[]>(`/api/v1/knowledge/notes?active_only=${activeOnly}`)
}

export async function createKnowledgeNote(content: string, category?: string) {
  return fetchAPI<KnowledgeNote>('/api/v1/knowledge/notes', {
    method: 'POST',
    body: JSON.stringify({ content, category: category || null }),
  })
}

export async function updateKnowledgeNote(noteId: string, data: { content?: string; category?: string; is_active?: boolean }) {
  return fetchAPI<KnowledgeNote>(`/api/v1/knowledge/notes/${noteId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteKnowledgeNote(noteId: string) {
  return fetchAPI<Record<string, never>>(`/api/v1/knowledge/notes/${noteId}`, {
    method: 'DELETE',
  })
}

// Learning Records
export interface LearningRecord {
  id: string
  record_type: string
  node_type: string | null
  description: string
  frequency: number
  created_at: string | null
}

export async function getLearningRecords() {
  return fetchAPI<LearningRecord[]>('/api/v1/knowledge/learning/records')
}

export async function deleteLearningRecord(id: string) {
  return fetchAPI<Record<string, never>>(`/api/v1/knowledge/learning/records/${id}`, {
    method: 'DELETE',
  })
}

// n8n Templates
export interface N8nTemplateSearchResult {
  totalWorkflows: number
  workflows: Array<{
    id: number
    name: string
    totalViews: number
    description: string
    createdAt: string
    is_imported?: boolean
    nodes: Array<{ name: string; displayName: string }>
  }>
}

export interface ImportedTemplate {
  id: string
  n8n_template_id: number
  name: string
  description: string | null
  categories: string[] | null
  node_types: string[] | null
  node_count: number
  total_views: number
  chunks: number
  distilled_text: string
  created_at: string | null
}

export async function searchN8nTemplates(q?: string, category?: string, page = 1, rows = 20) {
  const params = new URLSearchParams({ page: String(page), rows: String(rows) })
  if (q) params.set('q', q)
  if (category) params.set('category', category)
  return fetchAPI<N8nTemplateSearchResult>(`/api/v1/templates/search?${params}`)
}

export async function getTemplateCategories() {
  return fetchAPI<Array<{ name: string; count: number }>>('/api/v1/templates/categories')
}

export async function importTemplates(templateIds: number[]) {
  return fetchAPI<{ message: string; new_count: number; skipped?: number }>('/api/v1/templates/import', {
    method: 'POST',
    body: JSON.stringify({ template_ids: templateIds }),
  })
}

export async function importPopularTemplates(maxCount = 50, category?: string) {
  return fetchAPI<{ message: string }>('/api/v1/templates/import/popular', {
    method: 'POST',
    body: JSON.stringify({ max_count: maxCount, category: category || undefined }),
  })
}

export async function getImportedTemplates(page = 1, limit = 50, category?: string) {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (category) params.set('category', category)
  return fetchAPI<ImportedTemplate[]>(`/api/v1/templates/imported?${params}`)
}

export async function getImportedTemplateStats() {
  return fetchAPI<{ total_templates: number }>('/api/v1/templates/imported/stats')
}

export async function deleteImportedTemplate(id: string) {
  return fetchAPI<Record<string, never>>(`/api/v1/templates/imported/${id}`, {
    method: 'DELETE',
  })
}

// Debug
export interface ContextDebugResult {
  message: string
  keywords: string[]
  rag: { text: string; tokens: number; budget: number }
  knowledge_notes: { text: string; tokens: number; budget: number }
  learning_records: { text: string; tokens: number; budget: number }
  templates: { text: string; tokens: number; budget: number }
  total_tokens: number
}

export async function debugContext(message: string) {
  return fetchAPI<ContextDebugResult>('/api/v1/debug/context', {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

// Health
export async function getHealth() {
  return fetchAPI<{
    status: string
    version: string
    llm_provider: string
    services: Record<string, unknown>
  }>('/api/v1/health')
}
