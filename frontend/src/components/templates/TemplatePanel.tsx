'use client'

import { useState, useEffect, useCallback } from 'react'
import { useToastStore } from '@/stores/toast-store'
import {
  searchN8nTemplates,
  importTemplates,
  importPopularTemplates,
  getImportedTemplates,
  getImportedTemplateStats,
  deleteImportedTemplate,
  type ImportedTemplate,
} from '@/lib/api'
import {
  Search,
  Download,
  Trash2,
  Check,
  X,
  Eye,
  Package,
  Layers,
  TrendingUp,
  RefreshCw,
  ChevronLeft,
} from 'lucide-react'

type SubTab = 'browse' | 'imported'

interface TemplateSearchResult {
  id: number
  name: string
  totalViews: number
  description: string
  is_imported?: boolean
  nodes: Array<{ displayName: string }>
}

export function TemplatePanel() {
  const [subTab, setSubTab] = useState<SubTab>('browse')

  return (
    <div className="flex flex-col h-full">
      {/* Sub-tabs */}
      <div className="flex border-b border-surface-800 px-2">
        <button
          onClick={() => setSubTab('browse')}
          className={`flex-1 py-1.5 text-[11px] font-medium text-center transition-colors ${
            subTab === 'browse'
              ? 'text-primary-400 border-b border-primary-400'
              : 'text-surface-500 hover:text-surface-300'
          }`}
        >
          Browse
        </button>
        <button
          onClick={() => setSubTab('imported')}
          className={`flex-1 py-1.5 text-[11px] font-medium text-center transition-colors ${
            subTab === 'imported'
              ? 'text-primary-400 border-b border-primary-400'
              : 'text-surface-500 hover:text-surface-300'
          }`}
        >
          Imported
        </button>
      </div>

      {subTab === 'browse' ? <BrowseTemplates /> : <ImportedTemplates />}
    </div>
  )
}

function BrowseTemplates() {
  const toast = useToastStore()
  const [query, setQuery] = useState('')
  const [templates, setTemplates] = useState<TemplateSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState<Set<number>>(new Set())
  const [totalCount, setTotalCount] = useState(0)
  const [page, setPage] = useState(1)

  const doSearch = useCallback(async (q: string, p: number) => {
    setLoading(true)
    try {
      const data = await searchN8nTemplates(q || undefined, undefined, p, 15)
      setTemplates(data.workflows as TemplateSearchResult[])
      setTotalCount(data.totalWorkflows)
    } catch {
      toast.addToast('error', 'Failed to search templates')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    doSearch('', 1)
  }, [doSearch])

  const handleSearch = () => {
    setPage(1)
    doSearch(query, 1)
  }

  const handleImport = async (templateId: number) => {
    setImporting((prev) => new Set(prev).add(templateId))
    try {
      await importTemplates([templateId])
      toast.addToast('success', 'Template import started')
      // Mark as imported in local state
      setTemplates((prev) =>
        prev.map((t) => (t.id === templateId ? { ...t, is_imported: true } : t))
      )
    } catch {
      toast.addToast('error', 'Failed to import template')
    } finally {
      setImporting((prev) => {
        const next = new Set(prev)
        next.delete(templateId)
        return next
      })
    }
  }

  const handleImportPopular = async () => {
    try {
      await importPopularTemplates(50)
      toast.addToast('success', 'Importing top 50 popular templates...')
    } catch {
      toast.addToast('error', 'Failed to start popular import')
    }
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Search */}
      <div className="p-2 space-y-2">
        <div className="flex gap-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search templates..."
            className="flex-1 px-2.5 py-1.5 bg-surface-800 border border-surface-700 rounded text-sm text-surface-200 placeholder-surface-500 focus:outline-none focus:border-primary-500"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-2 py-1.5 bg-surface-800 border border-surface-700 rounded hover:bg-surface-700 transition-colors"
          >
            <Search size={14} className="text-surface-400" />
          </button>
        </div>

        {/* Bulk import */}
        <button
          onClick={handleImportPopular}
          className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-[11px] text-primary-400 hover:text-primary-300 bg-primary-400/5 hover:bg-primary-400/10 border border-primary-400/20 rounded transition-colors"
        >
          <TrendingUp size={12} />
          Import Top 50 Popular
        </button>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-1">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw size={16} className="text-surface-500 animate-spin" />
          </div>
        ) : templates.length === 0 ? (
          <p className="text-surface-500 text-xs text-center py-8">
            No templates found
          </p>
        ) : (
          templates.map((tpl) => (
            <div
              key={tpl.id}
              className="group px-2.5 py-2 rounded-lg hover:bg-surface-800/50 transition-colors"
            >
              <div className="flex items-start gap-2">
                <Package size={14} className="shrink-0 mt-0.5 text-surface-500" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-surface-200 truncate">{tpl.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="flex items-center gap-0.5 text-[10px] text-surface-500">
                      <Eye size={10} />
                      {tpl.totalViews.toLocaleString()}
                    </span>
                    <span className="flex items-center gap-0.5 text-[10px] text-surface-500">
                      <Layers size={10} />
                      {tpl.nodes?.length || 0} nodes
                    </span>
                  </div>
                </div>
                {tpl.is_imported ? (
                  <span className="shrink-0 flex items-center gap-0.5 text-[10px] text-green-400">
                    <Check size={12} />
                  </span>
                ) : (
                  <button
                    onClick={() => handleImport(tpl.id)}
                    disabled={importing.has(tpl.id)}
                    className="shrink-0 p-1 opacity-0 group-hover:opacity-100 text-primary-400 hover:text-primary-300 transition-all"
                    title="Import template"
                  >
                    <Download size={13} />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalCount > 15 && (
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-surface-800 text-[11px] text-surface-500">
          <button
            onClick={() => { setPage(page - 1); doSearch(query, page - 1) }}
            disabled={page <= 1}
            className="hover:text-surface-300 disabled:opacity-30"
          >
            <ChevronLeft size={14} />
          </button>
          <span>Page {page} · {totalCount.toLocaleString()} templates</span>
          <button
            onClick={() => { setPage(page + 1); doSearch(query, page + 1) }}
            disabled={page * 15 >= totalCount}
            className="hover:text-surface-300 disabled:opacity-30 rotate-180"
          >
            <ChevronLeft size={14} />
          </button>
        </div>
      )}
    </div>
  )
}

function ImportedTemplates() {
  const toast = useToastStore()
  const [templates, setTemplates] = useState<ImportedTemplate[]>([])
  const [stats, setStats] = useState<{ total_templates: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [tpls, st] = await Promise.all([
        getImportedTemplates(),
        getImportedTemplateStats(),
      ])
      setTemplates(tpls)
      setStats(st)
    } catch {
      toast.addToast('error', 'Failed to load imported templates')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleDelete = async (id: string) => {
    try {
      await deleteImportedTemplate(id)
      setTemplates((prev) => prev.filter((t) => t.id !== id))
      toast.addToast('success', 'Template removed')
    } catch {
      toast.addToast('error', 'Failed to remove template')
    }
    setConfirmDeleteId(null)
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Stats bar */}
      {stats && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-800 text-[11px] text-surface-500">
          <Package size={12} />
          <span>{stats.total_templates} templates imported</span>
          <button
            onClick={refresh}
            className="ml-auto hover:text-surface-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={12} />
          </button>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-0.5">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw size={16} className="text-surface-500 animate-spin" />
          </div>
        ) : templates.length === 0 ? (
          <p className="text-surface-500 text-xs text-center py-8">
            No templates imported yet.<br />
            Use the Browse tab to import.
          </p>
        ) : (
          templates.map((tpl) => (
            <div
              key={tpl.id}
              className="group px-2.5 py-2 rounded-lg hover:bg-surface-800/50 transition-colors"
            >
              <div className="flex items-start gap-2">
                <Package size={14} className="shrink-0 mt-0.5 text-primary-400/60" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-surface-200 truncate">{tpl.name}</p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <span className="text-[10px] text-surface-500">
                      {tpl.node_count} nodes · {tpl.chunks} chunks
                    </span>
                    {tpl.categories?.slice(0, 2).map((cat) => (
                      <span
                        key={cat}
                        className="text-[9px] px-1 py-0.5 rounded bg-surface-800 text-surface-400"
                      >
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>
                {confirmDeleteId === tpl.id ? (
                  <div className="flex items-center gap-0.5 shrink-0">
                    <button
                      onClick={() => handleDelete(tpl.id)}
                      className="p-1 text-red-400 hover:text-red-300"
                    >
                      <Check size={12} />
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="p-1 text-surface-500 hover:text-surface-300"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteId(tpl.id)}
                    className="shrink-0 p-1 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
                    title="Remove template"
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
