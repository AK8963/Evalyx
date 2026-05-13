'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { GitCompare, Play } from 'lucide-react'
import { toast } from 'sonner'

export default function RemoteEvalsPage() {
  const { project } = useProject()
  const [runConfig, setRunConfig] = useState('')

  const { data: evals = [], isLoading } = useQuery({
    queryKey: ['remote-evals', project?.id],
    queryFn: () => api.remoteEvals.list(project!.id),
    enabled: !!project,
  })

  const run = useMutation({
    mutationFn: () => {
      const config = JSON.parse(runConfig)
      return api.remoteEvals.run({ project_id: project!.id, ...config })
    },
    onSuccess: () => toast.success('Remote eval triggered'),
    onError: (e: unknown) => toast.error(e instanceof Error ? e.message : 'Failed to trigger eval'),
  })

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <h1 className="text-xl font-semibold">Remote Evals</h1>

      {/* Trigger */}
      <div className="rounded-xl border bg-card p-5 space-y-3">
        <h2 className="font-medium text-sm">Trigger Remote Eval</h2>
        <textarea
          value={runConfig}
          onChange={(e) => setRunConfig(e.target.value)}
          placeholder='{"dataset_id": "...", "model": "gpt-4", "scorers": [...]}'
          rows={4}
          className="w-full text-sm px-3 py-2 border rounded-md bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring resize-y"
        />
        <button
          onClick={() => run.mutate()}
          disabled={!runConfig.trim() || run.isPending}
          className="flex items-center gap-2 px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {run.isPending ? 'Triggering…' : 'Run'}
        </button>
      </div>

      {/* History */}
      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (evals as unknown[]).length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 gap-3 border rounded-xl">
          <GitCompare className="h-7 w-7 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No remote evals yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {(evals as { id: string; status: string; created_at: string }[]).map((e) => (
            <div key={e.id} className="rounded-xl border bg-card p-4 flex items-center gap-4">
              <GitCompare className="h-4 w-4 text-primary" />
              <p className="font-mono text-xs flex-1">{e.id.slice(0, 12)}…</p>
              <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground capitalize">
                {e.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
