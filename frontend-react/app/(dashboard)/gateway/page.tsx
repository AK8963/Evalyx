'use client'

import { useState, useRef } from 'react'
import { useProject } from '@/components/layout/ProjectSelector'
import { api } from '@/lib/api'
import { formatMs, formatCost } from '@/lib/utils'
import { Zap, Send, Square } from 'lucide-react'
import { toast } from 'sonner'

const MODELS = ['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'gemini-pro']

interface UsageStats {
  total_requests: number
  total_tokens: number
  total_cost: number
  avg_latency_ms: number
}

export default function GatewayPage() {
  const { project } = useProject()
  const [model, setModel] = useState('gpt-4')
  const [prompt, setPrompt] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [output, setOutput] = useState('')
  const [meta, setMeta] = useState<{ latency?: number; tokens?: number; cost?: number } | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  async function runStream() {
    if (!prompt.trim() || !project) return
    setStreaming(true)
    setOutput('')
    setMeta(null)

    const controller = new AbortController()
    abortRef.current = controller
    const t0 = Date.now()

    try {
      const res = await api.gateway.stream({
        project_id: project.id,
        model,
        messages: [{ role: 'user', content: prompt }],
        stream: true,
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response body')
      const decoder = new TextDecoder()

      let totalTokens = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n').filter((l) => l.startsWith('data: '))

        for (const line of lines) {
          const data = line.slice(6)
          if (data === '[DONE]') break
          try {
            const json = JSON.parse(data)
            const delta = json.choices?.[0]?.delta?.content ?? json.content ?? ''
            if (delta) setOutput((prev) => prev + delta)
            if (json.usage) totalTokens = json.usage.total_tokens ?? totalTokens
          } catch {
            // Non-JSON SSE line, skip
          }
        }
      }

      setMeta({ latency: Date.now() - t0, tokens: totalTokens || undefined })
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        toast.error(e instanceof Error ? e.message : 'Streaming failed')
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  function stopStream() {
    abortRef.current?.abort()
    setStreaming(false)
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center">
          <Zap className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Gateway</h1>
          <p className="text-xs text-muted-foreground">Unified LLM routing with streaming</p>
        </div>
      </div>

      {/* Config */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="text-sm px-3 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
        >
          {MODELS.map((m) => <option key={m}>{m}</option>)}
        </select>
      </div>

      {/* Input */}
      <div className="rounded-xl border bg-card p-4 space-y-3">
        <label className="text-sm font-medium">Prompt</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter your prompt…"
          rows={4}
          className="w-full text-sm px-3 py-2 border rounded-md bg-background resize-y focus:outline-none focus:ring-1 focus:ring-ring font-mono"
        />
        <div className="flex gap-2">
          <button
            onClick={runStream}
            disabled={!prompt.trim() || streaming}
            className="flex items-center gap-2 px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {streaming ? 'Streaming…' : 'Send (stream)'}
          </button>
          {streaming && (
            <button
              onClick={stopStream}
              className="flex items-center gap-2 px-3 py-1.5 border rounded-md text-sm hover:bg-muted"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Output */}
      {(output || streaming) && (
        <div className="rounded-xl border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">Response</label>
            {streaming && (
              <span className="flex items-center gap-1 text-xs text-primary">
                <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
                Streaming
              </span>
            )}
          </div>
          <pre className="text-sm whitespace-pre-wrap font-mono bg-muted rounded p-3 min-h-[80px] max-h-[400px] overflow-auto">
            {output}
            {streaming && <span className="animate-pulse">▋</span>}
          </pre>
          {meta && !streaming && (
            <div className="flex gap-4 text-xs text-muted-foreground">
              {meta.latency && <span>Latency: {formatMs(meta.latency)}</span>}
              {meta.tokens && <span>Tokens: {meta.tokens.toLocaleString()}</span>}
              {meta.cost && <span>Cost: {formatCost(meta.cost)}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
