'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { EyeOff, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

export default function MaskingPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [pattern, setPattern] = useState('')
  const [type, setType] = useState('regex')

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ['masking'],
    queryFn: () => api.masking.list(),
  })

  const create = useMutation({
    mutationFn: () => api.masking.create({ pattern, type, replacement: '[REDACTED]' }),
    onSuccess: () => {
      toast.success('Masking rule created')
      qc.invalidateQueries({ queryKey: ['masking'] })
      setShowCreate(false)
      setPattern('')
    },
    onError: () => toast.error('Failed to create rule'),
  })

  const del = useMutation({
    mutationFn: (id: string) => api.masking.delete(id),
    onSuccess: () => {
      toast.success('Rule deleted')
      qc.invalidateQueries({ queryKey: ['masking'] })
    },
  })

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Data Masking</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Rule
        </button>
      </div>

      <p className="text-sm text-muted-foreground">
        Define patterns to automatically redact sensitive data (PII, secrets) from traces before storage.
      </p>

      {showCreate && (
        <div className="rounded-xl border bg-card p-5 space-y-3">
          <h2 className="font-medium">New Masking Rule</h2>
          <div className="flex gap-2">
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="regex">Regex</option>
              <option value="field">Field name</option>
              <option value="keyword">Keyword</option>
            </select>
            <input
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder={type === 'regex' ? '\\b\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}\\b' : 'field_name or keyword'}
              className="flex-1 px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <p className="text-xs text-muted-foreground">Matches will be replaced with [REDACTED]</p>
          <div className="flex gap-2">
            <button
              onClick={() => create.mutate()}
              disabled={!pattern || create.isPending}
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
      ) : (rules as { id: string; pattern: string; type: string }[]).length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl">
          <EyeOff className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground">No masking rules yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {(rules as { id: string; pattern: string; type: string }[]).map((rule) => (
            <div key={rule.id} className="rounded-xl border bg-card p-4 flex items-center gap-4">
              <EyeOff className="h-4 w-4 text-primary shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted-foreground capitalize">{rule.type}</p>
                <p className="font-mono text-sm truncate">{rule.pattern}</p>
              </div>
              <button
                onClick={() => del.mutate(rule.id)}
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
