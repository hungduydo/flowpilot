const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
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

// Health
export async function getHealth() {
  return fetchAPI<{
    status: string
    version: string
    llm_provider: string
    services: Record<string, unknown>
  }>('/api/v1/health')
}
