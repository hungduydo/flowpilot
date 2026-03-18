'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/stores/chat-store'
import type { Message } from '@/lib/types'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const store = useChatStore()

  const connect = useCallback((conversationId?: string) => {
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
      console.log('WebSocket connected')
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
        console.error('Failed to parse WS message:', event.data)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      console.log('WebSocket disconnected')
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setConnected(false)
    }
  }, [])

  const sendMessage = useCallback(
    (content: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.error('WebSocket not connected')
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
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return {
    connected,
    connect,
    disconnect,
    sendMessage,
  }
}
