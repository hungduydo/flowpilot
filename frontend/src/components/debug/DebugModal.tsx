'use client'

import { useEffect, useState } from 'react'
import { X, Database, Activity } from 'lucide-react'
import { ContextDebugPanel } from './ContextDebugPanel'
import { PromptTracePanel } from './PromptTracePanel'
import type { PromptTraceEntry } from '@/lib/types'

type DebugTab = 'context' | 'trace'

interface DebugModalProps {
  open: boolean
  onClose: () => void
  initialTab?: DebugTab
  traceData?: PromptTraceEntry[] | null
}

export function DebugModal({ open, onClose, initialTab = 'context', traceData }: DebugModalProps) {
  const [activeTab, setActiveTab] = useState<DebugTab>(initialTab)

  // Sync initialTab when modal opens
  useEffect(() => {
    if (open) setActiveTab(initialTab)
  }, [open, initialTab])

  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  const tabs = [
    { id: 'context' as const, label: 'Context Pipeline', icon: Database },
    { id: 'trace' as const, label: 'Prompt Trace', icon: Activity },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-4xl h-[85vh] mx-4 bg-surface-900 border border-surface-700 rounded-xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-surface-800">
          <div>
            <h2 className="text-base font-semibold text-surface-100">
              Debug Tools
            </h2>
            <p className="text-xs text-surface-500 mt-0.5">
              Inspect intelligence pipeline context and LLM prompt traces
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-surface-800 px-5">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition-colors relative ${
                activeTab === id
                  ? 'text-primary-400'
                  : 'text-surface-500 hover:text-surface-300'
              }`}
            >
              <Icon size={14} />
              {label}
              {id === 'trace' && traceData && traceData.length > 0 && (
                <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-primary-500/20 text-primary-400">
                  {traceData.length}
                </span>
              )}
              {activeTab === id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-400 rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'context' && <ContextDebugPanel />}
          {activeTab === 'trace' && <PromptTracePanel trace={traceData} />}
        </div>
      </div>
    </div>
  )
}
