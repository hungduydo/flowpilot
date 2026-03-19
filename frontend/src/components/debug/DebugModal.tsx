'use client'

import { useEffect } from 'react'
import { X } from 'lucide-react'
import { ContextDebugPanel } from './ContextDebugPanel'

interface DebugModalProps {
  open: boolean
  onClose: () => void
}

export function DebugModal({ open, onClose }: DebugModalProps) {
  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-3xl h-[85vh] mx-4 bg-surface-900 border border-surface-700 rounded-xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-surface-800">
          <div>
            <h2 className="text-base font-semibold text-surface-100">
              Intelligence Pipeline Debug
            </h2>
            <p className="text-xs text-surface-500 mt-0.5">
              Inspect context assembly from RAG, Knowledge Notes, Learning Records, and Templates
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <ContextDebugPanel />
        </div>
      </div>
    </div>
  )
}
