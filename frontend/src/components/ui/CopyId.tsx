'use client'

import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

interface CopyIdProps {
  /** Label shown before the value (e.g. "Chat ID") */
  label: string
  /** The ID value to display and copy */
  value: string
  /** Max characters to show before truncating. Default: 8 */
  truncate?: number
}

/**
 * Compact inline ID display with one-click copy.
 * Shows: `Label: abc123...` with a copy button.
 */
export function CopyId({ label, value, truncate = 8 }: CopyIdProps) {
  const [copied, setCopied] = useState(false)

  const displayValue = value.length > truncate
    ? value.slice(0, truncate) + '...'
    : value

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Fallback for non-HTTPS contexts
      const textarea = document.createElement('textarea')
      textarea.value = value
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-[10px] text-surface-500 hover:text-surface-300 transition-colors group"
      title={`${label}: ${value}\nClick to copy`}
    >
      <span className="text-surface-600">{label}:</span>
      <code className="font-mono text-[10px]">{displayValue}</code>
      {copied ? (
        <Check size={10} className="text-emerald-400" />
      ) : (
        <Copy size={10} className="opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </button>
  )
}
