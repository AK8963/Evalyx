'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import type { Settings } from '@/types'

const PROVIDERS = [
  { key: 'openai_api_key', label: 'OpenAI API Key', placeholder: 'sk-…' },
  { key: 'anthropic_api_key', label: 'Anthropic API Key', placeholder: 'sk-ant-…' },
  { key: 'google_api_key', label: 'Google AI Key', placeholder: 'AIza…' },
  { key: 'ollama_base_url', label: 'Ollama Base URL', placeholder: 'http://localhost:11434' },
]

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

function CopyField({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div>
      <label className="text-sm font-medium block mb-1.5">{label}</label>
      <div className="flex gap-2">
        <input
          readOnly
          value={value}
          className={`flex-1 px-3 py-2 border rounded-md text-sm bg-muted focus:outline-none ${mono ? 'font-mono' : ''}`}
        />
        <button
          onClick={copy}
          className="px-3 py-2 border rounded-md text-sm hover:bg-muted transition-colors whitespace-nowrap"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const qc = useQueryClient()
  const [showToken, setShowToken] = useState(false)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.settings.get(),
  })

  const [form, setForm] = useState<Partial<Settings>>({})

  const save = useMutation({
    mutationFn: () => api.settings.update({ ...settings, ...form }),
    onSuccess: () => {
      toast.success('Settings saved')
      qc.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: () => toast.error('Failed to save settings'),
  })

  function field(key: keyof Settings) {
    return (form[key] as string) ?? (settings?.[key] as string) ?? ''
  }

  const token = typeof window !== 'undefined' ? localStorage.getItem('trustbrain_token') ?? '' : ''
  const sdkSnippet = `from trustbrain import TrustBrain

client = TrustBrain(
    api_url="${API_BASE}",
    api_key="${token ? token.slice(0, 8) + '…' : '<your-token>'}",
)

@client.trace
def my_llm_call(prompt: str) -> str:
    # your LLM logic here
    ...`

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-muted-foreground">Loading…</div>
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-xl font-semibold">Settings</h1>

      {/* API Integration */}
      <div className="rounded-xl border bg-card p-5 space-y-4">
        <div>
          <h2 className="font-medium">API Integration</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Use these credentials to send traces from your application to TrustBrain.
          </p>
        </div>

        <CopyField label="API Base URL" value={API_BASE} />

        <div>
          <label className="text-sm font-medium block mb-1.5">Your API Token</label>
          <div className="flex gap-2">
            <input
              readOnly
              type={showToken ? 'text' : 'password'}
              value={token}
              className="flex-1 px-3 py-2 border rounded-md text-sm bg-muted font-mono focus:outline-none"
            />
            <button
              onClick={() => setShowToken((s) => !s)}
              className="px-3 py-2 border rounded-md text-sm hover:bg-muted transition-colors"
            >
              {showToken ? 'Hide' : 'Show'}
            </button>
            <button
              onClick={() => { navigator.clipboard.writeText(token); toast.success('Token copied') }}
              className="px-3 py-2 border rounded-md text-sm hover:bg-muted transition-colors"
            >
              Copy
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-1.5">
            Pass this as <code className="bg-muted px-1 rounded">Authorization: Bearer &lt;token&gt;</code> header, or set <code className="bg-muted px-1 rounded">TRUSTBRAIN_API_KEY</code> env var.
          </p>
        </div>

        <CopyField
          label="Trace Ingest Endpoint"
          value={`${API_BASE}/api/v1/traces`}
        />

        <div>
          <label className="text-sm font-medium block mb-1.5">SDK Quick Start</label>
          <div className="relative">
            <pre className="bg-muted rounded-md p-4 text-xs font-mono overflow-x-auto whitespace-pre">{sdkSnippet}</pre>
            <button
              onClick={() => { navigator.clipboard.writeText(sdkSnippet); toast.success('Copied') }}
              className="absolute top-2 right-2 px-2 py-1 text-xs border rounded bg-card hover:bg-muted transition-colors"
            >
              Copy
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-1.5">
            Install: <code className="bg-muted px-1 rounded">pip install trustbrain</code>
          </p>
        </div>
      </div>

      {/* LLM Providers */}
      <div className="rounded-xl border bg-card p-5 space-y-4">
        <h2 className="font-medium">LLM Provider Keys</h2>
        {PROVIDERS.map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="text-sm font-medium block mb-1.5">{label}</label>
            <input
              type="password"
              value={field(key as keyof Settings)}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              placeholder={placeholder}
              className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        ))}
      </div>

      {/* General */}
      <div className="rounded-xl border bg-card p-5 space-y-4">
        <h2 className="font-medium">General</h2>

        <div>
          <label className="text-sm font-medium block mb-1.5">Default Model</label>
          <input
            value={field('default_model')}
            onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))}
            placeholder="gpt-4"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5">Rate Limit (req/min)</label>
          <input
            type="number"
            value={(form.rate_limit_per_minute ?? settings?.rate_limit_per_minute ?? '') as number}
            onChange={(e) =>
              setForm((f) => ({ ...f, rate_limit_per_minute: parseInt(e.target.value) || undefined }))
            }
            placeholder="60"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5">Data Retention (days)</label>
          <input
            type="number"
            value={(form.data_retention_days ?? settings?.data_retention_days ?? '') as number}
            onChange={(e) =>
              setForm((f) => ({ ...f, data_retention_days: parseInt(e.target.value) || undefined }))
            }
            placeholder="90"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        <div>
          <label className="text-sm font-medium block mb-1.5">Webhook URL</label>
          <input
            value={field('webhook_url')}
            onChange={(e) => setForm((f) => ({ ...f, webhook_url: e.target.value }))}
            placeholder="https://…"
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      <button
        onClick={() => save.mutate()}
        disabled={save.isPending || Object.keys(form).length === 0}
        className="px-5 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
      >
        {save.isPending ? 'Saving…' : 'Save Settings'}
      </button>
    </div>
  )
}
