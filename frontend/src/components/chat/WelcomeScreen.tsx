'use client'

import { Zap, Webhook, Clock, GitBranch, Mail } from 'lucide-react'

interface Props {
  onSuggestionClick: (message: string) => void
}

const suggestions = [
  {
    icon: Webhook,
    title: 'Webhook to Slack',
    prompt: 'Create a workflow that receives webhook data and sends a Slack notification',
  },
  {
    icon: Clock,
    title: 'Scheduled Report',
    prompt: 'Create a workflow that runs every day at 9am, fetches data from an API, and sends an email report',
  },
  {
    icon: GitBranch,
    title: 'GitHub Issues',
    prompt: 'Create a workflow that triggers on new GitHub issues and posts to Slack with the issue details',
  },
  {
    icon: Mail,
    title: 'Form Handler',
    prompt: 'Create a workflow that handles form submissions via webhook, validates the data, and sends a confirmation email',
  },
]

export function WelcomeScreen({ onSuggestionClick }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="w-16 h-16 rounded-2xl bg-primary-600/20 flex items-center justify-center mb-6">
        <Zap size={32} className="text-primary-400" />
      </div>

      <h2 className="text-2xl font-semibold text-surface-100 mb-2">
        LLM Workflow Builder
      </h2>
      <p className="text-surface-400 text-sm mb-8 max-w-md">
        Describe the n8n workflow you want to create in natural language.
        I&apos;ll generate it and deploy it directly to your n8n instance.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {suggestions.map((s) => (
          <button
            key={s.title}
            onClick={() => onSuggestionClick(s.prompt)}
            className="flex items-start gap-3 p-4 rounded-xl border border-surface-800 hover:border-surface-600 hover:bg-surface-800/50 text-left transition-all group"
          >
            <s.icon
              size={18}
              className="text-surface-500 group-hover:text-primary-400 transition-colors mt-0.5 shrink-0"
            />
            <div>
              <p className="text-sm font-medium text-surface-200 group-hover:text-surface-100">
                {s.title}
              </p>
              <p className="text-xs text-surface-500 mt-0.5 line-clamp-2">
                {s.prompt}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
