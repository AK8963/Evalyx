'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { Zap } from 'lucide-react'
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
      document.cookie = `evalyx_token=${localStorage.getItem('evalyx_token')}; path=/; SameSite=Lax`
      router.replace(params.get('from') ?? '/')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) return null

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-violet-50 via-white to-indigo-50 relative overflow-hidden">
      {/* Decorative blobs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-48 -right-48 h-96 w-96 rounded-full bg-violet-200/40 blur-3xl" />
        <div className="absolute -bottom-48 -left-48 h-96 w-96 rounded-full bg-indigo-200/40 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-64 w-64 rounded-full bg-purple-100/30 blur-2xl" />
      </div>

      <div className="relative w-full max-w-md px-6">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center mb-4 shadow-lg shadow-violet-300/50">
            <Zap className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-violet-700 to-indigo-600 bg-clip-text text-transparent">
            Evalyx
          </h1>
          <p className="text-sm text-slate-500 mt-1.5">AI Observability Platform</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-slate-200/80 p-8 shadow-2xl shadow-violet-100/60 bg-white/80 backdrop-blur-sm">
          {/* Tabs */}
          <div className="flex bg-slate-100 rounded-xl p-1 mb-6 gap-1">
            {(['login', 'register'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-1.5 text-sm font-medium capitalize rounded-lg transition-all ${
                  tab === t
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {t === 'login' ? 'Sign in' : 'Register'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1.5">Email address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-400/40 focus:border-violet-400 transition-colors placeholder:text-slate-400"
              />
            </div>

            {tab === 'register' && (
              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1.5">Full name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Doe"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-400/40 focus:border-violet-400 transition-colors placeholder:text-slate-400"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 transition-all mt-1 shadow-md shadow-violet-300/50 hover:shadow-lg hover:shadow-violet-300/60 hover:-translate-y-px active:translate-y-0"
            >
              {submitting
                ? 'Please wait…'
                : tab === 'login'
                ? 'Sign in'
                : 'Create account'}
            </button>
          </form>

          <p className="text-center text-xs text-slate-400 mt-6">
            {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={() => setTab(tab === 'login' ? 'register' : 'login')}
              className="text-violet-600 font-medium hover:underline"
            >
              {tab === 'login' ? 'Register' : 'Sign in'}
            </button>
          </p>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          Open-source LLM observability &amp; evaluation
        </p>
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
