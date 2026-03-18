'use client'

import { useState } from 'react'
import type { WorkflowData } from '@/lib/types'
import { WorkflowJsonViewer } from './WorkflowJsonViewer'
import {
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Download,
  Workflow,
  Boxes,
} from 'lucide-react'

interface Props {
  workflow: WorkflowData
  n8nUrl?: string | null
}

export function WorkflowCard({ workflow, n8nUrl }: Props) {
  const [showJson, setShowJson] = useState(false)
  const [copied, setCopied] = useState(false)

  const nodeCount = workflow.nodes?.length || 0
  const triggerNode = workflow.nodes?.find((n) =>
    n.type?.toLowerCase().includes('trigger') ||
    n.type?.toLowerCase().includes('webhook'),
  )

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(workflow, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(workflow, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${workflow.name || 'workflow'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="rounded-xl border border-surface-700 bg-surface-800/50 overflow-hidden">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-primary-600/20 flex items-center justify-center">
              <Workflow size={18} className="text-primary-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-surface-100">
                {workflow.name || 'Untitled Workflow'}
              </h3>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="flex items-center gap-1 text-xs text-surface-500">
                  <Boxes size={12} />
                  {nodeCount} nodes
                </span>
                {triggerNode && (
                  <span className="text-xs text-surface-500">
                    Trigger: {triggerNode.name}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Node list preview */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {workflow.nodes?.map((node) => (
            <span
              key={node.id || node.name}
              className="px-2 py-0.5 text-xs rounded-md bg-surface-700/80 text-surface-300"
            >
              {node.name}
            </span>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 px-4 pb-3">
        {n8nUrl && (
          <a
            href={n8nUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary-600 hover:bg-primary-500 text-white transition-colors"
          >
            <span>Open in n8n</span>
            <ExternalLink size={12} />
          </a>
        )}

        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-surface-700 hover:bg-surface-600 text-surface-300 transition-colors"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
        </button>

        <button
          onClick={handleDownload}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-surface-700 hover:bg-surface-600 text-surface-300 transition-colors"
        >
          <Download size={12} />
          <span>Download</span>
        </button>

        <button
          onClick={() => setShowJson(!showJson)}
          className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg bg-surface-700 hover:bg-surface-600 text-surface-300 transition-colors ml-auto"
        >
          <span>{showJson ? 'Hide' : 'View'} JSON</span>
          {showJson ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {/* JSON Viewer */}
      {showJson && (
        <div className="border-t border-surface-700">
          <WorkflowJsonViewer data={workflow} />
        </div>
      )}
    </div>
  )
}
