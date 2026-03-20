import { create } from 'zustand'
import type { Message, Conversation } from '@/lib/types'

const STORAGE_KEY = 'flowpilot-model'

/** Read persisted model selection from localStorage, returns [provider, model] or [null, null]. */
function loadPersistedModel(): [string | null, string | null] {
  if (typeof window === 'undefined') return [null, null]
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return [null, null]
    const { provider, model } = JSON.parse(raw)
    if (typeof provider === 'string' && typeof model === 'string') {
      return [provider, model]
    }
  } catch {
    // Corrupted data — clear it
    localStorage.removeItem(STORAGE_KEY)
  }
  return [null, null]
}

/** Persist model selection to localStorage. Null clears it. */
function persistModel(provider: string | null, model: string | null) {
  if (typeof window === 'undefined') return
  if (provider && model) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ provider, model }))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

interface ActiveWorkflow {
  id: string
  name: string
  editorUrl?: string | null
}

interface ChatState {
  // Conversations
  conversations: Conversation[]
  activeConversationId: string | null
  setConversations: (conversations: Conversation[]) => void
  setActiveConversation: (id: string | null) => void
  addConversation: (conversation: Conversation) => void
  removeConversation: (id: string) => void

  // Messages
  messages: Message[]
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  updateLastAssistantMessage: (content: string) => void
  appendToLastAssistantMessage: (token: string) => void

  // Active workflow (sticky per conversation)
  activeWorkflow: ActiveWorkflow | null
  setActiveWorkflow: (wf: ActiveWorkflow | null) => void

  // UI State
  isLoading: boolean
  setLoading: (loading: boolean) => void
  statusText: string
  setStatusText: (text: string) => void
  streamingContent: string
  setStreamingContent: (content: string) => void
  appendStreamingContent: (token: string) => void
  clearStreamingContent: () => void

  // Model selection (persisted to localStorage)
  selectedProvider: string | null
  selectedModel: string | null
  setSelectedProvider: (provider: string | null) => void
  setSelectedModel: (model: string | null) => void
  setSelectedModelSpec: (provider: string | null, model: string | null) => void
  hydrateModel: () => void

  // Debug mode
  debugMode: boolean
  setDebugMode: (debug: boolean) => void

  // Sidebar
  sidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  activeConversationId: null,
  setConversations: (conversations) => set({ conversations }),
  setActiveConversation: (id) => set({ activeConversationId: id }),
  addConversation: (conversation) =>
    set((state) => ({
      conversations: [conversation, ...state.conversations],
    })),
  removeConversation: (id) =>
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId:
        state.activeConversationId === id ? null : state.activeConversationId,
    })),

  messages: [],
  setMessages: (messages) => set({ messages }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  updateLastAssistantMessage: (content) =>
    set((state) => {
      const msgs = [...state.messages]
      const lastIdx = msgs.findLastIndex((m) => m.role === 'assistant')
      if (lastIdx >= 0) {
        msgs[lastIdx] = { ...msgs[lastIdx], content }
      }
      return { messages: msgs }
    }),
  appendToLastAssistantMessage: (token) =>
    set((state) => {
      const msgs = [...state.messages]
      const lastIdx = msgs.findLastIndex((m) => m.role === 'assistant')
      if (lastIdx >= 0) {
        msgs[lastIdx] = {
          ...msgs[lastIdx],
          content: msgs[lastIdx].content + token,
        }
      }
      return { messages: msgs }
    }),

  activeWorkflow: null,
  setActiveWorkflow: (wf) => set({ activeWorkflow: wf }),

  isLoading: false,
  setLoading: (loading) => set({ isLoading: loading }),
  statusText: '',
  setStatusText: (text) => set({ statusText: text }),
  streamingContent: '',
  setStreamingContent: (content) => set({ streamingContent: content }),
  appendStreamingContent: (token) =>
    set((state) => ({ streamingContent: state.streamingContent + token })),
  clearStreamingContent: () => set({ streamingContent: '' }),

  selectedProvider: null,
  selectedModel: null,
  setSelectedProvider: (provider) => {
    set({ selectedProvider: provider })
  },
  setSelectedModel: (model) => {
    set({ selectedModel: model })
  },
  setSelectedModelSpec: (provider, model) => {
    persistModel(provider, model)
    set({ selectedProvider: provider, selectedModel: model })
  },
  hydrateModel: () => {
    const [p, m] = loadPersistedModel()
    set({ selectedProvider: p, selectedModel: m })
  },

  debugMode: false,
  setDebugMode: (debug) => set({ debugMode: debug }),

  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}))
