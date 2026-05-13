'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { toast } from 'sonner'

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'needs_revision'] as const
const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-muted text-muted-foreground',
}

export default function ReviewPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('pending')

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['review', project?.id, statusFilter],
    queryFn: () => api.review.list(project!.id, statusFilter || undefined),
    enabled: !!project,
  })

  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.review.update(id, { status: status as never }),
    onSuccess: () => {
      toast.success('Status updated')
      qc.invalidateQueries({ queryKey: ['review'] })
    },
    onError: () => toast.error('Failed to update'),
  })

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold">Review Queue</h1>
        <div className="flex gap-1">
          {['', ...STATUS_OPTIONS].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 text-sm rounded-md border capitalize transition-colors ${
                statusFilter === s
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'hover:bg-muted'
              }`}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="flex items-center justify-center h-48 border rounded-xl text-muted-foreground">
          No items in this queue
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="rounded-xl border bg-card p-4 flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs text-muted-foreground">
                    {item.trace_id.slice(0, 8)}…
                  </span>
                  <span
                    className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                      PRIORITY_COLORS[item.priority] ?? 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {item.priority}
                  </span>
                  {item.auto_flagged && (
                    <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                      auto-flagged
                    </span>
                  )}
                </div>
                {item.flag_reason && (
                  <p className="text-sm text-muted-foreground mt-1">{item.flag_reason}</p>
                )}
                <p className="text-xs text-muted-foreground mt-1">{formatDate(item.created_at)}</p>
              </div>

              <select
                value={item.status}
                onChange={(e) => update.mutate({ id: item.id, status: e.target.value })}
                className="text-sm border rounded-md px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
