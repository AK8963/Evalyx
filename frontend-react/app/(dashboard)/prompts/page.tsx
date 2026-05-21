'use client'

import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useProject } from '@/components/layout/ProjectSelector'
import { formatDate } from '@/lib/utils'
import {
  FileText, Plus, Trash2, Rocket, Code2, Save,
  ChevronRight, ChevronDown, Settings2, MessageSquare,
  Wrench, Variable, Plug, X, RefreshCw, Play,
} from 'lucide-react'
import { toast } from 'sonner'
import type { Prompt } from '@/types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const OLLAMA_MODELS = [
  'llama3.2',
  'llama3.1',
  'llama3',
  'llama2',
  'mistral',
  'mixtral',
  'codellama',
  'phi3',
  'qwen2',
  'gemma2',
  'gemma',
  'deepseek-r1',
  'deepseek-coder',
  'zephyr',
  'vicuna',
  'orca-mini',
  'neural-chat',
]

const ROLE_OPTIONS = ['user', 'system', 'assistant'] as const
type Role = typeof ROLE_OPTIONS[number]

interface Message {
  role: Role
  content: string
}

// ---------------------------------------------------------------------------
// Shared UI
// ---------------------------------------------------------------------------

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {children}
    </span>
  )
}

function Collapsible({ title, children, defaultOpen = false }: {
  title: string; children: React.ReactNode; defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-md">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/40 transition-colors"
      >
        {title}
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>
      {open && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Variable detector
// ---------------------------------------------------------------------------

function detectVariables(text: string): string[] {
  const matches = text.matchAll(/\{\{(\w+)\}\}/g)
  const vars = new Set<string>()
  for (const m of matches) vars.add(m[1])
  return Array.from(vars)
}

function buildTemplate(messages: Message[]): string {
  return messages.map(m => `[${m.role.toUpperCase()}]\n${m.content}`).join('\n\n')
}

// ---------------------------------------------------------------------------
// Message block
// ---------------------------------------------------------------------------

function MessageBlock({
  message,
  onChange,
  onRemove,
}: {
  message: Message
  index: number
  onChange: (updated: Message) => void
  onRemove: () => void
}) {
  const roleColors: Record<Role, string> = {
    user: 'bg-blue-100 text-blue-700',
    system: 'bg-yellow-100 text-yellow-700',
    assistant: 'bg-green-100 text-green-700',
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-muted/30 border-b">
        <select
          value={message.role}
          onChange={e => onChange({ ...message, role: e.target.value as Role })}
          className="text-xs font-medium border-0 bg-transparent focus:outline-none cursor-pointer"
        >
          {ROLE_OPTIONS.map(r => (
            <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
          ))}
        </select>
        <div className="flex items-center gap-1.5">
          <Badge color={roleColors[message.role]}>{message.role}</Badge>
          <button onClick={onRemove} className="text-muted-foreground hover:text-destructive p-0.5">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <textarea
        value={message.content}
        onChange={e => onChange({ ...message, content: e.target.value })}
        rows={4}
        placeholder={`Enter ${message.role} message...`}
        className="w-full px-3 py-2 text-sm bg-background resize-y focus:outline-none font-mono"
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Params panel
// ---------------------------------------------------------------------------

function ParamsPanel({ params, onChange }: {
  params: { temperature: number; max_tokens: number; top_p: number }
  onChange: (p: { temperature: number; max_tokens: number; top_p: number }) => void
}) {
  return (
    <div className="space-y-3 text-xs">
      <div>
        <label className="text-muted-foreground flex justify-between mb-1">
          Temperature <strong>{params.temperature}</strong>
        </label>
        <input type="range" min={0} max={2} step={0.05} value={params.temperature}
          onChange={e => onChange({ ...params, temperature: Number(e.target.value) })}
          className="w-full" />
      </div>
      <div>
        <label className="text-muted-foreground flex justify-between mb-1">
          Max Tokens <strong>{params.max_tokens}</strong>
        </label>
        <input type="range" min={64} max={4096} step={64} value={params.max_tokens}
          onChange={e => onChange({ ...params, max_tokens: Number(e.target.value) })}
          className="w-full" />
      </div>
      <div>
        <label className="text-muted-foreground flex justify-between mb-1">
          Top P <strong>{params.top_p}</strong>
        </label>
        <input type="range" min={0} max={1} step={0.05} value={params.top_p}
          onChange={e => onChange({ ...params, top_p: Number(e.target.value) })}
          className="w-full" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Create / Edit form (right panel)
// ---------------------------------------------------------------------------

function PromptForm({ projectId, editPrompt, onSaved, onCancel }: {
  projectId: string
  editPrompt?: Prompt
  onSaved: (p: Prompt) => void
  onCancel: () => void
}) {
  const qc = useQueryClient()
  const [name, setName] = useState(editPrompt?.name ?? '')
  const [slug, setSlug] = useState(editPrompt?.name?.toLowerCase().replace(/\s+/g, '-') ?? '')
  const [model, setModel] = useState(editPrompt?.model ?? 'llama3.2')
  const [description, setDescription] = useState(editPrompt?.description ?? '')
  const [outputType, setOutputType] = useState('Text output')
  const [showParams, setShowParams] = useState(false)
  const [params, setParams] = useState({ temperature: 0.7, max_tokens: 512, top_p: 1.0 })
  const [messages, setMessages] = useState<Message[]>([{ role: 'user', content: '' }])
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState<{ role: string; content: string }[]>([])
  const [isChatting, setIsChatting] = useState(false)
  const [showChat, setShowChat] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (editPrompt?.template) {
      const parts = editPrompt.template.split(/\n\n(?=\[(USER|SYSTEM|ASSISTANT)\])/i)
      if (parts.length > 0 && parts[0].match(/^\[(USER|SYSTEM|ASSISTANT)\]/i)) {
        const parsed = parts.map(p => {
          const match = p.match(/^\[(\w+)\]\n([\s\S]*)$/)
          if (!match) return null
          return { role: match[1].toLowerCase() as Role, content: match[2] }
        }).filter(Boolean) as Message[]
        if (parsed.length) setMessages(parsed)
      } else {
        setMessages([{ role: 'user', content: editPrompt.template }])
      }
    }
  }, [editPrompt])

  const detectedVars = detectVariables(messages.map(m => m.content).join('\n'))

  function addMessage() {
    setMessages(prev => [...prev, { role: 'user', content: '' }])
  }

  function insertVariable() {
    const varName = window.prompt('Variable name (no spaces):')
    if (!varName) return
    setMessages(prev => {
      const last = { ...prev[prev.length - 1] }
      last.content += `{{${varName}}}`
      return [...prev.slice(0, -1), last]
    })
  }

  const mutation = useMutation({
    mutationFn: () => {
      const template = buildTemplate(messages)
      const payload = {
        project_id: projectId,
        name: name.trim(),
        description: description.trim() || undefined,
        template,
        variables: detectedVars,
        model,
        default_model: model,
        default_params: params,
      }
      if (editPrompt) return api.prompts.update(editPrompt.id, payload)
      return api.prompts.create(payload)
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['prompts', projectId] })
      toast.success(editPrompt ? 'Prompt updated' : 'Prompt saved')
      onSaved(saved as Prompt)
    },
    onError: () => toast.error('Failed to save prompt'),
  })

  async function handleChat() {
    if (!chatInput.trim()) return
    const userMsg = { role: 'user', content: chatInput }
    const newHistory = [...chatHistory, userMsg]
    setChatHistory(newHistory)
    setChatInput('')
    setIsChatting(true)
    try {
      const systemContent = messages.find(m => m.role === 'system')?.content ?? ''
      const apiMessages = [
        ...(systemContent ? [{ role: 'system' as const, content: systemContent }] : []),
        ...newHistory.map(m => ({ role: m.role as 'user' | 'assistant', content: m.content })),
      ]
      const res = await api.gateway.complete({
        project_id: projectId,
        model: `ollama/${model}`,
        messages: apiMessages,
        temperature: params.temperature,
        max_tokens: params.max_tokens,
      })
      setChatHistory(prev => [...prev, { role: 'assistant', content: res.content }])
    } catch {
      toast.error('Chat failed - ensure Ollama is running')
    } finally {
      setIsChatting(false)
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Sticky top bar - always visible, never inside the scroll area */}
      <div className="px-6 py-4 border-b flex items-center justify-between shrink-0">
        <h2 className="font-semibold text-base flex items-center gap-2">
          <Code2 className="h-4 w-4 text-muted-foreground" />
          {editPrompt ? 'Edit Prompt' : 'Create Prompt'}
        </h2>
        <div className="flex items-center gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 text-xs border rounded-md hover:bg-muted">
            Cancel
          </button>
          <button
            onClick={() => setShowChat(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-md hover:bg-muted ${showChat ? 'bg-muted' : ''}`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            {showChat ? 'Hide Chat' : 'Test Chat'}
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name.trim() || mutation.isPending}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            <Save className="h-3 w-3" />
            {mutation.isPending ? 'Saving...' : 'Save as custom prompt'}
          </button>
        </div>
      </div>

      {/* Body row: scrollable editor + chat preview side by side */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Editor - scrollable */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-4 space-y-4">
            {/* Name + Slug */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Name</label>
                <input
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Enter name"
                  value={name}
                  onChange={e => {
                    setName(e.target.value)
                    setSlug(e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''))
                  }}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Slug</label>
                <input
                  className="mt-1 w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Enter slug"
                  value={slug}
                  onChange={e => setSlug(e.target.value)}
                />
              </div>
            </div>

            {/* Model + Params */}
            <div>
              <label className="text-xs font-medium text-muted-foreground">Model</label>
              <div className="mt-1 flex items-center gap-2 border rounded-md px-3 py-2">
                <select
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  className="flex-1 text-sm bg-transparent focus:outline-none"
                >
                  {OLLAMA_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <button
                  onClick={() => setShowParams(!showParams)}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground border-l pl-3"
                >
                  <Settings2 className="h-3.5 w-3.5" /> Params
                </button>
              </div>
              {showParams && (
                <div className="mt-2 border rounded-md p-3">
                  <ParamsPanel params={params} onChange={setParams} />
                </div>
              )}
            </div>

            {/* Messages */}
            <div className="space-y-2">
              {messages.map((msg, i) => (
                <MessageBlock
                  key={i}
                  message={msg}
                  index={i}
                  onChange={updated => setMessages(prev => prev.map((m, j) => j === i ? updated : m))}
                  onRemove={() => setMessages(prev => prev.filter((_, j) => j !== i))}
                />
              ))}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={addMessage}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-md hover:bg-muted"
              >
                <MessageSquare className="h-3.5 w-3.5" /> + Message
              </button>
              <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-md hover:bg-muted">
                <Wrench className="h-3.5 w-3.5" /> Tools
              </button>
              <button
                onClick={insertVariable}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-md hover:bg-muted"
              >
                <Variable className="h-3.5 w-3.5" /> Mustache
              </button>
              <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-md hover:bg-muted">
                <Plug className="h-3.5 w-3.5" /> MCP
              </button>
              <div className="ml-auto">
                <select
                  value={outputType}
                  onChange={e => setOutputType(e.target.value)}
                  className="text-xs border rounded-md px-2 py-1.5 bg-background"
                >
                  <option>Text output</option>
                  <option>JSON output</option>
                  <option>Structured output</option>
                </select>
              </div>
            </div>

            {/* Variables detected */}
            {detectedVars.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1.5">
                  Detected Variables
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {detectedVars.map(v => (
                    <span key={v} className="font-mono text-xs bg-yellow-50 border border-yellow-200 text-yellow-800 px-2 py-0.5 rounded">
                      {'{{' + v + '}}'}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Description */}
            <Collapsible title="Description">
              <textarea
                className="w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                rows={3}
                placeholder="Optional description..."
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </Collapsible>

            {/* Metadata */}
            <Collapsible title="Metadata">
              <pre className="text-xs bg-muted rounded-md p-2 overflow-x-auto">
                {JSON.stringify({ model, params, variables: detectedVars, output_type: outputType }, null, 2)}
              </pre>
            </Collapsible>
          </div>
        </div>

        {/* Right: Chat preview - toggleable */}
        {showChat && <div className="w-80 border-l flex flex-col min-h-0 shrink-0">
          <div className="px-4 py-3 border-b">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Chat with your prompt</p>
            <p className="text-xs text-muted-foreground mt-0.5">Using {model} via Ollama</p>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {chatHistory.length === 0 ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                <p className="text-xs text-center">Send a message to test your prompt...</p>
              </div>
            ) : (
              chatHistory.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[90%] px-3 py-2 rounded-xl text-xs leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  }`}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}
            {isChatting && (
              <div className="flex justify-start">
                <div className="bg-muted px-3 py-2 rounded-xl text-xs text-muted-foreground">Thinking...</div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="p-3 border-t flex gap-2">
            <input
              className="flex-1 text-xs border rounded-md px-2 py-1.5 bg-background focus:outline-none"
              placeholder="Type a message..."
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChat() } }}
            />
            <button
              onClick={handleChat}
              disabled={!chatInput.trim() || isChatting}
              className="p-1.5 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Prompt detail (read-only view with render)
// ---------------------------------------------------------------------------

function PromptDetail({ prompt, onClose, onEdit }: {
  prompt: Prompt
  onClose: () => void
  onEdit: () => void
}) {
  const qc = useQueryClient()
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [rendered, setRendered] = useState('')
  const [rendering, setRendering] = useState(false)

  const varNames = prompt.variables ?? []

  async function renderPrompt() {
    setRendering(true)
    try {
      const res = await api.prompts.render(prompt.id, variables) as { rendered: string }
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
    <div className="flex flex-col h-full min-h-0 overflow-y-auto">
      <div className="px-6 py-4 border-b flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-base">{prompt.name}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            v{prompt.version} · {prompt.model ?? 'Ollama'} · {formatDate(prompt.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {prompt.is_deployed && (
            <Badge color="bg-green-100 text-green-700">
              <Rocket className="h-3 w-3 mr-1" /> Deployed
            </Badge>
          )}
          <button onClick={onEdit} className="text-xs px-3 py-1.5 border rounded-md hover:bg-muted">Edit</button>
          <button onClick={() => deletePrompt.mutate()} className="p-1.5 text-muted-foreground hover:text-destructive">
            <Trash2 className="h-4 w-4" />
          </button>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="px-6 py-4 space-y-4">
        {prompt.description && (
          <p className="text-sm text-muted-foreground">{prompt.description}</p>
        )}

        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Template</p>
          <pre className="text-xs bg-muted rounded-md p-3 whitespace-pre-wrap overflow-auto max-h-48 font-mono leading-relaxed">
            {prompt.template}
          </pre>
        </div>

        {varNames.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Variables</p>
            {varNames.map(v => (
              <div key={v} className="flex items-center gap-2">
                <span className="text-xs font-mono bg-yellow-50 border border-yellow-200 text-yellow-800 px-2 py-0.5 rounded">
                  {'{{' + v + '}}'}
                </span>
                <input
                  value={variables[v] ?? ''}
                  onChange={e => setVariables(prev => ({ ...prev, [v]: e.target.value }))}
                  placeholder={`Value for ${v}`}
                  className="flex-1 text-sm px-2 py-1 border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            ))}
            <button
              onClick={renderPrompt}
              disabled={rendering}
              className="px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
            >
              {rendering ? 'Rendering...' : 'Render'}
            </button>
            {rendered && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">Rendered</p>
                <pre className="text-xs bg-background border rounded-md p-3 whitespace-pre-wrap overflow-auto max-h-40 font-mono">
                  {rendered}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PromptsPage() {
  const { project } = useProject()
  const projectId = project?.id ?? ''
  const [selectedPrompt, setSelectedPrompt] = useState<Prompt | null>(null)
  const [mode, setMode] = useState<'list' | 'create' | 'edit'>('list')

  const { data: prompts = [], isLoading, refetch } = useQuery({
    queryKey: ['prompts', projectId],
    queryFn: () => api.prompts.list(projectId),
    enabled: !!projectId,
  })

  function startCreate() {
    setSelectedPrompt(null)
    setMode('create')
  }

  function startEdit(p: Prompt) {
    setSelectedPrompt(p)
    setMode('edit')
  }

  function handleSaved(p: Prompt) {
    setSelectedPrompt(p)
    setMode('list')
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Left: Prompt list */}
      <div className="w-72 border-r flex flex-col min-h-0 shrink-0">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <h1 className="font-semibold text-sm">Prompts</h1>
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{(prompts as Prompt[]).length}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={() => refetch()} className="p-1 rounded hover:bg-muted text-muted-foreground" title="Refresh">
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={startCreate}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              <Plus className="h-3.5 w-3.5" /> New
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-sm text-muted-foreground">Loading...</div>
          ) : !(prompts as Prompt[]).length ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              <FileText className="h-8 w-8 mx-auto mb-2 opacity-30" />
              No prompts yet.
            </div>
          ) : (
            (prompts as Prompt[]).map(p => (
              <button
                key={p.id}
                onClick={() => { setSelectedPrompt(p); setMode('list') }}
                className={`w-full text-left px-4 py-3 border-b hover:bg-muted/40 transition-colors ${selectedPrompt?.id === p.id && mode === 'list' ? 'bg-muted/60 border-l-2 border-l-primary' : ''}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-sm font-medium truncate">{p.name}</span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">v{p.version}</span>
                      {p.model && <span className="text-xs text-muted-foreground truncate">{p.model}</span>}
                    </div>
                  </div>
                  {p.is_deployed && <Rocket className="h-3 w-3 text-green-500 shrink-0 mt-0.5" />}
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right: Detail / Create / Edit */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {mode === 'create' || mode === 'edit' ? (
          <PromptForm
            projectId={projectId}
            editPrompt={mode === 'edit' ? selectedPrompt ?? undefined : undefined}
            onSaved={handleSaved}
            onCancel={() => setMode('list')}
          />
        ) : selectedPrompt ? (
          <PromptDetail
            prompt={selectedPrompt}
            onClose={() => setSelectedPrompt(null)}
            onEdit={() => startEdit(selectedPrompt)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-4">
            <FileText className="h-12 w-12 opacity-20" />
            <p className="text-sm">Select a prompt or create a new one</p>
            <button
              onClick={startCreate}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> Create Prompt
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
