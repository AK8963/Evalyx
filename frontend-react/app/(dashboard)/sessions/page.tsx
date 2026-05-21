'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate, formatCost, formatMs } from '@/lib/utils'
import {
  Plus, Trash2, X, ChevronRight, ChevronDown, Tag,
  Layers, Hash, RefreshCw, Pencil, Check, Copy,
  Clock, DollarSign, Loader2, Save,
} from 'lucide-react'
import { toast } from 'sonner'
import type { Session, SessionTrace } from '@/types'

// ---------------------------------------------------------------------------
// Shared UI primitives
// ---------------------------------------------------------------------------

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {children}
    </span>
  )
}

function Section({ title, children, defaultOpen = true }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-lg overflow-hidden mb-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-muted/40 hover:bg-muted/60 transition-colors text-xs font-semibold uppercase tracking-wide text-muted-foreground"
      >
        {title}
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Score badge
// ---------------------------------------------------------------------------

function ScorePill({ value }: { value: number | undefined }) {
  if (value === undefined || value === null) return <span className="text-xs text-muted-foreground">--</span>
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-green-100 text-green-700' : pct >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
  return <Badge color={color}>{pct}%</Badge>
}

// ---------------------------------------------------------------------------
// Create session modal
// ---------------------------------------------------------------------------

function CreateSessionModal({ projectId, onClose, onCreated }: {
  projectId: string
  onClose: () => void
  onCreated: (s: Session) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => api.sessions.create({
      project_id: projectId,
      name: name.trim(),
      description: description.trim() || undefined,
      tags: tags.split(',').map(t => t.trim()).filter(Boolean),
    }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ['sessions', projectId] })
      toast.success('Session created')
      onCreated(created)
    },
    onError: () => toast.error('Failed to create session'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background border rounded-xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-base">New Session</h2>
          <button onClick={onClose}><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground">Name *</label>
            <input
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="e.g. production-run-1"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Description</label>
            <textarea
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
              rows={3}
              placeholder="Optional description..."
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground">Tags (comma-separated)</label>
            <input
              className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="e.g. prod, v2, experiment"
              value={tags}
              onChange={e => setTags(e.target.value)}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-3 py-1.5 text-sm border rounded-md hover:bg-muted">Cancel</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name.trim() || mutation.isPending}
            className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {mutation.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Add Traces panel
// ---------------------------------------------------------------------------

function AddTracesPanel({ session, onAdded }: { session: Session; onAdded: (ids: string[]) => void }) {
  const [input, setInput] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: (ids: string[]) => api.sessions.addTraces(session.id, ids),
    onSuccess: (_, ids) => {
      qc.invalidateQueries({ queryKey: ['session', session.id] })
      qc.invalidateQueries({ queryKey: ['sessions', session.project_id] })
      setInput('')
      toast.success(`${ids.length} trace(s) added`)
      onAdded(ids)
    },
    onError: (err: Error) => toast.error(err.message || 'Failed to add traces'),
  })

  function handleAdd() {
    const ids = input.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
    if (!ids.length) return
    mutation.mutate(ids)
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Enter trace IDs separated by commas or newlines.</p>
      <textarea
        className="w-full border rounded-md px-3 py-2 text-xs font-mono bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        rows={3}
        placeholder="abc12345, def67890..."
        value={input}
        onChange={e => setInput(e.target.value)}
      />
      <button
        onClick={handleAdd}
        disabled={!input.trim() || mutation.isPending}
        className="px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 flex items-center gap-1.5"
      >
        {mutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
        {mutation.isPending ? 'Adding...' : 'Add Traces'}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Score panel
// ---------------------------------------------------------------------------

const OLLAMA_MODELS = [
  'llama2', 'llama3', 'llama3.2',
  'gemma2:9b', 'gemma2:27b',
  'mistral-nemo', 'mistral', 'mixtral',
  'qwen2', 'devstral',
  'codellama', 'phi3',
  'deepseek-r1', 'deepseek-coder',
]

function ScorePanel({ model, onModelChange, scoring, onScoreNow, onLLMScore }: {
  model: string
  onModelChange: (m: string) => void
  scoring: boolean
  onScoreNow: () => void   // from_traces (primary)
  onLLMScore: () => void   // ollama re-score (explicit)
}) {
  return (
    <div className="space-y-3">
      {/* Primary: aggregate from trace scores */}
      <div className="rounded-lg border bg-muted/20 p-3 space-y-2">
        <p className="text-xs font-semibold text-foreground">From Trace Metrics</p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Averages the same score metrics already on each trace (e.g. quality, helpfulness).
          Falls back to LLM if traces have no scores yet.
        </p>
        <button
          onClick={onScoreNow}
          disabled={scoring}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          {scoring ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
          {scoring ? 'Scoring...' : 'Sync from Traces'}
        </button>
      </div>

      {/* Secondary: explicit LLM re-score */}
      <div className="rounded-lg border p-3 space-y-2">
        <p className="text-xs font-semibold text-foreground">LLM Re-score (Ollama)</p>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Runs each trace through the LLM judge and stores the result as <span className="font-mono">session_ollama</span>.
        </p>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground font-medium">Model</label>
          <select
            value={model}
            onChange={e => onModelChange(e.target.value)}
            disabled={scoring}
            className="w-full border rounded-md px-2 py-1.5 text-xs bg-background disabled:opacity-50"
          >
            {OLLAMA_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <button
          onClick={onLLMScore}
          disabled={scoring}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-md hover:bg-muted disabled:opacity-50"
        >
          {scoring ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
          {scoring ? 'Scoring...' : 'Run LLM Score'}
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// CopyBtn
// ---------------------------------------------------------------------------

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="text-muted-foreground hover:text-foreground transition-colors"
    >
      {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}

// ---------------------------------------------------------------------------
// extractText helper (for trace input/output display)
// ---------------------------------------------------------------------------

function extractText(data: Record<string, unknown> | null | undefined): string {
  if (!data) return ''
  const msgs = data.messages
  if (Array.isArray(msgs) && msgs.length > 0) {
    return msgs
      .filter((m: unknown) => m && typeof m === 'object')
      .map((m: unknown) => {
        const mo = m as Record<string, unknown>
        return `[${mo.role ?? 'unknown'}]: ${mo.content ?? ''}`
      })
      .join('\n\n')
  }
  const text = data.answer ?? data.response ?? data.output ?? data.content
  if (typeof text === 'string') return text
  const q = data.question ?? data.prompt ?? data.text ?? data.input
  if (typeof q === 'string') return q
  return ''
}

// ---------------------------------------------------------------------------
// TraceInfoPanel — third column showing full trace details on click
// ---------------------------------------------------------------------------

function TraceInfoPanel({ traceId, onClose }: { traceId: string; onClose: () => void }) {
  const { data: trace, isLoading } = useQuery({
    queryKey: ['trace-detail', traceId],
    queryFn: () => api.traces.get(traceId),
    staleTime: 30_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }
  if (!trace) return null

  const scores = trace.scores ?? []
  const inputText = extractText(trace.input_data)
  const outputText = extractText(trace.output_data)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b bg-muted/20 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-[11px] text-muted-foreground">{traceId.slice(0, 16)}…</span>
              <CopyBtn text={traceId} />
            </div>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <Badge color={trace.status === 'success' ? 'bg-green-100 text-green-700' : trace.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}>
                {trace.status}
              </Badge>
              {trace.model && <span className="text-xs text-muted-foreground">{trace.model}</span>}
              <span className="text-xs text-muted-foreground">{formatDate(trace.timestamp ?? trace.created_at)}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-red-50 hover:text-red-600 text-muted-foreground transition-colors shrink-0"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {/* Score badges */}
        {scores.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {scores.map(s => {
              const pct = Math.round(s.score_value * 100)
              const color = pct >= 80 ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                : pct >= 50 ? 'bg-amber-100 text-amber-800 border-amber-300'
                : 'bg-red-100 text-red-800 border-red-300'
              return (
                <span key={s.id} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${color}`}>
                  <span className="font-normal text-muted-foreground">{s.scorer_name ?? s.scorer_type}:</span>
                  <span>{pct}%</span>
                </span>
              )
            })}
          </div>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 divide-x border-b bg-muted/10 shrink-0">
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <Clock className="h-3 w-3" /><span className="text-[10px] uppercase">Latency</span>
          </div>
          <p className="text-xs font-semibold">{formatMs(trace.latency_ms)}</p>
        </div>
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <span className="text-[10px] uppercase">Tokens</span>
          </div>
          <p className="text-xs font-semibold">
            {trace.prompt_tokens != null
              ? `${trace.prompt_tokens}+${trace.completion_tokens ?? 0}`
              : (trace.total_tokens?.toLocaleString() ?? '—')}
          </p>
        </div>
        <div className="px-2 py-1.5 text-center">
          <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
            <DollarSign className="h-3 w-3" /><span className="text-[10px] uppercase">Cost</span>
          </div>
          <p className="text-xs font-semibold">{formatCost(trace.cost_usd)}</p>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {trace.input_data && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Input</p>
            <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap max-h-52 overflow-y-auto">
              {inputText || JSON.stringify(trace.input_data, null, 2)}
            </div>
          </div>
        )}
        {trace.output_data && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Output</p>
            <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap max-h-52 overflow-y-auto">
              {outputText || JSON.stringify(trace.output_data, null, 2)}
            </div>
          </div>
        )}
        {trace.error_message && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-red-600 mb-2">Error</p>
            <pre className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-3 whitespace-pre-wrap">{trace.error_message}</pre>
          </div>
        )}
        {/* Environment / Tags */}
        {(trace.environment || (trace.tags && trace.tags.length > 0)) && (
          <div className="flex gap-1.5 flex-wrap items-center text-xs">
            {trace.environment && <Badge color="bg-blue-100 text-blue-700">{trace.environment}</Badge>}
            {trace.tags?.map(t => <Badge key={t} color="bg-muted text-muted-foreground">{t}</Badge>)}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// EditSessionPanel — inline edit for name/description/tags/metadata
// ---------------------------------------------------------------------------

function EditSessionPanel({ session, onSaved }: { session: Session; onSaved: () => void }) {
  const [name, setName] = useState(session.name)
  const [description, setDescription] = useState(session.description ?? '')
  const [tagsStr, setTagsStr] = useState((session.tags ?? []).join(', '))
  const [metaStr, setMetaStr] = useState(
    session.meta && Object.keys(session.meta).length > 0
      ? JSON.stringify(session.meta, null, 2)
      : ''
  )
  const [metaError, setMetaError] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => {
      let meta: Record<string, unknown> | undefined
      if (metaStr.trim()) {
        try { meta = JSON.parse(metaStr) } catch { throw new Error('Invalid JSON in metadata') }
      }
      return api.sessions.update(session.id, {
        name: name.trim() || session.name,
        description: description.trim() || undefined,
        tags: tagsStr.split(',').map(t => t.trim()).filter(Boolean),
        meta,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['session', session.id] })
      qc.invalidateQueries({ queryKey: ['sessions', session.project_id] })
      toast.success('Session updated')
      onSaved()
    },
    onError: (err: Error) => toast.error(err.message || 'Update failed'),
  })

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs font-medium text-muted-foreground">Name</label>
        <input
          className="mt-1 w-full border rounded-md px-2 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          value={name}
          onChange={e => setName(e.target.value)}
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground">Description</label>
        <textarea
          className="mt-1 w-full border rounded-md px-2 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
          rows={2}
          placeholder="Optional description..."
          value={description}
          onChange={e => setDescription(e.target.value)}
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground">Tags (comma-separated)</label>
        <input
          className="mt-1 w-full border rounded-md px-2 py-1.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          placeholder="prod, v2, experiment"
          value={tagsStr}
          onChange={e => setTagsStr(e.target.value)}
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground">Metadata (JSON)</label>
        <textarea
          className={`mt-1 w-full border rounded-md px-2 py-1.5 text-xs font-mono bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none ${metaError ? 'border-red-400' : ''}`}
          rows={3}
          placeholder='{"key": "value"}'
          value={metaStr}
          onChange={e => { setMetaStr(e.target.value); setMetaError('') }}
        />
        {metaError && <p className="text-xs text-red-500 mt-0.5">{metaError}</p>}
      </div>
      <button
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
      >
        {mutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
        Save Changes
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Session detail panel
// ---------------------------------------------------------------------------

function SessionDetail({
  sessionId, projectId, onClose, onSelectTrace, selectedTraceId,
}: {
  sessionId: string
  projectId: string
  onClose: () => void
  onSelectTrace: (id: string | null) => void
  selectedTraceId: string | null
}) {
  const qc = useQueryClient()
  const [scoring, setScoring] = useState(false)
  const [scoreModel, setScoreModel] = useState('llama2')

  const { data: session, isLoading, refetch: refetchSession } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.sessions.get(sessionId),
    refetchInterval: false,
  })

  const removeTrace = useMutation({
    mutationFn: (traceId: string) => api.sessions.removeTrace(sessionId, traceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['session', sessionId] })
      qc.invalidateQueries({ queryKey: ['sessions', projectId] })
      toast.success('Trace removed')
    },
    onError: () => toast.error('Failed to remove trace'),
  })

  async function autoScore(model: string) {
    setScoring(true)
    try {
      // Primary: aggregate existing trace metrics by scorer_name (same metrics as traces).
      // Falls back to Ollama LLM scoring automatically on backend if no trace scores exist.
      await api.sessions.score(sessionId, { scorer_type: 'from_traces', model })
      await qc.invalidateQueries({ queryKey: ['session', sessionId] })
      await qc.invalidateQueries({ queryKey: ['sessions', projectId] })
      toast.success('Session scored')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('no traces') || msg.includes('400')) {
        toast.error('Add traces before scoring')
      } else {
        toast.error('Scoring failed — is Ollama running?')
      }
    } finally {
      setScoring(false)
    }
  }

  async function handleTracesAdded() {
    await refetchSession()
    autoScore(scoreModel)
  }

  if (isLoading) return (
    <div className="p-6 flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />Loading...
    </div>
  )
  if (!session) return <div className="p-6 text-sm text-muted-foreground">Not found</div>

  return (
    <div className="p-4 space-y-3 overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-semibold text-base truncate">{session.name}</h2>
          <div className="flex items-center gap-1.5 mt-0.5">
            <p className="text-xs text-muted-foreground font-mono">{session.id.slice(0, 12)}…</p>
            <CopyBtn text={session.id} />
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {scoring && <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" aria-label="Scoring" />}
          <ScorePill value={session.manual_score} />
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-red-50 hover:text-red-600 text-muted-foreground transition-colors"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {session.description && (
        <p className="text-sm text-muted-foreground">{session.description}</p>
      )}

      {session.tags && session.tags.length > 0 && (
        <div className="flex gap-1.5 flex-wrap">
          {session.tags.map(t => (
            <Badge key={t} color="bg-muted text-muted-foreground">
              <Tag className="h-2.5 w-2.5 mr-1 inline" />{t}
            </Badge>
          ))}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="border rounded-lg p-3 text-center">
          <div className="text-lg font-semibold">{session.trace_count}</div>
          <div className="text-xs text-muted-foreground">Traces</div>
        </div>
        <div className="border rounded-lg p-3 text-center">
          <div className="flex justify-center"><ScorePill value={session.manual_score} /></div>
          <div className="text-xs text-muted-foreground mt-1">Score</div>
        </div>
        <div className="border rounded-lg p-3 text-center">
          <div className="text-xs font-semibold">{formatDate(session.created_at)}</div>
          <div className="text-xs text-muted-foreground">Created</div>
        </div>
      </div>

      {/* Aggregate scores */}
      {Object.keys(session.aggregate_scores ?? {}).length > 0 && (
        <Section title="Aggregate Scores">
          <div className="space-y-1">
            {Object.entries(session.aggregate_scores).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{k}</span>
                <ScorePill value={v as number} />
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Linked Traces */}
      <Section title={`Linked Traces (${session.trace_count})`}>
        {!session.traces?.length ? (
          <p className="text-xs text-muted-foreground">No traces linked yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="pb-1.5 pr-2 font-medium">ID</th>
                  <th className="pb-1.5 pr-2 font-medium">Model</th>
                  <th className="pb-1.5 pr-2 font-medium">Status</th>
                  <th className="pb-1.5 pr-2 font-medium">Latency</th>
                  <th className="pb-1.5 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {session.traces!.map((t: SessionTrace) => (
                  <tr
                    key={t.id}
                    onClick={() => onSelectTrace(selectedTraceId === t.id ? null : t.id)}
                    className={`border-b last:border-0 cursor-pointer transition-colors ${selectedTraceId === t.id ? 'bg-primary/8' : 'hover:bg-muted/30'}`}
                  >
                    <td className="py-1.5 pr-2 font-mono text-primary">{t.id.slice(0, 8)}</td>
                    <td className="py-1.5 pr-2 truncate max-w-[80px]">{t.model ?? '--'}</td>
                    <td className="py-1.5 pr-2">
                      <Badge color={t.status === 'success' ? 'bg-green-100 text-green-700' : t.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}>
                        {t.status ?? '--'}
                      </Badge>
                    </td>
                    <td className="py-1.5 pr-2">{t.latency_ms != null ? formatMs(t.latency_ms) : '--'}</td>
                    <td className="py-1.5">
                      <button
                        onClick={e => { e.stopPropagation(); removeTrace.mutate(t.id) }}
                        disabled={removeTrace.isPending}
                        className="text-muted-foreground hover:text-destructive"
                        title="Remove from session"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* Add Traces */}
      <Section title="Add Traces">
        <AddTracesPanel session={session} onAdded={handleTracesAdded} />
        {scoring && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-primary">
            <Loader2 className="h-3 w-3 animate-spin" />
            Auto-scoring with Ollama ({scoreModel})…
          </div>
        )}
      </Section>

      {/* Scoring */}
      <Section title="LLM Scoring" defaultOpen={true}>
        <ScorePanel
          model={scoreModel}
          onModelChange={setScoreModel}
          scoring={scoring}
          onScoreNow={() => autoScore(scoreModel)}
          onLLMScore={async () => {
            setScoring(true)
            try {
              await api.sessions.score(sessionId, { scorer_type: 'ollama', model: scoreModel })
              await qc.invalidateQueries({ queryKey: ['session', sessionId] })
              await qc.invalidateQueries({ queryKey: ['sessions', projectId] })
              toast.success('Session scored with LLM')
            } catch {
              toast.error('LLM scoring failed — is Ollama running?')
            } finally {
              setScoring(false)
            }
          }}
        />
      </Section>

      {/* Edit */}
      <Section title="Edit Session" defaultOpen={false}>
        <EditSessionPanel session={session} onSaved={() => {}} />
      </Section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function SessionsPage() {
  const { project } = useProject()
  const projectId = project?.id ?? ''
  const [showCreate, setShowCreate] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const qc = useQueryClient()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['sessions', projectId],
    queryFn: () => api.sessions.list(projectId),
    enabled: !!projectId,
  })

  const deleteSession = useMutation({
    mutationFn: (id: string) => api.sessions.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions', projectId] })
      if (selectedId) setSelectedId(null)
      setSelectedTraceId(null)
      toast.success('Session deleted')
    },
    onError: () => toast.error('Failed to delete session'),
  })

  const sessions = data?.items ?? []

  function handleSelectSession(id: string) {
    setSelectedId(id === selectedId ? null : id)
    setSelectedTraceId(null)
  }

  function handleCloseDetail() {
    setSelectedId(null)
    setSelectedTraceId(null)
  }

  return (
    <div className="flex min-h-0 overflow-hidden" style={{ height: 'calc(100vh - 80px)' }}>
      {/* ── Left: session list ── */}
      <div className="w-72 border-r flex flex-col min-h-0 shrink-0">
        <div className="px-4 py-3 border-b flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            <h1 className="font-semibold text-sm">Sessions</h1>
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              {isLoading ? '…' : (data?.total ?? 0)}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={() => refetch()} className="p-1 rounded hover:bg-muted text-muted-foreground" title="Refresh">
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              <Plus className="h-3.5 w-3.5" /> New
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />Loading...
            </div>
          ) : !sessions.length ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              <Layers className="h-8 w-8 mx-auto mb-2 opacity-30" />
              No sessions yet. Create one to group traces.
            </div>
          ) : (
            sessions.map(s => (
              <button
                key={s.id}
                onClick={() => handleSelectSession(s.id)}
                className={`w-full text-left px-4 py-3 border-b hover:bg-muted/40 transition-colors ${selectedId === s.id ? 'bg-muted/60 border-l-2 border-l-primary' : ''}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{s.name}</div>
                    <div className="text-xs text-muted-foreground font-mono mt-0.5">{s.id.slice(0, 12)}...</div>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Hash className="h-2.5 w-2.5" />{s.trace_count} traces
                      </span>
                      {s.tags?.slice(0, 2).map(t => (
                        <Badge key={t} color="bg-muted text-muted-foreground">{t}</Badge>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    <ScorePill value={s.manual_score} />
                    <button
                      onClick={e => { e.stopPropagation(); deleteSession.mutate(s.id) }}
                      className="text-muted-foreground hover:text-destructive p-0.5"
                      title="Delete session"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* ── Middle: session detail ── */}
      <div className={`border-r flex flex-col min-h-0 overflow-y-auto transition-all ${selectedId ? (selectedTraceId ? 'w-[420px] shrink-0' : 'flex-1') : 'flex-1'}`}>
        {selectedId ? (
          <SessionDetail
            key={selectedId}
            sessionId={selectedId}
            projectId={projectId}
            onClose={handleCloseDetail}
            onSelectTrace={setSelectedTraceId}
            selectedTraceId={selectedTraceId}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <Layers className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm">Select a session to view details</p>
          </div>
        )}
      </div>

      {/* ── Right: trace info ── */}
      {selectedTraceId && (
        <div className="flex-1 min-h-0 overflow-hidden border-l bg-card">
          <TraceInfoPanel
            key={selectedTraceId}
            traceId={selectedTraceId}
            onClose={() => setSelectedTraceId(null)}
          />
        </div>
      )}

      {showCreate && (
        <CreateSessionModal
          projectId={projectId}
          onClose={() => setShowCreate(false)}
          onCreated={s => { setShowCreate(false); setSelectedId(s.id) }}
        />
      )}
    </div>
  )
}
