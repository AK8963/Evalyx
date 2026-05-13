'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatMs, formatCost, formatDate, statusBadgeVariant } from '@/lib/utils'
import { Search } from 'lucide-react'
import type { Trace } from '@/types'

function Badge({ variant, children }: { variant: string; children: React.ReactNode }) {
  const cls: Record<string, string> = {
    default: 'bg-green-100 text-green-700',
    destructive: 'bg-red-100 text-red-700',
    outline: 'bg-yellow-100 text-yellow-700',
    secondary: 'bg-muted text-muted-foreground',
  }
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls[variant] ?? cls.secondary}`}>
      {children}
    </span>
  )
}

export default function SearchPage() {
  const { project } = useProject()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Trace[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  async function doSearch() {
    if (!query.trim() || !project) return
    setLoading(true)
    setSearched(true)
    try {
      const res = await api.search.traces(project.id, query)
      setResults(res)
    } finally {
      setLoading(false)
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
      <h1 className="text-xl font-semibold">Deep Search</h1>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
            placeholder="Search traces by content, model, metadata…"
            className="w-full pl-10 pr-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <button
          onClick={doSearch}
          disabled={!query.trim() || loading}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      {searched && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 py-2.5 border-b bg-muted/40 text-xs font-medium text-muted-foreground">
            {loading ? 'Searching…' : `${results.length} results`}
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                {['ID', 'Model', 'Status', 'Latency', 'Cost', 'Time'].map((h) => (
                  <th key={h} className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.length === 0 && !loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No results found
                  </td>
                </tr>
              ) : (
                results.map((t) => (
                  <tr key={t.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2 font-mono text-xs">{t.id.slice(0, 8)}…</td>
                    <td className="px-4 py-2">{t.model ?? '—'}</td>
                    <td className="px-4 py-2">
                      <Badge variant={statusBadgeVariant(t.status)}>{t.status}</Badge>
                    </td>
                    <td className="px-4 py-2">{formatMs(t.latency_ms)}</td>
                    <td className="px-4 py-2">{formatCost(t.cost_usd)}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">{formatDate(t.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
