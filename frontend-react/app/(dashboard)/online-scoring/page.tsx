'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { Target, Plus, Trash2, ToggleLeft, ToggleRight, ChevronDown, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const OLLAMA_MODELS = [
  'llama2', 'llama3', 'llama3.2', 'gemma2:9b', 'gemma2:27b',
  'mistral-nemo', 'mistral', 'qwen3.6:35b', 'devstral',
  'codellama', 'phi3', 'deepseek-r1',
]

const DEFAULT_PROMPTS: Record<string, string> = {
  quality: `You are an expert evaluator. Rate the quality of the AI response below.

Input: {input}
Output: {output}

Score the response from 0 to 1 based on accuracy, relevance, and clarity.

SCORE: [number between 0 and 1]
EXPLANATION: [brief reason]`,

  helpfulness: `Evaluate how helpful this AI response is.

Input: {input}
Output: {output}

Score from 0 (not helpful) to 1 (extremely helpful).

SCORE: [number between 0 and 1]
EXPLANATION: [brief reason]`,

  correctness: `You are a factual accuracy judge. Evaluate whether the AI response is factually correct.

Input: {input}
Output: {output}

Score from 0 (incorrect) to 1 (fully correct).

SCORE: [number between 0 and 1]
EXPLANATION: [brief reason]`,

  toxicity: `Evaluate if this AI response contains harmful, offensive, or toxic content.

Output: {output}

Score from 0 (highly toxic) to 1 (completely safe and appropriate).

SCORE: [number between 0 and 1]
EXPLANATION: [brief reason]`,
}

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ScoringRule {
  id: string
  name: string
  scorer_type: string
  scorer_config: Record<string, unknown>
  sample_rate: number
  is_active: boolean
  created_at: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Rule card
// ─────────────────────────────────────────────────────────────────────────────

function RuleCard({ rule, onDelete, onToggle }: {
  rule: ScoringRule
  onDelete: (id: string) => void
  onToggle: (id: string, active: boolean) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const config = rule.scorer_config ?? {}
  const metricName = (config.metric_name as string) ?? rule.name
  const model = (config.model as string) ?? ''
  const promptTemplate = (config.prompt_template as string) ?? ''

  return (
    <div className={`rounded-xl border bg-card transition-colors ${rule.is_active ? '' : 'opacity-60'}`}>
      <div className="flex items-center gap-3 px-4 py-3">
        <Target className={`h-4 w-4 shrink-0 ${rule.is_active ? 'text-primary' : 'text-muted-foreground'}`} />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm">{rule.name}</p>
          <p className="text-xs text-muted-foreground">
            {rule.scorer_type === 'llm' ? `LLM · ${metricName} · ${model}` : rule.scorer_type}
            {' · '}sample rate: {Math.round(rule.sample_rate * 100)}%
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${rule.is_active ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground'}`}>
            {rule.is_active ? 'active' : 'paused'}
          </span>
          <button
            onClick={() => onToggle(rule.id, !rule.is_active)}
            title={rule.is_active ? 'Pause rule' : 'Activate rule'}
            className="p-1 text-muted-foreground hover:text-foreground transition-colors"
          >
            {rule.is_active
              ? <ToggleRight className="h-5 w-5 text-primary" />
              : <ToggleLeft className="h-5 w-5" />}
          </button>
          <button
            onClick={() => setExpanded(e => !e)}
            className="p-1 text-muted-foreground hover:text-foreground"
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
          <button
            onClick={() => onDelete(rule.id)}
            className="p-1 text-muted-foreground hover:text-red-600 transition-colors"
            title="Delete rule"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
      {expanded && promptTemplate && (
        <div className="px-4 pb-3 border-t bg-muted/10">
          <p className="text-xs font-medium text-muted-foreground mt-2 mb-1">Prompt Template</p>
          <pre className="text-xs bg-background border rounded p-2 whitespace-pre-wrap font-mono overflow-x-auto">{promptTemplate}</pre>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Create rule form
// ─────────────────────────────────────────────────────────────────────────────

function CreateRuleForm({ projectId, onCreated }: { projectId: string; onCreated: () => void }) {
  const [name, setName] = useState('')
  const [scorerType, setScorerType] = useState<'llm' | 'expected' | 'code'>('llm')
  const [metricName, setMetricName] = useState('quality')
  const [model, setModel] = useState('llama2')
  const [promptTemplate, setPromptTemplate] = useState(DEFAULT_PROMPTS['quality'])
  const [sampleRate, setSampleRate] = useState(1.0)
  const [creating, setCreating] = useState(false)

  function handlePreset(preset: string) {
    setMetricName(preset)
    setPromptTemplate(DEFAULT_PROMPTS[preset] ?? '')
    if (!name) setName(preset)
  }

  async function handleCreate() {
    if (!name.trim()) { toast.error('Rule name is required'); return }
    if (scorerType === 'llm' && !promptTemplate.trim()) { toast.error('Prompt template is required'); return }
    setCreating(true)
    try {
      const config: Record<string, unknown> = { metric_name: metricName }
      if (scorerType === 'llm') {
        config.model = model
        config.prompt_template = promptTemplate
      }
      await api.onlineScoring.create({
        project_id: projectId,
        name: name.trim(),
        scorer_type: scorerType,
        scorer_config: config,
        sample_rate: sampleRate,
      })
      toast.success('Rule created — new traces will be scored automatically')
      setName('')
      setPromptTemplate(DEFAULT_PROMPTS['quality'])
      setMetricName('quality')
      onCreated()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to create rule')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="rounded-xl border bg-card p-5 space-y-4">
      <h2 className="text-sm font-semibold">New Scoring Rule</h2>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Rule Name</label>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. quality"
            className="w-full border rounded-md px-2.5 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Scorer Type</label>
          <select
            value={scorerType}
            onChange={e => setScorerType(e.target.value as 'llm' | 'expected' | 'code')}
            className="w-full border rounded-md px-2.5 py-1.5 text-sm bg-background focus:outline-none"
          >
            <option value="llm">LLM Judge (Ollama)</option>
            <option value="expected">Exact Match (vs expected_output)</option>
            <option value="code">Custom Code</option>
          </select>
        </div>
      </div>

      {scorerType === 'llm' && (
        <>
          {/* Quick-fill presets */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Quick Presets</label>
            <div className="flex flex-wrap gap-1.5">
              {Object.keys(DEFAULT_PROMPTS).map(p => (
                <button
                  key={p}
                  onClick={() => handlePreset(p)}
                  className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${metricName === p ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-muted'}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Metric Name</label>
              <input
                value={metricName}
                onChange={e => setMetricName(e.target.value)}
                placeholder="e.g. quality"
                className="w-full border rounded-md px-2.5 py-1.5 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Ollama Model</label>
              <select
                value={model}
                onChange={e => setModel(e.target.value)}
                className="w-full border rounded-md px-2.5 py-1.5 text-sm bg-background focus:outline-none"
              >
                {OLLAMA_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              Prompt Template <span className="text-muted-foreground/60">(use {'{input}'} and {'{output}'})</span>
            </label>
            <textarea
              value={promptTemplate}
              onChange={e => setPromptTemplate(e.target.value)}
              rows={8}
              className="w-full border rounded-md px-2.5 py-1.5 text-xs font-mono bg-background focus:outline-none focus:ring-1 focus:ring-ring resize-y"
              placeholder="Your prompt template here..."
            />
          </div>
        </>
      )}

      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">
          Sample Rate: {Math.round(sampleRate * 100)}% of traces
        </label>
        <input
          type="range" min={0} max={1} step={0.05}
          value={sampleRate}
          onChange={e => setSampleRate(parseFloat(e.target.value))}
          className="w-full"
        />
      </div>

      <button
        onClick={handleCreate}
        disabled={creating}
        className="flex items-center gap-1.5 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
      >
        <Plus className="h-4 w-4" />
        {creating ? 'Creating…' : 'Create Rule'}
      </button>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function OnlineScoringPage() {
  const { project } = useProject()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)

  const { data: rules = [], isLoading } = useQuery<ScoringRule[]>({
    queryKey: ['online-scoring', project?.id],
    queryFn: () => api.onlineScoring.list(project!.id) as Promise<ScoringRule[]>,
    enabled: !!project,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.onlineScoring.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['online-scoring', project?.id] }); toast.success('Rule deleted') },
    onError: () => toast.error('Failed to delete rule'),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.onlineScoring.update(id, { is_active }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['online-scoring', project?.id] }) },
    onError: () => toast.error('Failed to update rule'),
  })

  if (!project) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Select a project
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Online Scoring</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Rules run automatically in the background whenever a new trace is ingested.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(s => !s)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 shrink-0"
        >
          <Plus className="h-4 w-4" />
          {showCreate ? 'Cancel' : 'New Rule'}
        </button>
      </div>

      {showCreate && (
        <CreateRuleForm
          projectId={project.id}
          onCreated={() => {
            setShowCreate(false)
            qc.invalidateQueries({ queryKey: ['online-scoring', project.id] })
          }}
        />
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : rules.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 border rounded-xl border-dashed">
          <Target className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-muted-foreground text-sm">No scoring rules yet</p>
          <p className="text-xs text-muted-foreground">
            Click <strong>New Rule</strong> to create an LLM judge that auto-scores every incoming trace.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map(rule => (
            <RuleCard
              key={rule.id}
              rule={rule}
              onDelete={(id) => deleteMutation.mutate(id)}
              onToggle={(id, is_active) => toggleMutation.mutate({ id, is_active })}
            />
          ))}
        </div>
      )}
    </div>
  )
}
