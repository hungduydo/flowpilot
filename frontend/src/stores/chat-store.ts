import { create } from 'zustand'
import type { Message, Conversation } from '@/lib/types'

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

  // UI State
  isLoading: boolean
  setLoading: (loading: boolean) => void
  statusText: string
  setStatusText: (text: string) => void
  streamingContent: string
  setStreamingContent: (content: string) => void
  appendStreamingContent: (token: string) => void
  clearStreamingContent: () => void

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

  isLoading: false,
  setLoading: (loading) => set({ isLoading: loading }),
  statusText: '',
  setStatusText: (text) => set({ statusText: text }),
  streamingContent: '',
  setStreamingContent: (content) => set({ streamingContent: content }),
  appendStreamingContent: (token) =>
    set((state) => ({ streamingContent: state.streamingContent + token })),
  clearStreamingContent: () => set({ streamingContent: '' }),

  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}))
