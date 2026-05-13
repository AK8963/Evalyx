'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { toast } from 'sonner'

function LoginForm() {
  const { login, register, isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const params = useSearchParams()
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(params.get('from') ?? '/')
    }
  }, [isAuthenticated, isLoading, router, params])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    try {
      if (tab === 'login') {
        await login(email)
        toast.success('Welcome back!')
      } else {
        await register(email, name)
        toast.success('Account created!')
      }
      // Set cookie so middleware can detect auth
      document.cookie = `trustbrain_token=${localStorage.getItem('trustbrain_token')}; path=/; SameSite=Lax`
      router.replace(params.get('from') ?? '/')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) return null

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-md px-6">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 rounded-xl bg-primary flex items-center justify-center mb-3">
            <span className="text-2xl">🧠</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">TrustBrain</h1>
          <p className="text-sm text-muted-foreground mt-1">AI Observability Platform</p>
        </div>

        {/* Card */}
        <div className="border rounded-xl p-8 shadow-sm bg-card">
          {/* Tabs */}
          <div className="flex border-b mb-6">
            {(['login', 'register'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 pb-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                  tab === t
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="text-sm font-medium block mb-1.5">Email address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {tab === 'register' && (
              <div>
                <label className="text-sm font-medium block mb-1.5">Full name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors mt-2"
            >
              {submitting
                ? 'Please wait…'
                : tab === 'login'
                ? 'Sign in'
                : 'Create account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
