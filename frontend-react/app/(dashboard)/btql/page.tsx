'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { Code2, Play } from 'lucide-react'
import { toast } from 'sonner'
import type { BTQLResult } from '@/types'

const EXAMPLES = [
  'SELECT * FROM traces WHERE status = "error" LIMIT 10',
  'SELECT model, COUNT(*) as count FROM traces GROUP BY model',
  'SELECT AVG(latency_ms) as avg_latency FROM traces WHERE created_at > NOW() - INTERVAL 7 DAY',
]

export default function BTQLPage() {
  const { project } = useProject()
  const [query, setQuery] = useState(EXAMPLES[0])
  const [result, setResult] = useState<BTQLResult | null>(null)
  const [loading, setLoading] = useState(false)

  async function run() {
    if (!query.trim() || !project) return
    setLoading(true)
    try {
      const res = await api.btql.query(query, project.id)
      setResult(res)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Query failed')
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
      <div className="flex items-center gap-3">
        <Code2 className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-semibold">BTQL Query</h1>
      </div>

      {/* Examples */}
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            onClick={() => setQuery(ex)}
            className="text-xs px-2 py-1 border rounded hover:bg-muted transition-colors font-mono truncate max-w-xs"
          >
            {ex}
          </button>
        ))}
      </div>

      {/* Editor */}
      <div className="rounded-xl border bg-card p-4 space-y-3">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={5}
          className="w-full text-sm px-3 py-2 border rounded-md bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring resize-y"
          spellCheck={false}
        />
        <button
          onClick={run}
          disabled={!query.trim() || loading}
          className="flex items-center gap-2 px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {loading ? 'Running…' : 'Run Query'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 py-2.5 border-b bg-muted/40 flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
              {result.total_rows} rows · {result.execution_time_ms}ms
            </span>
          </div>
          <div className="overflow-auto max-h-[400px]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  {result.columns.map((col) => (
                    <th key={col} className="px-4 py-2 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/20">
                    {(row as unknown[]).map((cell, j) => (
                      <td key={j} className="px-4 py-2 text-sm font-mono whitespace-nowrap">
                        {cell != null ? String(cell) : '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
