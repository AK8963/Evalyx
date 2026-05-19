'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { ThumbsUp, ThumbsDown, Star, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import type { Trace, Annotation } from '@/types'

// Full shape returned by the backend
interface AnnRecord {
  id: string
  trace_id: string
  project_id: string
  thumbs_up: boolean | null
  rating: number | null
  comment: string | null
  label_names: string[]
  annotation_type: string
  created_at: string
}

interface Summary {
  total: number
  thumbs_up: number
  thumbs_down: number
  avg_rating: number | null
}

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'thumbs_up', label: 'Thumbs Up' },
  { key: 'thumbs_down', label: 'Thumbs Down' },
  { key: 'rating', label: 'Rating' },
  { key: 'comment', label: 'Comment' },
]

export default function AnnotationsPage() {
  const { project } = useProject()
  const qc = useQueryClient()

  const [traceId, setTraceId] = useState('')
  const [thumbs, setThumbs] = useState<boolean | null>(null)
  const [rating, setRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [comment, setComment] = useState('')
  const [filter, setFilter] = useState('all')

  // Fetch recent traces for the picker
  const { data: traces = [] } = useQuery({
    queryKey: ['traces-for-annotations', project?.id],
    queryFn: () => api.traces.list({ project_id: project!.id, limit: 100 }),
    enabled: !!project,
    staleTime: 60_000,
  })

  const { data: annotations = [], isLoading } = useQuery({
    queryKey: ['annotations', project?.id],
    queryFn: () => api.annotations.list(project!.id),
    enabled: !!project,
  })

  const { data: summary } = useQuery({
    queryKey: ['annotations-summary', project?.id],
    queryFn: () => api.annotations.summary(project!.id),
    enabled: !!project,
  })

  const save = useMutation({
    mutationFn: () => {
      const type = thumbs != null
        ? (thumbs ? 'thumbs_up' : 'thumbs_down')
        : rating > 0 ? 'rating' : 'comment'
      const payload: Record<string, unknown> = {
        trace_id: traceId,
        project_id: project!.id,
        annotation_type: type,
      }
      if (thumbs != null) payload.thumbs_up = thumbs
      if (rating > 0) payload.rating = rating
      if (comment.trim()) payload.comment = comment.trim()
      return api.annotations.create(payload as Partial<Annotation>)
    },
    onSuccess: () => {
      toast.success('Annotation saved')
      qc.invalidateQueries({ queryKey: ['annotations', project?.id] })
      qc.invalidateQueries({ queryKey: ['annotations-summary', project?.id] })
      setTraceId('')
      setThumbs(null)
      setRating(0)
      setComment('')
    },
    onError: () => toast.error('Failed to save annotation'),
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.annotations.delete(id),
    onSuccess: () => {
      toast.success('Deleted')
      qc.invalidateQueries({ queryKey: ['annotations', project?.id] })
      qc.invalidateQueries({ queryKey: ['annotations-summary', project?.id] })
    },
    onError: () => toast.error('Failed to delete'),
  })

  function traceLabel(t: Trace) {
    const inp = t.input_data as Record<string, unknown> | null
    const q = inp?.question ?? inp?.prompt ?? inp?.text ?? inp?.input
    const text = typeof q === 'string' ? q.slice(0, 70) : ''
    return text || t.id.slice(0, 8)
  }

  const allAnns = annotations as unknown as AnnRecord[]
  const filtered = allAnns.filter((a) => {
    if (filter === 'thumbs_up') return a.thumbs_up === true
    if (filter === 'thumbs_down') return a.thumbs_up === false
    if (filter === 'rating') return a.rating != null
    if (filter === 'comment') return !!a.comment
    return true
  })

  const canSave = !!traceId && (thumbs != null || rating > 0 || comment.trim().length > 0)
  const sum = summary as Summary | undefined

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Annotations</h1>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total', value: sum?.total ?? '—' },
          { label: 'Thumbs Up', value: sum?.thumbs_up ?? '—' },
          { label: 'Thumbs Down', value: sum?.thumbs_down ?? '—' },
          { label: 'Avg Rating', value: sum?.avg_rating != null ? `${sum.avg_rating.toFixed(1)} / 5` : '—' },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-xl border bg-card p-4">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold mt-0.5">{value}</p>
          </div>
        ))}
      </div>

      {/* Annotation form */}
      <div className="rounded-xl border bg-card p-5 space-y-4">
        <h2 className="font-medium text-sm">Add Annotation</h2>

        {/* Trace picker */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Trace *</label>
          <select
            value={traceId}
            onChange={(e) => setTraceId(e.target.value)}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">Select a trace…</option>
            {(traces as Trace[]).map((t) => (
              <option key={t.id} value={t.id}>
                {traceLabel(t)}
                {t.model ? ` — ${t.model}` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Sentiment */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Sentiment</label>
          <div className="flex gap-2">
            <button
              onClick={() => setThumbs(thumbs === true ? null : true)}
              className={`flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-sm transition-colors ${
                thumbs === true
                  ? 'bg-green-100 border-green-400 text-green-700 font-medium'
                  : 'hover:bg-green-50 hover:border-green-300 hover:text-green-700'
              }`}
            >
              <ThumbsUp className="h-4 w-4" /> Good
            </button>
            <button
              onClick={() => setThumbs(thumbs === false ? null : false)}
              className={`flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-sm transition-colors ${
                thumbs === false
                  ? 'bg-red-100 border-red-400 text-red-700 font-medium'
                  : 'hover:bg-red-50 hover:border-red-300 hover:text-red-700'
              }`}
            >
              <ThumbsDown className="h-4 w-4" /> Bad
            </button>
          </div>
        </div>

        {/* Star rating */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            Rating {rating > 0 && <span className="text-amber-500 ml-1">{rating} / 5</span>}
          </label>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                onClick={() => setRating(rating === n ? 0 : n)}
                onMouseEnter={() => setHoverRating(n)}
                onMouseLeave={() => setHoverRating(0)}
                className="focus:outline-none"
              >
                <Star
                  className={`h-6 w-6 transition-colors ${
                    n <= (hoverRating || rating)
                      ? 'text-amber-400 fill-amber-400'
                      : 'text-muted-foreground'
                  }`}
                />
              </button>
            ))}
          </div>
        </div>

        {/* Comment */}
        <div>
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Comment</label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Notes, corrections, or feedback…"
            rows={2}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-none"
          />
        </div>

        <button
          onClick={() => save.mutate()}
          disabled={!canSave || save.isPending}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
        >
          {save.isPending ? 'Saving…' : 'Save Annotation'}
        </button>
      </div>

      {/* Annotation list */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b flex items-center gap-3 flex-wrap">
          <h2 className="text-sm font-medium">Recent Annotations</h2>
          <div className="flex gap-1 flex-wrap ml-auto">
            {FILTERS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  filter === key
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/60'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <p className="px-5 py-8 text-sm text-muted-foreground">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="px-5 py-8 text-sm text-muted-foreground text-center">No annotations yet</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                {['Sentiment', 'Rating', 'Trace', 'Comment', 'Time', ''].map((h, i) => (
                  <th
                    key={i}
                    className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-2.5">
                    {a.thumbs_up === true ? (
                      <ThumbsUp className="h-4 w-4 text-green-600" />
                    ) : a.thumbs_up === false ? (
                      <ThumbsDown className="h-4 w-4 text-red-500" />
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {a.rating != null ? (
                      <span className="flex items-center gap-0.5">
                        <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />
                        <span className="text-xs font-medium">{a.rating}/5</span>
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                    {a.trace_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-2.5 max-w-xs truncate text-xs text-muted-foreground">
                    {a.comment ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(a.created_at)}
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => remove.mutate(a.id)}
                      disabled={remove.isPending}
                      className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                      title="Delete annotation"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
