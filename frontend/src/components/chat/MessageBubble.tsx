'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Message } from '@/lib/types'
import { WorkflowCard } from '../workflow/WorkflowCard'
import { DebugModal } from '../debug/DebugModal'
import { User, Bot, Activity } from 'lucide-react'

interface Props {
  message: Message
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const hasTrace = !isUser && message.prompt_trace && message.prompt_trace.length > 0
  const [showTrace, setShowTrace] = useState(false)

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
        <div className="flex items-center gap-2 mb-1.5">
          <p className="text-xs font-medium text-surface-500">
            {isUser ? 'You' : 'Assistant'}
          </p>

          {/* Trace button */}
          {hasTrace && (
            <button
              onClick={() => setShowTrace(true)}
              className="flex items-center gap-1 px-1.5 py-0.5 text-[10px] rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 transition-colors"
              title="View LLM prompt traces"
            >
              <Activity size={10} />
              {message.prompt_trace!.length} steps
            </button>
          )}
        </div>

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

      {/* Trace modal */}
      {hasTrace && (
        <DebugModal
          open={showTrace}
          onClose={() => setShowTrace(false)}
          initialTab="trace"
          traceData={message.prompt_trace}
        />
      )}
    </div>
  )
}
