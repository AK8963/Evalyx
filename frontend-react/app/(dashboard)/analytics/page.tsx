'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatMs, formatCost } from '@/lib/utils'
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

const METRICS = [
  { key: 'avg_latency', label: 'Avg Latency (ms)' },
  { key: 'total_cost', label: 'Cost (USD)' },
  { key: 'total_tokens', label: 'Total Tokens' },
  { key: 'error_count', label: 'Error Count' },
]

const PERIODS = [7, 14, 30]

export default function AnalyticsPage() {
  const { project } = useProject()
  const [metric, setMetric] = useState('avg_latency')
  const [days, setDays] = useState(7)

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary', project?.id, days],
    queryFn: () => api.analytics.summary(project!.id, days),
    enabled: !!project,
  })

  const { data: tsData } = useQuery({
    queryKey: ['ts', project?.id, metric, days],
    queryFn: () => api.analytics.timeSeries(project!.id, metric, days),
    enabled: !!project,
  })

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project to view analytics
      </div>
    )
  }

  const chartData = (tsData?.series ?? []).map((p: { date: string; value: number }) => ({
    date: new Date(p.date + 'T00:00:00Z').toLocaleDateString('en', { month: 'short', day: 'numeric' }),
    Value: Math.round(p.value * 100) / 100,
  }))

  const modelData = (summary as unknown as { traces_by_model?: Record<string, number> })?.traces_by_model
    ? Object.entries((summary as unknown as { traces_by_model: Record<string, number> }).traces_by_model).map(([name, value]) => ({ name, Traces: value }))
    : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold">Analytics</h1>

        <div className="flex gap-2">
          {PERIODS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-sm rounded-md border transition-colors ${
                days === d ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Summary KPIs */}
      {summary && (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {[
            { label: 'Total Traces', value: summary.total_traces.toLocaleString() },
            { label: 'Success Rate', value: `${(((summary.total_traces - (summary.error_traces ?? 0)) / Math.max(summary.total_traces, 1)) * 100).toFixed(1)}%` },
            { label: 'Avg Latency', value: formatMs(summary.avg_latency_ms) },
            { label: 'Total Cost', value: formatCost(summary.total_cost_usd) },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border bg-card p-4">
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="text-2xl font-bold mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Metric time-series */}
      <div className="rounded-xl border bg-card p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-sm font-medium">Time Series</h2>
          <div className="flex gap-1">
            {METRICS.map((m) => (
              <button
                key={m.key}
                onClick={() => setMetric(m.key)}
                className={`px-2 py-1 text-xs rounded border transition-colors ${
                  metric === m.key ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="lgValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="Value"
                stroke="#8b5cf6"
                fill="url(#lgValue)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
            No data for this period
          </div>
        )}
      </div>

      {/* Model breakdown */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="text-sm font-medium mb-4">Traces by Model</h2>
        {modelData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={modelData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={120} />
              <Tooltip />
              <Bar dataKey="Traces" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
            No model data yet
          </div>
        )}
      </div>
    </div>
  )
}
