'use client'

import { useState, useRef, useEffect } from 'react'
import { useChatStore } from '@/stores/chat-store'
import { ChevronDown, Cpu, Lock } from 'lucide-react'

interface ModelOption {
  provider: string
  model: string
  label: string
  shortLabel: string
  group: string
}

const MODEL_OPTIONS: ModelOption[] = [
  // Ollama Cloud
  { provider: 'ollama', model: 'qwen3.5:397b', label: 'Qwen 3.5 (397B)', shortLabel: 'Qwen 3.5', group: 'Ollama Cloud' },
  { provider: 'ollama', model: 'mistral-large-3:675b', label: 'Mistral Large 3 (675B)', shortLabel: 'Mistral L3', group: 'Ollama Cloud' },
  { provider: 'ollama', model: 'deepseek-v3.2', label: 'DeepSeek V3.2', shortLabel: 'DeepSeek', group: 'Ollama Cloud' },
  { provider: 'ollama', model: 'qwen3-coder:480b', label: 'Qwen3 Coder (480B)', shortLabel: 'Qwen3 Coder', group: 'Ollama Cloud' },
  { provider: 'ollama', model: 'gpt-oss:120b', label: 'GPT-OSS (120B)', shortLabel: 'GPT-OSS', group: 'Ollama Cloud' },
  // Anthropic
  { provider: 'anthropic', model: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4', shortLabel: 'Sonnet 4', group: 'Anthropic' },
  { provider: 'anthropic', model: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5', shortLabel: 'Haiku 4.5', group: 'Anthropic' },
  { provider: 'anthropic', model: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku', shortLabel: 'Haiku 3', group: 'Anthropic' },
  // OpenAI
  { provider: 'openai', model: 'gpt-4o', label: 'GPT-4o', shortLabel: 'GPT-4o', group: 'OpenAI' },
  { provider: 'openai', model: 'gpt-4o-mini', label: 'GPT-4o Mini', shortLabel: 'GPT-4o Mini', group: 'OpenAI' },
]

/** Check if a provider:model combo exists in the known options list */
function isModelAvailable(provider: string | null, model: string | null): boolean {
  if (!provider || !model) return false
  return MODEL_OPTIONS.some((o) => o.provider === provider && o.model === model)
}

export function ModelSelector() {
  const { selectedProvider, selectedModel, setSelectedModelSpec, isLoading } = useChatStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // On mount: hydrate from localStorage, validate, fallback if unavailable
  const [hydrated, setHydrated] = useState(false)
  useEffect(() => {
    const { hydrateModel } = useChatStore.getState()
    hydrateModel()
    setHydrated(true)
  }, [])

  // After hydration: validate persisted model
  useEffect(() => {
    if (!hydrated) return
    if (selectedProvider && selectedModel && !isModelAvailable(selectedProvider, selectedModel)) {
      console.warn(
        `[ModelSelector] Persisted model "${selectedProvider}:${selectedModel}" is no longer available, falling back to default`
      )
      setSelectedModelSpec(null, null)
    }
  }, [hydrated]) // eslint-disable-line react-hooks/exhaustive-deps

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open])

  const current = MODEL_OPTIONS.find(
    (o) => o.provider === selectedProvider && o.model === selectedModel
  ) || null

  const displayLabel = current ? current.shortLabel : 'Default'
  const displayGroup = current ? current.group : 'Server'

  const handleSelect = (option: ModelOption | null) => {
    if (option) {
      setSelectedModelSpec(option.provider, option.model)
    } else {
      setSelectedModelSpec(null, null)
    }
    setOpen(false)
  }

  // Group options
  const groups = MODEL_OPTIONS.reduce<Record<string, ModelOption[]>>((acc, opt) => {
    if (!acc[opt.group]) acc[opt.group] = []
    acc[opt.group].push(opt)
    return acc
  }, {})

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => !isLoading && setOpen(!open)}
        disabled={isLoading}
        className={`
          flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors
          ${isLoading
            ? 'bg-surface-800/50 text-surface-500 cursor-not-allowed'
            : 'bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-surface-100'
          }
        `}
        title={isLoading ? 'Model locked while generating' : 'Select LLM model'}
      >
        {isLoading ? (
          <Lock size={13} className="text-surface-500" />
        ) : (
          <Cpu size={14} />
        )}
        <span className="hidden sm:inline text-surface-500 text-xs">{displayGroup}:</span>
        <span className="max-w-[100px] truncate">{displayLabel}</span>
        {!isLoading && (
          <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        )}
      </button>

      {open && !isLoading && (
        <div className="absolute right-0 top-full mt-1.5 w-64 bg-surface-900 border border-surface-700 rounded-xl shadow-2xl z-50 overflow-hidden">
          {/* Default option */}
          <button
            onClick={() => handleSelect(null)}
            className={`
              w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors
              ${!current
                ? 'bg-primary-500/10 text-primary-400'
                : 'text-surface-300 hover:bg-surface-800 hover:text-surface-100'
              }
            `}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
            <span>Server Default</span>
            <span className="text-xs text-surface-500 ml-auto">from .env</span>
          </button>

          <div className="border-t border-surface-700/50" />

          {/* Grouped models */}
          {Object.entries(groups).map(([group, options]) => (
            <div key={group}>
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-surface-500 bg-surface-900/50">
                {group}
              </div>
              {options.map((option) => {
                const isActive = current?.provider === option.provider && current?.model === option.model
                return (
                  <button
                    key={`${option.provider}:${option.model}`}
                    onClick={() => handleSelect(option)}
                    className={`
                      w-full px-3 py-2 text-left text-sm flex items-center gap-2 transition-colors
                      ${isActive
                        ? 'bg-primary-500/10 text-primary-400'
                        : 'text-surface-300 hover:bg-surface-800 hover:text-surface-100'
                      }
                    `}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? 'bg-primary-400' : 'bg-surface-600'}`} />
                    <span>{option.label}</span>
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
