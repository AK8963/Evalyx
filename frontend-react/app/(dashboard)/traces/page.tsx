'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatMs, formatCost, formatDate, statusBadgeVariant } from '@/lib/utils'
import {
  Search, RefreshCw, Copy, Check, Clock, Hash, DollarSign,
  ChevronDown, ChevronRight, Database, MessageSquare, Pencil, X,
  ThumbsUp, ThumbsDown, Send, Star,
  Layers, GitCompare, CheckSquare, Square,
} from 'lucide-react'
import type { Trace, Session } from '@/types'

// ─────────────────────────────────────────────────────────────────────────────
// Shared primitives
// ─────────────────────────────────────────────────────────────────────────────

function Badge({ variant, children }: { variant: string; children: React.ReactNode }) {
  const cls: Record<string, string> = {
    default: 'bg-green-100 text-green-700',
    destructive: 'bg-red-100 text-red-700',
    outline: 'bg-yellow-100 text-yellow-700',
    secondary: 'bg-muted text-muted-foreground',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls[variant] ?? cls.secondary}`}>
      {children}
    </span>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="text-muted-foreground hover:text-foreground transition-colors"
      title="Copy"
    >
      {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Score badge — shown in the trace header (like Braintrust)
// ─────────────────────────────────────────────────────────────────────────────

function ScoreBadge({ name, value }: { name: string; value: number }) {
  const pct = Math.round(value * 100)
  const color =
    pct >= 80 ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
    : pct >= 50 ? 'bg-amber-100 text-amber-800 border-amber-300'
    : 'bg-red-100 text-red-800 border-red-300'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${color}`}>
      <span className="text-muted-foreground font-normal">{name}:</span>
      <span>{pct}%</span>
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Metadata tree renderer (recursive)
// ─────────────────────────────────────────────────────────────────────────────

function MetaValue({ val, depth = 0 }: { val: unknown; depth?: number }) {
  const [open, setOpen] = useState(depth < 2)
  if (val === null || val === undefined) return <span className="text-muted-foreground italic">null</span>
  if (typeof val === 'boolean') return <span className="text-blue-600">{String(val)}</span>
  if (typeof val === 'number') return <span className="text-blue-600">{val}</span>
  if (typeof val === 'string') return <span className="text-emerald-700 break-all">"{val}"</span>
  if (Array.isArray(val)) {
    if (val.length === 0) return <span className="text-muted-foreground">[]</span>
    return (
      <span>
        <button onClick={() => setOpen(o => !o)} className="text-muted-foreground hover:text-foreground">
          {open ? <ChevronDown className="inline h-3 w-3" /> : <ChevronRight className="inline h-3 w-3" />}
          <span className="ml-0.5">{val.length} items</span>
        </button>
        {open && (
          <div className="ml-4 border-l pl-2 mt-0.5 space-y-0.5">
            {val.map((item, i) => (
              <div key={i} className="flex gap-1 text-xs">
                <span className="text-muted-foreground shrink-0">[{i}]</span>
                <MetaValue val={item} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </span>
    )
  }
  if (typeof val === 'object') {
    const keys = Object.keys(val as Record<string, unknown>)
    if (keys.length === 0) return <span className="text-muted-foreground">{'{}'}</span>
    return (
      <span>
        <button onClick={() => setOpen(o => !o)} className="text-muted-foreground hover:text-foreground">
          {open ? <ChevronDown className="inline h-3 w-3" /> : <ChevronRight className="inline h-3 w-3" />}
          <span className="ml-0.5">{keys.length} items</span>
        </button>
        {open && (
          <div className="ml-4 border-l pl-2 mt-0.5 space-y-0.5">
            {keys.map((k) => (
              <div key={k} className="flex gap-1.5 text-xs">
                <span className="text-muted-foreground shrink-0 font-medium">{k}:</span>
                <MetaValue val={(val as Record<string, unknown>)[k]} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </span>
    )
  }
  return <span>{String(val)}</span>
}

function MetadataTree({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="space-y-1 text-xs">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="flex gap-1.5">
          <span className="text-muted-foreground font-medium shrink-0">{k}:</span>
          <MetaValue val={v} depth={0} />
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Format input/output as readable text
// ─────────────────────────────────────────────────────────────────────────────

function extractText(data: Record<string, unknown> | null | undefined): string {
  if (!data) return ''
  const text = data.answer ?? data.response ?? data.output ?? data.content
  if (typeof text === 'string') return text
  const question = data.question ?? data.prompt ?? data.text ?? data.input
  if (typeof question === 'string') return question
  return ''
}

function extractMessages(data: Record<string, unknown> | null | undefined): { role: string; content: string }[] | null {
  if (!data) return null
  const msgs = data.messages
  if (Array.isArray(msgs) && msgs.length > 0) {
    return msgs.filter(m => m && typeof m === 'object').map(m => ({
      role: (m as Record<string, unknown>).role as string ?? 'unknown',
      content: (m as Record<string, unknown>).content as string ?? '',
    }))
  }
  return null
}

function InputDisplay({ data, jsonMode }: { data: Record<string, unknown>; jsonMode: boolean }) {
  if (jsonMode) {
    return (
      <pre className="text-xs bg-muted/60 rounded-lg p-3 overflow-auto max-h-72 whitespace-pre-wrap leading-relaxed font-mono">
        {JSON.stringify(data, null, 2)}
      </pre>
    )
  }
  const msgs = extractMessages(data)
  if (msgs) {
    return (
      <div className="space-y-2">
        {msgs.map((m, i) => (
          <div key={i} className={`rounded-lg px-3 py-2 text-xs leading-relaxed ${
            m.role === 'user' ? 'bg-blue-50 border border-blue-200' :
            m.role === 'assistant' ? 'bg-muted border' :
            m.role === 'system' ? 'bg-amber-50 border border-amber-200' :
            'bg-muted border'
          }`}>
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground block mb-1">{m.role}</span>
            <p className="whitespace-pre-wrap">{m.content}</p>
          </div>
        ))}
      </div>
    )
  }
  const txt = extractText(data)
  if (txt) return <p className="text-xs leading-relaxed whitespace-pre-wrap">{txt}</p>
  return (
    <pre className="text-xs bg-muted/60 rounded-lg p-3 overflow-auto max-h-72 whitespace-pre-wrap leading-relaxed font-mono">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function OutputDisplay({ data, jsonMode }: { data: Record<string, unknown>; jsonMode: boolean }) {
  if (jsonMode) {
    return (
      <pre className="text-xs bg-muted/60 rounded-lg p-3 overflow-auto max-h-72 whitespace-pre-wrap leading-relaxed font-mono">
        {JSON.stringify(data, null, 2)}
      </pre>
    )
  }
  const txt = extractText(data)
  if (txt) return <p className="text-xs leading-relaxed whitespace-pre-wrap">{txt}</p>
  return (
    <pre className="text-xs bg-muted/60 rounded-lg p-3 overflow-auto max-h-72 whitespace-pre-wrap leading-relaxed font-mono">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Preview tab
// ─────────────────────────────────────────────────────────────────────────────

function PreviewTab({ trace, jsonMode, traceSessions = [] }: { trace: Trace; jsonMode: boolean; traceSessions?: Session[] }) {
  return (
    <div className="p-4 space-y-4">
      {/* Input */}
      {trace.input_data && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Input</p>
          <InputDisplay data={trace.input_data} jsonMode={jsonMode} />
        </div>
      )}

      {/* Output */}
      {trace.output_data && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Output</p>
          <OutputDisplay data={trace.output_data} jsonMode={jsonMode} />
        </div>
      )}

      {/* Expected output */}
      {trace.expected_output && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Expected Output</p>
          <pre className="text-xs bg-amber-50 border border-amber-200 rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap leading-relaxed">
            {JSON.stringify(trace.expected_output, null, 2)}
          </pre>
        </div>
      )}

      {/* Corrected Output (Beta) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Corrected Output <span className="text-[10px] font-normal normal-case">(Beta)</span></p>
          <label className="relative inline-flex items-center cursor-pointer">
            <span className="text-[10px] text-muted-foreground mr-1">JSON</span>
            <div className="w-8 h-4 bg-muted rounded-full relative">
              <div className="absolute left-0.5 top-0.5 w-3 h-3 bg-white rounded-full shadow" />
            </div>
          </label>
        </div>
        <div className="border-2 border-dashed border-muted rounded-lg px-4 py-3 text-center text-xs text-muted-foreground hover:border-muted-foreground/40 transition-colors cursor-pointer">
          Click to add corrected output
        </div>
      </div>

      {/* Error */}
      {trace.error_message && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-red-600 mb-2">Error</p>
          <pre className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 whitespace-pre-wrap">{trace.error_message}</pre>
        </div>
      )}

      {/* Metadata + trace info — always shown */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Trace Info</p>
        <div className="border rounded-lg p-3 bg-muted/20 space-y-1.5 text-xs">
          {/* Token breakdown */}
          {(trace.prompt_tokens != null || trace.completion_tokens != null || trace.total_tokens != null) && (
            <div className="flex gap-3 pb-1.5 border-b">
              {trace.prompt_tokens != null && (
                <span><span className="text-muted-foreground">Input tokens:</span> <span className="font-medium">{trace.prompt_tokens}</span></span>
              )}
              {trace.completion_tokens != null && (
                <span><span className="text-muted-foreground">Output tokens:</span> <span className="font-medium">{trace.completion_tokens}</span></span>
              )}
              {trace.total_tokens != null && (
                <span><span className="text-muted-foreground">Total:</span> <span className="font-medium">{trace.total_tokens}</span></span>
              )}
            </div>
          )}
          {/* Core fields */}
          {[
            ['Model', trace.model],
            ['Environment', trace.environment],
            ['Status', trace.status],
            ['Temperature', trace.temperature != null ? String(trace.temperature) : null],
            ['Max Tokens', trace.max_tokens != null ? String(trace.max_tokens) : null],
            ['Cost', trace.cost_usd != null ? formatCost(trace.cost_usd) : null],
            ['Created', formatDate(trace.created_at ?? trace.timestamp)],
          ].filter(([, v]) => v != null && v !== '').map(([k, v]) => (
            <div key={k as string} className="flex gap-1.5">
              <span className="text-muted-foreground font-medium shrink-0">{k as string}:</span>
              <span>{v as string}</span>
            </div>
          ))}
          {/* Tags */}
          {trace.tags && trace.tags.length > 0 && (
            <div className="flex gap-1.5 flex-wrap items-center">
              <span className="text-muted-foreground font-medium shrink-0">Tags:</span>
              {trace.tags.map(tag => (
                <span key={tag} className="px-1.5 py-0.5 rounded bg-muted text-[10px]">{tag}</span>
              ))}
            </div>
          )}
          {/* Sessions */}
          {traceSessions.length > 0 && (
            <div className="flex gap-1.5 flex-wrap items-center">
              <span className="text-muted-foreground font-medium shrink-0">Sessions:</span>
              {traceSessions.map(s => (
                <span key={s.id} className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 text-[10px] font-medium">
                  {s.name}
                </span>
              ))}
            </div>
          )}
          {/* Spans count */}
          {trace.spans && trace.spans.length > 0 && (
            <div className="flex gap-1.5">
              <span className="text-muted-foreground font-medium">Spans:</span>
              <span>{trace.spans.length} recorded</span>
            </div>
          )}
          {/* Custom metadata */}
          {trace.metadata && Object.keys(trace.metadata).length > 0 && (
            <div className="pt-1.5 border-t">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Custom Metadata</p>
              <MetadataTree data={trace.metadata} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Span Tree tab — Braintrust-style hierarchical span view
// ─────────────────────────────────────────────────────────────────────────────

function fmtMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${Math.round(ms)}ms`
}

function latencyColor(ms: number): string {
  if (ms > 30000) return 'text-red-500'
  if (ms > 10000) return 'text-amber-500'
  return 'text-foreground'
}

function SpanTreeTab({ trace }: { trace: Trace }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const scores = trace.scores ?? []
  const totalMs = trace.latency_ms ?? 0
  const llmMs = Math.round(totalMs * 0.92)
  const hasTokens = !!(trace.prompt_tokens || trace.completion_tokens)

  function toggle(id: string) {
    setCollapsed(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const rootOpen = !collapsed.has('root')
  const llmOpen = !collapsed.has('llm')

  // Build real child spans if available
  const realSpans = trace.spans && trace.spans.length > 0 ? trace.spans : null

  return (
    <div className="h-full overflow-auto p-3 text-xs">
      {/* ── Root span ── */}
      <div>
        <button
          className="w-full flex items-center gap-1.5 hover:bg-muted/30 rounded px-1 py-1.5 text-left"
          onClick={() => toggle('root')}
        >
          {rootOpen
            ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
            : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />}
          <span className="text-sky-500 shrink-0">↔</span>
          <span className="font-semibold font-mono truncate">{trace.id.slice(0, 8)}…</span>
          {trace.environment && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 ml-1 shrink-0">
              {trace.environment}
            </span>
          )}
          <span className={`ml-auto font-bold shrink-0 font-mono ${latencyColor(totalMs)}`}>
            {fmtMs(totalMs)}
          </span>
        </button>

        {/* Score badges directly under root */}
        {rootOpen && scores.length > 0 && (
          <div className="flex flex-wrap gap-1 ml-6 my-1.5">
            {scores.map(s => (
              <ScoreBadge key={s.id} name={s.scorer_name ?? s.scorer_type} value={s.score_value} />
            ))}
          </div>
        )}

        {/* Children */}
        {rootOpen && (
          <div className="ml-4 border-l border-muted pl-2 mt-1 space-y-0.5">
            {realSpans ? (
              /* Real spans from backend */
              realSpans.map((sp, i) => {
                const spName = sp.name ?? `Span ${i + 1}`
                const spMs = sp.duration_ms ?? 0
                const isLlm = spName.toLowerCase().includes('gen') || spName.toLowerCase().includes('llm')
                const spId = `span-${i}`
                const spOpen = !collapsed.has(spId)
                return (
                  <div key={spId}>
                    <button
                      className="w-full flex items-center gap-1.5 hover:bg-muted/30 rounded px-1 py-1.5 text-left"
                      onClick={() => toggle(spId)}
                    >
                      {spOpen
                        ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
                        : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />}
                      <span className={`shrink-0 ${isLlm ? 'text-pink-500' : 'text-sky-500'}`}>
                        {isLlm ? '⚡' : '↔'}
                      </span>
                      <span className="font-mono truncate">{spName}</span>
                      <span className={`ml-auto font-bold shrink-0 font-mono ${latencyColor(spMs)}`}>
                        {fmtMs(spMs)}
                      </span>
                    </button>
                    {spOpen && sp.attributes && (
                      <div className="ml-4 border-l border-muted pl-2 py-1 text-[10px] text-muted-foreground space-y-0.5 px-1">
                        {Object.entries(sp.attributes)
                          .filter(([, v]) => v !== null && v !== undefined)
                          .map(([k, v]) => (
                            <div key={k} className="flex gap-1">
                              <span className="font-medium">{k}:</span>
                              <span>{String(v)}</span>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                )
              })
            ) : (
              /* Synthesized LLM span */
              <div>
                <button
                  className="w-full flex items-center gap-1.5 hover:bg-muted/30 rounded px-1 py-1.5 text-left"
                  onClick={() => toggle('llm')}
                >
                  {llmOpen
                    ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
                    : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />}
                  <span className="text-pink-500 shrink-0">⚡</span>
                  <span className="font-mono truncate">LLM Generation</span>
                  {trace.model && (
                    <span className="text-muted-foreground ml-1 truncate max-w-[100px]">({trace.model})</span>
                  )}
                  <span className={`ml-auto font-bold shrink-0 font-mono ${latencyColor(llmMs)}`}>
                    {fmtMs(llmMs)}
                  </span>
                  {hasTokens && (
                    <span className="text-muted-foreground ml-3 shrink-0 font-mono">
                      {trace.prompt_tokens ?? 0} → {trace.completion_tokens ?? 0} (Σ {trace.total_tokens ?? 0})
                    </span>
                  )}
                </button>

                {llmOpen && (
                  <div className="ml-4 border-l border-muted pl-2 py-1 space-y-1.5">
                    {/* Attributes */}
                    <div className="text-[10px] text-muted-foreground space-y-0.5 px-1">
                      {trace.model && (
                        <div className="flex gap-1"><span className="font-medium">model:</span><span>{trace.model}</span></div>
                      )}
                      {trace.status && (
                        <div className="flex gap-1"><span className="font-medium">status:</span><span>{trace.status}</span></div>
                      )}
                      {hasTokens && (
                        <>
                          <div className="flex gap-1">
                            <span className="font-medium">prompt_tokens:</span>
                            <span>{trace.prompt_tokens ?? 0}</span>
                          </div>
                          <div className="flex gap-1">
                            <span className="font-medium">completion_tokens:</span>
                            <span>{trace.completion_tokens ?? 0}</span>
                          </div>
                          <div className="flex gap-1">
                            <span className="font-medium">total_tokens:</span>
                            <span>{trace.total_tokens ?? 0}</span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* Input preview */}
                    {trace.input_data && (
                      <div className="px-1">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-0.5">Input</p>
                        <pre className="text-[10px] bg-muted/50 rounded p-1.5 overflow-auto max-h-28 whitespace-pre-wrap leading-relaxed">
                          {JSON.stringify(trace.input_data, null, 2)}
                        </pre>
                      </div>
                    )}

                    {/* Output preview */}
                    {trace.output_data && (
                      <div className="px-1">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-0.5">Output</p>
                        <pre className="text-[10px] bg-muted/50 rounded p-1.5 overflow-auto max-h-28 whitespace-pre-wrap leading-relaxed">
                          {JSON.stringify(trace.output_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main TraceDetail panel
// ─────────────────────────────────────────────────────────────────────────────

function TraceDetail({ traceId, onClose }: { traceId: string; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<'preview' | 'spantree'>('preview')
  const [jsonMode, setJsonMode] = useState(false)
  const [actionPanel, setActionPanel] = useState<'dataset' | 'annotate' | 'comment' | null>(null)
  const [commentText, setCommentText] = useState('')
  const [thumbsUp, setThumbsUp] = useState<boolean | undefined>(undefined)
  const [rating, setRating] = useState(0)
  const [annotateComment, setAnnotateComment] = useState('')
  const [actionMsg, setActionMsg] = useState<string | null>(null)
  const { project } = useProject()

  const { data: trace, isLoading } = useQuery({
    queryKey: ['trace-detail', traceId],
    queryFn: () => api.traces.get(traceId),
    staleTime: 30_000,
  })

  const { data: allSessions } = useQuery({
    queryKey: ['sessions', project?.id],
    queryFn: () => api.sessions.list(project!.id, { limit: 100 }),
    enabled: !!project,
    staleTime: 60_000,
  })
  const traceSessions = (allSessions?.items ?? []).filter(s => s.trace_ids.includes(traceId))

  const { data: datasets = [] } = useQuery({
    queryKey: ['datasets-picker', project?.id],
    queryFn: () => api.datasets.list(project!.id),
    enabled: !!project && actionPanel === 'dataset',
  })

  function flash(msg: string) {
    setActionMsg(msg)
    setTimeout(() => setActionMsg(null), 3000)
  }

  async function addToDataset(datasetId: string) {
    if (!trace) return
    try {
      await api.datasets.addItem(datasetId, {
        input_data: trace.input_data,
        expected_output: trace.expected_output ?? undefined,
      })
      setActionPanel(null)
      flash('Added to dataset!')
    } catch { flash('Failed to add to dataset') }
  }

  async function submitAnnotation() {
    if (!trace || !project) return
    try {
      await api.annotations.create({
        trace_id: trace.id,
        project_id: project.id,
        thumbs_up: thumbsUp,
        rating: rating > 0 ? rating : undefined,
        comment: annotateComment || undefined,
      })
      setActionPanel(null)
      setThumbsUp(undefined); setRating(0); setAnnotateComment('')
      flash('Annotation saved!')
    } catch { flash('Failed to save annotation') }
  }

  async function submitComment() {
    if (!trace || !project || !commentText.trim()) return
    try {
      await api.annotations.create({
        trace_id: trace.id,
        project_id: project.id,
        comment: commentText,
      })
      setCommentText('')
      setActionPanel(null)
      flash('Comment added!')
    } catch { flash('Failed to add comment') }
  }

  if (isLoading || !trace) {
    return (
      <div className="rounded-xl border bg-card flex items-center justify-center h-full">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  const scores = trace.scores ?? []
  const tokensDisplay = trace.prompt_tokens != null || trace.completion_tokens != null
    ? `${trace.prompt_tokens ?? 0} + ${trace.completion_tokens ?? 0}`
    : trace.total_tokens != null
      ? trace.total_tokens.toLocaleString()
      : '—'

  return (
    <div className="border rounded-xl bg-card overflow-hidden flex flex-col h-full">

      {/* ── Top header ── */}
      <div className="px-4 pt-3 pb-2 border-b bg-muted/20 shrink-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-mono text-[11px] text-muted-foreground truncate max-w-[220px]">{traceId}</span>
              <CopyButton text={traceId} />
            </div>
            <div className="flex items-center gap-2 flex-wrap mt-1 text-[11px] text-muted-foreground">
              <span>{formatDate(trace.timestamp ?? trace.created_at)}</span>
              {trace.environment && (
                <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">
                  Env: {trace.environment}
                </span>
              )}
              {trace.model && (
                <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">
                  {trace.model}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
            <button
              onClick={() => setActionPanel(p => p === 'dataset' ? null : 'dataset')}
              className={`flex items-center gap-1 px-2 py-1 text-[11px] border rounded transition-colors whitespace-nowrap ${actionPanel === 'dataset' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}
            >
              <Database className="h-3 w-3" />Add to datasets
            </button>
            <button
              onClick={() => setActionPanel(p => p === 'annotate' ? null : 'annotate')}
              className={`flex items-center gap-1 px-2 py-1 text-[11px] border rounded transition-colors ${actionPanel === 'annotate' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}
            >
              <Pencil className="h-3 w-3" />Annotate
            </button>
            <button
              onClick={() => setActionPanel(p => p === 'comment' ? null : 'comment')}
              className={`flex items-center gap-1 px-2 py-1 text-[11px] border rounded transition-colors whitespace-nowrap ${actionPanel === 'comment' ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}
            >
              <MessageSquare className="h-3 w-3" />Comment
            </button>
            <button
              onClick={onClose}
              className="flex items-center gap-1 px-2 py-1 text-[11px] border rounded bg-muted/30 hover:bg-red-50 hover:border-red-300 hover:text-red-600 text-muted-foreground transition-colors"
            >
              <X className="h-3 w-3" />Close
            </button>
          </div>
        </div>

        {/* Score badges */}
        {scores.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {scores.map((s) => (
              <ScoreBadge key={s.id} name={s.scorer_name ?? s.scorer_type} value={s.score_value} />
            ))}
          </div>
        )}

        {/* Status message */}
        {actionMsg && (
          <div className="mt-2 px-2 py-1 rounded bg-green-100 text-green-700 text-[11px] font-medium">
            {actionMsg}
          </div>
        )}
      </div>

      {/* ── Action panels ── */}
      {actionPanel === 'dataset' && (
        <div className="border-b bg-muted/5 px-4 py-3 shrink-0">
          <p className="text-xs font-semibold mb-2">Select a dataset to add this trace to:</p>
          {datasets.length === 0 ? (
            <p className="text-xs text-muted-foreground">No datasets found. Create one first.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {datasets.map(d => (
                <button
                  key={d.id}
                  onClick={() => addToDataset(d.id)}
                  className="px-3 py-1 text-xs border rounded hover:bg-primary hover:text-primary-foreground transition-colors"
                >
                  {d.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {actionPanel === 'annotate' && (
        <div className="border-b bg-muted/5 px-4 py-3 shrink-0 space-y-2">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold">Feedback:</span>
            <button
              onClick={() => setThumbsUp(thumbsUp === true ? undefined : true)}
              className={`p-1 rounded transition-colors ${thumbsUp === true ? 'text-green-600 bg-green-100' : 'text-muted-foreground hover:text-green-600'}`}
            >
              <ThumbsUp className="h-4 w-4" />
            </button>
            <button
              onClick={() => setThumbsUp(thumbsUp === false ? undefined : false)}
              className={`p-1 rounded transition-colors ${thumbsUp === false ? 'text-red-600 bg-red-100' : 'text-muted-foreground hover:text-red-600'}`}
            >
              <ThumbsDown className="h-4 w-4" />
            </button>
            <span className="text-xs font-semibold ml-2">Rating:</span>
            {[1,2,3,4,5].map(n => (
              <button key={n} onClick={() => setRating(rating === n ? 0 : n)}>
                <Star className={`h-4 w-4 transition-colors ${n <= rating ? 'text-amber-400 fill-amber-400' : 'text-muted-foreground'}`} />
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              className="flex-1 text-xs border rounded px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="Add a note (optional)…"
              value={annotateComment}
              onChange={e => setAnnotateComment(e.target.value)}
            />
            <button
              onClick={submitAnnotation}
              className="flex items-center gap-1 px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90"
            >
              <Send className="h-3 w-3" />Save
            </button>
          </div>
        </div>
      )}

      {actionPanel === 'comment' && (
        <div className="border-b bg-muted/5 px-4 py-3 shrink-0">
          <div className="flex gap-2">
            <textarea
              className="flex-1 text-xs border rounded px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-none"
              rows={2}
              placeholder="Add a comment…"
              value={commentText}
              onChange={e => setCommentText(e.target.value)}
            />
            <button
              onClick={submitComment}
              disabled={!commentText.trim()}
              className="flex items-center gap-1 px-3 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50 self-start"
            >
              <Send className="h-3 w-3" />Post
            </button>
          </div>
        </div>
      )}

      {/* ── Stats bar ── */}
      <div className="grid grid-cols-4 divide-x border-b bg-muted/10 shrink-0">
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <Clock className="h-3 w-3" />
            <span className="text-[10px] uppercase">Latency</span>
          </div>
          <p className="text-xs font-semibold">{formatMs(trace.latency_ms)}</p>
        </div>
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <Hash className="h-3 w-3" />
            <span className="text-[10px] uppercase">Tokens</span>
          </div>
          <p className="text-xs font-semibold">{tokensDisplay}</p>
          {trace.prompt_tokens != null && (
            <p className="text-[10px] text-muted-foreground">in + out</p>
          )}
        </div>
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <DollarSign className="h-3 w-3" />
            <span className="text-[10px] uppercase">Cost</span>
          </div>
          <p className="text-xs font-semibold">{formatCost(trace.cost_usd)}</p>
        </div>
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <span className="text-[10px] uppercase">Status</span>
          </div>
          <div className="flex justify-center">
            <Badge variant={statusBadgeVariant(trace.status)}>{trace.status}</Badge>
          </div>
        </div>
      </div>

      {/* ── Tab bar ── */}
      <div className="flex items-center px-4 border-b bg-muted/10 shrink-0">
        {(['preview', 'spantree'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab === 'spantree' ? 'Span Tree' : 'Preview'}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1 py-1">
          {(['formatted', 'json'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setJsonMode(mode === 'json')}
              className={`px-2 py-0.5 text-[11px] rounded transition-colors ${
                (mode === 'json') === jsonMode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === 'preview'
          ? <div className="h-full overflow-y-auto"><PreviewTab trace={trace} jsonMode={jsonMode} traceSessions={traceSessions} /></div>
          : <div className="h-full overflow-hidden"><SpanTreeTab trace={trace} /></div>
        }
      </div>
    </div>
  )
}



// ─────────────────────────────────────────────────────────────────────────────
// Session picker dropdown
// ─────────────────────────────────────────────────────────────────────────────

function SessionPickerDropdown({
  projectId, onPick, onClose,
}: { projectId: string; onPick: (id: string, name: string) => void; onClose: () => void }) {
  const qc = useQueryClient()
  const [newName, setNewName] = useState('')

  const { data } = useQuery({
    queryKey: ['sessions', projectId],
    queryFn: () => api.sessions.list(projectId, { limit: 50 }),
    staleTime: 30_000,
  })
  const sessions = data?.items ?? []

  const create = useMutation({
    mutationFn: () => api.sessions.create({ project_id: projectId, name: newName.trim() }),
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: ['sessions', projectId] })
      onPick(session.id, session.name)
    },
  })

  return (
    <div className="absolute top-full left-0 mt-1 z-50 w-64 bg-popover border rounded-lg shadow-lg overflow-hidden">
      <div className="p-2 border-b">
        <p className="text-xs font-semibold text-muted-foreground mb-1">Add to existing session</p>
        {sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground py-1">No sessions yet — create one below</p>
        ) : (
          <div className="space-y-0.5 max-h-40 overflow-y-auto">
            {sessions.map(s => (
              <button
                key={s.id}
                onClick={() => onPick(s.id, s.name)}
                className="w-full text-left px-2 py-1.5 text-xs rounded hover:bg-muted transition-colors flex items-center justify-between"
              >
                <span className="truncate">{s.name}</span>
                <span className="text-muted-foreground ml-1 shrink-0">{s.trace_count} traces</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="p-2">
        <p className="text-xs font-semibold text-muted-foreground mb-1">Create new session</p>
        <div className="flex gap-1">
          <input
            className="flex-1 text-xs border rounded px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Session name…"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && newName.trim()) create.mutate() }}
          />
          <button
            onClick={() => create.mutate()}
            disabled={!newName.trim() || create.isPending}
            className="px-2 py-1 text-xs bg-primary text-primary-foreground rounded disabled:opacity-50"
          >
            +
          </button>
        </div>
      </div>
      <div className="px-2 pb-2">
        <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">Cancel</button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Compare view — side-by-side columns
// ─────────────────────────────────────────────────────────────────────────────

function CompareColumn({ traceId }: { traceId: string }) {
  const { data: trace, isLoading } = useQuery({
    queryKey: ['trace-detail', traceId],
    queryFn: () => api.traces.get(traceId),
    staleTime: 30_000,
  })

  if (isLoading || !trace) {
    return (
      <div className="flex-1 min-w-[220px] p-4 text-xs text-muted-foreground">Loading…</div>
    )
  }

  return (
    <div className="flex-1 min-w-[220px] flex flex-col overflow-hidden border-r last:border-r-0">
      {/* Mini header */}
      <div className="px-3 py-2 border-b bg-muted/10 shrink-0 space-y-1.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-mono text-[10px] text-muted-foreground">{traceId.slice(0, 8)}…</span>
          <CopyButton text={traceId} />
          <Badge variant={statusBadgeVariant(trace.status)}>{trace.status}</Badge>
        </div>
        <div className="flex gap-3 text-[10px] text-muted-foreground flex-wrap">
          <span>{formatMs(trace.latency_ms)}</span>
          {trace.total_tokens != null && <span>{trace.total_tokens} tok</span>}
          {trace.model && <span className="truncate max-w-[100px]">{trace.model}</span>}
          {formatCost(trace.cost_usd) !== '—' && <span>{formatCost(trace.cost_usd)}</span>}
        </div>
        {(trace.scores ?? []).length > 0 && (
          <div className="flex flex-wrap gap-0.5">
            {(trace.scores ?? []).map(s => (
              <ScoreBadge key={s.id} name={s.scorer_name ?? s.scorer_type} value={s.score_value} />
            ))}
          </div>
        )}
      </div>
      {/* Input / Output */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {trace.input_data && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Input</p>
            <InputDisplay data={trace.input_data} jsonMode={false} />
          </div>
        )}
        {trace.output_data && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">Output</p>
            <OutputDisplay data={trace.output_data} jsonMode={false} />
          </div>
        )}
        {!trace.input_data && !trace.output_data && (
          <p className="text-xs text-muted-foreground">No input/output data</p>
        )}
      </div>
    </div>
  )
}

function ComparePanel({ traceIds, onClose }: { traceIds: string[]; onClose: () => void }) {
  const ids = traceIds.slice(0, 3)
  return (
    <div className="border rounded-xl bg-card overflow-hidden flex flex-col" style={{ maxHeight: 'calc(100vh - 200px)' }}>
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/20 shrink-0">
        <div className="flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">Comparing {ids.length} traces</h3>
          <span className="text-xs text-muted-foreground">(max 3 at a time)</span>
        </div>
        <button
          onClick={onClose}
          className="flex items-center gap-1 px-2 py-1 text-[11px] border rounded hover:bg-red-50 hover:border-red-300 hover:text-red-600 text-muted-foreground transition-colors"
        >
          <X className="h-3 w-3" />Close
        </button>
      </div>
      <div className="flex flex-1 min-h-0 overflow-auto divide-x">
        {ids.map(id => <CompareColumn key={id} traceId={id} />)}
      </div>
    </div>
  )
}

const TIME_FILTERS = [
  { label: '1h',  hours: 1 },
  { label: '3h',  hours: 3 },
  { label: '1d',  days:  1 },
  { label: '3d',  days:  3 },
  { label: '7d',  days:  7 },
  { label: 'All', hours: undefined, days: undefined },
] as const
type TimeFilter = (typeof TIME_FILTERS)[number]

export default function TracesPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Trace | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [compareMode, setCompareMode] = useState(false)
  const [showSessionPicker, setShowSessionPicker] = useState(false)
  const [sessionMsg, setSessionMsg] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [activeFilter, setActiveFilter] = useState<TimeFilter>(TIME_FILTERS[5])

  // ── Filters ──
  const [modelFilter, setModelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [envFilter, setEnvFilter] = useState('')
  const [scoresFilter, setScoresFilter] = useState('')      // '' | 'yes' | 'no'
  const [sessionFilter, setSessionFilter] = useState('')    // session id
  const [minLatency, setMinLatency] = useState('')
  const [maxLatency, setMaxLatency] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Load sessions for filter dropdown
  const { data: sessionsData } = useQuery({
    queryKey: ['sessions', project?.id],
    queryFn: () => api.sessions.list(project!.id, { limit: 100 }),
    enabled: !!project,
    staleTime: 60_000,
  })
  const sessionsList = sessionsData?.items ?? []

  const PAGE_SIZE = 25

  function resetFilters() {
    setModelFilter(''); setStatusFilter(''); setEnvFilter('')
    setScoresFilter(''); setMinLatency(''); setMaxLatency('')
    setSessionFilter('')
    setPage(0)
  }

  const activeFilterCount = [modelFilter, statusFilter, envFilter, scoresFilter, minLatency, maxLatency, sessionFilter]
    .filter(Boolean).length

  const { data: traces = [], isFetching, refetch } = useQuery({
    queryKey: ['traces', project?.id, statusFilter, modelFilter, envFilter, scoresFilter, sessionFilter, minLatency, maxLatency, page, activeFilter.label],
    queryFn: () =>
      api.traces.list({
        project_id: project!.id,
        status: statusFilter || undefined,
        model: modelFilter || undefined,
        environment: envFilter || undefined,
        has_scores: scoresFilter === 'yes' ? true : scoresFilter === 'no' ? false : undefined,
        session_id: sessionFilter || undefined,
        min_latency_ms: minLatency ? Number(minLatency) : undefined,
        max_latency_ms: maxLatency ? Number(maxLatency) : undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        hours: ('hours' in activeFilter && activeFilter.hours != null) ? activeFilter.hours : undefined,
        days:  ('days'  in activeFilter && (activeFilter as {days?: number}).days  != null) ? (activeFilter as {days?: number}).days  : undefined,
      }),
    enabled: !!project,
  })

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === traces.length && traces.length > 0) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(traces.map(t => t.id)))
    }
  }

  function clearSelection() {
    setSelectedIds(new Set())
    setCompareMode(false)
    setShowSessionPicker(false)
  }

  async function handleSessionPick(sessionId: string, sessionName: string) {
    try {
      await api.sessions.addTraces(sessionId, [...selectedIds])
      setShowSessionPicker(false)
      setSessionMsg(`Added ${selectedIds.size} trace(s) to "${sessionName}"`)
      qc.invalidateQueries({ queryKey: ['sessions', project?.id] })
      setTimeout(() => setSessionMsg(null), 4000)
    } catch {
      setSessionMsg('Failed to add to session')
      setTimeout(() => setSessionMsg(null), 3000)
    }
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project to view traces
      </div>
    )
  }

  const allPageSelected = traces.length > 0 && selectedIds.size === traces.length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Traces</h1>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Time filter pills */}
      <div className="flex gap-1.5 flex-wrap">
        {TIME_FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => { setActiveFilter(f); setPage(0) }}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              activeFilter.label === f.label
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/70'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* ── Filters ── */}
      <div className="rounded-xl border bg-card p-3 space-y-3">
        {/* Row 1: always-visible filters */}
        <div className="flex gap-2 flex-wrap items-center">
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={modelFilter}
              onChange={(e) => { setModelFilter(e.target.value); setPage(0) }}
              placeholder="Filter by model…"
              className="pl-8 pr-3 py-1.5 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring w-44"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0) }}
            className="text-sm border rounded-md px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
            <option value="pending">Pending</option>
          </select>
          <select
            value={scoresFilter}
            onChange={(e) => { setScoresFilter(e.target.value); setPage(0) }}
            className="text-sm border rounded-md px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">All scores</option>
            <option value="yes">Has scores</option>
            <option value="no">No scores</option>
          </select>
          <select
            value={sessionFilter}
            onChange={(e) => { setSessionFilter(e.target.value); setPage(0) }}
            className="text-sm border rounded-md px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring max-w-[180px]"
          >
            <option value="">All sessions</option>
            {sessionsList.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <button
            onClick={() => setShowAdvanced(v => !v)}
            className={`flex items-center gap-1 px-3 py-1.5 text-xs border rounded-md transition-colors ${showAdvanced ? 'bg-primary/10 border-primary/40 text-primary' : 'hover:bg-muted'}`}
          >
            <ChevronDown className={`h-3 w-3 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
            More filters{activeFilterCount > 0 && !showAdvanced ? ` (${activeFilterCount})` : ''}
          </button>
          {activeFilterCount > 0 && (
            <button onClick={resetFilters} className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1">
              <X className="h-3 w-3" />Clear all
            </button>
          )}
        </div>

        {/* Row 2: advanced filters */}
        {showAdvanced && (
          <div className="flex gap-2 flex-wrap items-center pt-1 border-t">
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-muted-foreground whitespace-nowrap">Environment:</label>
              <input
                value={envFilter}
                onChange={e => { setEnvFilter(e.target.value); setPage(0) }}
                placeholder="production"
                className="text-xs border rounded-md px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring w-32"
              />
            </div>
            <div className="flex items-center gap-1.5">
              <label className="text-xs text-muted-foreground whitespace-nowrap">Latency (ms):</label>
              <input
                value={minLatency}
                onChange={e => { setMinLatency(e.target.value); setPage(0) }}
                placeholder="min"
                type="number"
                className="text-xs border rounded-md px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring w-20"
              />
              <span className="text-xs text-muted-foreground">–</span>
              <input
                value={maxLatency}
                onChange={e => { setMaxLatency(e.target.value); setPage(0) }}
                placeholder="max"
                type="number"
                className="text-xs border rounded-md px-2 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring w-20"
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Selection action bar ── */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-2 rounded-lg border bg-primary/5 border-primary/20 flex-wrap">
          <span className="text-sm font-medium text-primary">{selectedIds.size} selected</span>
          <button
            onClick={() => { setCompareMode(true); setSelected(null) }}
            disabled={selectedIds.size < 2}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-40 transition-colors"
          >
            <GitCompare className="h-3.5 w-3.5" />Compare
          </button>
          <div className="relative">
            <button
              onClick={() => setShowSessionPicker(p => !p)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded transition-colors ${
                showSessionPicker ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'
              }`}
            >
              <Layers className="h-3.5 w-3.5" />Save to Session
            </button>
            {showSessionPicker && (
              <SessionPickerDropdown
                projectId={project.id}
                onPick={handleSessionPick}
                onClose={() => setShowSessionPicker(false)}
              />
            )}
          </div>
          <button
            onClick={clearSelection}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground ml-auto"
          >
            <X className="h-3.5 w-3.5" />Clear
          </button>
        </div>
      )}

      {/* Session action feedback */}
      {sessionMsg && (
        <div className={`px-4 py-2 rounded-lg border text-sm ${
          sessionMsg.startsWith('Failed')
            ? 'bg-red-50 border-red-200 text-red-700'
            : 'bg-green-50 border-green-200 text-green-700'
        }`}>
          {sessionMsg}
        </div>
      )}

      {/* ── Compare mode ── */}
      {compareMode && selectedIds.size >= 2 ? (
        <ComparePanel
          traceIds={[...selectedIds]}
          onClose={() => { setCompareMode(false); clearSelection() }}
        />
      ) : (
        /* ── Normal split view ── */
        <div className="flex gap-4 min-h-[500px]">
          {/* Table */}
          <div className={`rounded-xl border bg-card overflow-hidden ${selected ? 'flex-1' : 'w-full'}`}>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="pl-3 pr-1 py-2.5 w-8">
                    <button onClick={toggleSelectAll} className="text-muted-foreground hover:text-foreground">
                      {allPageSelected
                        ? <CheckSquare className="h-3.5 w-3.5 text-primary" />
                        : <Square className="h-3.5 w-3.5" />}
                    </button>
                  </th>
                  {['ID', 'Model', 'Status', 'Scores', 'Latency', 'Tokens', 'Cost', 'Time'].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-muted-foreground">
                      {isFetching ? 'Loading…' : 'No traces found'}
                    </td>
                  </tr>
                ) : (
                  traces.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => setSelected(selected?.id === t.id ? null : t)}
                      className={`group border-b last:border-0 cursor-pointer transition-colors ${
                        selectedIds.has(t.id)
                          ? 'bg-primary/8 hover:bg-primary/10'
                          : selected?.id === t.id
                            ? 'bg-primary/5'
                            : 'hover:bg-muted/30'
                      }`}
                    >
                      <td
                        className="pl-3 pr-1 py-2.5 w-8"
                        onClick={e => { e.stopPropagation(); toggleSelect(t.id) }}
                      >
                        {selectedIds.has(t.id)
                          ? <CheckSquare className="h-3.5 w-3.5 text-primary" />
                          : <Square className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs">{t.id.slice(0, 8)}…</td>
                      <td className="px-4 py-2.5 max-w-[120px] truncate">{t.model ?? '—'}</td>
                      <td className="px-4 py-2.5">
                        <Badge variant={statusBadgeVariant(t.status)}>{t.status}</Badge>
                      </td>
                      <td className="px-4 py-2.5">
                        {(t.score_count ?? 0) > 0 ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px] font-semibold">
                            ✓ {t.score_count}
                          </span>
                        ) : (
                          <span className="text-muted-foreground text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{formatMs(t.latency_ms)}</td>
                      <td className="px-4 py-2.5">{t.total_tokens?.toLocaleString() ?? '—'}</td>
                      <td className="px-4 py-2.5 whitespace-nowrap">{formatCost(t.cost_usd)}</td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(t.timestamp ?? t.created_at)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-2 border-t text-xs text-muted-foreground">
              <span>
                Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + traces.length}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-2 py-1 border rounded hover:bg-muted disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={traces.length < PAGE_SIZE}
                  className="px-2 py-1 border rounded hover:bg-muted disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </div>

          {/* Detail panel */}
          {selected && !compareMode && (
            <div className="w-[520px] shrink-0 overflow-hidden flex flex-col" style={{ maxHeight: 'calc(100vh - 160px)' }}>
              <TraceDetail traceId={selected.id} onClose={() => setSelected(null)} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
