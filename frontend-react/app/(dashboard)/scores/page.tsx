'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate, formatCost, formatMs } from '@/lib/utils'
import {
  ChevronDown, ChevronRight, RefreshCw, Search,
  Star, TrendingUp,
} from 'lucide-react'
import type { Score } from '@/types'

// ---------------------------------------------------------------------------
// Shared UI
// ---------------------------------------------------------------------------

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {children}
    </span>
  )
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-muted rounded-full h-1.5 min-w-16">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium w-9 text-right">{pct}%</span>
    </div>
  )
}

function ScorerTypeBadge({ type }: { type: string }) {
  const cfg: Record<string, string> = {
    llm: 'bg-purple-100 text-purple-700',
    code: 'bg-blue-100 text-blue-700',
    human: 'bg-green-100 text-green-700',
    expected: 'bg-orange-100 text-orange-700',
    semantic: 'bg-pink-100 text-pink-700',
  }
  return <Badge color={cfg[type] ?? 'bg-muted text-muted-foreground'}>{type}</Badge>
}

// ---------------------------------------------------------------------------
// Expanded row detail
// ---------------------------------------------------------------------------

function ScoreDetailRow({ score }: { score: Score }) {
  return (
    <tr className="bg-muted/30">
      <td colSpan={7} className="px-6 py-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">

          {/* Left: Score info */}
          <div className="space-y-3">
            <div>
              <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px] mb-1">Score Info</p>
              <div className="space-y-1">
                <div className="flex justify-between"><span className="text-muted-foreground">Score ID</span><span className="font-mono">{score.id.slice(0, 20)}...</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Scorer</span><span>{score.scorer_name}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Type</span><ScorerTypeBadge type={score.scorer_type} /></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Value</span><span className="font-semibold">{Math.round(score.score_value * 100)}%</span></div>
                {score.model_used && <div className="flex justify-between"><span className="text-muted-foreground">Model Used</span><span>{score.model_used}</span></div>}
                <div className="flex justify-between"><span className="text-muted-foreground">Created</span><span>{formatDate(score.created_at)}</span></div>
              </div>
            </div>

            {score.explanation && (
              <div>
                <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px] mb-1">Explanation</p>
                <p className="text-xs leading-relaxed border rounded-md p-2 bg-background">{score.explanation}</p>
              </div>
            )}

            {score.scorer_config && Object.keys(score.scorer_config).length > 0 && (
              <div>
                <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px] mb-1">Scorer Config</p>
                <pre className="text-xs border rounded-md p-2 bg-background overflow-x-auto">{JSON.stringify(score.scorer_config, null, 2)}</pre>
              </div>
            )}
          </div>

          {/* Right: Trace context */}
          {score.trace && (
            <div className="space-y-3">
              <div>
                <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px] mb-1">Linked Trace</p>
                <div className="space-y-1">
                  <div className="flex justify-between"><span className="text-muted-foreground">Trace ID</span><span className="font-mono">{score.trace_id.slice(0, 20)}...</span></div>
                  {score.trace.model && <div className="flex justify-between"><span className="text-muted-foreground">Model</span><span>{score.trace.model}</span></div>}
                  {score.trace.status && <div className="flex justify-between"><span className="text-muted-foreground">Status</span>
                    <Badge color={score.trace.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>{score.trace.status}</Badge>
                  </div>}
                  {score.trace.latency_ms != null && <div className="flex justify-between"><span className="text-muted-foreground">Latency</span><span>{formatMs(score.trace.latency_ms)}</span></div>}
                  {score.trace.total_tokens != null && <div className="flex justify-between"><span className="text-muted-foreground">Tokens</span><span>{score.trace.total_tokens.toLocaleString()}</span></div>}
                  {score.trace.cost_usd != null && <div className="flex justify-between"><span className="text-muted-foreground">Cost</span><span>{formatCost(score.trace.cost_usd)}</span></div>}
                </div>
              </div>

              {score.trace.input_data && (
                <div>
                  <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px] mb-1">Trace Input</p>
                  <pre className="text-xs border rounded-md p-2 bg-background overflow-x-auto max-h-24">{JSON.stringify(score.trace.input_data, null, 2).slice(0, 500)}</pre>
                </div>
              )}

              {score.trace.output_data && (
                <div>
                  <p className="font-semibold text-muted-foreground uppercase tracking-wide text-[10px] mb-1">Trace Output</p>
                  <pre className="text-xs border rounded-md p-2 bg-background overflow-x-auto max-h-24">{JSON.stringify(score.trace.output_data, null, 2).slice(0, 500)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ScoresPage() {
  const { project } = useProject()
  const projectId = project?.id ?? ''
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [scorerType, setScorerType] = useState('')
  const [scorerName, setScorerName] = useState('')
  const [days, setDays] = useState<number | undefined>(undefined)
  const [offset, setOffset] = useState(0)
  const limit = 50

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['scores', projectId, scorerType, scorerName, days, offset],
    queryFn: () => api.scores.list({
      project_id: projectId,
      scorer_type: scorerType || undefined,
      scorer_name: scorerName || undefined,
      days,
      limit,
      offset,
    }),
    enabled: !!projectId,
  })

  const scores = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  function toggleRow(id: string) {
    setExpandedId(prev => prev === id ? null : id)
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="px-6 py-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Star className="h-5 w-5 text-yellow-500" />
          <h1 className="font-semibold text-base">Scores</h1>
          <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{isLoading ? '...' : `${total} total`}</span>
        </div>
        <button onClick={() => refetch()} className="p-1.5 rounded hover:bg-muted text-muted-foreground" title="Refresh">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Filter bar */}
      <div className="px-6 py-3 border-b flex items-center gap-3 flex-wrap bg-muted/20">
        <div className="flex items-center gap-1.5 border rounded-md px-2 py-1.5 bg-background">
          <Search className="h-3.5 w-3.5 text-muted-foreground" />
          <input
            className="text-xs bg-transparent outline-none w-36"
            placeholder="Scorer name..."
            value={scorerName}
            onChange={e => { setScorerName(e.target.value); setOffset(0) }}
          />
        </div>

        <select
          className="text-xs border rounded-md px-2 py-1.5 bg-background"
          value={scorerType}
          onChange={e => { setScorerType(e.target.value); setOffset(0) }}
        >
          <option value="">All types</option>
          <option value="llm">LLM</option>
          <option value="code">Code</option>
          <option value="human">Human</option>
          <option value="expected">Expected</option>
          <option value="semantic">Semantic</option>
        </select>

        <select
          className="text-xs border rounded-md px-2 py-1.5 bg-background"
          value={days ?? ''}
          onChange={e => { setDays(e.target.value ? Number(e.target.value) : undefined); setOffset(0) }}
        >
          <option value="">All time</option>
          <option value="1">Last 24h</option>
          <option value="7">Last 7d</option>
          <option value="30">Last 30d</option>
        </select>

        {(scorerType || scorerName || days) && (
          <button
            onClick={() => { setScorerType(''); setScorerName(''); setDays(undefined); setOffset(0) }}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="p-8 text-sm text-muted-foreground text-center">Loading scores...</div>
        ) : !scores.length ? (
          <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
            <TrendingUp className="h-10 w-10 mb-2 opacity-20" />
            <p className="text-sm">No scores found. Run evaluations on traces to see scores here.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-background border-b">
              <tr className="text-xs text-muted-foreground">
                <th className="text-left px-4 py-3 font-medium w-8"></th>
                <th className="text-left px-4 py-3 font-medium">Scorer</th>
                <th className="text-left px-3 py-3 font-medium">Type</th>
                <th className="text-left px-3 py-3 font-medium w-40">Score</th>
                <th className="text-left px-3 py-3 font-medium">Trace ID</th>
                <th className="text-left px-3 py-3 font-medium">Model</th>
                <th className="text-left px-3 py-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {scores.map(score => (
                <>
                  <tr
                    key={score.id}
                    onClick={() => toggleRow(score.id)}
                    className="border-b hover:bg-muted/30 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-muted-foreground">
                      {expandedId === score.id
                        ? <ChevronDown className="h-3.5 w-3.5" />
                        : <ChevronRight className="h-3.5 w-3.5" />}
                    </td>
                    <td className="px-4 py-3 font-medium text-xs">{score.scorer_name}</td>
                    <td className="px-3 py-3"><ScorerTypeBadge type={score.scorer_type} /></td>
                    <td className="px-3 py-3 w-40"><ScoreBar value={score.score_value} /></td>
                    <td className="px-3 py-3 font-mono text-xs text-muted-foreground">{score.trace_id.slice(0, 12)}...</td>
                    <td className="px-3 py-3 text-xs">{score.trace?.model ?? '--'}</td>
                    <td className="px-3 py-3 text-xs text-muted-foreground">{formatDate(score.created_at)}</td>
                  </tr>
                  {expandedId === score.id && <ScoreDetailRow key={`${score.id}-detail`} score={score} />}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-3 border-t flex items-center justify-between text-xs text-muted-foreground">
          <span>Page {currentPage} of {totalPages} ({total} total)</span>
          <div className="flex gap-2">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-muted"
            >
              Prev
            </button>
            <button
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
              className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-muted"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
