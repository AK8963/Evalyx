'use client'

import { useState } from 'react'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { Shield } from 'lucide-react'

export default function SSOPage() {
  const [config, setConfig] = useState({
    provider: 'okta',
    client_id: '',
    client_secret: '',
    issuer_url: '',
    redirect_uri: '',
  })
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    try {
      await api.sso.update(config)
      toast.success('SSO configuration saved')
    } catch {
      toast.error('Failed to save SSO config')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5 max-w-xl">
      <div className="flex items-center gap-3">
        <Shield className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-semibold">SSO Configuration</h1>
      </div>

      <div className="rounded-xl border bg-card p-5 space-y-4">
        <div>
          <label className="text-sm font-medium block mb-1.5">Provider</label>
          <select
            value={config.provider}
            onChange={(e) => setConfig((c) => ({ ...c, provider: e.target.value }))}
            className="w-full px-3 py-2 border rounded-md text-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {['okta', 'auth0', 'azure-ad', 'google'].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>

        {[
          { key: 'client_id', label: 'Client ID' },
          { key: 'client_secret', label: 'Client Secret', type: 'password' },
          { key: 'issuer_url', label: 'Issuer URL', placeholder: 'https://…' },
          { key: 'redirect_uri', label: 'Redirect URI', placeholder: 'https://your-app/api/auth/callback' },
        ].map(({ key, label, type, placeholder }) => (
          <div key={key}>
            <label className="text-sm font-medium block mb-1.5">{label}</label>
            <input
              type={type ?? 'text'}
              value={config[key as keyof typeof config]}
              onChange={(e) => setConfig((c) => ({ ...c, [key]: e.target.value }))}
              placeholder={placeholder}
              className="w-full px-3 py-2 border rounded-md text-sm bg-background font-mono focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        ))}

        <button
          onClick={save}
          disabled={saving}
          className="px-5 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save SSO Config'}
        </button>
      </div>
    </div>
  )
}
