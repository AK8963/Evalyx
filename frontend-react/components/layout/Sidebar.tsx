'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Activity,
  BarChart3,
  FlaskConical,
  Database,
  MessageSquare,
  Star,
  FileText,
  PlayCircle,
  Zap,
  Hash,
  Search,
  Code2,
  Target,
  GitCompare,
  Bell,
  EyeOff,
  Settings,
  Shield,
  LogOut,
  ChevronRight,
  Gauge,
  Layers,
  TrendingUp,
} from 'lucide-react'

const navGroups = [
  {
    label: 'Observability',
    items: [
      { href: '/', label: 'Dashboard', icon: LayoutDashboard },
      { href: '/traces', label: 'Traces', icon: Activity },
      { href: '/sessions', label: 'Sessions', icon: Layers },
      { href: '/analytics', label: 'Analytics', icon: BarChart3 },
     // { href: '/topics', label: 'Topics', icon: Hash },
      //{ href: '/search', label: 'Deep Search', icon: Search },
    ],
  },
  {
    label: 'Evaluation',
    items: [
      { href: '/experiments', label: 'Experiments', icon: FlaskConical },
      { href: '/scores', label: 'Scores', icon: TrendingUp },
      { href: '/datasets', label: 'Datasets', icon: Database },
      { href: '/metrics', label: 'Metrics', icon: Gauge },
      { href: '/annotations', label: 'Annotations', icon: Star },
      //{ href: '/review', label: 'Review Queue', icon: MessageSquare },
      //{ href: '/online-scoring', label: 'Online Scoring', icon: Target },
      //{ href: '/remote-evals', label: 'Remote Evals', icon: GitCompare },
    ],
  },
  {
    label: 'LLM Tools',
    items: [
      { href: '/prompts', label: 'Prompts', icon: FileText },
      { href: '/playground', label: 'Playground', icon: PlayCircle },
      //{ href: '/gateway', label: 'Gateway', icon: Zap },
      //{ href: '/ab-tests', label: 'A/B Tests', icon: GitCompare },
    ],
  },
  {
    label: 'Enterprise',
    items: [
      //{ href: '/btql', label: 'BTQL Query', icon: Code2 },
      //{ href: '/alerts', label: 'Alerts', icon: Bell },
      //{ href: '/masking', label: 'Data Masking', icon: EyeOff },
      { href: '/online-scoring', label: 'Online Scoring', icon: Target },
      { href: '/settings', label: 'Settings', icon: Settings },
      //{ href: '/settings/sso', label: 'SSO', icon: Shield },
    ],
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-sidebar border-r border-sidebar-border shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-sidebar-border">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shrink-0 shadow-sm shadow-violet-900/30">
          <Zap className="h-4 w-4 text-white" />
        </div>
        <span className="font-semibold text-sidebar-foreground tracking-tight">Evalyx</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-5">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="px-2 mb-1 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/40">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active =
                  href === '/' ? pathname === '/' : pathname.startsWith(href)
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      className={cn(
                        'flex items-center gap-2.5 px-2 py-1.5 rounded-md text-sm transition-colors',
                        active
                          ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                          : 'text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50',
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="flex-1">{label}</span>
                      {active && <ChevronRight className="h-3 w-3 opacity-60" />}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* User */}
      <div className="p-3 border-t border-sidebar-border">
        <div className="flex items-center gap-2.5 px-1 mb-2">
          <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center text-xs font-semibold text-primary shrink-0">
            {user?.name?.charAt(0)?.toUpperCase() ?? '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-sidebar-foreground truncate">
              {user?.name ?? 'User'}
            </p>
            <p className="text-xs text-sidebar-foreground/50 truncate">{user?.email ?? ''}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-sm text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
