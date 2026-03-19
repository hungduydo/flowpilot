'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/stores/chat-store'
import { useToastStore } from '@/stores/toast-store'
import type { Message } from '@/lib/types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

const MAX_RECONNECT_ATTEMPTS = 10
const INITIAL_BACKOFF = 1000
const MAX_BACKOFF = 30000

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const store = useChatStore()
  const toast = useToastStore()

  const reconnectAttempts = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastConversationId = useRef<string | undefined>(undefined)
  const intentionalClose = useRef(false)

  const clearReconnectTimer = () => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
  }

  const getBackoffDelay = () => {
    const delay = Math.min(
      INITIAL_BACKOFF * Math.pow(2, reconnectAttempts.current),
      MAX_BACKOFF,
    )
    return delay
  }

  const scheduleReconnect = useCallback(() => {
    if (intentionalClose.current) return
    if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
      toast.addToast('error', 'WebSocket connection lost. Please refresh the page.')
      return
    }

    const delay = getBackoffDelay()
    reconnectAttempts.current += 1

    reconnectTimer.current = setTimeout(() => {
      connect(lastConversationId.current)
    }, delay)
  }, [])

  const connect = useCallback((conversationId?: string) => {
    intentionalClose.current = false
    lastConversationId.current = conversationId
    clearReconnectTimer()

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close()
    }

    const path = conversationId
      ? `${WS_URL}/api/v1/ws/chat?conversation_id=${conversationId}`
      : `${WS_URL}/api/v1/ws/chat`

    const ws = new WebSocket(path)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (reconnectAttempts.current > 0) {
        toast.addToast('success', 'WebSocket reconnected')
      }
      reconnectAttempts.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'status':
            store.setStatusText(msg.data)
            break

          case 'token':
            store.appendToLastAssistantMessage(msg.data)
            break

          case 'message_complete': {
            const data = msg.data
            store.setLoading(false)
            store.setStatusText('')

            // Update last assistant message with full response
            if (data.workflow_json || data.n8n_url) {
              const messages = useChatStore.getState().messages
              const lastIdx = messages.findLastIndex(
                (m) => m.role === 'assistant',
              )
              if (lastIdx >= 0) {
                const updated = [...messages]
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  content: data.response || updated[lastIdx].content,
                  workflow_json: data.workflow_json,
                  n8n_url: data.n8n_url,
                  intent: data.intent,
                }
                store.setMessages(updated)
              }
            }

            // Update conversation ID
            if (data.conversation_id) {
              store.setActiveConversation(data.conversation_id)
            }
            break
          }

          case 'error':
            store.setLoading(false)
            store.setStatusText('')
            store.addMessage({
              id: `error-${Date.now()}`,
              role: 'assistant',
              content: `Error: ${msg.data}`,
              created_at: new Date().toISOString(),
            })
            break
        }
      } catch {
        toast.addToast('error', 'Failed to parse WebSocket message')
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (!intentionalClose.current) {
        toast.addToast('warning', 'WebSocket disconnected. Reconnecting...')
        scheduleReconnect()
      }
    }

    ws.onerror = () => {
      setConnected(false)
    }
  }, [scheduleReconnect])

  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        toast.addToast('error', 'WebSocket not connected. Please wait for reconnection.')
        return
      }

      // Add user message
      const userMsg: Message = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: content.trim(),
        created_at: new Date().toISOString(),
      }
      store.addMessage(userMsg)

      // Add placeholder assistant message for streaming
      const assistantMsg: Message = {
        id: `stream-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }
      store.addMessage(assistantMsg)
      store.setLoading(true)

      wsRef.current.send(
        JSON.stringify({
          type: 'chat_message',
          data: content.trim(),
          conversation_id: store.activeConversationId,
        }),
      )
    },
    [store.activeConversationId],
  )

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    clearReconnectTimer()
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  useEffect(() => {
    return () => {
      intentionalClose.current = true
      clearReconnectTimer()
      wsRef.current?.close()
    }
  }, [])

  return {
    connected,
    connect,
    disconnect,
    sendMessage,
  }
}
