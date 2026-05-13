'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import { FileText, Plus, Trash2, Rocket } from 'lucide-react'
import { toast } from 'sonner'
import type { Prompt } from '@/types'

function PromptEditor({
  prompt,
  onClose,
}: {
  prompt: Prompt
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [rendered, setRendered] = useState('')
  const [rendering, setRendering] = useState(false)

  const varNames = prompt.variables ?? []

  async function renderPrompt() {
    setRendering(true)
    try {
      const res = await api.prompts.render(prompt.id, variables)
      setRendered(res.rendered)
    } catch {
      toast.error('Failed to render')
    } finally {
      setRendering(false)
    }
  }

  const deletePrompt = useMutation({
    mutationFn: () => api.prompts.delete(prompt.id),
    onSuccess: () => {
      toast.success('Prompt deleted')
      qc.invalidateQueries({ queryKey: ['prompts'] })
      onClose()
    },
  })

  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-semibold">{prompt.name}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            v{prompt.version} · {prompt.model ?? 'any model'} · {formatDate(prompt.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          {prompt.is_deployed && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-green-100 text-green-700">
              <Rocket className="h-3 w-3" /> Deployed
            </span>
          )}
          <button
            onClick={() => deletePrompt.mutate()}
            className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>
      </div>

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1 uppercase">Template</p>
        <pre className="text-sm bg-muted rounded p-3 whitespace-pre-wrap overflow-auto max-h-40 font-mono">
          {prompt.template}
        </pre>
      </div>

      {varNames.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase">Variables</p>
          {varNames.map((v) => (
            <div key={v} className="flex items-center gap-2">
              <span className="text-xs font-mono bg-muted px-2 py-1 rounded">{`{{${v}}}`}</span>
              <input
                value={variables[v] ?? ''}
                onChange={(e) => setVariables((prev) => ({ ...prev, [v]: e.target.value }))}
                placeholder={`Value for ${v}`}
                className="flex-1 text-sm px-2 py-1 border rounded bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          ))}
          <button
            onClick={renderPrompt}
            disabled={rendering}
            className="px-3 py-1.5 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90 disabled:opacity-50"
          >
            {rendering ? 'Rendering…' : 'Render'}
          </button>
          {rendered && (
            <pre className="text-sm bg-muted rounded p-3 whitespace-pre-wrap">{rendered}</pre>
          )}
        </div>
      )}
    </div>
  )
}

export default function PromptsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Prompt | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', template: '', model: '' })

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ['prompts', project?.id],
    queryFn: () => api.prompts.list(project!.id),
    enabled: !!project,
  })

  const create = useMutation({
    mutationFn: () =>
      api.prompts.create({
        project_id: project!.id,
        name: form.name,
        template: form.template,
        model: form.model || undefined,
        variables: Array.from(form.template.matchAll(/\{\{(\w+)\}\}/g)).map((m) => m[1]),
      }),
    onSuccess: () => {
      toast.success('Prompt created')
      qc.invalidateQueries({ queryKey: ['prompts'] })
      setShowCreate(false)
      setForm({ name: '', template: '', model: '' })
    },
    onError: () => toast.error('Failed to create prompt'),
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
        <h1 className="text-xl font-semibold">Prompts</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Prompt
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="font-medium">New Prompt</h2>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Name (e.g. summarize-v1)"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <input
            value={form.model}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
            placeholder="Model (e.g. gpt-4, optional)"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <textarea
            value={form.template}
            onChange={(e) => setForm((f) => ({ ...f, template: e.target.value }))}
            placeholder="Prompt template. Use {{variable}} for variables."
            rows={5}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring resize-y"
          />
          <p className="text-xs text-muted-foreground">
            Variables detected:{' '}
            {[...form.template.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).join(', ') || 'none'}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.template || create.isPending}
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

      <div className="flex gap-4">
        {/* List */}
        <div className="w-72 shrink-0 space-y-2">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : prompts.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 gap-2 border rounded-xl">
              <FileText className="h-7 w-7 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">No prompts yet</p>
            </div>
          ) : (
            prompts.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelected(selected?.id === p.id ? null : p)}
                className={`w-full text-left rounded-xl border p-3 transition-colors ${
                  selected?.id === p.id ? 'border-primary bg-primary/5' : 'bg-card hover:bg-muted/30'
                }`}
              >
                <div className="flex items-start gap-2">
                  <FileText className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{p.name}</p>
                    <p className="text-xs text-muted-foreground">v{p.version} · {p.model ?? 'any'}</p>
                    {p.is_deployed && (
                      <span className="text-xs text-green-600 flex items-center gap-0.5">
                        <Rocket className="h-3 w-3" /> deployed
                      </span>
                    )}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Detail */}
        {selected && (
          <div className="flex-1">
            <PromptEditor prompt={selected} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
    </div>
  )
}
