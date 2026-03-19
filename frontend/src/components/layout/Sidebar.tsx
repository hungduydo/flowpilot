'use client'

import { useState, useEffect } from 'react'
import { useChat } from '@/hooks/use-chat'
import { useToastStore } from '@/stores/toast-store'
import { getN8nWorkflows, archiveN8nWorkflow, unarchiveN8nWorkflow } from '@/lib/api'
import { formatTimestamp, truncate } from '@/lib/utils'
import { SkeletonConversationList, SkeletonWorkflowList } from '@/components/ui/Skeleton'
import { VersionHistory } from '@/components/workflow/VersionHistory'
import { KnowledgePanel } from '@/components/knowledge/KnowledgePanel'
import {
  Plus,
  MessageSquare,
  Trash2,
  Check,
  X,
  Workflow,
  ExternalLink,
  Archive,
  ArchiveRestore,
  Clock,
  BookOpen,
} from 'lucide-react'

const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL || 'http://localhost:5678'

interface N8nWf {
  id: string
  name: string
  active: boolean
  isArchived?: boolean
  updatedAt: string
}

function getWfStatus(wf: N8nWf): { label: string; color: string } {
  if (wf.isArchived) return { label: 'Archived', color: 'text-surface-500 bg-surface-800' }
  if (wf.active) return { label: 'Active', color: 'text-green-400 bg-green-400/10' }
  return { label: 'Draft', color: 'text-amber-400 bg-amber-400/10' }
}

export function Sidebar() {
  const {
    conversations,
    activeConversationId,
    sidebarOpen,
    newConversation,
    loadConversation,
    removeConversation,
  } = useChat()

  const toast = useToastStore()
  const [n8nWorkflows, setN8nWorkflows] = useState<N8nWf[]>([])
  const [activeTab, setActiveTab] = useState<'chats' | 'workflows' | 'knowledge'>('chats')
  const [showArchived, setShowArchived] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [confirmArchiveId, setConfirmArchiveId] = useState<string | null>(null)
  const [loadingWorkflows, setLoadingWorkflows] = useState(false)
  const [loadingConversations, setLoadingConversations] = useState(false)
  const [historyWf, setHistoryWf] = useState<N8nWf | null>(null)

  const refreshWorkflows = () => {
    setLoadingWorkflows(true)
    getN8nWorkflows()
      .then((data) => setN8nWorkflows(data.data || []))
      .catch(() => {
        setN8nWorkflows([])
        toast.addToast('error', 'Failed to load n8n workflows')
      })
      .finally(() => setLoadingWorkflows(false))
  }

  // Load n8n workflows
  useEffect(() => {
    if (activeTab === 'workflows') {
      refreshWorkflows()
    }
  }, [activeTab])

  // Track conversation loading
  useEffect(() => {
    if (activeTab === 'chats' && conversations.length === 0) {
      setLoadingConversations(true)
      const timer = setTimeout(() => setLoadingConversations(false), 1500)
      return () => clearTimeout(timer)
    } else {
      setLoadingConversations(false)
    }
  }, [activeTab, conversations.length])

  const handleArchive = async (wfId: string) => {
    try {
      await archiveN8nWorkflow(wfId)
      refreshWorkflows()
      toast.addToast('success', 'Workflow archived')
    } catch (err) {
      toast.addToast('error', 'Failed to archive workflow')
    }
    setConfirmArchiveId(null)
  }

  const handleUnarchive = async (wfId: string) => {
    try {
      await unarchiveN8nWorkflow(wfId)
      refreshWorkflows()
      toast.addToast('success', 'Workflow unarchived')
    } catch (err) {
      toast.addToast('error', 'Failed to unarchive workflow')
    }
  }

  if (!sidebarOpen) return null

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-72 bg-surface-900 border-r border-surface-800 flex flex-col z-20">
      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={newConversation}
          className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg border border-surface-700 hover:bg-surface-800 text-surface-200 transition-colors text-sm"
        >
          <Plus size={16} />
          <span>New Chat</span>
        </button>
      </div>

      {/* Tab Switcher */}
      <div className="flex border-b border-surface-800 px-3">
        <button
          onClick={() => setActiveTab('chats')}
          className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
            activeTab === 'chats'
              ? 'text-primary-400 border-b-2 border-primary-400'
              : 'text-surface-500 hover:text-surface-300'
          }`}
        >
          Conversations
        </button>
        <button
          onClick={() => setActiveTab('workflows')}
          className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
            activeTab === 'workflows'
              ? 'text-primary-400 border-b-2 border-primary-400'
              : 'text-surface-500 hover:text-surface-300'
          }`}
        >
          Workflows
        </button>
        <button
          onClick={() => setActiveTab('knowledge')}
          className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${
            activeTab === 'knowledge'
              ? 'text-primary-400 border-b-2 border-primary-400'
              : 'text-surface-500 hover:text-surface-300'
          }`}
        >
          Knowledge
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {activeTab === 'knowledge' ? (
          <KnowledgePanel />
        ) : activeTab === 'chats' ? (
          <div className="p-2 space-y-0.5">
            {loadingConversations ? (
              <SkeletonConversationList />
            ) : conversations.length === 0 ? (
              <p className="text-surface-500 text-xs text-center py-8">
                No conversations yet
              </p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    activeConversationId === conv.id
                      ? 'bg-surface-800 text-surface-100'
                      : 'hover:bg-surface-800/50 text-surface-400'
                  }`}
                  onClick={() => loadConversation(conv.id)}
                >
                  <MessageSquare size={14} className="shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">
                      {truncate(conv.title || 'Untitled chat', 28)}
                    </p>
                    <p className="text-xs text-surface-500">
                      {formatTimestamp(conv.updated_at)}
                    </p>
                  </div>
                  {confirmDeleteId === conv.id ? (
                    <div className="flex items-center gap-0.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          removeConversation(conv.id)
                          setConfirmDeleteId(null)
                        }}
                        className="p-1 text-red-400 hover:text-red-300 transition-colors"
                        title="Confirm delete"
                      >
                        <Check size={13} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setConfirmDeleteId(null)
                        }}
                        className="p-1 text-surface-500 hover:text-surface-300 transition-colors"
                        title="Cancel"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setConfirmDeleteId(conv.id)
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-all"
                      title="Delete conversation"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {loadingWorkflows ? (
              <SkeletonWorkflowList />
            ) : <>
            {/* Filter toggle */}
            {n8nWorkflows.length > 0 && (
              <button
                onClick={() => setShowArchived(!showArchived)}
                className={`w-full flex items-center gap-1.5 px-3 py-1.5 mb-1 rounded text-xs transition-colors ${
                  showArchived
                    ? 'text-surface-300 bg-surface-800'
                    : 'text-surface-500 hover:text-surface-400'
                }`}
              >
                <Archive size={12} />
                {showArchived ? 'Hide archived' : 'Show archived'}
                {!showArchived && (
                  <span className="ml-auto text-surface-600">
                    {n8nWorkflows.filter((w) => w.isArchived).length}
                  </span>
                )}
              </button>
            )}
            {n8nWorkflows.filter((wf) => showArchived || !wf.isArchived).length === 0 ? (
              <p className="text-surface-500 text-xs text-center py-8">
                No workflows on n8n
              </p>
            ) : (
              n8nWorkflows.filter((wf) => showArchived || !wf.isArchived).map((wf) => {
                const status = getWfStatus(wf)
                return (
                <div
                  key={wf.id}
                  className="group px-3 py-2 rounded-lg hover:bg-surface-800/50 text-surface-400 transition-colors"
                >
                  {/* Title — full width */}
                  <a
                    href={`${N8N_URL}/workflow/${wf.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 min-w-0"
                  >
                    <Workflow size={14} className="shrink-0" />
                    <p className="text-sm truncate flex-1">{wf.name}</p>
                  </a>
                  {/* Status + time + actions — same row */}
                  <div className="flex items-center gap-1.5 mt-1 ml-[22px]">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${status.color}`}>
                      {status.label}
                    </span>
                    <span className="text-[11px] text-surface-500">{formatTimestamp(wf.updatedAt)}</span>
                    <div className="ml-auto flex items-center gap-0.5">
                      {confirmArchiveId === wf.id ? (
                        <>
                          <button
                            onClick={() => handleArchive(wf.id)}
                            className="p-1 text-amber-400 hover:text-amber-300 transition-colors"
                            title="Confirm archive"
                          >
                            <Check size={12} />
                          </button>
                          <button
                            onClick={() => setConfirmArchiveId(null)}
                            className="p-1 text-surface-500 hover:text-surface-300 transition-colors"
                            title="Cancel"
                          >
                            <X size={12} />
                          </button>
                        </>
                      ) : (
                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all">
                          <button
                            onClick={() => setHistoryWf(wf)}
                            className="p-1 hover:text-primary-400 transition-colors"
                            title="Version history"
                          >
                            <Clock size={12} />
                          </button>
                          {wf.isArchived ? (
                            <button
                              onClick={() => handleUnarchive(wf.id)}
                              className="p-1 hover:text-green-400 transition-colors"
                              title="Unarchive workflow"
                            >
                              <ArchiveRestore size={12} />
                            </button>
                          ) : (
                            <button
                              onClick={() => setConfirmArchiveId(wf.id)}
                              className="p-1 hover:text-amber-400 transition-colors"
                              title="Archive workflow"
                            >
                              <Archive size={12} />
                            </button>
                          )}
                          <a
                            href={`${N8N_URL}/workflow/${wf.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1 hover:text-primary-400 transition-colors"
                            title="Open in n8n"
                          >
                            <ExternalLink size={12} />
                          </a>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                )
              }))
            }
            </>}
          </div>
        )}
      </div>
      {/* Version History Panel */}
      {historyWf && (
        <VersionHistory
          workflowId={historyWf.id}
          workflowName={historyWf.name}
          onClose={() => setHistoryWf(null)}
          onRollback={refreshWorkflows}
        />
      )}
    </aside>
  )
}
