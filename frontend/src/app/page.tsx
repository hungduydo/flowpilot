'use client'

import { useEffect } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { ChatContainer } from '@/components/chat/ChatContainer'
import { useChat } from '@/hooks/use-chat'

export default function Home() {
  const { loadConversations, sidebarOpen } = useChat()

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div
        className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${
          sidebarOpen ? 'ml-72' : 'ml-0'
        }`}
      >
        <Header />
        <ChatContainer />
      </div>
    </div>
  )
}
