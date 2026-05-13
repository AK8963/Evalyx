'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { GitCompare } from 'lucide-react'

export default function ABTestsPage() {
  const { project } = useProject()

  const { data: tests = [], isLoading } = useQuery({
    queryKey: ['abtests', project?.id],
    queryFn: () => api.abTests.list(project!.id),
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
      <h1 className="text-xl font-semibold">A/B Tests</h1>
      <p className="text-sm text-muted-foreground">
        Compare model variants, prompts, or configurations using statistical A/B testing.
      </p>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (tests as unknown[]).length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl">
          <GitCompare className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground">No A/B tests yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {(tests as { id: string; name: string; status: string }[]).map((test) => (
            <div key={test.id} className="rounded-xl border bg-card p-4 flex items-center gap-4">
              <GitCompare className="h-4 w-4 text-primary" />
              <div className="flex-1">
                <p className="font-medium text-sm">{test.name}</p>
              </div>
              <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground capitalize">
                {test.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
