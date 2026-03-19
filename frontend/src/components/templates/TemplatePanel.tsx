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
  ChevronDown,
  ChevronRight,
  BookOpen,
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
      <div className="flex border-b border-surface-800 px-4">
        <button
          onClick={() => setSubTab('browse')}
          className={`px-4 py-2.5 text-sm font-medium text-center transition-colors ${
            subTab === 'browse'
              ? 'text-primary-400 border-b-2 border-primary-400'
              : 'text-surface-500 hover:text-surface-300'
          }`}
        >
          Browse
        </button>
        <button
          onClick={() => setSubTab('imported')}
          className={`px-4 py-2.5 text-sm font-medium text-center transition-colors ${
            subTab === 'imported'
              ? 'text-primary-400 border-b-2 border-primary-400'
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
      {/* Search + Bulk import */}
      <div className="px-4 py-3 space-y-2 border-b border-surface-800/50">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search templates..."
            className="flex-1 px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg text-sm text-surface-200 placeholder-surface-500 focus:outline-none focus:border-primary-500"
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-3 py-2 bg-surface-800 border border-surface-700 rounded-lg hover:bg-surface-700 transition-colors"
          >
            <Search size={15} className="text-surface-400" />
          </button>
          <button
            onClick={handleImportPopular}
            className="flex items-center gap-1.5 px-3 py-2 text-xs text-primary-400 hover:text-primary-300 bg-primary-400/5 hover:bg-primary-400/10 border border-primary-400/20 rounded-lg transition-colors whitespace-nowrap"
          >
            <TrendingUp size={13} />
            Import Top 50
          </button>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-1">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw size={20} className="text-surface-500 animate-spin" />
          </div>
        ) : templates.length === 0 ? (
          <p className="text-surface-500 text-sm text-center py-12">
            No templates found
          </p>
        ) : (
          templates.map((tpl) => (
            <div
              key={tpl.id}
              className="group flex items-start gap-3 px-3 py-2.5 rounded-lg hover:bg-surface-800/50 transition-colors"
            >
              <Package size={16} className="shrink-0 mt-0.5 text-surface-500" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-surface-200">{tpl.name}</p>
                {tpl.description && (
                  <p className="text-xs text-surface-500 mt-0.5 line-clamp-1">{tpl.description}</p>
                )}
                <div className="flex items-center gap-3 mt-1">
                  <span className="flex items-center gap-1 text-[11px] text-surface-500">
                    <Eye size={11} />
                    {tpl.totalViews.toLocaleString()}
                  </span>
                  <span className="flex items-center gap-1 text-[11px] text-surface-500">
                    <Layers size={11} />
                    {tpl.nodes?.length || 0} nodes
                  </span>
                </div>
              </div>
              {tpl.is_imported ? (
                <span className="shrink-0 flex items-center gap-1 text-xs text-green-400 px-2 py-1 rounded-md bg-green-400/10">
                  <Check size={13} />
                  Imported
                </span>
              ) : (
                <button
                  onClick={() => handleImport(tpl.id)}
                  disabled={importing.has(tpl.id)}
                  className="shrink-0 flex items-center gap-1 px-2.5 py-1 text-xs opacity-0 group-hover:opacity-100 text-primary-400 hover:text-primary-300 bg-primary-400/10 hover:bg-primary-400/15 rounded-md transition-all"
                  title="Import template"
                >
                  <Download size={13} />
                  Import
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalCount > 15 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-surface-800 text-xs text-surface-500">
          <button
            onClick={() => { setPage(page - 1); doSearch(query, page - 1) }}
            disabled={page <= 1}
            className="px-2 py-1 hover:text-surface-300 disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={15} />
          </button>
          <span>Page {page} · {totalCount.toLocaleString()} templates</span>
          <button
            onClick={() => { setPage(page + 1); doSearch(query, page + 1) }}
            disabled={page * 15 >= totalCount}
            className="px-2 py-1 hover:text-surface-300 disabled:opacity-30 rotate-180 transition-colors"
          >
            <ChevronLeft size={15} />
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
  const [expandedId, setExpandedId] = useState<string | null>(null)

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

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id)
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Stats bar */}
      {stats && (
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-surface-800 text-xs text-surface-500">
          <Package size={14} />
          <span>{stats.total_templates} templates imported</span>
          <button
            onClick={refresh}
            className="ml-auto p-1 hover:text-surface-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-1">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw size={20} className="text-surface-500 animate-spin" />
          </div>
        ) : templates.length === 0 ? (
          <div className="text-center py-12">
            <Package size={28} className="mx-auto text-surface-600 mb-2" />
            <p className="text-surface-500 text-sm">No templates imported yet</p>
            <p className="text-surface-600 text-xs mt-1">
              Use the Browse tab to search and import templates
            </p>
          </div>
        ) : (
          templates.map((tpl) => {
            const isExpanded = expandedId === tpl.id
            return (
              <div
                key={tpl.id}
                className="rounded-lg hover:bg-surface-800/50 transition-colors"
              >
                <div className="group flex items-start gap-3 px-3 py-2.5">
                  {/* Expand toggle */}
                  <button
                    onClick={() => toggleExpand(tpl.id)}
                    className="shrink-0 mt-0.5 text-surface-500 hover:text-surface-300 transition-colors"
                    title="Preview learned knowledge"
                  >
                    {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-surface-200">{tpl.name}</p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-[11px] text-surface-500">
                        {tpl.node_count} nodes · {tpl.chunks} chunks
                      </span>
                      {tpl.categories?.slice(0, 3).map((cat) => (
                        <span
                          key={cat}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-surface-800 text-surface-400"
                        >
                          {cat}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {confirmDeleteId === tpl.id ? (
                      <>
                        <button
                          onClick={() => handleDelete(tpl.id)}
                          className="p-1.5 text-red-400 hover:text-red-300"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="p-1.5 text-surface-500 hover:text-surface-300"
                        >
                          <X size={14} />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => toggleExpand(tpl.id)}
                          className="p-1.5 opacity-0 group-hover:opacity-100 hover:text-primary-400 transition-all"
                          title="Preview learned knowledge"
                        >
                          <BookOpen size={14} />
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(tpl.id)}
                          className="p-1.5 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
                          title="Remove template"
                        >
                          <Trash2 size={14} />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Expanded: distilled knowledge preview */}
                {isExpanded && tpl.distilled_text && (
                  <div className="mx-3 mb-3 ml-10 rounded-lg bg-surface-800/60 border border-surface-700/50 overflow-hidden">
                    <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-surface-700/50 bg-surface-800/40">
                      <BookOpen size={12} className="text-primary-400/70" />
                      <span className="text-[11px] font-medium text-surface-400">Learned Knowledge</span>
                    </div>
                    <pre className="px-3 py-2.5 text-xs text-surface-300 whitespace-pre-wrap font-mono leading-relaxed max-h-64 overflow-y-auto scrollbar-thin">
                      {tpl.distilled_text}
                    </pre>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
