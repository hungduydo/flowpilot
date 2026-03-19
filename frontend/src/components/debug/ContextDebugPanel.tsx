'use client'

import { useState } from 'react'
import {
  Search,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Database,
  BookOpen,
  Lightbulb,
  LayoutTemplate,
  Tag,
} from 'lucide-react'
import { debugContext, type ContextDebugResult } from '@/lib/api'

interface LayerSectionProps {
  title: string
  icon: React.ReactNode
  tokens: number
  budget: number
  text: string
  color: string
}

function LayerSection({ title, icon, tokens, budget, text, color }: LayerSectionProps) {
  const [expanded, setExpanded] = useState(false)
  const usage = budget > 0 ? Math.round((tokens / budget) * 100) : 0

  return (
    <div className="rounded-lg border border-surface-700/50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-800/50 transition-colors"
      >
        <span className={`${color}`}>{icon}</span>
        <span className="text-sm font-medium text-surface-200 flex-1 text-left">{title}</span>
        <div className="flex items-center gap-3">
          {/* Token usage bar */}
          <div className="flex items-center gap-2">
            <div className="w-20 h-1.5 bg-surface-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  usage > 80 ? 'bg-amber-400' : usage > 0 ? 'bg-primary-400' : 'bg-surface-600'
                }`}
                style={{ width: `${Math.min(100, usage)}%` }}
              />
            </div>
            <span className="text-[11px] text-surface-500 w-20 text-right">
              {tokens} / {budget}
            </span>
          </div>
          {expanded ? (
            <ChevronDown size={14} className="text-surface-500" />
          ) : (
            <ChevronRight size={14} className="text-surface-500" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-surface-700/50 bg-surface-800/30">
          {text ? (
            <pre className="px-4 py-3 text-xs text-surface-300 whitespace-pre-wrap font-mono leading-relaxed max-h-64 overflow-y-auto scrollbar-thin">
              {text}
            </pre>
          ) : (
            <p className="px-4 py-3 text-xs text-surface-500 italic">No context from this layer</p>
          )}
        </div>
      )}
    </div>
  )
}

export function ContextDebugPanel() {
  const [message, setMessage] = useState('')
  const [result, setResult] = useState<ContextDebugResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAnalyze = async () => {
    if (!message.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await debugContext(message.trim())
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to analyze context')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header info */}
      <div className="px-5 py-3 border-b border-surface-800">
        <p className="text-xs text-surface-500">
          Type a prompt to see what context each intelligence layer would inject. No LLM call is made.
        </p>
      </div>

      {/* Input */}
      <div className="px-5 py-3 border-b border-surface-800/50">
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            placeholder="e.g., Create a webhook that sends a Slack message"
            className="flex-1 px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-surface-200 placeholder-surface-500 focus:outline-none focus:border-primary-500"
          />
          <button
            onClick={handleAnalyze}
            disabled={loading || !message.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-500/10 border border-primary-500/20 rounded-lg text-sm text-primary-400 hover:bg-primary-500/20 disabled:opacity-40 transition-colors"
          >
            {loading ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Search size={14} />
            )}
            Analyze
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-5 space-y-4">
        {error && (
          <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}

        {result && (
          <>
            {/* Keywords */}
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Tag size={13} className="text-surface-400" />
                <span className="text-xs font-medium text-surface-400">
                  Extracted Keywords ({result.keywords.length})
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {result.keywords.map((kw) => (
                  <span
                    key={kw}
                    className={`text-[11px] px-2 py-0.5 rounded-full ${
                      kw.startsWith('n8n-nodes-base.')
                        ? 'bg-primary-400/10 text-primary-400 border border-primary-400/20'
                        : 'bg-surface-800 text-surface-400 border border-surface-700'
                    }`}
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>

            {/* Total tokens */}
            <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-surface-800/50 border border-surface-700/50">
              <span className="text-xs text-surface-400">Total context tokens:</span>
              <span className="text-sm font-medium text-surface-200">
                {result.total_tokens.toLocaleString()}
              </span>
              <span className="text-xs text-surface-500">
                / {result.rag.budget + result.knowledge_notes.budget + result.learning_records.budget + result.templates.budget} max
              </span>
              <div className="flex-1" />
              <div className="w-32 h-2 bg-surface-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-400 rounded-full transition-all"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round(
                        (result.total_tokens /
                          (result.rag.budget +
                            result.knowledge_notes.budget +
                            result.learning_records.budget +
                            result.templates.budget)) *
                          100
                      )
                    )}%`,
                  }}
                />
              </div>
            </div>

            {/* Layer sections */}
            <div className="space-y-2">
              <LayerSection
                title="RAG Knowledge Base"
                icon={<Database size={15} />}
                tokens={result.rag.tokens}
                budget={result.rag.budget}
                text={result.rag.text}
                color="text-blue-400"
              />
              <LayerSection
                title="Knowledge Notes"
                icon={<BookOpen size={15} />}
                tokens={result.knowledge_notes.tokens}
                budget={result.knowledge_notes.budget}
                text={result.knowledge_notes.text}
                color="text-emerald-400"
              />
              <LayerSection
                title="Learning Records"
                icon={<Lightbulb size={15} />}
                tokens={result.learning_records.tokens}
                budget={result.learning_records.budget}
                text={result.learning_records.text}
                color="text-amber-400"
              />
              <LayerSection
                title="Template Examples"
                icon={<LayoutTemplate size={15} />}
                tokens={result.templates.tokens}
                budget={result.templates.budget}
                text={result.templates.text}
                color="text-purple-400"
              />
            </div>
          </>
        )}

        {!result && !error && (
          <div className="text-center py-16">
            <Search size={32} className="mx-auto text-surface-600 mb-3" />
            <p className="text-surface-500 text-sm">
              Enter a prompt above to analyze the intelligence pipeline
            </p>
            <p className="text-surface-600 text-xs mt-1">
              See exactly what context gets injected from each of the 4 layers
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
