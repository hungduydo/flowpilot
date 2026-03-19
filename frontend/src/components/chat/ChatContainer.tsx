'use client'

import { useRef, useEffect } from 'react'
import { useChat } from '@/hooks/use-chat'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import { Workflow, ExternalLink, X } from 'lucide-react'

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL || 'http://localhost:5678'

export function ChatContainer() {
  const { messages, isLoading, statusText, activeWorkflow, sendMessage, detachWorkflow } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Active Workflow Banner */}
      {activeWorkflow && (
        <div className="border-b border-surface-800 bg-surface-900/80 backdrop-blur-sm">
          <div className="max-w-3xl mx-auto px-4 py-2 flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-primary-500/10 border border-primary-500/20">
              <Workflow size={13} className="text-primary-400" />
              <span className="text-xs font-medium text-primary-400">Editing</span>
            </div>
            <span className="text-sm text-surface-200 truncate flex-1">
              {activeWorkflow.name}
            </span>
            {activeWorkflow.editorUrl && (
              <a
                href={activeWorkflow.editorUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-surface-400 hover:text-primary-400 transition-colors"
              >
                <ExternalLink size={11} />
                n8n
              </a>
            )}
            <button
              onClick={detachWorkflow}
              className="p-1 text-surface-500 hover:text-surface-300 transition-colors"
              title="Detach workflow (next message creates new)"
            >
              <X size={13} />
            </button>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.length === 0 ? (
            <WelcomeScreen onSuggestionClick={sendMessage} />
          ) : (
            <div className="space-y-1">
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
            </div>
          )}

          {/* Typing indicator */}
          {isLoading && (
            <div className="mt-4">
              <TypingIndicator statusText={statusText} />
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input Area */}
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  )
}
