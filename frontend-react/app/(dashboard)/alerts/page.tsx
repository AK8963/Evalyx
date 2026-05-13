'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { Bell, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

export default function AlertsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', condition: '', threshold: '', channel: 'email' })

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['alerts', project?.id],
    queryFn: () => api.alerts.list(project!.id),
    enabled: !!project,
  })

  const create = useMutation({
    mutationFn: () =>
      api.alerts.create({
        project_id: project!.id,
        name: form.name,
        condition: form.condition,
        threshold: parseFloat(form.threshold) || 0,
        channel: form.channel as never,
        is_active: true,
      }),
    onSuccess: () => {
      toast.success('Alert created')
      qc.invalidateQueries({ queryKey: ['alerts'] })
      setShowCreate(false)
      setForm({ name: '', condition: '', threshold: '', channel: 'email' })
    },
    onError: () => toast.error('Failed to create alert'),
  })

  const toggle = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.alerts.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  const del = useMutation({
    mutationFn: (id: string) => api.alerts.delete(id),
    onSuccess: () => {
      toast.success('Alert deleted')
      qc.invalidateQueries({ queryKey: ['alerts'] })
    },
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
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Alerts</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Alert
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="font-medium">New Alert Rule</h2>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Alert name"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <input
            value={form.condition}
            onChange={(e) => setForm((f) => ({ ...f, condition: e.target.value }))}
            placeholder="Condition (e.g. error_rate > threshold)"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono"
          />
          <div className="flex gap-3">
            <input
              type="number"
              value={form.threshold}
              onChange={(e) => setForm((f) => ({ ...f, threshold: e.target.value }))}
              placeholder="Threshold"
              className="flex-1 px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <select
              value={form.channel}
              onChange={(e) => setForm((f) => ({ ...f, channel: e.target.value }))}
              className="flex-1 px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {['email', 'webhook', 'slack'].map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.condition || create.isPending}
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

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : alerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl">
          <Bell className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground">No alerts configured</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div key={alert.id} className="rounded-xl border bg-card p-4 flex items-center gap-4">
              <Bell className={`h-4 w-4 shrink-0 ${alert.is_active ? 'text-primary' : 'text-muted-foreground'}`} />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{alert.name}</p>
                <p className="text-xs text-muted-foreground font-mono">{alert.condition} &gt; {alert.threshold}</p>
                <p className="text-xs text-muted-foreground">Channel: {alert.channel}</p>
              </div>
              <button
                onClick={() => toggle.mutate({ id: alert.id, is_active: !alert.is_active })}
                className={`relative w-9 h-5 rounded-full transition-colors ${alert.is_active ? 'bg-primary' : 'bg-muted'}`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${alert.is_active ? 'translate-x-4' : ''}`}
                />
              </button>
              <button
                onClick={() => del.mutate(alert.id)}
                className="text-muted-foreground hover:text-destructive transition-colors"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
