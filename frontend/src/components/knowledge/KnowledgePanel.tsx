'use client'

import { useState, useEffect } from 'react'
import { useToastStore } from '@/stores/toast-store'
import {
  getKnowledgeNotes,
  createKnowledgeNote,
  deleteKnowledgeNote,
  updateKnowledgeNote,
  KnowledgeNote,
} from '@/lib/api'
import {
  Plus,
  Trash2,
  Check,
  X,
  BookOpen,
  Edit3,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react'
import { formatTimestamp } from '@/lib/utils'

// Category options for dropdown
const CATEGORIES = [
  { value: '', label: 'All' },
  { value: 'node', label: 'Node' },
  { value: 'credential', label: 'Credential' },
  { value: 'pattern', label: 'Pattern' },
  { value: 'rule', label: 'Rule' },
]

export function KnowledgePanel() {
  const toast = useToastStore()
  const [notes, setNotes] = useState<KnowledgeNote[]>([])
  const [loading, setLoading] = useState(true)
  const [newContent, setNewContent] = useState('')
  const [newCategory, setNewCategory] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')

  const loadNotes = async () => {
    setLoading(true)
    try {
      const data = await getKnowledgeNotes(false) // show all, including inactive
      setNotes(data)
    } catch {
      toast.addToast('error', 'Failed to load knowledge notes')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadNotes()
  }, [])

  const handleCreate = async () => {
    if (!newContent.trim()) return
    try {
      await createKnowledgeNote(newContent.trim(), newCategory || undefined)
      setNewContent('')
      setNewCategory('')
      setShowForm(false)
      toast.addToast('success', 'Knowledge note saved')
      loadNotes()
    } catch {
      toast.addToast('error', 'Failed to save note')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteKnowledgeNote(id)
      toast.addToast('success', 'Note deleted')
      loadNotes()
    } catch {
      toast.addToast('error', 'Failed to delete note')
    }
    setConfirmDeleteId(null)
  }

  const handleToggleActive = async (note: KnowledgeNote) => {
    try {
      await updateKnowledgeNote(note.id, { is_active: !note.is_active })
      loadNotes()
    } catch {
      toast.addToast('error', 'Failed to update note')
    }
  }

  const handleStartEdit = (note: KnowledgeNote) => {
    setEditingId(note.id)
    setEditContent(note.content)
  }

  const handleSaveEdit = async (id: string) => {
    if (!editContent.trim()) return
    try {
      await updateKnowledgeNote(id, { content: editContent.trim() })
      setEditingId(null)
      toast.addToast('success', 'Note updated')
      loadNotes()
    } catch {
      toast.addToast('error', 'Failed to update note')
    }
  }

  const categoryColor = (cat: string | null) => {
    switch (cat) {
      case 'node': return 'text-blue-400 bg-blue-400/10'
      case 'credential': return 'text-purple-400 bg-purple-400/10'
      case 'pattern': return 'text-emerald-400 bg-emerald-400/10'
      case 'rule': return 'text-amber-400 bg-amber-400/10'
      default: return 'text-surface-400 bg-surface-800'
    }
  }

  return (
    <div className="p-2 space-y-2">
      {/* Add button */}
      <button
        onClick={() => setShowForm(!showForm)}
        className="w-full flex items-center gap-1.5 px-3 py-2 rounded-lg border border-dashed border-surface-700 hover:border-surface-500 text-surface-400 hover:text-surface-200 transition-colors text-xs"
      >
        <Plus size={14} />
        Add knowledge note
      </button>

      {/* Add form */}
      {showForm && (
        <div className="bg-surface-800/50 rounded-lg p-3 space-y-2 border border-surface-700">
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder='e.g. "Use Facebook Graph API node with facebook credential for Facebook posts"'
            className="w-full bg-surface-900 rounded-md px-3 py-2 text-xs text-surface-200 placeholder-surface-600 border border-surface-700 focus:border-primary-500 focus:outline-none resize-none"
            rows={3}
            autoFocus
          />
          <div className="flex items-center gap-2">
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="bg-surface-900 rounded-md px-2 py-1.5 text-xs text-surface-300 border border-surface-700 focus:border-primary-500 focus:outline-none"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
            <div className="flex-1" />
            <button
              onClick={() => { setShowForm(false); setNewContent(''); setNewCategory('') }}
              className="px-2 py-1 text-xs text-surface-500 hover:text-surface-300"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!newContent.trim()}
              className="px-3 py-1 text-xs bg-primary-600 hover:bg-primary-500 text-white rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save
            </button>
          </div>
        </div>
      )}

      {/* Notes list */}
      {loading ? (
        <div className="space-y-2 py-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="animate-pulse bg-surface-800 rounded-lg h-16" />
          ))}
        </div>
      ) : notes.length === 0 ? (
        <div className="text-center py-8">
          <BookOpen size={24} className="mx-auto text-surface-600 mb-2" />
          <p className="text-surface-500 text-xs">No knowledge notes yet</p>
          <p className="text-surface-600 text-[11px] mt-1">
            Add notes to teach the AI your preferences
          </p>
        </div>
      ) : (
        <div className="space-y-1">
          {notes.map((note) => (
            <div
              key={note.id}
              className={`group rounded-lg px-3 py-2 transition-colors ${
                note.is_active
                  ? 'bg-surface-800/30 hover:bg-surface-800/60'
                  : 'bg-surface-900/50 opacity-50 hover:opacity-70'
              }`}
            >
              {editingId === note.id ? (
                <div className="space-y-2">
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full bg-surface-900 rounded-md px-2 py-1.5 text-xs text-surface-200 border border-surface-700 focus:border-primary-500 focus:outline-none resize-none"
                    rows={3}
                    autoFocus
                  />
                  <div className="flex justify-end gap-1">
                    <button
                      onClick={() => setEditingId(null)}
                      className="p-1 text-surface-500 hover:text-surface-300"
                    >
                      <X size={12} />
                    </button>
                    <button
                      onClick={() => handleSaveEdit(note.id)}
                      className="p-1 text-primary-400 hover:text-primary-300"
                    >
                      <Check size={12} />
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start gap-2">
                    <p className="flex-1 text-xs text-surface-300 leading-relaxed">
                      {note.content}
                    </p>
                    {confirmDeleteId === note.id ? (
                      <div className="flex items-center gap-0.5 shrink-0">
                        <button
                          onClick={() => handleDelete(note.id)}
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
                      <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-all">
                        <button
                          onClick={() => handleStartEdit(note)}
                          className="p-1 hover:text-primary-400 transition-colors"
                          title="Edit"
                        >
                          <Edit3 size={11} />
                        </button>
                        <button
                          onClick={() => handleToggleActive(note)}
                          className="p-1 hover:text-amber-400 transition-colors"
                          title={note.is_active ? 'Disable' : 'Enable'}
                        >
                          {note.is_active ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(note.id)}
                          className="p-1 hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    {note.category && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${categoryColor(note.category)}`}>
                        {note.category}
                      </span>
                    )}
                    <span className="text-[10px] text-surface-600">
                      {formatTimestamp(note.created_at)}
                    </span>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
