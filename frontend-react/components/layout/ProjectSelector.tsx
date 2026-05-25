'use client'

import { useState, useEffect, createContext, useContext } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Project } from '@/types'
import { ChevronDown, FolderOpen, PlusCircle } from 'lucide-react'
import { toast } from 'sonner'

interface ProjectContextValue {
  project: Project | null
  setProject: (p: Project) => void
  projects: Project[]
}

const ProjectContext = createContext<ProjectContextValue>({
  project: null,
  setProject: () => {},
  projects: [],
})

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [project, setProjectState] = useState<Project | null>(null)

  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.projects.list(),
  })

  // Auto-select first project
  useEffect(() => {
    if (!project && projects.length > 0) {
      setProjectState(projects[0])
    }
  }, [projects, project])

  const setProject = (p: Project) => {
    setProjectState(p)
    localStorage.setItem('evalyx_project_id', p.id)
  }

  return (
    <ProjectContext.Provider value={{ project, setProject, projects }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  return useContext(ProjectContext)
}

export function ProjectSelector() {
  const { project, setProject, projects } = useProject()
  const [open, setOpen] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  async function createProject() {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const p = await api.projects.create(newName.trim())
      setProject(p)
      setNewName('')
      setShowCreate(false)
      toast.success(`Project "${p.name}" created`)
    } catch {
      toast.error('Failed to create project')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-sm px-2 py-1 rounded-md hover:bg-accent transition-colors"
      >
        <FolderOpen className="h-4 w-4 text-muted-foreground" />
        <span className="font-medium max-w-[160px] truncate">
          {project?.name ?? 'Select project…'}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-60 bg-popover border rounded-lg shadow-lg z-50 py-1">
          {projects.map((p) => (
            <button
              key={p.id}
              onClick={() => { setProject(p); setOpen(false) }}
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent transition-colors truncate"
            >
              {p.name}
            </button>
          ))}

          <div className="border-t mt-1 pt-1">
            {showCreate ? (
              <div className="px-3 py-2 flex gap-2">
                <input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && createProject()}
                  placeholder="Project name"
                  className="flex-1 text-sm px-2 py-1 border rounded focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <button
                  onClick={createProject}
                  disabled={creating}
                  className="text-sm px-2 py-1 bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50"
                >
                  {creating ? '…' : 'Add'}
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowCreate(true)}
                className="w-full text-left px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors flex items-center gap-2"
              >
                <PlusCircle className="h-3.5 w-3.5" />
                New project
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
