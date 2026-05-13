'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { Hash } from 'lucide-react'

export default function TopicsPage() {
  const { project } = useProject()
  const [extracting, setExtracting] = useState(false)

  const { data: topics = [], isLoading, refetch } = useQuery({
    queryKey: ['topics', project?.id],
    queryFn: () => api.topics.list(project!.id),
    enabled: !!project,
  })

  async function extract() {
    if (!project) return
    setExtracting(true)
    try {
      await api.topics.extract(project.id)
      refetch()
    } finally {
      setExtracting(false)
    }
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
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Topics</h1>
        <button
          onClick={extract}
          disabled={extracting}
          className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          {extracting ? 'Extracting…' : 'Extract Topics'}
        </button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : topics.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl">
          <Hash className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground">No topics extracted yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
          {topics.map((t) => (
            <div key={t.id} className="rounded-xl border bg-card p-4">
              <div className="flex items-start gap-3">
                <Hash className="h-4 w-4 text-primary mt-0.5" />
                <div>
                  <p className="font-medium">{t.name}</p>
                  {t.description && (
                    <p className="text-sm text-muted-foreground mt-0.5">{t.description}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">{t.trace_count} traces</p>
                  {t.keywords && t.keywords.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {t.keywords.slice(0, 5).map((kw) => (
                        <span key={kw} className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
