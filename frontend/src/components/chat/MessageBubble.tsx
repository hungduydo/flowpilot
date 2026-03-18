'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Message } from '@/lib/types'
import { WorkflowCard } from '../workflow/WorkflowCard'
import { User, Bot } from 'lucide-react'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 py-4 ${isUser ? '' : ''}`}>
      {/* Avatar */}
      <div
        className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${
          isUser
            ? 'bg-primary-600/20 text-primary-400'
            : 'bg-emerald-600/20 text-emerald-400'
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-surface-500 mb-1.5">
          {isUser ? 'You' : 'Assistant'}
        </p>

        {/* Text content */}
        <div className="chat-markdown text-surface-200 text-sm leading-relaxed">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {/* Workflow card */}
        {message.workflow_json && (
          <div className="mt-3">
            <WorkflowCard
              workflow={message.workflow_json}
              n8nUrl={message.n8n_url}
            />
          </div>
        )}
      </div>
    </div>
  )
}
