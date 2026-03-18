export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  workflow_json?: WorkflowData | null
  n8n_url?: string | null
  intent?: string
  created_at: string
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
}

export interface N8nWorkflow {
  id: string
  name: string
  active: boolean
  createdAt: string
  updatedAt: string
  nodes?: WorkflowNode[]
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
