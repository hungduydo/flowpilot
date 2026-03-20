export interface PromptTraceEntry {
  step: string
  provider: string
  model: string
  temperature: number
  messages: Array<{ role: string; content: string }>
  response_preview: string
  token_usage: Record<string, number>
  duration_ms: number
  error: string | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  workflow_json?: WorkflowData | null
  n8n_url?: string | null
  intent?: string
  created_at: string
  prompt_trace?: PromptTraceEntry[] | null
}

export interface Conversation {
  id: string
  title: string
  current_workflow_id?: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface WorkflowData {
  name: string
  nodes: WorkflowNode[]
  connections: Record<string, unknown>
  settings?: Record<string, unknown>
}

export interface WorkflowNode {
  id: string
  name: string
  type: string
  typeVersion?: number
  position: [number, number]
  parameters: Record<string, unknown>
  credentials?: Record<string, unknown>
}

export interface ChatResponse {
  response: string
  intent: string
  workflow_json?: WorkflowData | null
  n8n_url?: string | null
  conversation_id?: string
  message_id?: string
  prompt_trace?: PromptTraceEntry[] | null
}

export interface N8nWorkflow {
  id: string
  name: string
  active: boolean
  createdAt: string
  updatedAt: string
  nodes?: WorkflowNode[]
}

export interface WorkflowVersion {
  id: string
  workflow_id: string
  version: number
  name: string
  workflow_json: Record<string, unknown>
  change_summary: string | null
  created_at: string
  created_by: string
}

export interface KnowledgeNote {
  id: string
  content: string
  category: string | null
  is_active: boolean
  created_at: string | null
  updated_at?: string | null
}

// WebSocket message types
export type WSMessageType =
  | 'chat_message'
  | 'status'
  | 'token'
  | 'message_complete'
  | 'error'

export interface WSMessage {
  type: WSMessageType
  data: string | ChatResponse
  conversation_id?: string
}
