'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatMs, formatCost, formatDate, statusBadgeVariant } from '@/lib/utils'
import {
  Activity,
  CheckCircle2,
  DollarSign,
  Clock,
  TrendingUp,
  Zap,
  AlertTriangle,
  BarChart2,
} from 'lucide-react'
import {
  AreaChart, Area,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'

const COLORS = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6']

function StatCard({
  label, value, icon: Icon, sub, trend, trendUp,
}: {
  label: string; value: string | number; icon: React.ElementType
  sub?: string; trend?: string; trendUp?: boolean
}) {
  return (
    <div className="rounded-xl border bg-card p-5 flex gap-4 items-start">
      <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-muted-foreground truncate">{label}</p>
        <p className="text-2xl font-bold mt-0.5 truncate">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
        {trend && (
          <p className={`text-xs mt-1 font-medium ${trendUp ? 'text-green-600' : 'text-red-500'}`}>
            {trend}
          </p>
        )}
      </div>
    </div>
  )
}

function ChartCard({ title, subtitle, children, full }: {
  title: string; subtitle?: string; children: React.ReactNode; full?: boolean
}) {
  return (
    <div className={`rounded-xl border bg-card p-5 ${full ? 'col-span-full' : ''}`}>
      <div className="mb-4">
        <h2 className="text-sm font-semibold">{title}</h2>
        {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  )
}

function EmptyChart() {
  return (
    <div className="h-44 flex items-center justify-center text-sm text-muted-foreground">
      No data yet
    </div>
  )
}

function Badge({ variant, children }: { variant: string; children: React.ReactNode }) {
  const cls = {
    default: 'bg-green-100 text-green-700',
    destructive: 'bg-red-100 text-red-700',
    outline: 'bg-yellow-100 text-yellow-700',
    secondary: 'bg-muted text-muted-foreground',
  }[variant] ?? 'bg-muted text-muted-foreground'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {children}
    </span>
  )
}

function ChartGradients() {
  return (
    <defs>
      <linearGradient id="gLatency" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.25} />
        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
      </linearGradient>
      <linearGradient id="gCount" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.25} />
        <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
      </linearGradient>
      <linearGradient id="gCost" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
      </linearGradient>
      <linearGradient id="gTokens" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.25} />
        <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
      </linearGradient>
      <linearGradient id="gErrors" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.25} />
        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
      </linearGradient>
    </defs>
  )
}

function toDateLabel(date: string) {
  return new Date(date + 'T00:00:00Z').toLocaleDateString('en', { month: 'short', day: 'numeric' })
}

const TIME_FILTERS = [
  { label: '1hr',  hours: 1 },
  { label: '3hr',  hours: 3 },
  { label: '1d',   days: 1 },
  { label: '3d',   days: 3 },
  { label: '7d',   days: 7 },
  { label: 'All', hours: undefined, days: undefined },
] as const

type TF = typeof TIME_FILTERS[number]

function getApiParams(tf: TF): { days?: number; hours?: number } {
  if ('hours' in tf && (tf as {hours?: number}).hours !== undefined) return { hours: (tf as {hours?: number}).hours }
  if ('days' in tf && (tf as {days?: number}).days !== undefined) return { days: (tf as {days?: number}).days }
  return {}  // All = no time filter
}

export default function DashboardPage() {
  const { project } = useProject()
  const [activeFilter, setActiveFilter] = useState<TF>(TIME_FILTERS[4])
  const apiParams = getApiParams(activeFilter)

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary', project?.id, activeFilter.label],
    queryFn: () => api.analytics.summary(project!.id, apiParams.days, apiParams.hours),
    enabled: !!project,
  })

  const { data: latencyTs } = useQuery({
    queryKey: ['ts-avg_latency', project?.id, activeFilter.label],
    queryFn: () => api.analytics.timeSeries(project!.id, 'avg_latency', apiParams.days, apiParams.hours),
    enabled: !!project,
  })
  const { data: countTs } = useQuery({
    queryKey: ['ts-trace_count', project?.id, activeFilter.label],
    queryFn: () => api.analytics.timeSeries(project!.id, 'trace_count', apiParams.days, apiParams.hours),
    enabled: !!project,
  })
  const { data: costTs } = useQuery({
    queryKey: ['ts-total_cost', project?.id, activeFilter.label],
    queryFn: () => api.analytics.timeSeries(project!.id, 'total_cost', apiParams.days, apiParams.hours),
    enabled: !!project,
  })
  const { data: tokenTs } = useQuery({
    queryKey: ['ts-total_tokens', project?.id, activeFilter.label],
    queryFn: () => api.analytics.timeSeries(project!.id, 'total_tokens', apiParams.days, apiParams.hours),
    enabled: !!project,
  })
  const { data: errorTs } = useQuery({
    queryKey: ['ts-error_count', project?.id, activeFilter.label],
    queryFn: () => api.analytics.timeSeries(project!.id, 'error_count', apiParams.days, apiParams.hours),
    enabled: !!project,
  })

  const { data: modelStats = [] } = useQuery({
    queryKey: ['analytics-models', project?.id, activeFilter.label],
    queryFn: () => api.analytics.models(project!.id, apiParams.days, apiParams.hours),
    enabled: !!project,
  })

  const { data: traces = [] } = useQuery({
    queryKey: ['traces-recent', project?.id],
    queryFn: () => api.traces.list({ project_id: project!.id, limit: 10 }),
    enabled: !!project,
  })

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <TrendingUp className="h-10 w-10 text-muted-foreground/40" />
        <p className="text-muted-foreground">Select or create a project to view the dashboard</p>
      </div>
    )
  }

  const filterPills = (
    <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
      {TIME_FILTERS.map((tf) => (
        <button key={tf.label} onClick={() => setActiveFilter(tf)}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            activeFilter.label === tf.label
              ? 'bg-background shadow text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}>{tf.label}</button>
      ))}
    </div>
  )

  const errorCount = summary?.error_traces ?? summary?.error_count ?? 0
  const successRate = summary
    ? ((summary.total_traces - errorCount) / Math.max(summary.total_traces, 1)) * 100
    : 0

  // Time series data
  const tsLatency = (latencyTs?.series ?? []).map((p) => ({ time: toDateLabel(p.date), value: Math.round(p.value) }))
  const tsCount   = (countTs?.series  ?? []).map((p) => ({ time: toDateLabel(p.date), value: Math.round(p.value) }))
  const tsCost    = (costTs?.series   ?? []).map((p) => ({ time: toDateLabel(p.date), value: +(p.value).toFixed(4) }))
  const tsTokens  = (tokenTs?.series  ?? []).map((p) => ({ time: toDateLabel(p.date), value: Math.round(p.value) }))
  const tsErrors  = (errorTs?.series  ?? []).map((p) => ({ time: toDateLabel(p.date), value: Math.round(p.value) }))

  // Merge time series for combined chart
  const combinedTs = tsCount.map((c, i) => ({
    time: c.time,
    Traces: c.value,
    Errors: tsErrors[i]?.value ?? 0,
  }))

  // Model breakdown for pie
  const pieData = modelStats.length > 0
    ? modelStats.map((m) => ({ name: m.model, value: m.count }))
    : []

  // Model performance bar data
  const modelBarData = modelStats.map((m) => ({
    model: m.model.length > 12 ? m.model.slice(0, 12) + 'ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦' : m.model,
    'Avg Latency (ms)': Math.round(m.avg_latency_ms ?? 0),
    'Error %': +(m.error_rate * 100).toFixed(1),
    'Cost/trace ($)': +(m.avg_cost_usd ?? 0).toFixed(4),
  }))

  const axisStyle = { fontSize: 11, fill: '#888' }
  const tooltipStyle = { fontSize: 12, borderRadius: 8 }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Overview · {activeFilter.label}</p>
        </div>
        {filterPills}
      </div>

      {/* Row 1: KPI Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Total Traces"  value={(summary?.total_traces ?? 0).toLocaleString()} icon={Activity} />
        <StatCard label="Success Rate"  value={`${successRate.toFixed(1)}%`} icon={CheckCircle2} sub={`${errorCount} errors`} />
        <StatCard label="Avg Latency"   value={formatMs(summary?.avg_latency_ms)} icon={Clock} />
        <StatCard label="Total Cost"    value={formatCost(summary?.total_cost_usd)} icon={DollarSign} />
      </div>
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Total Tokens"  value={(summary?.total_tokens ?? 0).toLocaleString()} icon={Zap} />
        <StatCard label="Error Count"   value={errorCount.toLocaleString()} icon={AlertTriangle} sub={`${(summary?.error_rate ?? 0 * 100).toFixed(1)}% error rate`} />
        <StatCard label="Models Active" value={modelStats.length} icon={BarChart2} sub="last 7 days" />
        <StatCard label="Cost / Trace"  value={summary?.total_traces ? formatCost((summary.total_cost_usd ?? 0) / summary.total_traces) : 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'} icon={TrendingUp} sub="average" />
      </div>

      {/* Row 2: Trace Volume + Error trend (combined) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="Daily Trace Volume" subtitle="Success vs errors per day">
          {combinedTs.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={combinedTs} barGap={2}>
                <ChartGradients />
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="time" tick={axisStyle} />
                <YAxis tick={axisStyle} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend iconSize={10} />
                <Bar dataKey="Traces" fill="#06b6d4" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Errors" fill="#ef4444" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </ChartCard>

        <ChartCard title="Avg Latency Trend" subtitle="Milliseconds per day">
          {tsLatency.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <AreaChart data={tsLatency}>
                <ChartGradients />
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="time" tick={axisStyle} />
                <YAxis tick={axisStyle} unit="ms" />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} ms`, 'Latency']} />
                <Area type="monotone" dataKey="value" name="Latency" stroke="#8b5cf6" fill="url(#gLatency)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </ChartCard>
      </div>

      {/* Row 3: Cost trend + Token usage */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="Daily Cost (USD)" subtitle="Spend trend over 7 days">
          {tsCost.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <AreaChart data={tsCost}>
                <ChartGradients />
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="time" tick={axisStyle} />
                <YAxis tick={axisStyle} tickFormatter={(v) => `$${v}`} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`$${v}`, 'Cost']} />
                <Area type="monotone" dataKey="value" name="Cost" stroke="#10b981" fill="url(#gCost)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </ChartCard>

        <ChartCard title="Token Usage" subtitle="Total tokens consumed per day">
          {tsTokens.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <AreaChart data={tsTokens}>
                <ChartGradients />
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="time" tick={axisStyle} />
                <YAxis tick={axisStyle} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${Number(v).toLocaleString()}`, 'Tokens']} />
                <Area type="monotone" dataKey="value" name="Tokens" stroke="#f59e0b" fill="url(#gTokens)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </ChartCard>
      </div>

      {/* Row 4: Model distribution + Avg latency per model */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="Traces by Model" subtitle="Distribution across models">
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <ChartGradients />
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} dataKey="value" paddingAngle={2}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend iconSize={10} />
              </PieChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </ChartCard>

        <ChartCard title="Avg Latency by Model" subtitle="Milliseconds per model">
          {modelBarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modelBarData} layout="vertical" margin={{ left: 10 }}>
                <ChartGradients />
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} horizontal={false} />
                <XAxis type="number" tick={axisStyle} unit="ms" />
                <YAxis type="category" dataKey="model" tick={axisStyle} width={110} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} ms`, 'Avg Latency']} />
                <Bar dataKey="Avg Latency (ms)" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyChart />}
        </ChartCard>
      </div>

      {/* Row 5: Model performance table */}
      {modelStats.length > 0 && (
        <div className="rounded-xl border bg-card">
          <div className="px-5 py-4 border-b flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Model Performance Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  {['Model', 'Traces', 'Avg Latency', 'Avg Cost', 'Total Tokens', 'Error Rate'].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {modelStats.map((m) => (
                  <tr key={m.model} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-2.5 font-medium">{m.model}</td>
                    <td className="px-4 py-2.5">{m.count.toLocaleString()}</td>
                    <td className="px-4 py-2.5">{formatMs(m.avg_latency_ms ?? undefined)}</td>
                    <td className="px-4 py-2.5">{formatCost(m.avg_cost_usd)}</td>
                    <td className="px-4 py-2.5">{m.total_tokens.toLocaleString()}</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        m.error_rate > 0.05 ? 'bg-red-100 text-red-700' :
                        m.error_rate > 0 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {(m.error_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Row 6: Error count sparkline */}
      {tsErrors.some(e => e.value > 0) && (
        <ChartCard title="Error Count Over Time" subtitle="Daily failures">
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={tsErrors}>
              <ChartGradients />
              <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
              <XAxis dataKey="time" tick={axisStyle} />
              <YAxis tick={axisStyle} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => [v, 'Errors']} />
              <Area type="monotone" dataKey="value" name="Errors" stroke="#ef4444" fill="url(#gErrors)" strokeWidth={2} dot={{ fill: '#ef4444', r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Row 7: Recent Traces */}
      <div className="rounded-xl border bg-card">
        <div className="px-5 py-4 border-b">
          <h2 className="text-sm font-semibold">Recent Traces</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/40">
                {['ID', 'Model', 'Status', 'Latency', 'Tokens', 'Cost', 'Time'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {traces.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No traces yet. Send some traces using the SDK.
                  </td>
                </tr>
              ) : (
                traces.map((t) => (
                  <tr key={t.id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-xs">{t.id.slice(0, 8)}...</td>
                    <td className="px-4 py-2.5 max-w-[130px] truncate">{t.model ?? '--'}</td>
                    <td className="px-4 py-2.5">
                      <Badge variant={statusBadgeVariant(t.status)}>{t.status}</Badge>
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">{formatMs(t.latency_ms)}</td>
                    <td className="px-4 py-2.5">{t.total_tokens?.toLocaleString() ?? '--'}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">{formatCost(t.cost_usd)}</td>
                    <td className="px-4 py-2.5 text-muted-foreground text-xs whitespace-nowrap">
                      {formatDate(t.timestamp ?? t.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

