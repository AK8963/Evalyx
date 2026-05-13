'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { ThumbsUp, ThumbsDown, Star, MessageSquare } from 'lucide-react'
import { toast } from 'sonner'

export default function AnnotationsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [traceId, setTraceId] = useState('')
  const [comment, setComment] = useState('')

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

  const annotate = useMutation({
    mutationFn: (type: string) =>
      api.annotations.create({
        trace_id: traceId,
        project_id: project!.id,
        annotation_type: type as never,
        comment: comment || undefined,
      }),
    onSuccess: () => {
      toast.success('Annotation saved')
      qc.invalidateQueries({ queryKey: ['annotations', project?.id] })
      setTraceId('')
      setComment('')
    },
    onError: () => toast.error('Failed to save annotation'),
  })

  const typeIcon: Record<string, React.ReactNode> = {
    thumbs_up: <ThumbsUp className="h-3.5 w-3.5" />,
    thumbs_down: <ThumbsDown className="h-3.5 w-3.5" />,
    rating: <Star className="h-3.5 w-3.5" />,
    comment: <MessageSquare className="h-3.5 w-3.5" />,
    label: <span className="text-xs">🏷</span>,
  }

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
      {summary && (
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(summary as Record<string, number>)
            .slice(0, 3)
            .map(([k, v]) => (
              <div key={k} className="rounded-xl border bg-card p-4">
                <p className="text-sm text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</p>
                <p className="text-2xl font-bold mt-0.5">{v}</p>
              </div>
            ))}
        </div>
      )}

      {/* Quick annotate */}
      <div className="rounded-xl border bg-card p-5 space-y-3">
        <h2 className="font-medium text-sm">Quick Annotate</h2>
        <input
          value={traceId}
          onChange={(e) => setTraceId(e.target.value)}
          placeholder="Trace ID"
          className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono"
        />
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Comment (optional)"
          rows={2}
          className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-none"
        />
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => annotate.mutate('thumbs_up')}
            disabled={!traceId || annotate.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-sm hover:bg-green-50 hover:border-green-300 hover:text-green-700 disabled:opacity-50 transition-colors"
          >
            <ThumbsUp className="h-4 w-4" /> Thumbs Up
          </button>
          <button
            onClick={() => annotate.mutate('thumbs_down')}
            disabled={!traceId || annotate.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-sm hover:bg-red-50 hover:border-red-300 hover:text-red-700 disabled:opacity-50 transition-colors"
          >
            <ThumbsDown className="h-4 w-4" /> Thumbs Down
          </button>
          <button
            onClick={() => annotate.mutate('comment')}
            disabled={!traceId || !comment || annotate.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded-md text-sm hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 disabled:opacity-50 transition-colors"
          >
            <MessageSquare className="h-4 w-4" /> Add Comment
          </button>
        </div>
      </div>

      {/* Annotation list */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b">
          <h2 className="text-sm font-medium">Recent Annotations</h2>
        </div>
        {isLoading ? (
          <p className="px-5 py-8 text-sm text-muted-foreground">Loading…</p>
        ) : annotations.length === 0 ? (
          <p className="px-5 py-8 text-sm text-muted-foreground text-center">No annotations yet</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                {['Type', 'Trace ID', 'Comment', 'Time'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {annotations.map((a) => (
                <tr key={a.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-2.5">
                    <span className="flex items-center gap-1.5">
                      {typeIcon[a.annotation_type] ?? '—'}
                      <span className="text-xs capitalize">{a.annotation_type.replace(/_/g, ' ')}</span>
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs">{a.trace_id.slice(0, 8)}…</td>
                  <td className="px-4 py-2.5 max-w-xs truncate text-muted-foreground">
                    {a.comment ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(a.created_at)}
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
