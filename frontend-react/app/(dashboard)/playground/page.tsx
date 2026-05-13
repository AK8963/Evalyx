'use client'

import { useState } from 'react'
import { useProject } from '@/components/layout/ProjectSelector'
import { api } from '@/lib/api'
import { formatMs, formatCost } from '@/lib/utils'
import { Send, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import type { ChatMessage } from '@/types'

const MODELS = [
  'gpt-4',
  'gpt-3.5-turbo',
  'claude-3-opus-20240229',
  'claude-3-sonnet-20240229',
  'gemini-pro',
  'ollama-llama2',
]

export default function PlaygroundPage() {
  const { project } = useProject()
  const [model, setModel] = useState('gpt-4')
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [system, setSystem] = useState('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [lastMeta, setLastMeta] = useState<{ tokens: number; cost: number; latency: number } | null>(null)

  async function send() {
    if (!input.trim() || !project) return
    const userMsg: ChatMessage = { role: 'user', content: input.trim() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setLoading(true)

    try {
      const payload = {
        project_id: project.id,
        model,
        messages: [
          ...(system ? [{ role: 'system' as const, content: system }] : []),
          ...newMessages,
        ],
        temperature,
        max_tokens: maxTokens,
      }
      const res = await api.gateway.complete(payload)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.content }])
      setLastMeta({
        tokens: res.total_tokens,
        cost: res.cost_usd,
        latency: res.latency_ms,
      })
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project
      </div>
    )
  }

  return (
    <div className="flex gap-5 h-[calc(100vh-8rem)]">
      {/* Config panel */}
      <div className="w-64 shrink-0 space-y-4">
        <h1 className="text-xl font-semibold">Playground</h1>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {MODELS.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">
              Temperature: {temperature}
            </label>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-primary"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Max Tokens</label>
            <input
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(parseInt(e.target.value) || 1024)}
              className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">System prompt</label>
            <textarea
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              placeholder="You are a helpful assistant…"
              rows={4}
              className="w-full text-sm px-2 py-1.5 border rounded-md bg-background resize-none focus:outline-none focus:ring-1 focus:ring-ring font-mono"
            />
          </div>

          <button
            onClick={() => { setMessages([]); setLastMeta(null) }}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear conversation
          </button>
        </div>

        {lastMeta && (
          <div className="rounded-lg border p-3 text-xs space-y-1 text-muted-foreground">
            <p>Tokens: {lastMeta.tokens.toLocaleString()}</p>
            <p>Cost: {formatCost(lastMeta.cost)}</p>
            <p>Latency: {formatMs(lastMeta.latency)}</p>
          </div>
        )}
      </div>

      {/* Chat */}
      <div className="flex-1 flex flex-col border rounded-xl bg-card overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 space-y-3">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Send a message to start
            </div>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[70%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                    m.role === 'user'
                      ? 'bg-primary text-primary-foreground rounded-br-sm'
                      : 'bg-muted rounded-bl-sm'
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-2.5 flex gap-1 items-center">
                <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t p-3 flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
            rows={2}
            className="flex-1 text-sm px-3 py-2 border rounded-lg bg-background resize-none focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            className="self-end px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
