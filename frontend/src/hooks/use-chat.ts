'use client'

import { useCallback, useRef } from 'react'
import { useChatStore } from '@/stores/chat-store'
import { useToastStore } from '@/stores/toast-store'
import { sendChatMessage, getConversations, getConversation, deleteConversation } from '@/lib/api'
import type { Message } from '@/lib/types'

export function useChat() {
  const store = useChatStore()
  const toast = useToastStore()
  const abortRef = useRef<AbortController | null>(null)

  const loadConversations = useCallback(async () => {
    try {
      const data = await getConversations()
      store.setConversations(
        data.conversations.map((c) => ({
          ...c,
          current_workflow_id: null,
          message_count: c.message_count || 0,
        })),
      )
    } catch (err) {
      toast.addToast('error', 'Failed to load conversations')
    }
  }, [])

  const loadConversation = useCallback(async (id: string) => {
    try {
      const data = await getConversation(id)
      store.setActiveConversation(id)

      const mappedMessages = data.messages.map((m) => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        workflow_json: m.metadata?.workflow_json as Message['workflow_json'],
        n8n_url: m.metadata?.n8n_url,
        intent: m.metadata?.intent,
        created_at: m.created_at,
      }))
      store.setMessages(mappedMessages)

      // Restore active workflow from last message that had a workflow
      const lastWfMsg = [...mappedMessages]
        .reverse()
        .find((m) => m.n8n_url || m.workflow_json)
      if (lastWfMsg?.n8n_url) {
        // Extract workflow ID from n8n URL: http://localhost:5678/workflow/ABC123
        const urlMatch = lastWfMsg.n8n_url.match(/\/workflow\/([^/]+)/)
        if (urlMatch) {
          const wfName = lastWfMsg.workflow_json
            ? (lastWfMsg.workflow_json as Record<string, unknown>).name as string
            : 'Workflow'
          store.setActiveWorkflow({
            id: urlMatch[1],
            name: wfName || 'Workflow',
            editorUrl: lastWfMsg.n8n_url,
          })
        }
      } else {
        store.setActiveWorkflow(null)
      }
    } catch (err) {
      toast.addToast('error', 'Failed to load conversation')
    }
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || store.isLoading) return

    // Add user message
    const userMsg: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      created_at: new Date().toISOString(),
    }
    store.addMessage(userMsg)
    store.setLoading(true)
    store.setStatusText('Thinking...')

    try {
      // Pass active workflow ID so backend knows we're editing
      const response = await sendChatMessage(
        content.trim(),
        store.activeConversationId || undefined,
        store.activeWorkflow?.id || undefined,
      )

      // Set conversation ID if new
      if (response.conversation_id && !store.activeConversationId) {
        store.setActiveConversation(response.conversation_id)
        loadConversations()
      }

      // Extract workflow data
      const wfData = response.workflow as Record<string, unknown> | null
      const workflowJson = wfData?.workflow_json as Message['workflow_json'] ?? null
      const n8nUrl = (wfData?.n8n_editor_url as string) || response.n8n_url || null
      const n8nWorkflowId = wfData?.n8n_workflow_id as string | null

      // Update active workflow if response contains one
      if (n8nWorkflowId) {
        const wfName = workflowJson
          ? (workflowJson as Record<string, unknown>).name as string
          : store.activeWorkflow?.name || 'Workflow'
        store.setActiveWorkflow({
          id: n8nWorkflowId,
          name: wfName || 'Workflow',
          editorUrl: n8nUrl,
        })
      }

      const assistantMsg: Message = {
        id: response.message_id || `msg-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        workflow_json: workflowJson,
        n8n_url: n8nUrl,
        intent: response.intent,
        created_at: new Date().toISOString(),
      }
      store.addMessage(assistantMsg)
    } catch (err) {
      const errorMsg: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to send message'}`,
        created_at: new Date().toISOString(),
      }
      store.addMessage(errorMsg)
    } finally {
      store.setLoading(false)
      store.setStatusText('')
    }
  }, [store.activeConversationId, store.isLoading, store.activeWorkflow, loadConversations])

  const newConversation = useCallback(() => {
    store.setActiveConversation(null)
    store.setMessages([])
    store.setActiveWorkflow(null)
    store.setStatusText('')
  }, [])

  const detachWorkflow = useCallback(() => {
    store.setActiveWorkflow(null)
  }, [])

  const removeConversation = useCallback(async (id: string) => {
    try {
      await deleteConversation(id)
      store.removeConversation(id)
      if (store.activeConversationId === id) {
        store.setMessages([])
        store.setActiveWorkflow(null)
      }
    } catch (err) {
      toast.addToast('error', 'Failed to delete conversation')
    }
  }, [store.activeConversationId])

  const cancelRequest = useCallback(() => {
    abortRef.current?.abort()
    store.setLoading(false)
    store.setStatusText('')
  }, [])

  return {
    messages: store.messages,
    isLoading: store.isLoading,
    statusText: store.statusText,
    conversations: store.conversations,
    activeConversationId: store.activeConversationId,
    activeWorkflow: store.activeWorkflow,
    sidebarOpen: store.sidebarOpen,
    toggleSidebar: store.toggleSidebar,
    sendMessage,
    newConversation,
    detachWorkflow,
    loadConversations,
    loadConversation,
    removeConversation,
    cancelRequest,
  }
}
