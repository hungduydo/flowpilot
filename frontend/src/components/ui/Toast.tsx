'use client'

import { useEffect, useState } from 'react'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import type { Toast as ToastData, ToastType } from '@/stores/toast-store'

const TOAST_DURATION = 4000

const typeConfig: Record<ToastType, { icon: typeof CheckCircle; bg: string; border: string; text: string; progress: string }> = {
  success: {
    icon: CheckCircle,
    bg: 'bg-green-950/90',
    border: 'border-green-800',
    text: 'text-green-300',
    progress: 'bg-green-500',
  },
  error: {
    icon: AlertCircle,
    bg: 'bg-red-950/90',
    border: 'border-red-800',
    text: 'text-red-300',
    progress: 'bg-red-500',
  },
  warning: {
    icon: AlertTriangle,
    bg: 'bg-amber-950/90',
    border: 'border-amber-800',
    text: 'text-amber-300',
    progress: 'bg-amber-500',
  },
  info: {
    icon: Info,
    bg: 'bg-blue-950/90',
    border: 'border-blue-800',
    text: 'text-blue-300',
    progress: 'bg-blue-500',
  },
}

interface ToastProps {
  toast: ToastData
  onDismiss: (id: string) => void
}

export function Toast({ toast, onDismiss }: ToastProps) {
  const [visible, setVisible] = useState(false)
  const config = typeConfig[toast.type]
  const Icon = config.icon

  useEffect(() => {
    // Trigger slide-in
    requestAnimationFrame(() => setVisible(true))
  }, [])

  const handleDismiss = () => {
    setVisible(false)
    setTimeout(() => onDismiss(toast.id), 200)
  }

  return (
    <div
      className={`
        relative flex items-start gap-2.5 px-4 py-3 rounded-lg border shadow-lg
        backdrop-blur-sm min-w-[320px] max-w-[420px]
        transition-all duration-200 ease-out overflow-hidden
        ${config.bg} ${config.border}
        ${visible ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'}
      `}
    >
      <Icon size={18} className={`shrink-0 mt-0.5 ${config.text}`} />
      <p className={`flex-1 text-sm leading-snug ${config.text}`}>
        {toast.message}
      </p>
      <button
        onClick={handleDismiss}
        className={`shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors ${config.text}`}
      >
        <X size={14} />
      </button>

      {/* Progress bar */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white/5">
        <div
          className={`h-full ${config.progress} opacity-60`}
          style={{
            animation: `toast-progress ${TOAST_DURATION}ms linear forwards`,
          }}
        />
      </div>
    </div>
  )
}
