'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { FlaskConical, Plus } from 'lucide-react'
import { toast } from 'sonner'

export default function ExperimentsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const { data: experiments = [], isLoading } = useQuery({
    queryKey: ['experiments', project?.id],
    queryFn: () => api.experiments.list(project!.id),
    enabled: !!project,
  })

  const create = useMutation({
    mutationFn: () =>
      api.experiments.create({ project_id: project!.id, name, description }),
    onSuccess: () => {
      toast.success('Experiment created')
      qc.invalidateQueries({ queryKey: ['experiments', project?.id] })
      setShowCreate(false)
      setName('')
      setDescription('')
    },
    onError: () => toast.error('Failed to create experiment'),
  })

  const statusColor: Record<string, string> = {
    draft: 'bg-yellow-100 text-yellow-700',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
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
        <h1 className="text-xl font-semibold">Experiments</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Experiment
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="font-medium">New Experiment</h2>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Experiment name"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-none"
          />
          <div className="flex gap-2">
            <button
              onClick={() => create.mutate()}
              disabled={!name || create.isPending}
              className="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
            >
              {create.isPending ? 'Creating…' : 'Create'}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-1.5 border rounded-md text-sm hover:bg-muted"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-40 text-muted-foreground">
          Loading…
        </div>
      ) : experiments.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl">
          <FlaskConical className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground">No experiments yet</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {experiments.map((exp) => (
            <div key={exp.id} className="rounded-xl border bg-card p-4 flex items-start gap-4">
              <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <FlaskConical className="h-4 w-4 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium">{exp.name}</p>
                  <span
                    className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                      statusColor[exp.status] ?? 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {exp.status}
                  </span>
                </div>
                {exp.description && (
                  <p className="text-sm text-muted-foreground mt-0.5 truncate">{exp.description}</p>
                )}
                <p className="text-xs text-muted-foreground mt-1">{formatDate(exp.created_at)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
