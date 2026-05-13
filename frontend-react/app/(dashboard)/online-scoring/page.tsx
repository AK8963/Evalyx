'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { Target } from 'lucide-react'

export default function OnlineScoringPage() {
  const { project } = useProject()

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ['online-scoring', project?.id],
    queryFn: () => api.onlineScoring.list(project!.id),
    enabled: !!project,
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
      <h1 className="text-xl font-semibold">Online Scoring</h1>
      <p className="text-sm text-muted-foreground">
        Configure real-time evaluation rules applied automatically to incoming traces.
      </p>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (rules as unknown[]).length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl">
          <Target className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground">No online scoring rules yet</p>
          <p className="text-xs text-muted-foreground">Create rules via the Evaluations API</p>
        </div>
      ) : (
        <div className="space-y-2">
          {(rules as { id: string; name: string; scorer_type: string; is_active: boolean }[]).map((rule) => (
            <div key={rule.id} className="rounded-xl border bg-card p-4 flex items-center gap-4">
              <Target className="h-4 w-4 text-primary" />
              <div className="flex-1">
                <p className="font-medium text-sm">{rule.name}</p>
                <p className="text-xs text-muted-foreground">{rule.scorer_type}</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ${rule.is_active ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground'}`}>
                {rule.is_active ? 'active' : 'inactive'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
