'use client'

import { useState } from 'react'
import { useChat } from '@/hooks/use-chat'
import { useChatStore } from '@/stores/chat-store'
import {
  PanelLeftClose,
  PanelLeftOpen,
  ExternalLink,
  Zap,
  LayoutTemplate,
  Bug,
} from 'lucide-react'
import { TemplateModal } from '@/components/templates/TemplateModal'
import { DebugModal } from '@/components/debug/DebugModal'
import { ModelSelector } from './ModelSelector'
import type { PromptTraceEntry } from '@/lib/types'

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL || 'http://localhost:5678'

export function Header() {
  const { sidebarOpen, toggleSidebar, messages } = useChat()
  const debugMode = useChatStore((s) => s.debugMode)
  const setDebugMode = useChatStore((s) => s.setDebugMode)
  const [showTemplates, setShowTemplates] = useState(false)
  const [showDebug, setShowDebug] = useState(false)
  const [debugInitialTab, setDebugInitialTab] = useState<'context' | 'trace'>('context')

  // Get trace data from last assistant message
  const lastAssistantMsg = [...messages].reverse().find((m) => m.role === 'assistant')
  const lastTraceData: PromptTraceEntry[] | null = lastAssistantMsg?.prompt_trace || null

  const openDebugModal = (tab: 'context' | 'trace' = 'context') => {
    setDebugInitialTab(tab)
    setShowDebug(true)
  }

  return (
    <>
      <header className="h-14 border-b border-surface-800 bg-surface-900/80 backdrop-blur-sm flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={toggleSidebar}
            className="p-2 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
            title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            {sidebarOpen ? (
              <PanelLeftClose size={18} />
            ) : (
              <PanelLeftOpen size={18} />
            )}
          </button>

          <div className="flex items-center gap-2">
            <Zap size={20} className="text-primary-400" />
            <h1 className="text-base font-semibold text-surface-100">
              FlowPilot
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ModelSelector />

          <div className="w-px h-5 bg-surface-700" />

          {/* Debug mode toggle */}
          <button
            onClick={() => setDebugMode(!debugMode)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg transition-colors ${
              debugMode
                ? 'bg-amber-500/15 border border-amber-500/30 text-amber-400'
                : 'bg-surface-800 hover:bg-surface-700 text-surface-500 hover:text-surface-300'
            }`}
            title={debugMode ? 'Disable prompt tracing' : 'Enable prompt tracing'}
          >
            <div className={`w-1.5 h-1.5 rounded-full ${debugMode ? 'bg-amber-400 animate-pulse' : 'bg-surface-600'}`} />
            Trace
          </button>

          <button
            onClick={() => openDebugModal(lastTraceData ? 'trace' : 'context')}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-surface-100 transition-colors relative"
            title="Debug intelligence pipeline"
          >
            <Bug size={14} />
            <span>Debug</span>
            {lastTraceData && lastTraceData.length > 0 && (
              <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-primary-500 text-[9px] flex items-center justify-center text-white font-bold">
                {lastTraceData.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setShowTemplates(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-surface-100 transition-colors"
            title="Browse n8n templates"
          >
            <LayoutTemplate size={14} />
            <span>Templates</span>
          </button>
          <a
            href={N8N_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-surface-100 transition-colors"
          >
            <span>Open n8n</span>
            <ExternalLink size={14} />
          </a>
        </div>
      </header>

      <TemplateModal
        open={showTemplates}
        onClose={() => setShowTemplates(false)}
      />
      <DebugModal
        open={showDebug}
        onClose={() => setShowDebug(false)}
        initialTab={debugInitialTab}
        traceData={lastTraceData}
      />
    </>
  )
}
