'use client'

import { useState } from 'react'
import { useChat } from '@/hooks/use-chat'
import {
  PanelLeftClose,
  PanelLeftOpen,
  ExternalLink,
  Zap,
  LayoutTemplate,
} from 'lucide-react'
import { TemplateModal } from '@/components/templates/TemplateModal'

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL || 'http://localhost:5678'

export function Header() {
  const { sidebarOpen, toggleSidebar } = useChat()
  const [showTemplates, setShowTemplates] = useState(false)

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
    </>
  )
}
