'use client'

import { useState, useEffect } from 'react'
import { getWorkflowVersions, rollbackWorkflowVersion } from '@/lib/api'
import { formatTimestamp } from '@/lib/utils'
import { WorkflowJsonViewer } from './WorkflowJsonViewer'
import {
  X,
  Clock,
  Eye,
  EyeOff,
  RotateCcw,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react'

interface WorkflowVersionData {
  id: string
  workflow_id: string
  version: number
  name: string
  workflow_json: Record<string, unknown>
  change_summary: string | null
  created_at: string
  created_by: string
}

interface Props {
  workflowId: string
  workflowName: string
  onClose: () => void
  onRollback?: () => void
}

export function VersionHistory({ workflowId, workflowName, onClose, onRollback }: Props) {
  const [versions, setVersions] = useState<WorkflowVersionData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [confirmRollbackId, setConfirmRollbackId] = useState<string | null>(null)
  const [rollingBack, setRollingBack] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  useEffect(() => {
    loadVersions()
  }, [workflowId])

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  const loadVersions = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getWorkflowVersions(workflowId)
      setVersions(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load versions')
    } finally {
      setLoading(false)
    }
  }

  const handleRollback = async (versionId: string, versionNum: number) => {
    setRollingBack(true)
    try {
      await rollbackWorkflowVersion(workflowId, versionId)
      setToast({ message: `Rolled back to version ${versionNum}`, type: 'success' })
      setConfirmRollbackId(null)
      await loadVersions()
      onRollback?.()
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : 'Rollback failed',
        type: 'error',
      })
    } finally {
      setRollingBack(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="relative w-full max-w-lg h-full bg-surface-900 border-l border-surface-700 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-800">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-primary-400" />
            <div>
              <h2 className="text-sm font-semibold text-surface-100">Version History</h2>
              <p className="text-xs text-surface-500 mt-0.5">{workflowName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Toast */}
        {toast && (
          <div
            className={`mx-4 mt-3 px-3 py-2 rounded-lg text-xs flex items-center gap-2 ${
              toast.type === 'success'
                ? 'bg-green-400/10 text-green-400 border border-green-400/20'
                : 'bg-red-400/10 text-red-400 border border-red-400/20'
            }`}
          >
            {toast.type === 'success' ? <Check size={12} /> : <AlertCircle size={12} />}
            {toast.message}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={20} className="animate-spin text-surface-500" />
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <AlertCircle size={20} className="mx-auto text-red-400 mb-2" />
              <p className="text-xs text-red-400">{error}</p>
              <button
                onClick={loadVersions}
                className="mt-2 text-xs text-primary-400 hover:text-primary-300"
              >
                Retry
              </button>
            </div>
          ) : versions.length === 0 ? (
            <p className="text-surface-500 text-xs text-center py-12">
              No version history yet
            </p>
          ) : (
            versions.map((v, idx) => (
              <div
                key={v.id}
                className={`rounded-lg border transition-colors ${
                  idx === 0
                    ? 'border-primary-500/30 bg-primary-500/5'
                    : 'border-surface-700 bg-surface-800/50'
                }`}
              >
                {/* Version header */}
                <div className="flex items-center justify-between p-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-surface-200">
                        v{v.version}
                      </span>
                      {idx === 0 && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-primary-500/20 text-primary-400">
                          Current
                        </span>
                      )}
                      <span className="text-xs text-surface-500">
                        {formatTimestamp(v.created_at)}
                      </span>
                    </div>
                    {v.change_summary && (
                      <p className="text-xs text-surface-400 mt-1 truncate">
                        {v.change_summary}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-1 ml-2 shrink-0">
                    {/* View JSON toggle */}
                    <button
                      onClick={() =>
                        setExpandedId(expandedId === v.id ? null : v.id)
                      }
                      className="p-1.5 rounded hover:bg-surface-700 text-surface-400 hover:text-surface-200 transition-colors"
                      title={expandedId === v.id ? 'Hide JSON' : 'View JSON'}
                    >
                      {expandedId === v.id ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>

                    {/* Rollback (not on current version) */}
                    {idx !== 0 && (
                      confirmRollbackId === v.id ? (
                        <div className="flex items-center gap-0.5">
                          <button
                            onClick={() => handleRollback(v.id, v.version)}
                            disabled={rollingBack}
                            className="p-1.5 rounded text-amber-400 hover:text-amber-300 hover:bg-surface-700 transition-colors disabled:opacity-50"
                            title="Confirm rollback"
                          >
                            {rollingBack ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : (
                              <Check size={13} />
                            )}
                          </button>
                          <button
                            onClick={() => setConfirmRollbackId(null)}
                            className="p-1.5 rounded text-surface-500 hover:text-surface-300 hover:bg-surface-700 transition-colors"
                            title="Cancel"
                          >
                            <X size={13} />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmRollbackId(v.id)}
                          className="p-1.5 rounded hover:bg-surface-700 text-surface-400 hover:text-amber-400 transition-colors"
                          title="Rollback to this version"
                        >
                          <RotateCcw size={13} />
                        </button>
                      )
                    )}
                  </div>
                </div>

                {/* Expanded JSON viewer */}
                {expandedId === v.id && (
                  <div className="border-t border-surface-700">
                    <WorkflowJsonViewer data={v.workflow_json} />
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
