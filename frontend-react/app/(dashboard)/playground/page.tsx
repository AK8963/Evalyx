'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useProject } from '@/components/layout/ProjectSelector'
import { api } from '@/lib/api'
import { formatMs, formatCost } from '@/lib/utils'
import { Send, Trash2, FlaskConical, Loader2, Database } from 'lucide-react'
import { toast } from 'sonner'
import type { ChatMessage, Trace, Dataset, DatasetItem, Metric } from '@/types'

// ---------------------------------------------------------------------------
// Dataset helpers
// ---------------------------------------------------------------------------

function extractItemText(val: unknown, keys: string[]): string {
  if (!val) return ''
  if (typeof val === 'string') return val
  const obj = val as Record<string, unknown>
  for (const k of keys) {
    if (obj[k] !== undefined) return String(obj[k])
  }
  return JSON.stringify(val)
}

const STOP_WORDS = new Set([
  'what','is','are','was','were','the','a','an','how','why','when','where',
  'who','which','that','this','it','in','on','at','to','for','of','and','or',
  'but','not','do','does','did','can','could','would','should','will','have',
  'has','had','be','been','being','my','your','me','i','about','its','their',
])

function meaningfulWords(text: string): Set<string> {
  const words = text.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/)
  return new Set(words.filter((w) => w.length > 2 && !STOP_WORDS.has(w)))
}

function wordOverlap(a: string, b: string): number {
  const sa = meaningfulWords(a)
  const sb = meaningfulWords(b)
  if (sa.size === 0 || sb.size === 0) return 0
  let common = 0
  sa.forEach((w) => { if (sb.has(w)) common++ })
  return common / Math.max(sa.size, sb.size)
}

function findInDataset(query: string, items: DatasetItem[]): DatasetItem | null {
  const q = query.toLowerCase().trim()
  // Tier 1: exact match
  for (const item of items) {
    const text = extractItemText(item.input_data, ['question', 'text', 'input', 'prompt']).toLowerCase().trim()
    if (q === text) return item
  }
  // Tier 2: one is a substring of the other (only for non-trivial queries)
  if (q.split(/\s+/).length > 3) {
    for (const item of items) {
      const text = extractItemText(item.input_data, ['question', 'text', 'input', 'prompt']).toLowerCase().trim()
      if (text.includes(q) || q.includes(text)) return item
    }
  }
  // Tier 3: meaningful-word overlap >= 60% with at least 1 matching keyword
  const qWords = meaningfulWords(q)
  if (qWords.size === 0) return null   // purely stop-word query — no match
  let best: DatasetItem | null = null
  let bestScore = 0.6 // raised threshold
  for (const item of items) {
    const text = extractItemText(item.input_data, ['question', 'text', 'input', 'prompt'])
    const score = wordOverlap(q, text)
    if (score > bestScore) { bestScore = score; best = item }
  }
  return best
}

function extractAnswerText(val: unknown): string {
  return extractItemText(val, ['answer', 'text', 'output', 'content', 'response'])
}

function itemLabel(item: DatasetItem): string {
  const q = extractItemText(item.input_data, ['question', 'text', 'input', 'prompt'])
  return q ? q.slice(0, 60) + (q.length > 60 ? '...' : '') : item.id.slice(0, 8)
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHAT_MODELS = [
  'ollama-llama3',
  'ollama-llama2',
  'gpt-4',
  'gpt-3.5-turbo',
  'claude-3-opus-20240229',
  'claude-3-sonnet-20240229',
  'gemini-pro',
]

const METRIC_PROMPTS: Record<string, string> = {
  Correctness: `You are an impartial judge evaluating an AI assistant's factual accuracy.

Question: {input}
Answer: {output}

Rate the factual correctness of the answer on a scale from 0 to 1.
- 1.0 = completely accurate, no errors
- 0.5 = partially correct, minor errors or omissions
- 0.0 = factually wrong or completely off-topic

Respond with EXACTLY:
SCORE: [number between 0 and 1]
EXPLANATION: [one or two sentences explaining your reasoning]`,

  Relevance: `You are an impartial judge evaluating an AI assistant's response relevance.

Question: {input}
Answer: {output}

Rate how relevant and on-topic the answer is to the question on a scale from 0 to 1.
- 1.0 = directly answers the question with no off-topic content
- 0.5 = partially relevant, goes off-topic or misses part of the question
- 0.0 = entirely irrelevant, does not address the question

Respond with EXACTLY:
SCORE: [number between 0 and 1]
EXPLANATION: [one or two sentences explaining your reasoning]`,

  Clarity: `You are an impartial judge evaluating an AI assistant's communication clarity.

Question: {input}
Answer: {output}

Rate how clear, readable, and well-structured the answer is on a scale from 0 to 1.
- 1.0 = extremely clear, easy to understand, well-organized
- 0.5 = somewhat clear but could be improved in structure or phrasing
- 0.0 = confusing, hard to parse, or poorly written

Respond with EXACTLY:
SCORE: [number between 0 and 1]
EXPLANATION: [one or two sentences explaining your reasoning]`,
}

const METRICS = Object.keys(METRIC_PROMPTS)

function scoreColour(score: number) {
  if (score >= 0.7) return 'text-green-600'
  if (score >= 0.4) return 'text-yellow-600'
  return 'text-red-500'
}

function scoreBg(score: number) {
  if (score >= 0.7) return 'bg-green-50 border-green-200'
  if (score >= 0.4) return 'bg-yellow-50 border-yellow-200'
  return 'bg-red-50 border-red-200'
}

function traceLabel(t: Trace): string {
  const short = t.id.slice(0, 8)
  const input = t.input_data as Record<string, unknown> | null
  const question =
    (input?.question as string) ||
    (input?.messages as { content: string }[])?.[0]?.content ||
    JSON.stringify(input)
  return `#${short} — ${String(question).slice(0, 60)}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function PlaygroundPage() {
  const { project } = useProject()
  const [tab, setTab] = useState<'chat' | 'eval'>('chat')

  // ── Chat state ────────────────────────────────────────────────────────────
  const [model, setModel] = useState('ollama-llama3')

  const { data: ollamaModelsData } = useQuery({
    queryKey: ['gateway-models'],
    queryFn: () => api.gatewayModels.list(),
    staleTime: 30_000,
  })
  const ollamaModels: string[] = ollamaModelsData?.models ?? []
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [system, setSystem] = useState('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatLoading, setChatLoading] = useState(false)
  const [lastMeta, setLastMeta] = useState<{
    model: string
    tokens: number
    prompt_tokens: number
    completion_tokens: number
    cost: number
    latency: number
  } | null>(null)
  const [lastTraceId, setLastTraceId] = useState<string | null>(null)

  // ── Eval state ────────────────────────────────────────────────────────────
  const [selectedTraceId, setSelectedTraceId] = useState<string>('')
  const [metric, setMetric] = useState<string>('Correctness')
  const [promptText, setPromptText] = useState<string>(METRIC_PROMPTS['Correctness'])
  const [evalModel, setEvalModel] = useState('llama3')
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalResult, setEvalResult] = useState<{
    score: number
    explanation: string
    trace_input: unknown
    trace_output: unknown
    latency_ms: number
  } | null>(null)

  // ── Dataset state (shared between tabs) ──────────────────────────────────
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('')
  const [evalSourceMode, setEvalSourceMode] = useState<'trace' | 'dataset'>('trace')
  const [selectedDatasetItemId, setSelectedDatasetItemId] = useState<string>('')

  const { data: datasets = [] } = useQuery<Dataset[]>({
    queryKey: ['datasets', project?.id],
    queryFn: () => api.datasets.list(project!.id),
    enabled: !!project,
  })

  const { data: datasetItems = [] } = useQuery<DatasetItem[]>({
    queryKey: ['dataset-items', selectedDatasetId],
    queryFn: () => api.datasets.items(selectedDatasetId),
    enabled: !!selectedDatasetId,
  })

  const { data: traces = [] } = useQuery<Trace[]>({
    queryKey: ['traces', project?.id],
    queryFn: () => api.traces.list({ project_id: project!.id, limit: 50 }),
    enabled: !!project,
  })

  const { data: pgMetrics = [] } = useQuery<Metric[]>({
    queryKey: ['metrics', project?.id],
    queryFn: () => api.metrics.list(project?.id),
    enabled: !!project,
  })

  const selectedMetricObj = pgMetrics.find((m) => m.name === metric)

  async function sendChat() {
    if (!input.trim() || !project) return
    const userMsg: ChatMessage = { role: 'user', content: input.trim() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setChatLoading(true)

    // ── Dataset-grounded LLM mode ─────────────────────────────────────────
    if (selectedDatasetId && datasetItems.length > 0) {
      const matched = findInDataset(userMsg.content, datasetItems)
      if (!matched) {
        setMessages((prev) => [...prev, { role: 'assistant', content: 'There is no answer in the dataset.' }])
        setLastMeta(null)
        setChatLoading(false)
        return
      }
      // Build context from matched item and call LLM
      const inputText = extractItemText(matched.input_data, ['question', 'text', 'input', 'prompt'])
      const outputText = extractAnswerText(matched.expected_output) || JSON.stringify(matched.expected_output)
      const datasetContext = `You are answering based solely on the following dataset entry.\n\nDataset entry:\nInput: ${inputText}\nExpected output: ${outputText}\n\nAnswer the user's question using only the information above. Do not add information from outside this context.`
      try {
        const res = await api.gateway.complete({
          project_id: project.id,
          model,
          messages: [
            { role: 'system' as const, content: datasetContext },
            ...newMessages,
          ],
          temperature,
          max_tokens: maxTokens,
        })
        setMessages((prev) => [...prev, { role: 'assistant', content: res.content }])
        setLastMeta({ model: res.model, tokens: res.total_tokens, prompt_tokens: res.prompt_tokens, completion_tokens: res.completion_tokens, cost: res.cost_usd, latency: res.latency_ms })
        if (res.trace_id) setLastTraceId(res.trace_id)
      } catch (e: unknown) {
        toast.error(e instanceof Error ? e.message : 'Request failed')
      } finally {
        setChatLoading(false)
      }
      return
    }

    // ── Normal LLM mode ───────────────────────────────────────────────────
    try {
      const res = await api.gateway.complete({
        project_id: project.id,
        model,
        messages: [
          ...(system ? [{ role: 'system' as const, content: system }] : []),
          ...newMessages,
        ],
        temperature,
        max_tokens: maxTokens,
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: res.content }])
      setLastMeta({ model: res.model, tokens: res.total_tokens, prompt_tokens: res.prompt_tokens, completion_tokens: res.completion_tokens, cost: res.cost_usd, latency: res.latency_ms })
      if (res.trace_id) setLastTraceId(res.trace_id)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setChatLoading(false)
    }
  }

  function switchToEval() {
    if (lastTraceId) setSelectedTraceId(lastTraceId)
    setTab('eval')
  }

  async function runEval() {
    setEvalLoading(true)
    setEvalResult(null)
    const mt = selectedMetricObj?.metric_type ?? 'llm_judge'
    const isLlm = mt === 'llm_judge' || mt === 'ollama'

    try {
      if (evalSourceMode === 'dataset') {
        if (!selectedDatasetItemId) { toast.error('Select a dataset item'); setEvalLoading(false); return }
        if (isLlm) {
          if (!promptText.trim()) { toast.error('Prompt template is empty'); setEvalLoading(false); return }
          const res = await api.evals.quickDatasetItem({
            dataset_item_id: selectedDatasetItemId,
            metric_name: metric,
            model: evalModel,
            prompt_template: promptText,
          })
          setEvalResult({ score: res.score, explanation: res.explanation, trace_input: res.trace_input, trace_output: res.trace_output, latency_ms: res.latency_ms })
        } else {
          const item = datasetItems.find((i) => i.id === selectedDatasetItemId)
          if (!item) { toast.error('Item not found'); setEvalLoading(false); return }
          const res = await api.metrics.test({
            metric_type: mt,
            config: (selectedMetricObj?.config ?? {}) as Record<string, unknown>,
            input: item.input_data,
            output: item.expected_output,
            expected: item.expected_output,
          })
          setEvalResult({ score: res.score, explanation: res.explanation, trace_input: item.input_data, trace_output: item.expected_output, latency_ms: res.latency_ms })
        }
      } else {
        if (!selectedTraceId) { toast.error('Select a trace first'); setEvalLoading(false); return }
        if (isLlm) {
          if (!promptText.trim()) { toast.error('Prompt template is empty'); setEvalLoading(false); return }
          const res = await api.evals.quick({
            trace_id: selectedTraceId,
            metric_name: metric,
            model: evalModel,
            prompt_template: promptText,
          })
          setEvalResult(res)
        } else {
          const t = traces.find((x) => x.id === selectedTraceId)
          if (!t) { toast.error('Trace not found'); setEvalLoading(false); return }
          const res = await api.metrics.test({
            metric_type: mt,
            config: (selectedMetricObj?.config ?? {}) as Record<string, unknown>,
            input: t.input_data,
            output: t.output_data,
            expected: null,
          })
          setEvalResult({ score: res.score, explanation: res.explanation, trace_input: t.input_data, trace_output: t.output_data, latency_ms: res.latency_ms })
        }
      }
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Eval failed')
    } finally {
      setEvalLoading(false)
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
    <div className="space-y-4 h-[calc(100vh-6rem)] flex flex-col">
      {/* Tab toggle */}
      <div className="flex items-center gap-1 bg-muted rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('chat')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === 'chat' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          Chat
        </button>
        <button
          onClick={switchToEval}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === 'eval' ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          <FlaskConical className="h-3.5 w-3.5" />
          Eval
          {lastTraceId && tab === 'chat' && (
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" title="New trace ready to evaluate" />
          )}
        </button>
      </div>

      {/* ── CHAT TAB ── */}
      {tab === 'chat' && (
        <div className="flex gap-5 flex-1 min-h-0">
          <div className="w-64 shrink-0 space-y-4 overflow-y-auto">
            <h1 className="text-xl font-semibold">Playground</h1>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Model</label>
                <input
                  list="pg-models-list"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="ollama-llama3:8b"
                  className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <datalist id="pg-models-list">
                  {CHAT_MODELS.map((m) => <option key={m} value={m} />)}
                  {(ollamaModels ?? []).map((m: string) => {
                    const key = `ollama-${m}`
                    return <option key={key} value={key} label={m} />
                  })}
                </datalist>
                <p className="text-[10px] text-muted-foreground mt-1">
                  Type any model, e.g. <span className="font-mono">ollama-mistral:latest</span>
                </p>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Temperature: {temperature}</label>
                <input type="range" min={0} max={2} step={0.1} value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-primary" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Max Tokens</label>
                <input type="number" value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value) || 1024)}
                  className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">System prompt</label>
                <textarea value={system} onChange={(e) => setSystem(e.target.value)}
                  placeholder="You are a helpful assistant…" rows={4}
                  className="w-full text-sm px-2 py-1.5 border rounded-md bg-background resize-none focus:outline-none focus:ring-1 focus:ring-ring font-mono" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1 flex items-center gap-1">
                  <Database className="h-3 w-3" /> Dataset <span className="text-muted-foreground/60">(optional)</span>
                </label>
                <select value={selectedDatasetId} onChange={(e) => { setSelectedDatasetId(e.target.value) }}
                  className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                  <option value="">-- Free chat (LLM answers) --</option>
                  {datasets.map((ds) => <option key={ds.id} value={ds.id}>{ds.name}</option>)}
                </select>
                {selectedDatasetId && (
                  <p className="text-[10px] text-primary mt-1">Dataset mode: answers from dataset only</p>
                )}
              </div>
              <button onClick={() => { setMessages([]); setLastMeta(null); setLastTraceId(null) }}
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <Trash2 className="h-3.5 w-3.5" />
                Clear conversation
              </button>
            </div>
            {lastMeta && (
              <div className="rounded-lg border p-3 text-xs space-y-2 text-muted-foreground">
                <p className="font-medium text-foreground text-[11px] uppercase tracking-wide">Trace Parameters</p>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                  <span>Model</span><span className="text-foreground font-mono truncate" title={lastMeta.model}>{lastMeta.model}</span>
                  <span>Temperature</span><span className="text-foreground">{temperature}</span>
                  <span>Max Tokens</span><span className="text-foreground">{maxTokens.toLocaleString()}</span>
                  <span>Prompt Tokens</span><span className="text-foreground">{lastMeta.prompt_tokens?.toLocaleString() ?? '—'}</span>
                  <span>Completion Tokens</span><span className="text-foreground">{lastMeta.completion_tokens?.toLocaleString() ?? '—'}</span>
                  <span>Total Tokens</span><span className="text-foreground">{lastMeta.tokens?.toLocaleString() ?? '—'}</span>
                  <span>Cost</span><span className="text-foreground">{lastMeta.cost != null ? formatCost(lastMeta.cost) : '—'}</span>
                  <span>Latency</span><span className="text-foreground">{formatMs(lastMeta.latency)}</span>
                  <span>Status</span><span className="text-green-600">success</span>
                  <span>Environment</span><span className="text-foreground">playground</span>
                </div>
                {lastTraceId && (
                  <p className="font-mono text-[10px] text-muted-foreground/60 truncate pt-0.5" title={lastTraceId}>ID: {lastTraceId}</p>
                )}
              </div>
            )}
            {lastTraceId && (
              <button onClick={switchToEval}
                className="w-full flex items-center justify-center gap-1.5 text-xs px-3 py-2 border border-primary/40 text-primary rounded-md hover:bg-primary/5 transition-colors">
                <FlaskConical className="h-3.5 w-3.5" />
                Evaluate last response
              </button>
            )}
          </div>

          <div className="flex-1 flex flex-col border rounded-xl bg-card overflow-hidden">
            <div className="flex-1 overflow-auto p-4 space-y-3">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm gap-2">
                  <p>Send a message to start</p>
                  <p className="text-xs opacity-60">Try: &ldquo;Who commanded Allied forces in WWII?&rdquo;</p>
                </div>
              ) : (
                messages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[70%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                      m.role === 'user'
                        ? 'bg-primary text-primary-foreground rounded-br-sm'
                        : 'bg-muted rounded-bl-sm'
                    }`}>
                      {m.content}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-2.5 flex gap-1 items-center">
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              )}
            </div>
            <div className="border-t p-3 flex gap-2">
              <textarea value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat() } }}
                placeholder="Type a message… (Enter to send, Shift+Enter for newline)" rows={2}
                className="flex-1 text-sm px-3 py-2 border rounded-lg bg-background resize-none focus:outline-none focus:ring-1 focus:ring-ring" />
              <button onClick={sendChat} disabled={!input.trim() || chatLoading}
                className="self-end px-3 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── EVAL TAB ── */}
      {tab === 'eval' && (
        <div className="flex gap-5 flex-1 min-h-0">
          {/* Left config */}
          <div className="w-72 shrink-0 space-y-4 overflow-y-auto">
            <h1 className="text-xl font-semibold">LLM-as-Judge Eval</h1>

            {/* Eval Source toggle */}
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Eval Source</label>
              <div className="flex gap-1 bg-muted rounded-lg p-0.5">
                <button onClick={() => setEvalSourceMode('trace')}
                  className={`flex-1 text-xs py-1.5 rounded-md transition-colors ${evalSourceMode === 'trace' ? 'bg-background shadow font-medium' : 'text-muted-foreground hover:text-foreground'}`}>
                  From Trace
                </button>
                <button onClick={() => setEvalSourceMode('dataset')}
                  className={`flex-1 flex items-center justify-center gap-1 text-xs py-1.5 rounded-md transition-colors ${evalSourceMode === 'dataset' ? 'bg-background shadow font-medium' : 'text-muted-foreground hover:text-foreground'}`}>
                  <Database className="h-3 w-3" /> Dataset
                </button>
              </div>
            </div>

            {/* Trace picker */}
            {evalSourceMode === 'trace' && (
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Trace</label>
                <select value={selectedTraceId} onChange={(e) => setSelectedTraceId(e.target.value)}
                  className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                  <option value="">-- select a trace --</option>
                  {traces.map((t) => (
                    <option key={t.id} value={t.id}>{traceLabel(t)}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Dataset + item picker */}
            {evalSourceMode === 'dataset' && (
              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">Dataset</label>
                  <select value={selectedDatasetId} onChange={(e) => { setSelectedDatasetId(e.target.value); setSelectedDatasetItemId('') }}
                    className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                    <option value="">-- select a dataset --</option>
                    {datasets.map((ds) => <option key={ds.id} value={ds.id}>{ds.name}</option>)}
                  </select>
                </div>
                {selectedDatasetId && (
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">Item</label>
                    <select value={selectedDatasetItemId} onChange={(e) => setSelectedDatasetItemId(e.target.value)}
                      className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                      <option value="">-- select an item --</option>
                      {datasetItems.map((item) => (
                        <option key={item.id} value={item.id}>{itemLabel(item)}</option>
                      ))}
                    </select>
                  </div>
                )}
                {selectedDatasetItemId && (() => {
                  const item = datasetItems.find((i) => i.id === selectedDatasetItemId)
                  if (!item) return null
                  return (
                    <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-2">
                      <div>
                        <p className="font-medium mb-0.5">Input</p>
                        <p className="text-muted-foreground line-clamp-3">{extractItemText(item.input_data, ['question', 'text', 'input', 'prompt'])}</p>
                      </div>
                      <div>
                        <p className="font-medium mb-0.5">Expected Output</p>
                        <p className="text-muted-foreground line-clamp-3">{extractAnswerText(item.expected_output)}</p>
                      </div>
                    </div>
                  )
                })()}
              </div>
            )}

            {/* Trace detail preview (unchanged, trace mode only) */}
            {evalSourceMode === 'trace' && selectedTraceId && (() => {
              const t = traces.find((x) => x.id === selectedTraceId)
              if (!t) return null
              const inp = t.input_data as Record<string, unknown> | null
              const out = t.output_data as Record<string, unknown> | null
              const q = (inp?.question as string) || JSON.stringify(inp)
              const a = (out?.answer as string) || JSON.stringify(out)
              return (
                <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-3">
                  <div>
                    <p className="font-medium mb-0.5">Input</p>
                    <p className="text-muted-foreground line-clamp-3">{q}</p>
                  </div>
                  <div>
                    <p className="font-medium mb-0.5">Output</p>
                    <p className="text-muted-foreground line-clamp-3">{a}</p>
                  </div>
                  <div className="border-t pt-2 space-y-1.5">
                    <p className="font-medium text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Trace Parameters</p>
                    <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                      <span className="text-muted-foreground">Model</span>
                      <span className="font-mono truncate" title={t.model ?? ''}>{t.model ?? '—'}</span>
                      <span className="text-muted-foreground">Status</span>
                      <span className={t.status === 'success' ? 'text-green-600' : 'text-red-500'}>{t.status}</span>
                      <span className="text-muted-foreground">Environment</span>
                      <span>{t.environment ?? '—'}</span>
                      <span className="text-muted-foreground">Prompt Tokens</span>
                      <span>{t.prompt_tokens?.toLocaleString() ?? '—'}</span>
                      <span className="text-muted-foreground">Completion Tokens</span>
                      <span>{t.completion_tokens?.toLocaleString() ?? '—'}</span>
                      <span className="text-muted-foreground">Total Tokens</span>
                      <span>{t.total_tokens?.toLocaleString() ?? '—'}</span>
                      <span className="text-muted-foreground">Latency</span>
                      <span>{t.latency_ms != null ? formatMs(t.latency_ms) : '—'}</span>
                      <span className="text-muted-foreground">Cost</span>
                      <span>{t.cost_usd != null ? formatCost(t.cost_usd) : '—'}</span>
                    </div>
                    {t.tags && t.tags.length > 0 && (
                      <div className="flex gap-1 flex-wrap pt-0.5">
                        <span className="text-muted-foreground">Tags</span>
                        {t.tags.map((tag) => (
                          <span key={tag} className="px-1.5 py-0.5 bg-primary/10 text-primary rounded text-[10px]">{tag}</span>
                        ))}
                      </div>
                    )}
                    {t.timestamp && (
                      <p className="text-muted-foreground/60 text-[10px] pt-0.5">{new Date(t.timestamp).toLocaleString()}</p>
                    )}
                    <p className="font-mono text-[10px] text-muted-foreground/50 truncate" title={t.id}>ID: {t.id}</p>
                  </div>
                </div>
              )
            })()}

            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Metric</label>
              <select value={metric}
                onChange={(e) => {
                  const name = e.target.value
                  setMetric(name)
                  const dbM = pgMetrics.find((m) => m.name === name)
                  if (!dbM || dbM.metric_type === 'llm_judge' || dbM.metric_type === 'ollama') {
                    setPromptText(METRIC_PROMPTS[name] ?? (dbM?.prompt_template ?? ''))
                  }
                }}
                className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                {pgMetrics.length > 0
                  ? pgMetrics.map((m) => <option key={m.id} value={m.name}>{m.name}{!m.is_builtin ? ' (custom)' : ''}</option>)
                  : METRICS.map((m) => <option key={m}>{m}</option>)
                }
              </select>
              {selectedMetricObj && selectedMetricObj.metric_type !== 'llm_judge' && selectedMetricObj.metric_type !== 'ollama' && (
                <p className="text-[10px] text-blue-600 mt-1 capitalize">{selectedMetricObj.metric_type} metric — no prompt needed</p>
              )}
            </div>

            {(!selectedMetricObj || selectedMetricObj.metric_type === 'llm_judge' || selectedMetricObj.metric_type === 'ollama') && (
              <>
                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">
                    Prompt template <span className="text-muted-foreground/60">(editable)</span>
                  </label>
                  <textarea value={promptText} onChange={(e) => setPromptText(e.target.value)} rows={10}
                    className="w-full text-xs px-2 py-1.5 border rounded-md bg-background resize-y focus:outline-none focus:ring-1 focus:ring-ring font-mono" />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">Ollama model</label>
                  <input value={evalModel} onChange={(e) => setEvalModel(e.target.value)} placeholder="llama3"
                    className="w-full text-sm px-2 py-1.5 border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
              </>
            )}

            {selectedMetricObj && selectedMetricObj.metric_type !== 'llm_judge' && selectedMetricObj.metric_type !== 'ollama' && (
              <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-2">
                <p className="font-medium">Metric Config</p>
                <pre className="font-mono text-[11px] whitespace-pre-wrap">{JSON.stringify(selectedMetricObj.config ?? {}, null, 2)}</pre>
              </div>
            )}

            <button onClick={runEval} disabled={evalLoading || (evalSourceMode === 'trace' && !selectedTraceId) || (evalSourceMode === 'dataset' && !selectedDatasetItemId)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50 transition-colors">
              {evalLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
              {evalLoading ? 'Running…' : 'Run Eval'}
            </button>
          </div>

          {/* Right result */}
          <div className="flex-1 flex flex-col border rounded-xl bg-card overflow-auto p-6">
            {!evalResult && !evalLoading && (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                <FlaskConical className="h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm">Select a trace and metric, then click <strong>Run Eval</strong></p>
              </div>
            )}
            {evalLoading && (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm">Asking {evalModel} to judge…</p>
              </div>
            )}
            {evalResult && !evalLoading && (
              <div className="space-y-5">
                <div className={`rounded-xl border p-6 text-center ${scoreBg(evalResult.score)}`}>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">{metric} score</p>
                  <p className={`text-6xl font-bold ${scoreColour(evalResult.score)}`}>
                    {Math.round(evalResult.score * 100)}%
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    {evalResult.score.toFixed(3)} · {formatMs(evalResult.latency_ms)} · {evalModel}
                  </p>
                </div>
                <div className="rounded-xl border bg-muted/30 p-4">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Explanation</p>
                  <p className="text-sm">{evalResult.explanation}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border p-3 text-xs">
                    <p className="font-medium mb-1">Input</p>
                    <p className="text-muted-foreground whitespace-pre-wrap line-clamp-6">
                      {JSON.stringify(evalResult.trace_input, null, 2)}
                    </p>
                  </div>
                  <div className="rounded-lg border p-3 text-xs">
                    <p className="font-medium mb-1">Output</p>
                    <p className="text-muted-foreground whitespace-pre-wrap line-clamp-6">
                      {JSON.stringify(evalResult.trace_output, null, 2)}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

