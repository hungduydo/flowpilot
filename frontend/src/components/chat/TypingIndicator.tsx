'use client'

import { Bot } from 'lucide-react'

interface Props {
  statusText?: string
}

export function TypingIndicator({ statusText }: Props) {
  return (
    <div className="flex gap-3 py-4">
      <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-600/20 text-emerald-400">
        <Bot size={16} />
      </div>
      <div className="flex items-center gap-2">
        {statusText ? (
          <span className="text-sm text-surface-400 animate-pulse">
            {statusText}
          </span>
        ) : (
          <div className="flex gap-1">
            <span className="typing-dot w-2 h-2 rounded-full bg-surface-500" />
            <span className="typing-dot w-2 h-2 rounded-full bg-surface-500" />
            <span className="typing-dot w-2 h-2 rounded-full bg-surface-500" />
          </div>
        )}
      </div>
    </div>
  )
}
