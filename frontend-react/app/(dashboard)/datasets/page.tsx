'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { Database, Plus, Upload } from 'lucide-react'
import { toast } from 'sonner'

export default function DatasetsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null)

  const { data: datasets = [], isLoading } = useQuery({
    queryKey: ['datasets', project?.id],
    queryFn: () => api.datasets.list(project!.id),
    enabled: !!project,
  })

  const { data: items = [] } = useQuery({
    queryKey: ['dataset-items', selectedDataset],
    queryFn: () => api.datasets.items(selectedDataset!),
    enabled: !!selectedDataset,
  })

  const create = useMutation({
    mutationFn: () =>
      api.datasets.create({ project_id: project!.id, name, description }),
    onSuccess: () => {
      toast.success('Dataset created')
      qc.invalidateQueries({ queryKey: ['datasets', project?.id] })
      setShowCreate(false)
      setName('')
      setDescription('')
    },
    onError: () => toast.error('Failed to create dataset'),
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
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Datasets</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Dataset
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="font-medium">New Dataset</h2>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Dataset name"
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
              className="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm disabled:opacity-50"
            >
              {create.isPending ? 'Creating…' : 'Create'}
            </button>
            <button onClick={() => setShowCreate(false)} className="px-4 py-1.5 border rounded-md text-sm hover:bg-muted">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex gap-4 min-h-[400px]">
        {/* Dataset list */}
        <div className="w-72 shrink-0 space-y-2">
          {isLoading ? (
            <p className="text-sm text-muted-foreground p-4">Loading…</p>
          ) : datasets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 gap-2 border rounded-xl">
              <Database className="h-7 w-7 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">No datasets</p>
            </div>
          ) : (
            datasets.map((ds) => (
              <button
                key={ds.id}
                onClick={() => setSelectedDataset(ds.id === selectedDataset ? null : ds.id)}
                className={`w-full text-left rounded-xl border p-4 transition-colors ${
                  selectedDataset === ds.id ? 'border-primary bg-primary/5' : 'bg-card hover:bg-muted/30'
                }`}
              >
                <div className="flex items-start gap-3">
                  <Database className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{ds.name}</p>
                    <p className="text-xs text-muted-foreground">
                      v{ds.version} · {ds.item_count ?? 0} items
                    </p>
                    <p className="text-xs text-muted-foreground">{formatDate(ds.created_at)}</p>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Items panel */}
        {selectedDataset && (
          <div className="flex-1 rounded-xl border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b flex items-center justify-between">
              <h2 className="text-sm font-medium">Dataset Items</h2>
              <span className="text-xs text-muted-foreground">{items.length} items</span>
            </div>
            <div className="overflow-auto max-h-[500px]">
              {items.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-40 gap-2">
                  <Upload className="h-7 w-7 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">No items yet. Import traces to populate.</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40">
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">ID</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Input</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Expected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id} className="border-b last:border-0 hover:bg-muted/20">
                        <td className="px-4 py-2 font-mono text-xs">{item.id.slice(0, 8)}…</td>
                        <td className="px-4 py-2 max-w-[200px]">
                          <pre className="text-xs truncate">{JSON.stringify(item.input_data)}</pre>
                        </td>
                        <td className="px-4 py-2 max-w-[200px]">
                          <pre className="text-xs truncate">
                            {item.expected_output ? JSON.stringify(item.expected_output) : '—'}
                          </pre>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
