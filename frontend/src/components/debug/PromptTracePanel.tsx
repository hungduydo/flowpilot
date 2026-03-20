'use client'

import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Zap,
  MessageSquare,
  Thermometer,
  Cpu,
  Activity,
} from 'lucide-react'
import type { PromptTraceEntry } from '@/lib/types'

// Step name → display config
const STEP_CONFIG: Record<string, { label: string; color: string; bgColor: string }> = {
  intent_classification: { label: 'Intent Classification', color: 'text-surface-400', bgColor: 'bg-surface-700/50' },
  phase1_plan: { label: 'Phase 1: Plan', color: 'text-blue-400', bgColor: 'bg-blue-500/10' },
  phase2_generate: { label: 'Phase 2: Generate JSON', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },
  edit_function_calling: { label: 'Edit: Function Calling', color: 'text-amber-400', bgColor: 'bg-amber-500/10' },
  edit_function_calling_retry: { label: 'Edit: Function Calling (Retry)', color: 'text-orange-400', bgColor: 'bg-orange-500/10' },
  chat_response: { label: 'Chat Response', color: 'text-purple-400', bgColor: 'bg-purple-500/10' },
  structured_output: { label: 'Structured Output', color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },
  function_calling: { label: 'Function Calling', color: 'text-amber-400', bgColor: 'bg-amber-500/10' },
  chat_completion: { label: 'Chat Completion', color: 'text-purple-400', bgColor: 'bg-purple-500/10' },
}

function getStepConfig(step: string) {
  return STEP_CONFIG[step] || { label: step, color: 'text-surface-400', bgColor: 'bg-surface-700/50' }
}

const ROLE_COLORS: Record<string, string> = {
  system: 'text-amber-400',
  user: 'text-blue-400',
  assistant: 'text-emerald-400',
}

interface TraceStepCardProps {
  entry: PromptTraceEntry
  index: number
}

function TraceStepCard({ entry, index }: TraceStepCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [expandedMessages, setExpandedMessages] = useState<Set<number>>(new Set())
  const config = getStepConfig(entry.step)
  const totalTokens = entry.token_usage?.total_tokens || 0

  const toggleMessage = (idx: number) => {
    setExpandedMessages((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  return (
    <div className="relative">
      {/* Timeline connector */}
      {index > 0 && (
        <div className="absolute left-[15px] -top-3 w-px h-3 bg-surface-700" />
      )}

      <div className="rounded-lg border border-surface-700/50 overflow-hidden">
        {/* Header */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-800/50 transition-colors"
        >
          {/* Step number circle */}
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${config.bgColor} ${config.color} shrink-0`}>
            {index + 1}
          </div>

          {/* Step label */}
          <span className={`text-sm font-medium ${config.color} flex-1 text-left`}>
            {config.label}
          </span>

          {/* Meta chips */}
          <div className="flex items-center gap-2.5 text-[11px] text-surface-500">
            {/* Provider:Model */}
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-800 border border-surface-700">
              <Cpu size={10} />
              {entry.provider}:{entry.model.split(':')[0]}
            </span>

            {/* Temperature */}
            <span className="flex items-center gap-1">
              <Thermometer size={10} />
              {entry.temperature}
            </span>

            {/* Duration */}
            <span className="flex items-center gap-1">
              <Clock size={10} />
              {entry.duration_ms >= 1000
                ? `${(entry.duration_ms / 1000).toFixed(1)}s`
                : `${Math.round(entry.duration_ms)}ms`}
            </span>

            {/* Tokens */}
            {totalTokens > 0 && (
              <span className="flex items-center gap-1">
                <Zap size={10} />
                {totalTokens.toLocaleString()}
              </span>
            )}
          </div>

          {expanded ? (
            <ChevronDown size={14} className="text-surface-500" />
          ) : (
            <ChevronRight size={14} className="text-surface-500" />
          )}
        </button>

        {/* Expanded content */}
        {expanded && (
          <div className="border-t border-surface-700/50 bg-surface-800/20">
            {/* Messages */}
            <div className="px-4 py-3 space-y-2">
              <div className="flex items-center gap-1.5 mb-2">
                <MessageSquare size={12} className="text-surface-400" />
                <span className="text-xs font-medium text-surface-400">
                  Messages ({entry.messages.length})
                </span>
              </div>

              {entry.messages.map((msg, msgIdx) => {
                const isExpanded = expandedMessages.has(msgIdx)
                const content = msg.content || ''
                const isLong = content.length > 300
                const displayContent = isLong && !isExpanded
                  ? content.slice(0, 300) + '...'
                  : content

                return (
                  <div key={msgIdx} className="rounded border border-surface-700/30 overflow-hidden">
                    <button
                      onClick={() => isLong && toggleMessage(msgIdx)}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-left ${
                        isLong ? 'cursor-pointer hover:bg-surface-700/30' : 'cursor-default'
                      }`}
                    >
                      <span className={`text-[10px] font-mono font-bold uppercase ${ROLE_COLORS[msg.role] || 'text-surface-400'}`}>
                        {msg.role}
                      </span>
                      <span className="text-[10px] text-surface-600">
                        {content.length.toLocaleString()} chars
                      </span>
                      {isLong && (
                        <span className="text-[10px] text-surface-500 ml-auto">
                          {isExpanded ? 'collapse' : 'expand'}
                        </span>
                      )}
                    </button>
                    <pre className="px-3 py-2 text-xs text-surface-300 whitespace-pre-wrap font-mono leading-relaxed max-h-80 overflow-y-auto scrollbar-thin border-t border-surface-700/30 bg-surface-900/30">
                      {displayContent}
                    </pre>
                  </div>
                )
              })}
            </div>

            {/* Response preview */}
            {entry.response_preview && (
              <div className="px-4 py-3 border-t border-surface-700/30">
                <div className="flex items-center gap-1.5 mb-2">
                  <Activity size={12} className="text-emerald-400" />
                  <span className="text-xs font-medium text-surface-400">Response Preview</span>
                </div>
                <pre className="text-xs text-surface-300 whitespace-pre-wrap font-mono leading-relaxed max-h-40 overflow-y-auto scrollbar-thin p-2 rounded bg-surface-900/30 border border-surface-700/30">
                  {entry.response_preview}
                </pre>
              </div>
            )}

            {/* Token breakdown */}
            {totalTokens > 0 && (
              <div className="px-4 py-2 border-t border-surface-700/30 flex items-center gap-4 text-[11px] text-surface-500">
                <span>Input: {(entry.token_usage?.input_tokens || 0).toLocaleString()}</span>
                <span>Output: {(entry.token_usage?.output_tokens || 0).toLocaleString()}</span>
                <span>Total: {totalTokens.toLocaleString()}</span>
              </div>
            )}

            {/* Error */}
            {entry.error && (
              <div className="px-4 py-2 border-t border-red-500/20 bg-red-500/5 text-xs text-red-400">
                Error: {entry.error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface PromptTracePanelProps {
  trace: PromptTraceEntry[] | null | undefined
}

export function PromptTracePanel({ trace }: PromptTracePanelProps) {
  if (!trace || trace.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-5">
        <Activity size={32} className="text-surface-600 mb-3" />
        <p className="text-surface-500 text-sm text-center">
          No prompt traces available
        </p>
        <p className="text-surface-600 text-xs mt-1 text-center">
          Enable debug mode in the header and send a message to capture LLM prompt traces
        </p>
      </div>
    )
  }

  // Summary stats
  const totalDuration = trace.reduce((sum, t) => sum + t.duration_ms, 0)
  const totalTokens = trace.reduce((sum, t) => sum + (t.token_usage?.total_tokens || 0), 0)

  return (
    <div className="flex flex-col h-full">
      {/* Summary bar */}
      <div className="px-5 py-3 border-b border-surface-800 flex items-center gap-4">
        <span className="text-xs text-surface-400">
          <span className="font-medium text-surface-200">{trace.length}</span> LLM calls
        </span>
        <span className="text-xs text-surface-400 flex items-center gap-1">
          <Clock size={11} />
          {totalDuration >= 1000
            ? `${(totalDuration / 1000).toFixed(1)}s`
            : `${Math.round(totalDuration)}ms`}
          {' '}total
        </span>
        {totalTokens > 0 && (
          <span className="text-xs text-surface-400 flex items-center gap-1">
            <Zap size={11} />
            {totalTokens.toLocaleString()} tokens
          </span>
        )}
      </div>

      {/* Steps timeline */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-5 space-y-3">
        {trace.map((entry, idx) => (
          <TraceStepCard key={idx} entry={entry} index={idx} />
        ))}
      </div>
    </div>
  )
}
