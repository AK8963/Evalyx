'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { FlaskConical, Plus, ChevronDown, ChevronRight, Loader2, Trash2, X, CheckSquare, Square } from 'lucide-react'
import { toast } from 'sonner'
import type { Dataset, Eval, Metric } from '@/types'

function scoreColour(score: number | null | undefined) {
  if (score == null) return 'text-muted-foreground'
  if (score >= 0.7) return 'text-green-600'
  if (score >= 0.4) return 'text-yellow-600'
  return 'text-red-500'
}

function scoreBg(score: number | null | undefined) {
  if (score == null) return 'bg-muted/30'
  if (score >= 0.7) return 'bg-green-50 border-green-200'
  if (score >= 0.4) return 'bg-yellow-50 border-yellow-200'
  return 'bg-red-50 border-red-200'
}

// ---------------------------------------------------------------------------
// Item Detail Modal
// ---------------------------------------------------------------------------

/** Extract a human-readable string from a result row field.
 *  Priority: explicit keys from the data object, raw JSON fallback. */
function extractText(
  raw: string | undefined,
  dataObj: Record<string, unknown> | undefined | null,
  ...keys: string[]
): string {
  // If raw value is non-empty and not JSON, use it directly
  if (raw && raw.trim() !== '' && !raw.trimStart().startsWith('{') && !raw.trimStart().startsWith('[')) {
    return raw
  }
  // Try parsing raw as JSON
  if (raw && raw.trim() !== '') {
    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>
      if (typeof parsed === 'object' && parsed !== null) {
        for (const k of keys) {
          if (typeof parsed[k] === 'string' && parsed[k]) return parsed[k] as string
        }
        return JSON.stringify(parsed, null, 2)
      }
    } catch { /* not JSON */ }
    return raw
  }
  // Try dataObj
  if (dataObj && typeof dataObj === 'object') {
    for (const k of keys) {
      if (typeof dataObj[k] === 'string' && dataObj[k]) return dataObj[k] as string
    }
    return JSON.stringify(dataObj, null, 2)
  }
  return '[none]'
}

interface ResultRow {
  item_id?: string
  input?: string
  output?: string
  generated_output?: string
  input_data?: Record<string, unknown>
  actual_output?: Record<string, unknown>
  expected_output?: Record<string, unknown>
  scores?: { score: number; explanation?: string; scorer_name?: string }[]
}

function ItemModal({ row, onClose }: { row: ResultRow; onClose: () => void }) {
  const inp = extractText(row.input, row.input_data, 'question', 'prompt', 'text', 'input')
  const actualOut = row.generated_output || extractText(row.output, row.actual_output, 'answer', 'response', 'output', 'text')
  const expectedOut = row.expected_output ? extractText(undefined, row.expected_output, 'answer', 'response', 'output', 'text', 'expected') : row.generated_output ? extractText(row.output, null, 'answer', 'response', 'output', 'text') : '[none]'
  const out = actualOut
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="bg-background rounded-xl border shadow-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b">
          <h2 className="font-semibold text-sm">Result Detail</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">Input</p>
            <pre className="bg-muted/40 rounded-lg p-3 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{inp}</pre>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">Expected Output</p>
              <pre className="bg-muted/40 rounded-lg p-3 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{expectedOut}</pre>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 mb-1.5">Output Generated</p>
              <pre className="bg-blue-50 border border-blue-100 rounded-lg p-3 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{actualOut}</pre>
            </div>
          </div>
          {row.scores && row.scores.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Scores</p>
              <div className="space-y-2">
                {row.scores.map((s, i) => (
                  <div key={i} className={`rounded-lg border p-3 ${scoreBg(s.score)}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium">{s.scorer_name ?? `Metric ${i + 1}`}</span>
                      <span className={`text-lg font-bold ${scoreColour(s.score)}`}>{Math.round(s.score * 100)}%</span>
                    </div>
                    {s.explanation && <p className="text-xs text-muted-foreground leading-relaxed">{s.explanation}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Experiment detail panel
// ---------------------------------------------------------------------------
function ExperimentDetail({ evalId }: { evalId: string }) {
  const [selectedRow, setSelectedRow] = useState<ResultRow | null>(null)
  const { data: evalDetail } = useQuery<Eval>({
    queryKey: ['eval', evalId],
    queryFn: () => api.evals.get(evalId),
    // Poll every 1s while running, stop when done
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'completed' || s === 'failed' ? false : 1000
    },
  })

  if (!evalDetail) return <div className="p-4 text-sm text-muted-foreground">Loading...</div>

  const isRunning = evalDetail.status === 'running' || evalDetail.status === 'pending'
  const results = (evalDetail.results as unknown as ResultRow[]) ?? []
  const total = evalDetail.total_examples ?? 0
  const done = evalDetail.completed_examples ?? results.length
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  // Collect scorer names from whatever results we have so far
  const scorerNames: string[] = []
  results.forEach((r) => {
    r.scores?.forEach((s) => {
      const n = s.scorer_name ?? 'Score'
      if (!scorerNames.includes(n)) scorerNames.push(n)
    })
  })
  if (scorerNames.length === 0) scorerNames.push('Score')

  // Pending count = items not yet scored
  const pending = Math.max(0, total - results.length)

  return (
    <div className="border-t bg-muted/20 p-4 space-y-3">
      {selectedRow && <ItemModal row={selectedRow} onClose={() => setSelectedRow(null)} />}

      {/* Stats row */}
      <div className="flex gap-4 text-xs flex-wrap items-center">
        {evalDetail.avg_score != null && (
          <span className={`font-semibold ${scoreColour(evalDetail.avg_score)}`}>Avg: {Math.round(evalDetail.avg_score * 100)}%</span>
        )}
        {evalDetail.min_score != null && (
          <span className="text-muted-foreground">Min: {Math.round(evalDetail.min_score * 100)}%</span>
        )}
        {evalDetail.max_score != null && (
          <span className="text-muted-foreground">Max: {Math.round(evalDetail.max_score * 100)}%</span>
        )}
        <span className="text-muted-foreground">{done}/{total} items</span>
        {isRunning && (
          <span className="flex items-center gap-1 text-blue-600 font-medium">
            <Loader2 className="h-3 w-3 animate-spin" />
            Scoring item {results.length + 1} of {total}…
          </span>
        )}
      </div>

      {/* Progress bar (only while running or if partial results exist) */}
      {(isRunning || (done > 0 && done < total)) && (
        <div className="space-y-1">
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500 rounded-full"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-[11px] text-muted-foreground">{pct}% complete — {done} of {total} items scored</p>
        </div>
      )}

      {/* Results table — shows scored rows + pending placeholders */}
      {(results.length > 0 || isRunning) && (
        <div className="overflow-x-auto rounded-lg border text-xs">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium w-8">#</th>
                <th className="px-3 py-2 text-left font-medium min-w-[160px]">Input</th>
                <th className="px-3 py-2 text-left font-medium min-w-[160px]">Expected Output</th>
                <th className="px-3 py-2 text-left font-medium min-w-[160px] text-blue-700">Output Generated</th>
                {scorerNames.map((n) => (
                  <th key={n} className="px-3 py-2 text-left font-medium whitespace-nowrap">{n}</th>
                ))}
                <th className="px-3 py-2 text-left font-medium min-w-[200px]">Explanation</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {/* Scored items */}
              {results.map((row, i) => {
                const inp = extractText(row.input, row.input_data, 'question', 'prompt', 'text', 'input')
                const actualOut = row.generated_output || extractText(row.output, row.actual_output, 'answer', 'response', 'output', 'text')
                const expectedOut = row.expected_output ? extractText(undefined, row.expected_output, 'answer', 'response', 'output', 'text', 'expected') : row.generated_output ? extractText(row.output, null, 'answer', 'response', 'output', 'text') : '—'
                const firstScore = row.scores?.[0]
                return (
                  <tr key={row.item_id ?? i} className="hover:bg-primary/5 cursor-pointer transition-colors" onClick={() => setSelectedRow(row)}>
                    <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                    <td className="px-3 py-2"><p className="line-clamp-2">{inp}</p></td>
                    <td className="px-3 py-2"><p className="line-clamp-2">{expectedOut}</p></td>
                    <td className="px-3 py-2 text-blue-700"><p className="line-clamp-2">{actualOut}</p></td>
                    {scorerNames.map((n, si) => {
                      const s = row.scores?.find((x) => (x.scorer_name ?? 'Score') === n) ?? row.scores?.[si]
                      return (
                        <td key={n} className={`px-3 py-2 font-bold whitespace-nowrap ${scoreColour(s?.score)}`}>
                          {s?.score != null ? `${Math.round(s.score * 100)}%` : '—'}
                        </td>
                      )
                    })}
                    <td className="px-3 py-2 text-muted-foreground"><p className="line-clamp-2">{firstScore?.explanation ?? '—'}</p></td>
                  </tr>
                )
              })}

              {/* Currently-scoring row (pulsing) */}
              {isRunning && pending > 0 && (
                <tr className="bg-blue-50/60 animate-pulse">
                  <td className="px-3 py-2 text-muted-foreground">{results.length + 1}</td>
                  <td className="px-3 py-2 text-blue-500 font-medium" colSpan={3}>
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="h-3 w-3 animate-spin" /> Scoring…
                    </span>
                  </td>
                  {scorerNames.map((n) => (
                    <td key={n} className="px-3 py-2 text-blue-300">—</td>
                  ))}
                  <td className="px-3 py-2 text-blue-300">—</td>
                </tr>
              )}

              {/* Remaining pending rows */}
              {isRunning && Array.from({ length: Math.max(0, pending - 1) }).map((_, i) => (
                <tr key={`pending-${i}`} className="opacity-30">
                  <td className="px-3 py-2 text-muted-foreground">{results.length + 2 + i}</td>
                  <td className="px-3 py-2 text-muted-foreground" colSpan={3}>Waiting…</td>
                  {scorerNames.map((n) => (
                    <td key={n} className="px-3 py-2">—</td>
                  ))}
                  <td className="px-3 py-2">—</td>
                </tr>
              ))}
            </tbody>
          </table>
          {results.length > 0 && !isRunning && (
            <p className="text-[11px] text-muted-foreground/60 px-3 py-1.5 border-t">Click any row to see full text</p>
          )}
        </div>
      )}

      {evalDetail.status === 'failed' && (
        <p className="text-xs text-red-500">{(evalDetail as unknown as { error_message?: string }).error_message ?? 'Evaluation failed'}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function ExperimentsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [datasetId, setDatasetId] = useState('')
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['Correctness'])
  const [evalModel, setEvalModel] = useState('llama3')

  const { data: experiments = [], isLoading } = useQuery<Eval[]>({
    queryKey: ['evals', project?.id],
    queryFn: () => api.evals.list(project!.id),
    enabled: !!project,
    refetchInterval: 3000,
  })

  // Auto-expand the first running/pending experiment
  const firstRunning = experiments.find((e) => e.status === 'running' || e.status === 'pending')
  if (firstRunning && expandedId === null) {
    // Use setTimeout to avoid setting state during render
    setTimeout(() => setExpandedId(firstRunning.id), 0)
  }

  const { data: datasets = [] } = useQuery<Dataset[]>({
    queryKey: ['datasets', project?.id],
    queryFn: () => api.datasets.list(project!.id),
    enabled: !!project,
  })

  const { data: metrics = [] } = useQuery<Metric[]>({
    queryKey: ['metrics', project?.id],
    queryFn: () => api.metrics.list(project?.id),
    enabled: !!project,
  })

  const create = useMutation({
    mutationFn: () => {
      const scorers = selectedMetrics.map((mName) => {
        const m = metrics.find((x) => x.name === mName)
        return { name: mName, type: 'ollama' as const, model: evalModel, config: { prompt_template: m?.prompt_template ?? '' } }
      })
      return api.evals.create({ project_id: project!.id, name, description, dataset_id: datasetId || undefined, scorers })
    },
    onSuccess: () => {
      toast.success('Experiment started')
      qc.invalidateQueries({ queryKey: ['evals', project?.id] })
      setShowCreate(false); setName(''); setDescription(''); setDatasetId('')
      setSelectedMetrics(['Correctness']); setEvalModel('llama3')
    },
    onError: (e: Error) => toast.error(e.message || 'Failed'),
  })

  const deleteExp = useMutation({
    mutationFn: (id: string) => api.evals.delete(id),
    onSuccess: () => { toast.success('Deleted'); qc.invalidateQueries({ queryKey: ['evals', project?.id] }) },
    onError: () => toast.error('Delete failed'),
  })

  function toggleMetric(n: string) {
    setSelectedMetrics((prev) => prev.includes(n) ? prev.filter((x) => x !== n) : [...prev, n])
  }

  const statusColour: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-600',
  }

  if (!project) return <div className="flex items-center justify-center h-64 text-muted-foreground">Select a project</div>

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Experiments</h1>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">
          <Plus className="h-4 w-4" /> New Experiment
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-4">
          <h2 className="font-medium">New Experiment</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-muted-foreground block mb-1">Name *</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. WWII Correctness v3"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-muted-foreground block mb-1">Description</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Dataset *</label>
              <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                <option value="">— select —</option>
                {datasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>{ds.name} ({ds.example_count ?? ds.item_count ?? 0} items)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Judge model</label>
              <input value={evalModel} onChange={(e) => setEvalModel(e.target.value)} placeholder="llama3"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-2">Metrics * (select one or more)</label>
            <div className="flex flex-wrap gap-2">
              {metrics.map((m) => {
                const checked = selectedMetrics.includes(m.name)
                return (
                  <button key={m.id} type="button" onClick={() => toggleMetric(m.name)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-colors ${
                      checked ? 'bg-primary text-primary-foreground border-primary' : 'bg-background text-muted-foreground hover:bg-muted'
                    }`}>
                    {checked ? <CheckSquare className="h-3 w-3" /> : <Square className="h-3 w-3" />}
                    {m.name}
                    {m.is_builtin && <span className="opacity-50 text-[10px]">built-in</span>}
                  </button>
                )
              })}
            </div>
            {selectedMetrics.length > 0 && (
              <p className="text-xs text-muted-foreground mt-1">Selected: {selectedMetrics.join(', ')}</p>
            )}
          </div>

          <div className="flex gap-2">
            <button onClick={() => create.mutate()}
              disabled={!name || !datasetId || selectedMetrics.length === 0 || create.isPending}
              className="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm disabled:opacity-50 flex items-center gap-2">
              {create.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {create.isPending ? 'Starting…' : 'Run Experiment'}
            </button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-1.5 border rounded-md text-sm hover:bg-muted">Cancel</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : experiments.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 gap-2 border rounded-xl">
          <FlaskConical className="h-8 w-8 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">No experiments yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {experiments.map((exp) => (
            <div key={exp.id} className="rounded-xl border bg-card overflow-hidden">
              <div className="px-4 py-3 flex items-center gap-3 cursor-pointer hover:bg-muted/20 transition-colors"
                onClick={() => setExpandedId(expandedId === exp.id ? null : exp.id)}>
                <FlaskConical className="h-4 w-4 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm">{exp.name}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColour[exp.status] ?? 'bg-muted text-muted-foreground'}`}>
                      {exp.status === 'running' ? <span className="flex items-center gap-1"><Loader2 className="h-2.5 w-2.5 animate-spin" />{exp.status}</span> : exp.status}
                    </span>
                    {exp.avg_score != null && (
                      <span className={`text-xs font-semibold ${scoreColour(exp.avg_score)}`}>avg {Math.round(exp.avg_score * 100)}%</span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatDate(exp.created_at)} · {exp.completed_examples}/{exp.total_examples} items
                  </p>
                </div>
                <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete this experiment?')) deleteExp.mutate(exp.id) }}
                  className="p-1.5 text-muted-foreground hover:text-red-500 rounded transition-colors shrink-0" title="Delete">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
                {expandedId === exp.id ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
              </div>
              {expandedId === exp.id && <ExperimentDetail evalId={exp.id} />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
