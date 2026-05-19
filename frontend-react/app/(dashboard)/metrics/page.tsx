'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import {
  Gauge, Plus, Trash2, ChevronDown, ChevronRight, Lock,
  X, Check, Beaker, Code2, FlaskConical, Sigma,
  BrainCircuit, Play, Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import type { Metric, AutoevalScorer, MetricTestResult, MetricType } from '@/types'

// ---------------------------------------------------------------------------
// Autoeval scorer config schemas (UI-side, keeps backend simple)
// ---------------------------------------------------------------------------
const AUTOEVAL_CONFIG_FIELDS: Record<string, { key: string; label: string; type: string; placeholder?: string }[]> = {
  regex:       [{ key: 'pattern', label: 'Regex Pattern', type: 'text', placeholder: '^\\d+$' }],
  numeric_diff:[{ key: 'tolerance', label: 'Tolerance', type: 'number', placeholder: '0.05' }],
  length:      [
    { key: 'min_chars', label: 'Min Characters', type: 'number', placeholder: '1' },
    { key: 'max_chars', label: 'Max Characters', type: 'number', placeholder: '1000' },
  ],
  exact_match: [{ key: 'case_sensitive', label: 'Case Sensitive (true/false)', type: 'text', placeholder: 'false' }],
  contains:    [{ key: 'case_sensitive', label: 'Case Sensitive (true/false)', type: 'text', placeholder: 'false' }],
}

// ---------------------------------------------------------------------------
// Type badges
// ---------------------------------------------------------------------------
const TYPE_META: Record<string, { short: string; color: string }> = {
  llm_judge: { short: 'LLM',   color: 'text-purple-600 bg-purple-50 border-purple-200' },
  ollama:    { short: 'LLM',   color: 'text-purple-600 bg-purple-50 border-purple-200' },
  autoeval:  { short: 'Auto',  color: 'text-blue-600 bg-blue-50 border-blue-200' },
  formula:   { short: 'Fx',    color: 'text-orange-600 bg-orange-50 border-orange-200' },
  code:      { short: 'Code',  color: 'text-green-600 bg-green-50 border-green-200' },
}

function TypeBadge({ type }: { type: string }) {
  const m = TYPE_META[type] ?? { short: type, color: 'text-muted-foreground bg-muted border-border' }
  return <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${m.color}`}>{m.short}</span>
}

// ---------------------------------------------------------------------------
// Expanded detail per metric type
// ---------------------------------------------------------------------------
function MetricDetail({ metric }: { metric: Metric }) {
  const cfg = metric.config ?? {}
  const mt = metric.metric_type

  if (mt === 'llm_judge' || mt === 'ollama') {
    const tpl = metric.prompt_template ?? (cfg.prompt_template as string) ?? ''
    return (
      <div className="px-4 pb-4 border-t space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mt-3">Prompt Template</p>
        <pre className="text-xs bg-muted/40 rounded-lg p-3 whitespace-pre-wrap font-mono leading-relaxed">{tpl}</pre>
        <p className="text-[11px] text-muted-foreground/60">
          Placeholders: <code className="font-mono bg-muted px-1 rounded">{'{input}'}</code> and <code className="font-mono bg-muted px-1 rounded">{'{output}'}</code>.
          Returns <code className="font-mono bg-muted px-1 rounded">SCORE: 0-1</code>.
        </p>
      </div>
    )
  }
  if (mt === 'autoeval') {
    return (
      <div className="px-4 pb-4 border-t space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mt-3">Scorer Config</p>
        <pre className="text-xs bg-muted/40 rounded-lg p-3 font-mono">{JSON.stringify(cfg, null, 2)}</pre>
      </div>
    )
  }
  if (mt === 'formula') {
    return (
      <div className="px-4 pb-4 border-t space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mt-3">Expression</p>
        <pre className="text-xs bg-muted/40 rounded-lg p-3 font-mono">{String(cfg.expression ?? '')}</pre>
        <p className="text-[11px] text-muted-foreground/60">
          Variables: <code className="font-mono bg-muted px-1 rounded">input</code>, <code className="font-mono bg-muted px-1 rounded">output</code>, <code className="font-mono bg-muted px-1 rounded">expected</code>. Returns float 0-1.
        </p>
      </div>
    )
  }
  if (mt === 'code') {
    return (
      <div className="px-4 pb-4 border-t space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mt-3">Code Snippet</p>
        <pre className="text-xs bg-muted/40 rounded-lg p-3 whitespace-pre-wrap font-mono leading-relaxed">{String(cfg.snippet ?? '')}</pre>
        <p className="text-[11px] text-muted-foreground/60">
          Define <code className="font-mono bg-muted px-1 rounded">score(input, output, expected, metadata)</code> returning float 0-1 or dict.
        </p>
      </div>
    )
  }
  return null
}

// ---------------------------------------------------------------------------
// Built-in row
// ---------------------------------------------------------------------------
function BuiltinRow({ metric }: { metric: Metric }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <button className="w-full flex items-center gap-3 px-4 py-3.5 text-left hover:bg-muted/30 transition-colors"
        onClick={() => setExpanded(!expanded)}>
        <Lock className="h-4 w-4 text-muted-foreground/60 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm">{metric.name}</p>
          {metric.description && <p className="text-xs text-muted-foreground mt-0.5 truncate">{metric.description}</p>}
        </div>
        <TypeBadge type={metric.metric_type} />
        <span className="text-[11px] px-2 py-0.5 bg-muted rounded-full text-muted-foreground shrink-0">built-in</span>
        {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
      </button>
      {expanded && <MetricDetail metric={metric} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Custom row
// ---------------------------------------------------------------------------
function CustomRow({ metric, onDelete }: { metric: Metric; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3.5">
        <button className="flex-1 flex items-center gap-3 text-left" onClick={() => setExpanded(!expanded)}>
          <Gauge className="h-4 w-4 text-primary shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm">{metric.name}</p>
            {metric.description && <p className="text-xs text-muted-foreground mt-0.5 truncate">{metric.description}</p>}
          </div>
          <TypeBadge type={metric.metric_type} />
          {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
        </button>
        <button onClick={onDelete} className="p-1.5 text-muted-foreground hover:text-red-500 rounded transition-colors">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {expanded && <MetricDetail metric={metric} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline test panel
// ---------------------------------------------------------------------------
function TestPanel({ metricType, config }: { metricType: string; config: Record<string, unknown> }) {
  const [inp, setInp] = useState('What is the capital of France?')
  const [out, setOut] = useState('The capital of France is Paris.')
  const [exp, setExp] = useState('Paris')
  const [result, setResult] = useState<MetricTestResult | null>(null)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    setRunning(true); setErr(''); setResult(null)
    try {
      const r = await api.metrics.test({ metric_type: metricType, config, input: inp, output: out, expected: exp || undefined })
      setResult(r)
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : 'Test failed') }
    finally { setRunning(false) }
  }

  return (
    <div className="border rounded-xl p-4 space-y-3 bg-muted/20">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
        <Beaker className="h-3.5 w-3.5" /> Test with sample data
      </p>
      <div className="grid grid-cols-3 gap-2">
        {([['Input', inp, setInp], ['Output', out, setOut], ['Expected', exp, setExp]] as const).map(([label, val, setter]) => (
          <div key={label} className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">{label}</label>
            <textarea value={val} onChange={(e) => setter(e.target.value)} rows={2}
              className="w-full px-2 py-1.5 border rounded-md text-xs bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono resize-none" />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={run} disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-xs disabled:opacity-50">
          {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          {running ? 'Running...' : 'Run Test'}
        </button>
        {result && (
          <>
            <span className="text-sm font-semibold">
              Score: <span className={result.score >= 0.7 ? 'text-green-600' : result.score >= 0.4 ? 'text-yellow-600' : 'text-red-600'}>
                {result.score.toFixed(2)}
              </span>
            </span>
            {result.latency_ms > 0 && <span className="text-xs text-muted-foreground">{result.latency_ms}ms</span>}
          </>
        )}
        {err && <p className="text-xs text-red-500 flex-1">{err}</p>}
      </div>
      {result?.explanation && (
        <p className="text-xs text-muted-foreground bg-background border rounded p-2">{result.explanation}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Create form â€” 4-type system
// ---------------------------------------------------------------------------
const DEFAULT_CODE = `def score(input, output, expected, metadata):
    # Available libs: math, re, json, statistics, difflib
    # Return float 0-1 or {"score": float, "explanation": str}
    if not output:
        return {"score": 0.0, "explanation": "Empty output"}
    return {"score": 1.0, "explanation": "Looks good"}`

const DEFAULT_PROMPT = `You are an impartial judge evaluating an AI assistant.

Question: {input}
Answer: {output}

Rate the response quality on a scale from 0 to 1.
- 1.0 = excellent
- 0.5 = acceptable
- 0.0 = poor

Respond with EXACTLY:
SCORE: [number between 0 and 1]
EXPLANATION: [one sentence]`

function CreateMetricForm({ projectId, onDone }: { projectId?: string; onDone: () => void }) {
  const qc = useQueryClient()
  const [step, setStep] = useState<'type' | 'config'>('type')
  const [selectedType, setSelectedType] = useState<MetricType>('llm_judge')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [promptTemplate, setPromptTemplate] = useState(DEFAULT_PROMPT)
  const [llmModel, setLlmModel] = useState('llama3')
  const [selectedScorer, setSelectedScorer] = useState('')
  const [scorerConfig, setScorerConfig] = useState<Record<string, string>>({})
  const [formula, setFormula] = useState('len(str(output)) > 10')
  const [snippet, setSnippet] = useState(DEFAULT_CODE)

  const { data: autoevals = [] } = useQuery<AutoevalScorer[]>({
    queryKey: ['autoevals'],
    queryFn: () => api.autoevals.list(),
    enabled: selectedType === 'autoeval',
  })

  const buildConfig = (): Record<string, unknown> => {
    if (selectedType === 'llm_judge') return { prompt_template: promptTemplate, model: llmModel }
    if (selectedType === 'autoeval') return { scorer: selectedScorer, ...Object.fromEntries(Object.entries(scorerConfig).filter(([, v]) => v !== '')) }
    if (selectedType === 'formula') return { expression: formula }
    if (selectedType === 'code') return { snippet, timeout_s: 10 }
    return {}
  }

  const create = useMutation({
    mutationFn: () => api.metrics.create({
      name,
      description: description || undefined,
      metric_type: selectedType,
      prompt_template: selectedType === 'llm_judge' ? promptTemplate : undefined,
      config: buildConfig(),
      project_id: projectId,
    }),
    onSuccess: () => { toast.success('Metric created'); qc.invalidateQueries({ queryKey: ['metrics'] }); onDone() },
    onError: () => toast.error('Failed to create metric'),
  })

  const typeOptions: { type: MetricType; icon: React.ReactNode; title: string; desc: string }[] = [
    { type: 'llm_judge', icon: <BrainCircuit className="h-5 w-5" />, title: 'LLM Judge',       desc: 'Prompt an LLM to score output quality' },
    { type: 'autoeval',  icon: <FlaskConical className="h-5 w-5" />, title: 'Pre-built Scorer', desc: 'Exact match, ROUGE, regex, semantic similarity, numeric diff...' },
    { type: 'formula',   icon: <Sigma className="h-5 w-5" />,        title: 'Formula',          desc: 'One-line Python expression using input, output, expected' },
    { type: 'code',      icon: <Code2 className="h-5 w-5" />,        title: 'Code Snippet',     desc: 'Custom Python function â€” math, re, json, difflib available' },
  ]

  const configFields = AUTOEVAL_CONFIG_FIELDS[selectedScorer] ?? []

  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-medium">{step === 'type' ? 'New Metric â€” Choose Type' : `New Metric`}</h2>
        <button onClick={onDone} className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>

      {step === 'type' && (
        <div className="grid grid-cols-2 gap-3">
          {typeOptions.map(({ type, icon, title, desc }) => (
            <button key={type} onClick={() => { setSelectedType(type); setStep('config') }}
              className="flex flex-col gap-2 p-4 border rounded-xl text-left hover:border-primary hover:bg-primary/5 transition-all">
              <div className="text-primary">{icon}</div>
              <p className="font-medium text-sm">{title}</p>
              <p className="text-xs text-muted-foreground leading-snug">{desc}</p>
            </button>
          ))}
        </div>
      )}

      {step === 'config' && (
        <div className="space-y-4">
          <button onClick={() => setStep('type')} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5 rotate-180" /> Back
          </button>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Name *</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Helpfulness"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Description</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional"
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
          </div>

          {/* LLM Judge */}
          {selectedType === 'llm_judge' && (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Ollama model</label>
                <input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} placeholder="llama3"
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  Prompt Template â€” use <code className="font-mono bg-muted px-1 rounded text-[11px]">{'{input}'}</code> and <code className="font-mono bg-muted px-1 rounded text-[11px]">{'{output}'}</code>
                </label>
                <textarea value={promptTemplate} onChange={(e) => setPromptTemplate(e.target.value)} rows={10}
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono resize-y" />
              </div>
            </div>
          )}

          {/* Autoeval */}
          {selectedType === 'autoeval' && (
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Scorer *</label>
                <select value={selectedScorer} onChange={(e) => { setSelectedScorer(e.target.value); setScorerConfig({}) }}
                  className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring">
                  <option value="">-- Select a scorer --</option>
                  {autoevals.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
                </select>
                {selectedScorer && <p className="text-xs text-muted-foreground">{autoevals.find((s) => s.name === selectedScorer)?.description}</p>}
              </div>
              {configFields.map((f) => (
                <div key={f.key} className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">{f.label}</label>
                  <input type={f.type} value={scorerConfig[f.key] ?? ''} placeholder={f.placeholder}
                    onChange={(e) => setScorerConfig((prev) => ({ ...prev, [f.key]: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring" />
                </div>
              ))}
            </div>
          )}

          {/* Formula */}
          {selectedType === 'formula' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">
                Python expression â€” variables: <code className="font-mono bg-muted px-1 rounded">input</code>, <code className="font-mono bg-muted px-1 rounded">output</code>, <code className="font-mono bg-muted px-1 rounded">expected</code>. Returns float 0-1 or bool.
              </label>
              <textarea value={formula} onChange={(e) => setFormula(e.target.value)} rows={3}
                className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono resize-y" />
              <div className="flex flex-wrap gap-2">
                {[
                  "str(output).strip() == str(expected).strip()",
                  "len(str(output).split()) / max(1, len(str(expected).split()))",
                  "abs(float(output) - float(expected)) < 0.05",
                ].map((ex) => (
                  <button key={ex} onClick={() => setFormula(ex)}
                    className="text-[11px] text-primary font-mono hover:underline underline-offset-2">{ex}</button>
                ))}
              </div>
            </div>
          )}

          {/* Code */}
          {selectedType === 'code' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">
                Python snippet â€” define <code className="font-mono bg-muted px-1 rounded">score(input, output, expected, metadata)</code>.
                Available: <code className="font-mono bg-muted px-1 rounded">math, re, json, statistics, difflib</code>
              </label>
              <textarea value={snippet} onChange={(e) => setSnippet(e.target.value)} rows={12}
                className="w-full px-3 py-2 border rounded-md text-xs bg-background focus:outline-none focus:ring-1 focus:ring-ring font-mono resize-y" />
            </div>
          )}

          {/* Live test panel â€” only show after name is filled */}
          {name.trim() && <TestPanel metricType={selectedType} config={buildConfig()} />}

          <div className="flex gap-2">
            <button onClick={() => create.mutate()}
              disabled={!name || (selectedType === 'autoeval' && !selectedScorer) || create.isPending}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm disabled:opacity-50">
              <Check className="h-3.5 w-3.5" />
              {create.isPending ? 'Creating...' : 'Create Metric'}
            </button>
            <button onClick={onDone} className="px-4 py-1.5 border rounded-md text-sm hover:bg-muted">Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function MetricsPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)

  const { data: metrics = [], isLoading } = useQuery({
    queryKey: ['metrics', project?.id],
    queryFn: () => api.metrics.list(project?.id),
  })

  const deleteMetric = useMutation({
    mutationFn: (id: string) => api.metrics.delete(id),
    onSuccess: () => { toast.success('Metric deleted'); qc.invalidateQueries({ queryKey: ['metrics'] }) },
    onError: (err: Error) => toast.error(err.message ?? 'Failed to delete metric'),
  })

  const builtin = metrics.filter((m) => m.is_builtin)
  const custom = metrics.filter((m) => !m.is_builtin)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Metrics</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Scorer definitions for evaluations. Supports LLM judge, pre-built scorers, formulas, and custom code.
          </p>
        </div>
        {!showCreate && (
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90">
            <Plus className="h-4 w-4" /> New Metric
          </button>
        )}
      </div>

      {showCreate && <CreateMetricForm projectId={project?.id} onDone={() => setShowCreate(false)} />}

      {isLoading ? (
        <div className="text-sm text-muted-foreground p-6">Loading...</div>
      ) : (
        <>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Built-in</h2>
            <div className="space-y-2">
              {builtin.map((m) => <BuiltinRow key={m.id} metric={m} />)}
            </div>
          </div>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
              Custom {custom.length > 0 && <span className="normal-case font-normal">({custom.length})</span>}
            </h2>
            {custom.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-28 border rounded-xl gap-2">
                <Gauge className="h-6 w-6 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No custom metrics yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {custom.map((m) => (
                  <CustomRow key={m.id} metric={m}
                    onDelete={() => { if (confirm(`Delete metric "${m.name}"?`)) deleteMetric.mutate(m.id) }} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

