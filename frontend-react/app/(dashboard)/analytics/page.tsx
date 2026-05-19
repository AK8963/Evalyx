'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatMs, formatCost } from '@/lib/utils'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

const METRIC_DEFS = [
  { key: 'avg_latency', label: 'Latency (ms)', color: '#8b5cf6' },
  { key: 'total_cost', label: 'Cost (USD)', color: '#10b981' },
  { key: 'total_tokens', label: 'Tokens', color: '#f59e0b' },
  { key: 'error_count', label: 'Errors', color: '#ef4444' },
  { key: 'trace_count', label: 'Traces', color: '#06b6d4' },
  { key: 'error_rate', label: 'Error Rate', color: '#f97316' },
  { key: 'avg_cost', label: 'Avg Cost', color: '#84cc16' },
]

const TIME_FILTERS = [
  { label: '1hr',  hours: 1 },
  { label: '3hr',  hours: 3 },
  { label: '1d',   days: 1 },
  { label: '3d',   days: 3 },
  { label: '7d',   days: 7 },
  { label: '14d',  days: 14 },
  { label: '30d',  days: 30 },
] as const
type TF = typeof TIME_FILTERS[number]

const CHART_TYPES = ['Area', 'Line', 'Bar'] as const
type CT = typeof CHART_TYPES[number]

function getApiParams(tf: TF): { days?: number; hours?: number } {
  if ('hours' in tf) return { hours: tf.hours }
  return { days: tf.days }
}

export default function AnalyticsPage() {
  const { project } = useProject()
  const [activeFilter, setActiveFilter] = useState<TF>(TIME_FILTERS[4])
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['avg_latency'])
  const [chartType, setChartType] = useState<CT>('Area')
  const apiParams = getApiParams(activeFilter)
  const days = apiParams.days ?? 7
  const hours = apiParams.hours

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary', project?.id, activeFilter.label],
    queryFn: () => api.analytics.summary(project!.id, days, hours),
    enabled: !!project,
  })

  // Fetch each selected metric
  const metricQueries = METRIC_DEFS.map((m) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useQuery({
      queryKey: ['ts', project?.id, m.key, activeFilter.label],
      queryFn: () => api.analytics.timeSeries(project!.id, m.key, days, hours),
      enabled: !!project && selectedMetrics.includes(m.key),
    })
  })

  const { data: modelStats = [] } = useQuery({
    queryKey: ['analytics-models', project?.id, activeFilter.label],
    queryFn: () => api.analytics.models(project!.id, days, hours),
    enabled: !!project,
  })

  if (!project) {
    return <div className="flex items-center justify-center h-64 text-muted-foreground">Select a project to view analytics</div>
  }

  // Build combined chart data
  const baseLabel = (pt: { date?: string; hour?: string }) =>
    pt.hour ?? (pt.date ? new Date(pt.date + 'T00:00:00Z').toLocaleDateString('en', { month: 'short', day: 'numeric' }) : '')

  let chartData: Record<string, string | number>[] = []
  METRIC_DEFS.forEach((m, i) => {
    if (!selectedMetrics.includes(m.key)) return
    const series = metricQueries[i].data?.series ?? []
    if (chartData.length === 0) {
      chartData = series.map((p) => ({ time: baseLabel(p as { date?: string; hour?: string }), [m.label]: Math.round(p.value * 1000) / 1000 }))
    } else {
      series.forEach((p, idx) => {
        if (chartData[idx]) chartData[idx][m.label] = Math.round(p.value * 1000) / 1000
      })
    }
  })

  function toggleMetric(key: string) {
    setSelectedMetrics((prev) =>
      prev.includes(key) ? (prev.length > 1 ? prev.filter((k) => k !== key) : prev) : [...prev, key]
    )
  }

  function renderChart() {
    const selected = METRIC_DEFS.filter((m) => selectedMetrics.includes(m.key))
    const commonProps = { data: chartData, margin: { top: 5, right: 10, bottom: 5, left: 0 } }
    const axisProps = { tick: { fontSize: 11 }, opacity: 0.6 }

    if (chartType === 'Bar') {
      return (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="time" {...axisProps} />
            <YAxis {...axisProps} />
            <Tooltip />
            {selected.length > 1 && <Legend />}
            {selected.map((m) => <Bar key={m.key} dataKey={m.label} fill={m.color} radius={[2, 2, 0, 0]} />)}
          </BarChart>
        </ResponsiveContainer>
      )
    }
    if (chartType === 'Line') {
      return (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="time" {...axisProps} />
            <YAxis {...axisProps} />
            <Tooltip />
            {selected.length > 1 && <Legend />}
            {selected.map((m) => <Line key={m.key} type="monotone" dataKey={m.label} stroke={m.color} strokeWidth={2} dot={false} />)}
          </LineChart>
        </ResponsiveContainer>
      )
    }
    // Area (default)
    return (
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart {...commonProps}>
          <defs>
            {selected.map((m) => (
              <linearGradient key={m.key} id={`lg_${m.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={m.color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={m.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="time" {...axisProps} />
          <YAxis {...axisProps} />
          <Tooltip />
          {selected.length > 1 && <Legend />}
          {selected.map((m) => (
            <Area key={m.key} type="monotone" dataKey={m.label} stroke={m.color} fill={`url(#lg_${m.key})`} strokeWidth={2} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  const modelBarData = modelStats.map((m) => ({ name: m.model, Traces: m.count, 'Avg ms': Math.round(m.avg_latency_ms ?? 0) }))

  return (
    <div className="space-y-5">
      {/* Header + time filter */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
          {TIME_FILTERS.map((tf) => (
            <button key={tf.label} onClick={() => setActiveFilter(tf)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                activeFilter.label === tf.label ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'
              }`}>{tf.label}</button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {[
            { label: 'Total Traces', value: summary.total_traces.toLocaleString() },
            { label: 'Success Rate', value: `${((summary.success_rate ?? (1 - summary.error_rate)) * 100).toFixed(1)}%` },
            { label: 'Avg Latency', value: formatMs(summary.avg_latency_ms) },
            { label: 'Total Cost', value: formatCost(summary.total_cost_usd) },
            { label: 'Error Rate', value: `${(summary.error_rate * 100).toFixed(1)}%` },
            { label: 'P95 Latency', value: summary.p95_latency_ms != null ? formatMs(summary.p95_latency_ms) : 'N/A' },
            { label: 'P99 Latency', value: summary.p99_latency_ms != null ? formatMs(summary.p99_latency_ms) : 'N/A' },
            { label: 'Cost / 1K Tokens', value: summary.cost_per_1k_tokens != null ? `$${summary.cost_per_1k_tokens.toFixed(4)}` : 'N/A' },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border bg-card p-4">
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="text-2xl font-bold mt-1">{value}</p>
            </div>
          ))}
        </div>
      )}
      {/* Token Breakdown */}
      {summary && (summary.prompt_tokens != null || summary.completion_tokens != null) && (
        <div className="rounded-xl border bg-card p-5">
          <h2 className="text-sm font-medium mb-3">Token Breakdown</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Total Tokens', value: (summary.total_tokens ?? 0).toLocaleString() },
              { label: 'Prompt Tokens', value: (summary.prompt_tokens ?? 0).toLocaleString() },
              { label: 'Completion Tokens', value: (summary.completion_tokens ?? 0).toLocaleString() },
              {
                label: 'Completion Ratio',
                value: (summary.prompt_tokens ?? 0) + (summary.completion_tokens ?? 0) > 0
                  ? `${(((summary.completion_tokens ?? 0) / ((summary.prompt_tokens ?? 0) + (summary.completion_tokens ?? 0))) * 100).toFixed(1)}%`
                  : 'N/A',
              },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg bg-muted/40 p-3">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="text-lg font-semibold mt-0.5">{value}</p>
              </div>
            ))}
          </div>
          {/* Stacked bar showing prompt vs completion */}
          {(summary.prompt_tokens ?? 0) + (summary.completion_tokens ?? 0) > 0 && (
            <div className="mt-3">
              <div className="flex rounded overflow-hidden h-4">
                <div
                  className="bg-violet-500 transition-all"
                  style={{ width: `${((summary.prompt_tokens ?? 0) / ((summary.prompt_tokens ?? 0) + (summary.completion_tokens ?? 0))) * 100}%` }}
                  title={`Prompt: ${(summary.prompt_tokens ?? 0).toLocaleString()}`}
                />
                <div
                  className="bg-emerald-500 transition-all"
                  style={{ width: `${((summary.completion_tokens ?? 0) / ((summary.prompt_tokens ?? 0) + (summary.completion_tokens ?? 0))) * 100}%` }}
                  title={`Completion: ${(summary.completion_tokens ?? 0).toLocaleString()}`}
                />
              </div>
              <div className="flex gap-4 mt-1.5 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-violet-500" /> Prompt</span>
                <span className="flex items-center gap-1"><span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500" /> Completion</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Multi-metric chart */}
      <div className="rounded-xl border bg-card p-5">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="text-sm font-medium">Time Series</h2>
          <div className="flex items-center gap-3">
            {/* Chart type */}
            <div className="flex gap-1 bg-muted rounded-md p-0.5">
              {CHART_TYPES.map((ct) => (
                <button key={ct} onClick={() => setChartType(ct)}
                  className={`px-2.5 py-0.5 rounded text-xs font-medium transition-colors ${chartType === ct ? 'bg-background shadow' : 'text-muted-foreground'}`}>
                  {ct}
                </button>
              ))}
            </div>
          </div>
        </div>
        {/* Metric toggles */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          {METRIC_DEFS.map((m) => {
            const active = selectedMetrics.includes(m.key)
            return (
              <button key={m.key} onClick={() => toggleMetric(m.key)}
                style={active ? { borderColor: m.color, color: m.color, backgroundColor: m.color + '18' } : {}}
                className={`px-2.5 py-1 rounded-full border text-xs font-medium transition-colors ${active ? '' : 'border-border text-muted-foreground hover:bg-muted'}`}>
                {m.label}
              </button>
            )
          })}
        </div>
        {chartData.length > 0 ? renderChart() : (
          <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">No data for this period</div>
        )}
      </div>

      {/* Model breakdown */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="text-sm font-medium mb-4">Traces by Model</h2>
        {modelBarData.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={Math.max(120, modelBarData.length * 36)}>
              <BarChart data={modelBarData} layout="vertical" margin={{ left: 0, right: 20, top: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={130} />
                <Tooltip />
                <Bar dataKey="Traces" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4 divide-y rounded-xl border overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 text-xs text-muted-foreground font-medium bg-muted/40">
                <span>Model</span>
                <div className="flex gap-6">
                  <span>Traces</span>
                  <span>Avg Latency</span>
                  <span>Err Rate</span>
                  <span>Avg Cost</span>
                  <span>Total Tokens</span>
                </div>
              </div>
              {modelStats.map((m) => (
                <div key={m.model} className="flex items-center justify-between px-4 py-2.5 text-sm hover:bg-muted/30">
                  <span className="font-mono text-xs text-muted-foreground">{m.model}</span>
                  <div className="flex gap-6 text-xs">
                    <span>{m.count}</span>
                    <span>{formatMs(m.avg_latency_ms)}</span>
                    <span className={m.error_rate != null && m.error_rate > 0.1 ? 'text-red-500 font-medium' : ''}>
                      {m.error_rate != null ? `${(m.error_rate * 100).toFixed(1)}%` : '--'}
                    </span>
                    <span>{formatCost(m.avg_cost_usd)}</span>
                    <span>{(m.total_tokens ?? 0).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">No model data yet</div>
        )}
      </div>
    </div>
  )
}

