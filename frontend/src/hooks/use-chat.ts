'use client'

import { useCallback, useRef } from 'react'
import { useChatStore } from '@/stores/chat-store'
import { sendChatMessage, getConversations, getConversation, deleteConversation } from '@/lib/api'
import type { Message } from '@/lib/types'

export function useChat() {
  const store = useChatStore()
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
      console.error('Failed to load conversations:', err)
    }
  }, [])

  const loadConversation = useCallback(async (id: string) => {
    try {
      const data = await getConversation(id)
      store.setActiveConversation(id)
      store.setMessages(
        data.messages.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          workflow_json: m.metadata?.workflow_json as Message['workflow_json'],
          n8n_url: m.metadata?.n8n_url,
          intent: m.metadata?.intent,
          created_at: m.created_at,
        })),
      )
    } catch (err) {
      console.error('Failed to load conversation:', err)
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
      const response = await sendChatMessage(
        content.trim(),
        store.activeConversationId || undefined,
      )

      // Set conversation ID if new
      if (response.conversation_id && !store.activeConversationId) {
        store.setActiveConversation(response.conversation_id)
        // Refresh conversation list
        loadConversations()
      }

      // Add assistant message
      // Extract workflow data — API returns nested structure:
      // response.workflow = { workflow_json, n8n_workflow_id, n8n_editor_url, ... }
      const wfData = response.workflow as Record<string, unknown> | null
      const workflowJson = wfData?.workflow_json as Message['workflow_json'] ?? null
      const n8nUrl = (wfData?.n8n_editor_url as string) || response.n8n_url || null

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
  }, [store.activeConversationId, store.isLoading, loadConversations])

  const newConversation = useCallback(() => {
    store.setActiveConversation(null)
    store.setMessages([])
    store.setStatusText('')
  }, [])

  const removeConversation = useCallback(async (id: string) => {
    try {
      await deleteConversation(id)
      store.removeConversation(id)
      if (store.activeConversationId === id) {
        store.setMessages([])
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
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
    sidebarOpen: store.sidebarOpen,
    toggleSidebar: store.toggleSidebar,
    sendMessage,
    newConversation,
    loadConversations,
    loadConversation,
    removeConversation,
    cancelRequest,
  }
}
