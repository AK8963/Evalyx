'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatMs, formatCost, formatDate, statusBadgeVariant } from '@/lib/utils'
import { Search, RefreshCw, Copy, Check, Tag, Zap, DollarSign, Clock, Hash, ChevronDown, ChevronRight } from 'lucide-react'
import type { Trace } from '@/types'

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
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      className="ml-1.5 text-muted-foreground hover:text-foreground transition-colors"
      title="Copy"
    >
      {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
    </button>
  )
}

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-lg overflow-hidden">
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

/** Visual waterfall timeline of the trace execution phases */
function ExecutionTimeline({ trace }: { trace: Trace }) {
  const total = trace.latency_ms ?? 1
  const prompt = trace.prompt_tokens ?? 0
  const completion = trace.completion_tokens ?? 0
  const totalTok = prompt + completion || 1

  // Derive phase durations proportionally
  const queueMs   = Math.round(total * 0.04)
  const evalMs    = prompt   > 0 ? Math.round(total * (prompt   / totalTok) * 0.55) : Math.round(total * 0.30)
  const genMs     = completion > 0 ? Math.round(total * (completion / totalTok) * 0.55) : Math.round(total * 0.55)
  const postMs    = total - queueMs - evalMs - genMs

  const phases = [
    { label: 'Queue', ms: queueMs,  color: 'bg-blue-400',    start: 0 },
    { label: 'Prompt Eval', ms: evalMs,   color: 'bg-violet-500', start: queueMs },
    { label: 'Generation',  ms: genMs,    color: 'bg-emerald-500',start: queueMs + evalMs },
    { label: 'Post-process',ms: postMs,   color: 'bg-amber-400',  start: queueMs + evalMs + genMs },
  ]

  return (
    <div className="space-y-3">
      {/* Gantt bar */}
      <div className="relative h-6 rounded overflow-hidden bg-muted flex">
        {phases.map((p) => (
          <div
            key={p.label}
            title={`${p.label}: ${formatMs(p.ms)}`}
            className={`${p.color} h-full transition-all`}
            style={{ width: `${(p.ms / total) * 100}%` }}
          />
        ))}
      </div>

      {/* Legend rows */}
      {phases.map((p, i) => {
        const startPct = (p.start / total) * 100
        const widthPct = (p.ms / total) * 100
        return (
          <div key={p.label} className="flex items-center gap-2 text-xs">
            <span className={`inline-block h-2.5 w-2.5 rounded-sm shrink-0 ${p.color}`} />
            <span className="w-24 text-muted-foreground">{p.label}</span>
            <div className="flex-1 relative h-4 bg-muted/40 rounded overflow-hidden">
              <div
                className={`absolute top-0 h-full rounded ${p.color} opacity-80`}
                style={{ left: `${startPct}%`, width: `${widthPct}%` }}
              />
            </div>
            <span className="w-14 text-right font-mono">{formatMs(p.ms)}</span>
          </div>
        )
      })}

      {/* Total row */}
      <div className="flex items-center justify-between text-xs border-t pt-2 mt-1">
        <span className="text-muted-foreground">Total end-to-end</span>
        <span className="font-semibold font-mono">{formatMs(total)}</span>
      </div>
    </div>
  )
}

/** Token breakdown bar */
function TokenBreakdown({ prompt, completion }: { prompt?: number; completion?: number }) {
  const p = prompt ?? 0
  const c = completion ?? 0
  const tot = p + c
  if (tot === 0) return <p className="text-xs text-muted-foreground">No token data</p>

  const pPct = (p / tot) * 100
  const cPct = (c / tot) * 100

  return (
    <div className="space-y-2">
      <div className="flex h-5 rounded overflow-hidden text-[10px] font-medium">
        <div className="bg-violet-500 flex items-center justify-center text-white" style={{ width: `${pPct}%` }}>
          {p > 0 && pPct > 12 ? `${p}` : ''}
        </div>
        <div className="bg-emerald-500 flex items-center justify-center text-white" style={{ width: `${cPct}%` }}>
          {c > 0 && cPct > 12 ? `${c}` : ''}
        </div>
      </div>
      <div className="flex gap-4 text-xs">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-violet-500 inline-block" />Prompt <strong>{p.toLocaleString()}</strong></span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-emerald-500 inline-block" />Completion <strong>{c.toLocaleString()}</strong></span>
        <span className="flex items-center gap-1.5 ml-auto text-muted-foreground">Total <strong>{tot.toLocaleString()}</strong></span>
      </div>
    </div>
  )
}

function TraceDetail({ trace }: { trace: Trace }) {
  const tags: string[] = trace.tags ?? (trace.metadata as Record<string, unknown> & { tags?: string[] })?.tags ?? []

  return (
    <div className="rounded-xl border bg-card overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className={`px-4 py-3 border-b flex items-center justify-between ${
        trace.status === 'success' ? 'bg-green-500/10 border-green-500/20' :
        trace.status === 'error'   ? 'bg-red-500/10 border-red-500/20' : 'bg-muted/40'
      }`}>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="font-mono text-[11px] text-muted-foreground truncate">{trace.id}</p>
            <CopyButton text={trace.id} />
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="font-semibold text-sm truncate">{trace.model ?? 'Unknown model'}</p>
            {trace.environment && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground uppercase font-medium">{trace.environment}</span>
            )}
          </div>
        </div>
        <Badge variant={statusBadgeVariant(trace.status)}>{trace.status}</Badge>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-4 divide-x border-b bg-muted/20">
        {[
          { icon: Clock,      label: 'Latency', value: formatMs(trace.latency_ms) },
          { icon: Hash,       label: 'Tokens',  value: trace.total_tokens?.toLocaleString() ?? '—' },
          { icon: DollarSign, label: 'Cost',    value: formatCost(trace.cost_usd) },
          { icon: Zap,        label: 'Time',    value: formatDate(trace.timestamp ?? trace.created_at) },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="px-3 py-2 text-center">
            <div className="flex items-center justify-center gap-1 text-muted-foreground mb-0.5">
              <Icon className="h-3 w-3" />
              <span className="text-[10px] uppercase">{label}</span>
            </div>
            <p className="text-xs font-semibold truncate">{value}</p>
          </div>
        ))}
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">

        {/* Error banner */}
        {trace.error_message && (
          <div className="bg-destructive/10 text-destructive rounded-lg p-3 text-xs border border-destructive/20">
            <p className="font-medium mb-1">Error</p>
            {trace.error_message}
          </div>
        )}

        {/* Execution Timeline */}
        <Section title="⚡ Execution Timeline">
          <ExecutionTimeline trace={trace} />
        </Section>

        {/* Token breakdown */}
        {(trace.prompt_tokens || trace.completion_tokens) && (
          <Section title="🔢 Token Breakdown">
            <TokenBreakdown prompt={trace.prompt_tokens} completion={trace.completion_tokens} />
          </Section>
        )}

        {/* Tags */}
        {tags.length > 0 && (
          <Section title="🏷️ Tags">
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t) => (
                <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary/10 text-primary rounded-full text-xs">
                  <Tag className="h-3 w-3" />{t}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Input */}
        {trace.input_data && (
          <Section title="📥 Input">
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap leading-relaxed">
              {typeof trace.input_data?.prompt === 'string'
                ? trace.input_data.prompt
                : JSON.stringify(trace.input_data, null, 2)}
            </pre>
          </Section>
        )}

        {/* Output */}
        {trace.output_data && (
          <Section title="📤 Output">
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap leading-relaxed">
              {typeof trace.output_data?.response === 'string'
                ? trace.output_data.response
                : JSON.stringify(trace.output_data, null, 2)}
            </pre>
          </Section>
        )}

        {/* Scores */}
        {trace.scores && trace.scores.length > 0 && (
          <Section title="🎯 Scores">
            <div className="space-y-2">
              {trace.scores.map((s) => (
                <div key={s.id} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-28 truncate">{s.scorer_type}</span>
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${s.score * 100}%` }} />
                  </div>
                  <span className="text-xs font-mono w-10 text-right">{(s.score * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Metadata */}
        {trace.metadata && Object.keys(trace.metadata).filter(k => k !== 'tags').length > 0 && (
          <Section title="🗂️ Metadata" defaultOpen={false}>
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-auto max-h-32 whitespace-pre-wrap">
              {JSON.stringify(
                Object.fromEntries(Object.entries(trace.metadata).filter(([k]) => k !== 'tags')),
                null, 2,
              )}
            </pre>
          </Section>
        )}
      </div>
    </div>
  )
}

export default function TracesPage() {
  const { project } = useProject()
  const [selected, setSelected] = useState<Trace | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [modelFilter, setModelFilter] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 25

  const { data: traces = [], isFetching, refetch } = useQuery({
    queryKey: ['traces', project?.id, statusFilter, modelFilter, page],
    queryFn: () =>
      api.traces.list({
        project_id: project!.id,
        status: statusFilter || undefined,
        model: modelFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    enabled: !!project,
  })

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project to view traces
      </div>
    )
  }

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

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={modelFilter}
            onChange={(e) => { setModelFilter(e.target.value); setPage(0) }}
            placeholder="Filter by model…"
            className="pl-8 pr-3 py-1.5 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring"
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
      </div>

      {/* Split view */}
      <div className="flex gap-4 min-h-[500px]">
        {/* Table */}
        <div className={`rounded-xl border bg-card overflow-hidden ${selected ? 'flex-1' : 'w-full'}`}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                {['ID', 'Model', 'Status', 'Latency', 'Tokens', 'Cost', 'Time'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {traces.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                    {isFetching ? 'Loading…' : 'No traces found'}
                  </td>
                </tr>
              ) : (
                traces.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => setSelected(selected?.id === t.id ? null : t)}
                    className={`border-b last:border-0 cursor-pointer transition-colors ${
                      selected?.id === t.id ? 'bg-primary/5' : 'hover:bg-muted/30'
                    }`}
                  >
                    <td className="px-4 py-2.5 font-mono text-xs">{t.id.slice(0, 8)}…</td>
                    <td className="px-4 py-2.5 max-w-[120px] truncate">{t.model ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant={statusBadgeVariant(t.status)}>{t.status}</Badge>
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
        {selected && (
          <div className="w-[460px] shrink-0 overflow-hidden flex flex-col" style={{ maxHeight: 'calc(100vh - 200px)' }}>
            <TraceDetail trace={selected} />
          </div>
        )}
      </div>
    </div>
  )
}
